"""Pago presencial: intención, autorización de cobro y compatibilidad histórica."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest import TestCase

import psycopg
from pypdf import PdfReader

import comprobantes as c
import services as s
from manage import cedula_demo

check = TestCase()


def reserva(conn, user, dias=3):
    return s.reservar(conn, user['id'], {'cancha_id': 1, 'tipo_evento': 'HORA',
        'fecha': str(datetime.now(s.TZ).date() + timedelta(days=dias)), 'hora': '12:00', 'horas': 1})


def administrador(conn):
    user = s.registrar(conn, {'nombre': 'Administrador de prueba', 'email': 'caja@arena.test',
        'cedula': cedula_demo(902), 'telefono': '0990000000', 'password': 'PruebaCaja!2026',
        'confirmacion': 'PruebaCaja!2026', 'consentimiento': True})
    conn.execute("UPDATE usuarios SET rol='ADMIN' WHERE id=%s", (user['id'],))
    return user['id']


def test_efectivo_es_intencion_sin_pago_ni_correo(conn, user):
    order = reserva(conn, user)
    for _ in range(2):
        result = s.pagar(conn, user['id'], order['id'],
            {'metodo': 'EFECTIVO', 'acepta_simulacion': True, 'efectivo_recibido': True})
        assert result['pendiente'] is True
    detail = s.detalle_orden(conn, user['id'], order['id'])
    assert detail['estado'] == 'PENDIENTE' and detail['metodo_previsto'] == 'EFECTIVO'
    assert detail['pago'] is None and detail['reserva']['estado'] == 'PENDIENTE'
    assert conn.execute('SELECT count(*) AS n FROM correo_salida').fetchone()['n'] == 0
    assert not s.historial(conn, user['id'])['ordenes'][0]['estado'] == 'PAGADA'


def test_solo_admin_cobra_efectivo_y_no_duplica(conn, user):
    order = reserva(conn, user)
    s.pagar(conn, user['id'], order['id'], {'metodo': 'EFECTIVO', 'acepta_simulacion': True})
    with check.assertRaises(s.HTTPError) as error:
        s.cobrar_efectivo(conn, user['id'], order['id'])
    assert error.exception.status == 403
    aid = administrador(conn)
    assert len(s.reportes(conn, aid, {})['efectivo_pendiente']) == 1
    s.cobrar_efectivo(conn, aid, order['id'])
    s.cobrar_efectivo(conn, aid, order['id'])
    detail = s.detalle_orden(conn, user['id'], order['id'])
    assert detail['estado'] == 'PAGADA' and detail['pago']['metodo'] == 'EFECTIVO'
    assert detail['reserva']['estado'] == 'CONFIRMADA'
    assert len(s.reportes(conn, aid, {})['efectivo_pendiente']) == 0
    assert conn.execute('SELECT count(*) AS n FROM pagos').fetchone()['n'] == 1
    assert conn.execute('SELECT count(*) AS n FROM correo_salida').fetchone()['n'] == 1


def test_tarjeta_y_metodos_anteriores_generan_comprobante(conn, user):
    for i, method in enumerate(['TARJETA', 'TRANSFERENCIA', 'DEBITO', 'CREDITO']):
        order = reserva(conn, user, i + 3)
        s.pagar(conn, user['id'], order['id'], {'metodo': method, 'acepta_simulacion': True})
        detail = s.detalle_orden(conn, user['id'], order['id'])
        assert detail['pago']['metodo'] == method and detail['monto'] == Decimal('27')
        receipt = c.datos_comprobante(conn, order['id'], user['id'])
        context = c.contexto_correo({'comprobante': receipt, 'asunto': 'Confirmación',
            'cuerpo': 'Registro de prueba.'}, 'http://127.0.0.1:8765')
        pdf = PdfReader(BytesIO(c.crear_pdf(context)))
        assert c.METODOS[method] in pdf.pages[0].extract_text()


def test_efectivo_torneo_y_escuela_se_confirman_al_cobrar(conn, user):
    aid = administrador(conn)
    tournament = s.inscribir_torneo(conn, user['id'],
        {'torneo_id': 1, 'equipo': 'Equipo caja', 'acepta_reglamento': True})
    before = next(t['disponibles'] for t in s.catalogo(conn)['torneos'] if t['id'] == 1)
    s.pagar(conn, user['id'], tournament['id'], {'metodo': 'EFECTIVO', 'acepta_simulacion': True})
    assert next(t['disponibles'] for t in s.catalogo(conn)['torneos'] if t['id'] == 1) == before
    s.cobrar_efectivo(conn, aid, tournament['id'])
    assert next(t['disponibles'] for t in s.catalogo(conn)['torneos'] if t['id'] == 1) == before - 1
    today = datetime.now(s.TZ).date()
    hid = conn.execute("SELECT id FROM horarios_chaca WHERE categoria='Sub-12' AND activo LIMIT 1").fetchone()['id']
    school = s.inscribir_escuela(conn, user['id'], {'alumno': 'Alumno caja', 'cedula': cedula_demo(903),
        'nacimiento': str(date(today.year - 10, 1, 1)), 'categoria': 'Sub-12', 'horario_id': hid, 'consentimiento': True})
    s.pagar(conn, user['id'], school['id'], {'metodo': 'EFECTIVO', 'acepta_simulacion': True})
    assert s.detalle_orden(conn, user['id'], school['id'])['escuela']['estado'] == 'PENDIENTE'
    s.cobrar_efectivo(conn, aid, school['id'])
    assert s.detalle_orden(conn, user['id'], school['id'])['escuela']['estado'] == 'ACTIVA'


def test_conflicto_de_horario_no_cobra_efectivo(conn, user):
    cash = reserva(conn, user)
    s.pagar(conn, user['id'], cash['id'], {'metodo': 'EFECTIVO', 'acepta_simulacion': True})
    other = reserva(conn, user)
    s.pagar(conn, user['id'], other['id'], {'metodo': 'TARJETA', 'acepta_simulacion': True})
    aid = administrador(conn)
    with check.assertRaises(psycopg.IntegrityError):
        with conn.transaction():
            s.cobrar_efectivo(conn, aid, cash['id'])
    detail = s.detalle_orden(conn, user['id'], cash['id'])
    assert detail['pago'] is None and detail['estado'] == 'PENDIENTE'
    with check.assertRaises(s.ErrorValidacion):
        s.cobrar_efectivo(conn, aid, other['id'])


def test_migracion_conserva_pagos_anteriores_y_se_puede_repetir(conn, user):
    order = reserva(conn, user)
    s.pagar(conn, user['id'], order['id'], {'metodo': 'DEBITO', 'acepta_simulacion': True})
    previous = dict(s.detalle_orden(conn, user['id'], order['id'])['pago'])
    conn.execute('ALTER TABLE ordenes DROP COLUMN metodo_previsto')
    conn.execute('ALTER TABLE pagos DROP CONSTRAINT pagos_metodo_check')
    conn.execute("ALTER TABLE pagos ADD CONSTRAINT pagos_metodo_check CHECK (metodo IN ('TRANSFERENCIA','DEBITO','CREDITO'))")
    migration = Path(__file__).resolve().parents[1] / 'sql/migrations/005_metodos_pago.sql'
    for _ in range(2):
        conn.execute(migration.read_text(encoding='utf-8'))
    assert dict(s.detalle_orden(conn, user['id'], order['id'])['pago']) == previous
    assert s.detalle_orden(conn, user['id'], order['id'])['metodo_previsto'] is None
