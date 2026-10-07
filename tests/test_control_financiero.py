"""Saldos basados solo en cobros reales y gastos con historial de anulación."""

from datetime import datetime, timedelta
from decimal import Decimal
import pytest

import services as s
from db import preparar_control_financiero


def test_migracion_financiera_repetible(conn):
    preparar_control_financiero()
    preparar_control_financiero()
    assert conn.execute("SELECT to_regclass('public.gastos') AS nombre").fetchone()['nombre'] == 'gastos'


def test_ingresos_por_categoria_y_gastos_con_auditoria(conn, user):
    admin_id = conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()['id']
    amounts = {'RESERVA': '25.00', 'TORNEO': '30.00', 'ESCUELA': '65.00', 'MENSUALIDAD': '30.00'}
    for kind, amount in amounts.items():
        order = conn.execute(
            """INSERT INTO ordenes(usuario_id,tipo,descripcion,monto)
               VALUES(%s,%s,%s,%s) RETURNING id""",
            (user['id'], kind, 'Cobro de prueba', amount),
        ).fetchone()
        conn.execute(
            """INSERT INTO pagos(orden_id,monto,metodo,referencia,simulado,confirmado_por)
               VALUES(%s,%s,'EFECTIVO',%s,false,%s)""",
            (order['id'], amount, f'CONF-{kind}', admin_id),
        )
        conn.execute("UPDATE ordenes SET estado='PAGADA' WHERE id=%s", (order['id'],))
    simulated = conn.execute(
        """INSERT INTO ordenes(usuario_id,tipo,descripcion,monto)
           VALUES(%s,'TORNEO','Pago simulado',500) RETURNING id""", (user['id'],)
    ).fetchone()
    conn.execute(
        """INSERT INTO pagos(orden_id,monto,metodo,referencia)
           VALUES(%s,500,'EFECTIVO','SIM-PRUEBA')""", (simulated['id'],)
    )
    conn.execute("UPDATE ordenes SET estado='PAGADA' WHERE id=%s", (simulated['id'],))
    conn.execute(
        """INSERT INTO ordenes(usuario_id,tipo,descripcion,monto)
           VALUES(%s,'RESERVA','Pendiente',1000)""", (user['id'],)
    )

    with pytest.raises(s.HTTPError) as denied:
        s.registrar_gasto(conn, user['id'], {'categoria':'TORNEOS','concepto':'Trofeos','monto':'10.50','fecha_gasto':str(datetime.now(s.TZ).date())})
    assert denied.value.status == 403
    today = str(datetime.now(s.TZ).date())
    expense = s.registrar_gasto(conn, admin_id, {'categoria':'TORNEOS','concepto':'Trofeos finales','monto':'10.50','fecha_gasto':today})
    s.registrar_gasto(conn, admin_id, {'categoria':'SUPER_CHACA','concepto':'Material deportivo','monto':'6','fecha_gasto':today})
    report = s.reportes(conn, admin_id, {'desde':'2000-01-01','hasta':'2000-01-02'})
    assert report['pagos'] == []
    money = report['finanzas']
    assert money['RESERVAS'] == {'ingresos':Decimal('25'), 'gastos':Decimal('0'), 'saldo':Decimal('25')}
    assert money['TORNEOS'] == {'ingresos':Decimal('30'), 'gastos':Decimal('10.50'), 'saldo':Decimal('19.50')}
    assert money['SUPER_CHACA']['inscripciones'] == Decimal('65')
    assert money['SUPER_CHACA']['mensualidades'] == Decimal('30')
    assert money['SUPER_CHACA']['saldo'] == Decimal('89')
    assert money['GENERAL'] == {'ingresos':Decimal('150'), 'gastos':Decimal('16.50'), 'saldo':Decimal('133.50')}
    assert all('email' not in row for row in report['gastos'])

    with pytest.raises(s.HTTPError) as denied:
        s.anular_gasto(conn, user['id'], expense['id'], {'motivo':'Duplicado'})
    assert denied.value.status == 403
    s.anular_gasto(conn, admin_id, expense['id'], {'motivo':'Compra duplicada'})
    changed = s.reportes(conn, admin_id, {})
    assert changed['finanzas']['TORNEOS']['saldo'] == Decimal('30')
    assert changed['finanzas']['GENERAL']['gastos'] == Decimal('6')
    voided = next(row for row in changed['gastos'] if row['id'] == expense['id'])
    assert voided['anulado_en'] is not None
    assert voided['motivo_anulacion'] == 'Compra duplicada'
    with pytest.raises(s.ErrorValidacion):
        s.anular_gasto(conn, admin_id, expense['id'], {'motivo':'Otra vez'})


@pytest.mark.parametrize('data', [
    {'categoria':'OTRO','concepto':'Trofeos','monto':'5.00'},
    {'categoria':'TORNEOS','concepto':'x','monto':'5.00'},
    {'categoria':'TORNEOS','concepto':'Trofeos','monto':'0'},
    {'categoria':'TORNEOS','concepto':'Trofeos','monto':'1.234'},
    {'categoria':'TORNEOS','concepto':'Trofeos','monto':'NaN'},
])
def test_rechaza_gasto_invalido(conn, data):
    admin_id = conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()['id']
    with pytest.raises(s.ErrorValidacion):
        s.registrar_gasto(conn, admin_id, {'fecha_gasto':str(datetime.now(s.TZ).date()), **data})
    assert conn.execute('SELECT count(*) AS n FROM gastos').fetchone()['n'] == 0


def test_rechaza_gasto_futuro(conn):
    admin_id = conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()['id']
    with pytest.raises(s.ErrorValidacion):
        s.registrar_gasto(conn, admin_id, {'categoria':'TORNEOS','concepto':'Trofeos',
            'monto':'10','fecha_gasto':str(datetime.now(s.TZ).date()+timedelta(days=1))})
