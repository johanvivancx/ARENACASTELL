"""Publicación de resultados con estadísticas coherentes y permisos administrativos."""

import pytest

import copa
import services as s
from db import preparar_resultados_copa


def test_migracion_copa_repetible(conn):
    preparar_resultados_copa()
    preparar_resultados_copa()
    assert conn.execute("SELECT to_regclass('public.copa_resultados') AS tabla").fetchone()['tabla'] == 'copa_resultados'


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
