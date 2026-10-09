# Prueba opciones administrativas

from datetime import datetime, timedelta
from decimal import Decimal
import pytest
import psycopg
from manage import cedula_demo, insert_user
from models import Administrador
import services as s
from conftest import confirmar_transferencia


def test_crear_administrador_exige_rol_y_password_actual(conn, user):
    admin = Administrador('Admin Actual', 'actual@arena.test', cedula_demo(912), '0990000000')
    admin.set_password('ActualSegura!2026')
    insert_user(conn, admin)
    aid = conn.execute("SELECT id FROM usuarios WHERE email='actual@arena.test'").fetchone()['id']
    datos = {
        'nombre': 'Nueva Administradora', 'email': 'nueva@arena.test',
        'cedula': cedula_demo(913), 'telefono': '0991234567',
        'nueva_password': 'NuevaSegura!2026', 'confirmacion': 'NuevaSegura!2026',
        'password_actual': 'ActualSegura!2026',
    }
    with pytest.raises(s.HTTPError) as forbidden:
        s.crear_administrador(conn, user['id'], datos)
    assert forbidden.value.status == 403
    with pytest.raises(s.HTTPError) as wrong_password:
        s.crear_administrador(conn, aid, {**datos, 'password_actual': 'equivocada'})
    assert wrong_password.value.status == 403
    assert conn.execute("SELECT count(*) AS n FROM usuarios WHERE email=%s", (datos['email'],)).fetchone()['n'] == 0
    with pytest.raises(s.ErrorValidacion):
        s.crear_administrador(conn, aid, {**datos, 'confirmacion': 'DistintaSegura!2026'})
    result = s.crear_administrador(conn, aid, datos)
    assert 'Administrador creado' in result['message']
    creado = conn.execute("SELECT * FROM usuarios WHERE email=%s", (datos['email'],)).fetchone()
    assert creado['rol'] == 'ADMIN'
    assert Administrador.desde_fila(creado).verificar_password(datos['nueva_password'])
    with pytest.raises(s.ErrorValidacion):
        s.crear_administrador(conn, aid, datos)


def test_admin_ve_pendientes_y_pagadas_cliente_solo_lo_suyo(conn,user,pay_data):
    other=s.registrar(conn,{'nombre':'Otra Persona','email':'otra@arena.test','cedula':cedula_demo(910),
        'telefono':'0990000000','password':'OtraClaveSegura!','confirmacion':'OtraClaveSegura!', 'consentimiento':True})
    admin=Administrador('Administrador Prueba','operador@arena.test',cedula_demo(911),'0990000000')
    admin.set_password('AdministradorSeguro!')
    insert_user(conn,admin)
    aid=conn.execute("SELECT id FROM usuarios WHERE email='operador@arena.test'").fetchone()['id']
    day=str(datetime.now(s.TZ).date()+timedelta(days=3))
    first=s.reservar(conn,user['id'],{'cancha_id':1,'tipo_evento':'HORA','fecha':day,'hora':'10:00','horas':1})
    second=s.reservar(conn,other['id'],{'cancha_id':1,'tipo_evento':'EVENTO','fecha':day,'hora':'12:00','horas':2})
    confirmar_transferencia(conn,user['id'],first['id'],pay_data)
    report=s.reportes(conn,aid,{})
    assert {r['estado_pago'] for r in report['reservas']}=={'PAGADA','PENDIENTE'}
    assert {o['id'] for o in report['operaciones']}=={first['id'],second['id']}
    assert len(report['pagos'])==1 and len(report['reservas'])==2
    s.solicitar_restablecimiento(conn,{'email':user['email']})
    mail_report=s.reportes(conn,aid,{})['correos']
    assert len(mail_report)==2
    assert all('cuerpo' not in row for row in mail_report)
    assert '#token=' not in str(mail_report)
    assert {o['id'] for o in s.historial(conn,user['id'])['ordenes']}=={first['id']}
    assert {o['id'] for o in s.historial(conn,other['id'])['ordenes']}=={second['id']}
    with pytest.raises(s.HTTPError) as forbidden:
        s.reportes(conn,user['id'],{})
    assert forbidden.value.status==403


