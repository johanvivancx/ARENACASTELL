"""Publicación de resultados con estadísticas coherentes y permisos administrativos."""

import pytest

import copa
import services as s
from db import preparar_resultados_copa


def test_posiciones_historicas_recalculadas_desde_los_partidos():
    data = copa.base()
    finished = [m for m in data['matches'] if m.get('status') not in ('suspended','rescheduled','scheduled')]
    assert len(finished) == 41
    assert sum(m['homeGoals']+m['awayGoals'] for m in finished) == 399
    assert sum(player['goals'] for player in data['scorers']) == 395
    standings = copa.calcular_posiciones(data['matches'], data['standings'])
    assert standings == data['standings']
    for rows in standings.values():
        assert sum(row[6] for row in rows) == sum(row[7] for row in rows)
        assert all(row[1] == row[3]*3+row[4] and row[2] == row[3]+row[4]+row[5]
                   and row[8] == row[6]-row[7] for row in rows)


def test_empate_completo_se_muestra_en_orden_alfabetico():
    groups = {'Grupo de prueba': [['Zeta'], ['Álfa']]}
    rows = copa.calcular_posiciones([], groups)['Grupo de prueba']
    assert [row[0] for row in rows] == ['Álfa', 'Zeta']
    assert [row[9] for row in rows] == [1, 2]


def test_migracion_copa_repetible(conn):
    preparar_resultados_copa()
    preparar_resultados_copa()
    assert conn.execute("SELECT to_regclass('public.copa_resultados') AS tabla").fetchone()['tabla'] == 'copa_resultados'
    assert conn.execute("SELECT to_regclass('public.copa_partidos_programados') AS tabla").fetchone()['tabla'] == 'copa_partidos_programados'
    assert conn.execute("SELECT 1 FROM information_schema.columns WHERE table_name='copa_resultados' AND column_name='estado'").fetchone()


def test_partido_en_vivo_no_altera_posiciones_hasta_finalizar(conn):
    admin = conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()['id']
    panel = copa.panel_admin(conn, admin)
    fixture = next(row for row in panel['fixtures'] if row['home'] == 'Argentina' and row['away'] == 'Japón')
    scorer = next(row for row in panel['players']['Japón'] if row['number'] == '13')
    before = copa.estado_publico(conn)
    start = copa.guardar_resultado(conn, admin, {
        'fixture_id': fixture['id'], 'homeGoals': 0, 'awayGoals': 0,
        'revision': 0, 'estado': 'EN_JUEGO', 'goals': []})
    assert start['estado'] == 'EN_JUEGO' and start['revision'] == 1
    live = copa.guardar_resultado(conn, admin, {
        'fixture_id': fixture['id'], 'homeGoals': 0, 'awayGoals': 1,
        'revision': 1, 'estado': 'EN_JUEGO',
        'goals': [{'country': 'Japón', 'playerId': scorer['id'], 'goals': 1}]})
    assert live['revision'] == 2
    public = copa.estado_publico(conn)
    played = next(row for row in public['matches'] if row.get('id') == fixture['id'])
    assert (played['status'], played['homeGoals'], played['awayGoals']) == ('live', 0, 1)
    assert public['standings'] == before['standings']
    assert public['scorers'] == before['scorers']
    assert public['goleadoresPendientes'] == before['goleadoresPendientes']
    assert next(row for row in copa.panel_admin(conn, admin)['fixtures'] if row['id'] == fixture['id'])['result']['status'] == 'EN_JUEGO'
    with pytest.raises(s.ErrorValidacion, match='resultado final'):
        copa.guardar_jugador_del_partido(conn, admin, {'fixture_id': fixture['id']})
    with pytest.raises(s.HTTPError) as stale:
        copa.guardar_resultado(conn, admin, {
            'fixture_id': fixture['id'], 'homeGoals': 0, 'awayGoals': 0,
            'revision': 1, 'estado': 'FINALIZADO', 'goals': []})
    assert stale.value.status == 409
    final = copa.guardar_resultado(conn, admin, {
        'fixture_id': fixture['id'], 'homeGoals': 0, 'awayGoals': 1,
        'revision': 2, 'estado': 'FINALIZADO',
        'goals': [{'country': 'Japón', 'playerId': scorer['id'], 'goals': 1}]})
    assert final['estado'] == 'FINALIZADO'
    after = copa.estado_publico(conn)
    assert next(row for row in after['matches'] if row.get('id') == fixture['id'])['status'] == 'final'
    assert after['standings'] != before['standings']
    assert next(row for row in after['scorers'] if row['country'] == 'Japón' and row['number'] == '13')['goals'] == next(row for row in before['scorers'] if row['country'] == 'Japón' and row['number'] == '13')['goals'] + 1
    with pytest.raises(s.ErrorValidacion):
        copa.guardar_resultado(conn, admin, {
            'fixture_id': fixture['id'], 'homeGoals': 0, 'awayGoals': 1,
            'revision': 3, 'estado': 'EN_JUEGO', 'goals': []})


