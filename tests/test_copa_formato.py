"""La nueva fase no debe anunciar semifinalistas antes de jugarse."""

from itertools import combinations
from copy import deepcopy

import copa
import pytest

from models import ErrorValidacion


def game(stage, home, away, status="final", home_goals=0, away_goals=0):
    return {"stage": stage, "home": home, "away": away, "status": status,
            "homeGoals": home_goals, "awayGoals": away_goals}


def test_grupos_confirmados_no_anuncian_semifinalistas_antes_de_jugar():
    state = copa.formato_actual([])
    assert state["groupsConfirmed"]
    assert state["groups"]["A"]["teams"] == ["Noruega", "Cabo Verde", "Portugal", "Japón"]
    assert state["groups"]["B"]["teams"] == ["Francia", "Ecuador", "Egipto", "Colombia", "Marruecos"]
    assert state["groups"]["BRONCE"]["teams"] == ["Venezuela", "Alemania", "Uruguay", "España", "Argentina", "Brasil"]
    assert copa.base()["format"]["bonuses"] == {"Noruega": 2, "Francia": 2}
    assert not state["semifinalistsConfirmed"]
    assert state["qualified"] == {"ORO": [], "PLATA": []}


def test_semifinalistas_aparecen_solo_cuando_terminan_ambos_grupos(monkeypatch):
    configured = deepcopy(copa.base())
    configured["format"]["groupsConfirmed"] = True
    configured["format"]["groups"] = {
        "A": ["Noruega", "Cabo Verde", "Portugal", "Japón"],
        "B": ["Francia", "Ecuador", "Egipto", "Colombia", "Marruecos"],
        "BRONCE": ["Venezuela", "Alemania", "Uruguay", "España", "Argentina", "Brasil"],
    }
    configured["format"]["bonuses"] = {"Noruega": 2, "Francia": 2}
    monkeypatch.setattr(copa, "base", lambda: configured)
    rules = configured["format"]["groups"]
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
    assert {row[0]: row for row in after["format"]["groups"]["A"]["standings"]}["Noruega"][1:3] == [5, 1]
    assert not after["format"]["semifinalistsConfirmed"]
