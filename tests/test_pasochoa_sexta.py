"""Inscripción de la sexta edición en la base temporal de las pruebas."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from manage import cedula_demo, insert_user
from models import Administrador, ErrorValidacion
import services as s

ROOT = Path(__file__).resolve().parents[1]
NAME = 'Pasochoa Cup · Sexta edición'
SCRIPT = ROOT / 'sql/pgadmin/13_pasochoa_sexta_edicion.sql'


def siguiente_edicion(conn):
    torneo = conn.execute('SELECT * FROM torneos WHERE nombre=%s', (NAME,)).fetchone()
    # Solo en esta base temporal: mantener la prueba útil después de septiembre.
    conn.execute('UPDATE torneos SET fecha_inicio=current_date+30 WHERE id=%s', (torneo['id'],))
    return torneo


def inscribir(conn, uid, tid, nombre):
    return s.inscribir_torneo(conn, uid, {
        'torneo_id': tid, 'equipo': nombre, 'acepta_reglamento': True,
    })


def test_paso_13_repetible_no_cambia_historial_ni_reabre_torneo(conn, user, pay_data):
    anterior = inscribir(conn, user['id'], 1, 'Equipo anterior')
    s.pagar(conn, user['id'], anterior['id'], pay_data)
    antes = s.detalle_orden(conn, user['id'], anterior['id'])
    conn.execute('DELETE FROM torneos WHERE nombre=%s', (NAME,))
    conn.commit()
    for _ in range(2):
        conn.execute(SCRIPT.read_text(encoding='utf8'))
    filas = conn.execute('SELECT * FROM torneos WHERE nombre=%s', (NAME,)).fetchall()
    assert len(filas) == 1
    torneo = filas[0]
    assert torneo['fecha_inicio'] == date(2026, 9, 30)
    assert (torneo['costo'], torneo['cupos'], torneo['max_jugadores']) == (Decimal('30'), 16, 20)
    assert torneo['visible'] and torneo['abierto']
    assert s.detalle_orden(conn, user['id'], anterior['id']) == antes
    conn.execute('UPDATE torneos SET abierto=false WHERE id=%s', (torneo['id'],))
    conn.commit()
    conn.execute(SCRIPT.read_text(encoding='utf8'))
    assert not conn.execute('SELECT abierto FROM torneos WHERE id=%s', (torneo['id'],)).fetchone()['abierto']
    assert conn.execute('SELECT count(*) AS n FROM pagos').fetchone()['n'] == 1


def test_pasochoa_pago_historial_y_panel_admin(conn, user, pay_data):
    torneo = siguiente_edicion(conn)
    otra = s.registrar(conn, {
        'nombre': 'Otra Persona', 'email': 'otra.sexta@arena.test', 'cedula': cedula_demo(930),
        'telefono': '0990000000', 'password': 'OtraClaveSegura!',
        'confirmacion': 'OtraClaveSegura!', 'consentimiento': True,
    })
    admin = Administrador('Admin Prueba', 'admin.sexta@arena.test', cedula_demo(931), '0990000000')
    admin.set_password('AdminSextaSegura!')
    insert_user(conn, admin)
    aid = conn.execute("SELECT id FROM usuarios WHERE email='admin.sexta@arena.test'").fetchone()['id']
    orden = inscribir(conn, user['id'], torneo['id'], 'Equipo de la sexta')
    pendiente = inscribir(conn, otra['id'], torneo['id'], 'Otro equipo pendiente')
    assert s.detalle_orden(conn, user['id'], orden['id'])['monto'] == Decimal('30')
    s.pagar(conn, user['id'], orden['id'], pay_data)
    s.pagar(conn, user['id'], orden['id'], pay_data)
    detalle = s.detalle_orden(conn, user['id'], orden['id'])
    assert detalle['estado'] == 'PAGADA' and detalle['equipo']['estado'] == 'CONFIRMADO'
    assert detalle['pago']['monto'] == Decimal('30')
    historial = s.historial(conn, user['id'])
    assert [o['id'] for o in historial['ordenes']] == [orden['id']]
    assert 'máximo 20' in historial['correos'][0]['cuerpo']
    assert s.historial(conn, otra['id'])['ordenes'][0]['id'] == pendiente['id']
    with pytest.raises(s.HTTPError) as privado:
        s.detalle_orden(conn, otra['id'], orden['id'])
    assert privado.value.status == 404
    with pytest.raises(s.HTTPError) as prohibido:
        s.reportes(conn, user['id'], {})
    assert prohibido.value.status == 403
    reporte = s.reportes(conn, aid, {})
    assert {o['estado'] for o in reporte['operaciones']} == {'PAGADA', 'PENDIENTE'}
    assert reporte['resumen']['equipos'] == 1 and len(reporte['pagos']) == 1
    assert reporte['pagos'][0]['monto'] == Decimal('30')
    disponible = next(t for t in s.catalogo(conn)['torneos'] if t['id'] == torneo['id'])
    assert disponible['disponibles'] == 15


def test_pasochoa_no_confirma_un_equipo_17(conn, user, pay_data):
    torneo = siguiente_edicion(conn)
    ordenes = [inscribir(conn, user['id'], torneo['id'], f'Equipo sexta {n}') for n in range(17)]
    for orden in ordenes[:16]:
        s.pagar(conn, user['id'], orden['id'], pay_data)
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            s.pagar(conn, user['id'], ordenes[16]['id'], pay_data)
    assert conn.execute('SELECT count(*) AS n FROM pagos').fetchone()['n'] == 16
    detalle = s.detalle_orden(conn, user['id'], ordenes[16]['id'])
    assert detalle['estado'] == 'PENDIENTE' and detalle['pago'] is None
    assert next(t for t in s.catalogo(conn)['torneos'] if t['id'] == torneo['id'])['disponibles'] == 0


def test_pasochoa_cierra_inscripcion_y_pago_al_comenzar(conn, user, pay_data):
    torneo = siguiente_edicion(conn)
    pendiente = inscribir(conn, user['id'], torneo['id'], 'Equipo sin pagar')
    conn.execute('UPDATE torneos SET fecha_inicio=current_date WHERE id=%s', (torneo['id'],))
    with pytest.raises(ErrorValidacion, match='cerradas'):
        inscribir(conn, user['id'], torneo['id'], 'Equipo fuera de fecha')
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            s.pagar(conn, user['id'], pendiente['id'], pay_data)
    assert conn.execute('SELECT count(*) AS n FROM pagos').fetchone()['n'] == 0