def test_programar_siguiente_fecha_y_publicar_marcador(conn, user):
    admin = conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()['id']
    new_match = {'round': 8, 'date': '2026-10-16', 'time': '20:00',
                 'home': 'Argentina', 'away': 'Japón'}
    with pytest.raises(s.HTTPError) as denied:
        copa.programar_partido(conn, user['id'], new_match)
    assert denied.value.status == 403
    created = copa.programar_partido(conn, admin, new_match)
    fixture_id = created['fixture_id']
    assert fixture_id.startswith('admin:')
    with pytest.raises(s.ErrorValidacion, match='ya está programado'):
        copa.programar_partido(conn, admin, {**new_match, 'home': 'Japón', 'away': 'Argentina'})
    assert any(m['id'] == fixture_id for m in copa.panel_admin(conn, admin)['fixtures'])
    scheduled = next(m for m in copa.estado_publico(conn)['matches'] if m.get('id') == fixture_id)
    assert scheduled['round'] == 8 and scheduled['status'] == 'scheduled'
    before = copa.estado_publico(conn)['standings']
    copa.guardar_resultado(conn, admin, {'fixture_id': fixture_id, 'homeGoals': 1,
        'awayGoals': 0, 'revision': 0, 'estado': 'EN_JUEGO', 'goals': []})
    live = copa.estado_publico(conn)
    assert next(m for m in live['matches'] if m.get('id') == fixture_id)['status'] == 'live'
    assert live['standings'] == before
    copa.guardar_resultado(conn, admin, {'fixture_id': fixture_id, 'homeGoals': 1,
        'awayGoals': 0, 'revision': 1, 'estado': 'FINALIZADO', 'goals': []})
    final = copa.estado_publico(conn)
    assert final['throughRound'] == 8
    assert next(m for m in final['matches'] if m.get('id') == fixture_id)['status'] == 'final'
    assert final['standings'] != before


def test_resultado_actualiza_tabla_y_goleadores_sin_duplicar(conn, user):
    admin = conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()['id']
    original = copa.estado_publico(conn)
    assert original['throughRound'] == 6
    assert len([m for m in original['matches'] if m['round'] == 7]) == 6
    fixtures = copa.panel_admin(conn, admin)
    match = next(m for m in fixtures['fixtures'] if m['home'] == 'Argentina' and m['away'] == 'Japón')
    japanese = next(p for p in fixtures['players']['Japón'] if p['number'] == '13')
    argentine = next(p for p in fixtures['players']['Argentina'] if p['name'] == 'Sebastián Arias')
    data = {'fixture_id':match['id'], 'homeGoals':1, 'awayGoals':2, 'revision':0,
            'goals':[{'country':'Argentina','playerId':argentine['id'],'goals':1},
                     {'country':'Japón','playerId':japanese['id'],'goals':2}]}
    with pytest.raises(s.HTTPError) as denied:
        copa.guardar_resultado(conn, user['id'], data)
    assert denied.value.status == 403
    first = copa.guardar_resultado(conn, admin, data)
    assert first['revision'] == 1 and first['goleadores_pendientes'] == 0
    published = copa.estado_publico(conn)
    assert published['throughRound'] == 7 and published['partialRound']
    played = next(m for m in published['matches'] if m.get('id') == match['id'])
    assert (played['homeGoals'],played['awayGoals'],played['status']) == (1,2,'final')
    japan_before = next(row for row in original['standings']['Grupo 2'] if row[0] == 'Japón')
    japan_after = next(row for row in published['standings']['Grupo 2'] if row[0] == 'Japón')
    assert japan_after[1] == japan_before[1]+3 and japan_after[2] == japan_before[2]+1
    taipe_before = next(p for p in original['scorers'] if p['country']=='Japón' and p['number']=='13')
    taipe_after = next(p for p in published['scorers'] if p['country']=='Japón' and p['number']=='13')
    assert taipe_after['goals'] == taipe_before['goals']+2
    with pytest.raises(s.HTTPError) as stale:
        copa.guardar_resultado(conn, admin, data)
    assert stale.value.status == 409
    edited = copa.guardar_resultado(conn, admin, {**data, 'awayGoals':3, 'revision':1,
        'goals':[{'country':'Argentina','playerId':argentine['id'],'goals':1},
                 {'country':'Japón','playerId':japanese['id'],'goals':3}]})
    assert edited['revision'] == 2
    current = copa.estado_publico(conn)
    assert next(p for p in current['scorers'] if p['country']=='Japón' and p['number']=='13')['goals'] == taipe_before['goals']+3
    assert conn.execute("SELECT count(*) AS n FROM copa_goles").fetchone()['n'] == 2


