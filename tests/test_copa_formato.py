"""La nueva fase no debe anunciar semifinalistas antes de jugarse."""

from itertools import combinations

import copa
import pytest

from models import ErrorValidacion


def game(stage, home, away, status="final", home_goals=0, away_goals=0):
    return {"stage": stage, "home": home, "away": away, "status": status,
            "homeGoals": home_goals, "awayGoals": away_goals}


def test_tablas_separadas_ignoran_en_juego_y_conservan_bonificacion():
    matches = [
        game("GRUPO_A", "Noruega", "Cabo Verde", home_goals=2),
        game("GRUPO_B", "Francia", "Ecuador", "live", home_goals=4),
        game("BRONCE", "Venezuela", "Alemania", home_goals=1),
        game("FASE1", "Portugal", "Japón", home_goals=9),
    ]
    state = copa.formato_actual(matches)
    group_a = {row[0]: row for row in state["groups"]["A"]["standings"]}
    group_b = {row[0]: row for row in state["groups"]["B"]["standings"]}
    bronze = {row[0]: row for row in state["groups"]["BRONCE"]["standings"]}
    assert group_a["Noruega"][1:3] == [5, 1]
    assert group_b["Francia"][1:3] == [2, 0]
    assert bronze["Venezuela"][1:3] == [3, 1]
    assert group_a["Portugal"][1:3] == [0, 0]
    assert not state["semifinalistsConfirmed"]
    assert state["qualified"] == {"ORO": [], "PLATA": []}


def test_semifinalistas_aparecen_solo_cuando_terminan_ambos_grupos():
    rules = copa.base()["format"]["groups"]
    a = [game("GRUPO_A", home, away, home_goals=1)
         for home, away in combinations(rules["A"], 2)]
    b_pairs = list(combinations(rules["B"], 2))
    b = [game("GRUPO_B", home, away, home_goals=1) for home, away in b_pairs]
    assert len(a) == 6 and len(b) == 10
    assert not copa.formato_actual(a + b[:-1])["semifinalistsConfirmed"]
    complete = copa.formato_actual(a + b)
    assert complete["semifinalistsConfirmed"]
    assert len(complete["qualified"]["ORO"]) == 4
    assert len(complete["qualified"]["PLATA"]) == 4
    assert set(complete["qualified"]["ORO"]).isdisjoint(complete["qualified"]["PLATA"])


def test_resultado_de_nueva_fase_no_modifica_primera_fase(conn):
    admin = conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()["id"]
    proposed = {"round": 8, "stage": "GRUPO_A", "date": "2026-10-16",
                "time": "20:00", "home": "Noruega", "away": "Cabo Verde"}
    with pytest.raises(ErrorValidacion, match="grupo"):
        copa.programar_partido(conn, admin, {**proposed, "away": "Brasil"})
    before = copa.estado_publico(conn)
    fixture_id = copa.programar_partido(conn, admin, proposed)["fixture_id"]
    copa.guardar_resultado(conn, admin, {"fixture_id": fixture_id, "homeGoals": 2,
        "awayGoals": 0, "estado": "FINALIZADO", "revision": 0, "goals": []})
    after = copa.estado_publico(conn)
    assert after["standings"] == before["standings"]
    assert after["format"]["groups"]["A"]["standings"][0][0:3] == ["Noruega", 5, 1]
    assert not after["format"]["semifinalistsConfirmed"]
