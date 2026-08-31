"""Reglas nuevas de los flyers; todas las escrituras usan la base aislada."""
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from manage import cedula_demo
from models import ErrorValidacion, InscripcionSuperChaca, InscripcionTorneo
import services as s

ROOT = Path(__file__).resolve().parents[1]


def test_copa_en_juego_no_admite_nuevas_inscripciones(conn, user):
    conn.execute((ROOT/'sql/seed.sql').read_text(encoding='utf8'))
    copa = next(t for t in s.catalogo(conn)['torneos'] if 'Mundial' in t['nombre'])
    assert copa['costo'] == Decimal('25') and copa['max_jugadores'] == 15
    assert copa['fecha_inicio'] == date(2026, 8, 28) and not copa['abierto']
    with pytest.raises(ErrorValidacion, match='cerradas'):
        s.inscribir_torneo(conn, user['id'], {'torneo_id': copa['id'], 'equipo': 'Equipo tardío', 'acepta_reglamento': True})


@pytest.mark.parametrize('edad,categoria', [(4, 'Sub-6'), (5, 'Sub-6'), (17, 'Sub-18')])
def test_escuela_extremos_edad_y_mensualidad(conn, user, pay_data, edad, categoria):
    hoy = datetime.now(s.TZ).date()
    horario = next(h for h in s.catalogo(conn)['horarios_chaca'] if h['categoria'] == categoria)
    order = s.inscribir_escuela(conn, user['id'], {
        'alumno': 'Alumno ficticio', 'cedula': cedula_demo(710),
        'nacimiento': str(date(hoy.year-edad, 1, 1)), 'categoria': categoria,
        'horario_id': horario['id'], 'consentimiento': True,
    })
    s.pagar(conn, user['id'], order['id'], pay_data)
    detail = s.detalle_orden(conn, user['id'], order['id'])
    assert detail['escuela']['categoria'] == categoria
    assert detail['pago']['monto'] == Decimal('50')


@pytest.mark.parametrize('edad', [3, 18])
def test_edad_fuera_de_oferta(edad):
    with pytest.raises(ErrorValidacion):
        InscripcionSuperChaca(date(2026-edad, 1, 1), 'Sub-6', date(2026, 8, 30))


def test_limite_especifico_no_se_puede_saltar_en_sql(conn, user, pay_data):
    conn.execute('UPDATE torneos SET max_jugadores=15 WHERE id=1')
    order = s.inscribir_torneo(conn, user['id'], {'torneo_id': 1, 'equipo': 'Equipo de quince', 'acepta_reglamento': True})
    s.pagar(conn, user['id'], order['id'], pay_data)
    team = s.detalle_orden(conn, user['id'], order['id'])['equipo']
    for n in range(15):
        s.agregar_jugador(conn, user['id'], team['id'], {'nombre': f'Jugador {n}', 'cedula': cedula_demo(720+n)})
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute("INSERT INTO jugadores(equipo_id,nombre,cedula) VALUES(%s,'Jugador extra',%s)", (team['id'], cedula_demo(750)))
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute('UPDATE torneos SET max_jugadores=14 WHERE id=1')
    assert s.lista_equipo(conn, user['id'], team['id'])['max_jugadores'] == 15
    assert 'máximo 15' in s.historial(conn, user['id'])['correos'][0]['cuerpo']
    with pytest.raises(ErrorValidacion):
        InscripcionTorneo(25, jugadores=16, max_jugadores=15)


def test_migracion_repetible_conserva_operaciones_y_horarios_antiguos(conn, user, pay_data):
    conn.execute("UPDATE torneos SET nombre='Copa Castell', descripcion='Torneo amateur de fútbol 7. Hasta 20 jugadores por equipo.', costo=120 WHERE id=1")
    order = s.inscribir_torneo(conn, user['id'], {'torneo_id': 1, 'equipo': 'Equipo anterior', 'acepta_reglamento': True})
    s.pagar(conn, user['id'], order['id'], pay_data)
    team = s.detalle_orden(conn, user['id'], order['id'])['equipo']
    s.agregar_jugador(conn, user['id'], team['id'], {'nombre': 'Jugador anterior', 'cedula': cedula_demo(790)})
    legacy = conn.execute("INSERT INTO horarios_chaca(categoria,dias,inicio,fin) VALUES('Sub-6','Lunes y miércoles','15:00','16:30') RETURNING id").fetchone()['id']
    for _ in range(2):
        conn.execute((ROOT/'sql/migrations/001_flyers.sql').read_text(encoding='utf8'))
        conn.execute((ROOT/'sql/seed.sql').read_text(encoding='utf8'))
    catalog = s.catalogo(conn)
    copa = next(t for t in catalog['torneos'] if t['nombre'] == 'Copa Castell · Mundial de Campeones')
    assert len(catalog['torneos']) == 2 and copa['max_jugadores'] == 15
    assert len(catalog['horarios_chaca']) == 14
    assert all(h['id'] != legacy for h in catalog['horarios_chaca'])
    assert conn.execute('SELECT id FROM horarios_chaca WHERE id=%s', (legacy,)).fetchone()
    assert s.detalle_orden(conn, user['id'], order['id'])['pago']['monto'] == Decimal('120')
    assert len(s.lista_equipo(conn, user['id'], team['id'])['jugadores']) == 1
    with pytest.raises(ErrorValidacion, match='horario'):
        with conn.transaction():
            s.inscribir_escuela(conn, user['id'], {
                'alumno': 'Alumno ficticio', 'cedula': cedula_demo(791),
                'nacimiento': str(date(datetime.now(s.TZ).year-4, 1, 1)),
                'categoria': 'Sub-6', 'horario_id': legacy, 'consentimiento': True,
            })