def test_reprogramado_pertenece_a_fecha_seis_y_goles_pendientes(conn):
    admin = conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()['id']
    fixture = next(m for m in copa.panel_admin(conn, admin)['fixtures'] if m['home']=='Alemania' and m['away']=='Venezuela')
    assert fixture['round'] == 6
    result = copa.guardar_resultado(conn, admin, {'fixture_id':fixture['id'], 'homeGoals':2,
        'awayGoals':1, 'revision':0, 'goals':[]})
    assert result['goleadores_pendientes'] == 3
    state = copa.estado_publico(conn)
    assert state['throughRound'] == 6 and not state['partialRound']
    assert state['goleadoresPendientes'] == 3
    assert next(m for m in state['matches'] if m.get('id')==fixture['id'])['round'] == 6
    before_points = next(row[1] for row in state['standings']['Grupo 1'] if row[0]=='Alemania')
    players = copa.panel_admin(conn, admin)['players']
    completed = copa.guardar_resultado(conn, admin, {'fixture_id':fixture['id'],
        'homeGoals':2, 'awayGoals':1, 'revision':1, 'goals':[
            {'country':'Alemania','playerId':players['Alemania'][0]['id'],'goals':2},
            {'country':'Venezuela','playerId':players['Venezuela'][0]['id'],'goals':1}]})
    assert completed['goleadores_pendientes'] == 0
    finished = copa.estado_publico(conn)
    assert finished['goleadoresPendientes'] == 0
    assert next(row[1] for row in finished['standings']['Grupo 1'] if row[0]=='Alemania') == before_points


def test_rechaza_goles_incoherentes_y_jugador_ajeno(conn):
    admin = conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()['id']
    fixture = next(m for m in copa.panel_admin(conn, admin)['fixtures'] if m['home']=='Argentina')
    wrong = {'fixture_id':fixture['id'], 'homeGoals':1, 'awayGoals':0, 'revision':0,
             'goals':[{'country':'Noruega','playerId':'s:0','goals':1}]}
    with pytest.raises(s.ErrorValidacion):
        copa.guardar_resultado(conn, admin, wrong)
    player = copa.panel_admin(conn, admin)['players']['Argentina'][0]
    wrong['goals'] = [{'country':'Argentina','playerId':player['id'],'goals':2}]
    with pytest.raises(s.ErrorValidacion):
        copa.guardar_resultado(conn, admin, wrong)
    assert conn.execute("SELECT count(*) AS n FROM copa_resultados").fetchone()['n'] == 0


def test_jugador_nuevo_suma_goles_y_se_conserva_al_corregir(conn):
    admin = conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()['id']
    fixture = next(m for m in copa.panel_admin(conn, admin)['fixtures'] if m['home']=='Francia' and m['away']=='España')
    data = {'fixture_id':fixture['id'], 'homeGoals':1, 'awayGoals':0,
            'revision':0, 'goals':[{'country':'Francia','playerId':'new',
                                   'name':'Jugador Nuevo Prueba','number':'98','goals':1}]}
    copa.guardar_resultado(conn, admin, data)
    state = copa.estado_publico(conn)
    player = next(p for p in state['scorers'] if p['name']=='Jugador Nuevo Prueba')
    assert player['goals'] == 1
    saved = next(m for m in copa.panel_admin(conn, admin)['fixtures'] if m['id']==fixture['id'])
    assert saved['result']['goals'][0]['jugador_nombre'] == 'Jugador Nuevo Prueba'
    copa.guardar_resultado(conn, admin, {**data, 'revision':1, 'homeGoals':2,
        'goals':[{'country':'Francia','playerId':'new','name':'Jugador Nuevo Prueba',
                  'number':'98','goals':2}]})
    assert next(p for p in copa.estado_publico(conn)['scorers'] if p['name']=='Jugador Nuevo Prueba')['goals'] == 2