def test_reserva_manual_bloquea_horario_sin_inventar_un_pago(conn,user):
    admin_id=conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()['id']
    day=str(datetime.now(s.TZ).date()+timedelta(days=3))
    data={'cliente':'Contacto WhatsApp','telefono':'0991234567','cancha_id':1,
          'tipo_evento':'HORA','fecha':day,'hora':'12:00','horas':2,'monto':'24.50'}
    with pytest.raises(s.HTTPError) as forbidden:
        s.registrar_reserva_manual(conn,user['id'],data)
    assert forbidden.value.status==403
    assert conn.execute("SELECT count(*) AS n FROM reservas").fetchone()['n']==0

    order=s.registrar_reserva_manual(conn,admin_id,data)
    row=conn.execute("""SELECT r.estado AS reserva,o.estado AS pago,o.metodo_previsto,o.monto,
                        o.descripcion FROM reservas r JOIN ordenes o ON o.id=r.orden_id
                        WHERE o.id=%s""",(order['id'],)).fetchone()
    assert (row['reserva'],row['pago'],row['metodo_previsto'])==('CONFIRMADA','PENDIENTE','EFECTIVO')
    assert row['monto']==Decimal('24.50')
    assert 'Contacto WhatsApp' in row['descripcion']
    assert conn.execute("SELECT count(*) AS n FROM pagos").fetchone()['n']==0
    availability=s.disponibilidad(conn,{'fecha':day,'cancha':1,'horas':1})
    assert not next(slot for slot in availability['horarios'] if slot['hora']=='12:00')['disponible']
    assert not next(slot for slot in availability['horarios'] if slot['hora']=='13:00')['disponible']
    report=s.reportes(conn,admin_id,{})
    assert report['reservas'][0]['manual'] is True
    assert report['resumen']['pagos']==0 and len(report['efectivo_pendiente'])==1

    with pytest.raises(psycopg.IntegrityError):
        with conn.transaction():
            s.registrar_reserva_manual(conn,admin_id,{**data,'cliente':'Otro contacto','hora':'13:00'})
    assert conn.execute("SELECT count(*) AS n FROM reservas").fetchone()['n']==1

    s.cobrar_efectivo(conn,admin_id,order['id'])
    assert conn.execute("SELECT count(*) AS n FROM pagos").fetchone()['n']==1
    assert conn.execute("SELECT monto FROM pagos WHERE orden_id=%s",(order['id'],)).fetchone()['monto']==Decimal('24.50')
    paid_report=s.reportes(conn,admin_id,{})
    assert paid_report['resumen']['reservas']==1
    assert paid_report['finanzas']['RESERVAS']['ingresos']==Decimal('24.50')
    with pytest.raises(s.ErrorValidacion):
        s.cancelar_reserva_manual(conn,admin_id,order['id'])

    second=s.registrar_reserva_manual(conn,admin_id,{**data,'hora':'16:00'})
    assert not next(slot for slot in s.disponibilidad(conn,{'fecha':day,'cancha':1,'horas':1})['horarios']
                    if slot['hora']=='16:00')['disponible']
    with pytest.raises(s.HTTPError) as forbidden:
        s.cancelar_reserva_manual(conn,user['id'],second['id'])
    assert forbidden.value.status==403
    s.cancelar_reserva_manual(conn,admin_id,second['id'])
    assert next(slot for slot in s.disponibilidad(conn,{'fecha':day,'cancha':1,'horas':1})['horarios']
                if slot['hora']=='16:00')['disponible']
    report=s.reportes(conn,admin_id,{})
    assert any(row['orden_id']==second['id'] and row['estado']=='CANCELADA' for row in report['reservas'])
    assert all(row['orden_id']!=second['id'] for row in report['efectivo_pendiente'])

    with pytest.raises(s.ErrorValidacion):
        s.registrar_reserva_manual(conn,admin_id,{**data,'hora':'17:00','monto':'0'})
    with pytest.raises(s.ErrorValidacion):
        s.registrar_reserva_manual(conn,admin_id,{**data,'hora':'17:00','monto':'24.567'})


def test_reserva_manual_pasada_y_cobros_por_metodo(conn, monkeypatch):
    test_date = datetime.now(s.TZ).date()

    class HoraDePrueba(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.combine(test_date, datetime.min.time(), tz or s.TZ).replace(hour=21)

    monkeypatch.setattr(s, "datetime", HoraDePrueba)
    admin = Administrador('Admin de reservas', 'reservas@arena.test', cedula_demo(914), '0990000000')
    admin.set_password('AdminSegura!2026')
    insert_user(conn, admin)
    aid = conn.execute("SELECT id FROM usuarios WHERE email='reservas@arena.test'").fetchone()['id']
    data = {
        'cliente': 'Reserva anterior', 'cancha_id': 1, 'tipo_evento': 'HORA',
        'fecha': test_date.isoformat(), 'horas': 1, 'monto': '25.00',
        'cobro_estado': 'PAGADA',
    }
    request = {'fecha': data['fecha'], 'cancha': 1, 'horas': 1}
    assert not next(slot for slot in s.disponibilidad(conn, request)['horarios'] if slot['hora'] == '19:00')['disponible']
    assert next(slot for slot in s.disponibilidad(conn, request, incluir_horas_pasadas=True)['horarios'] if slot['hora'] == '19:00')['disponible']
    cash = s.registrar_reserva_manual(conn, aid, {**data, 'hora': '19:00', 'metodo': 'EFECTIVO'})
    transfer = s.registrar_reserva_manual(conn, aid, {**data, 'hora': '20:00', 'metodo': 'TRANSFERENCIA', 'monto': '24.00'})
    pending = s.registrar_reserva_manual(conn, aid, {**data, 'hora': '18:00', 'metodo': 'TRANSFERENCIA', 'cobro_estado': 'PENDIENTE'})
    rows = conn.execute("SELECT orden_id,metodo,monto,simulado FROM pagos ORDER BY id").fetchall()
    assert [(row['metodo'], row['monto'], row['simulado']) for row in rows] == [
        ('EFECTIVO', Decimal('25.00'), False),
        ('TRANSFERENCIA', Decimal('24.00'), False),
    ]
    assert {row['orden_id'] for row in rows} == {cash['id'], transfer['id']}
    report = s.reportes(conn, aid, {})
    assert report['reservas_manuales_cobradas'] == {
        'EFECTIVO': Decimal('25.00'), 'TRANSFERENCIA': Decimal('24.00'),
    }
    assert report['finanzas']['RESERVAS']['ingresos'] == Decimal('49.00')
    assert any(row['id'] == pending['id'] for row in report['transferencias_pendientes'])
    assert not next(slot for slot in s.disponibilidad(conn, request, incluir_horas_pasadas=True)['horarios'] if slot['hora'] == '19:00')['disponible']


def test_limpieza_de_pruebas_conserva_administradores_y_copa(conn, user):
    admin = s.registrar(conn, {
        'nombre': 'Administrador de limpieza', 'cedula': cedula_demo(947),
        'telefono': '0990000000', 'email': 'limpieza@arena.test',
        'password': 'ClaveLimpieza!2026', 'confirmacion': 'ClaveLimpieza!2026',
        'consentimiento': True,
    })
    conn.execute("UPDATE usuarios SET rol='ADMIN' WHERE id=%s", (admin['id'],))
    conn.execute(
        """INSERT INTO copa_resultados(fixture_id,fecha,local,visitante,goles_local,goles_visitante,registrado_por)
           VALUES('partido-conservado',7,'Argentina','Japón',2,1,%s)""",
        (admin['id'],),
    )
    day = str(datetime.now(s.TZ).date() + timedelta(days=3))
    booked = s.reservar(conn, user['id'], {
        'cancha_id': 1, 'tipo_evento': 'HORA', 'fecha': day, 'hora': '12:00', 'horas': 1,
    })
    s.registrar_gasto(conn, admin['id'], {
        'categoria': 'RESERVAS', 'fecha_gasto': str(datetime.now(s.TZ).date()),
        'concepto': 'Prueba de gasto', 'monto': '2.00',
    })
    preview = s.resumen_datos_prueba(conn, admin['id'])
    assert preview['clientes'] == 1 and preview['reservas'] == 1
    assert preview['ordenes'] == 1 and preview['gastos'] == 1
    with pytest.raises(s.HTTPError) as forbidden:
        s.resumen_datos_prueba(conn, user['id'])
    assert forbidden.value.status == 403
    payload = {'confirmacion': 'BORRAR DATOS DE PRUEBA', 'password': 'ClaveLimpieza!2026',
               'resumen': preview}
    with pytest.raises(s.HTTPError) as stale:
        s.limpiar_datos_prueba(conn, admin['id'], {**payload, 'resumen': {**preview, 'ordenes': 0}})
    assert stale.value.status == 409
    assert conn.execute('SELECT count(*) AS n FROM ordenes').fetchone()['n'] == 1
    result = s.limpiar_datos_prueba(conn, admin['id'], payload)
    assert result['eliminados']['ordenes'] == 1
    assert all(value == 0 for value in s.resumen_datos_prueba(conn, admin['id']).values())
    assert conn.execute('SELECT count(*) AS n FROM usuarios WHERE rol=\'ADMIN\'').fetchone()['n'] == 2
    assert conn.execute('SELECT count(*) AS n FROM copa_resultados').fetchone()['n'] == 1
    assert conn.execute('SELECT count(*) AS n FROM canchas').fetchone()['n'] > 0
    assert conn.execute('SELECT count(*) AS n FROM torneos').fetchone()['n'] > 0
