"""Fotos de MVP aisladas de los resultados y validadas por plantilla."""

import base64
from io import BytesIO

from PIL import Image
import pytest

import copa
import services as s


def _foto():
    output = BytesIO()
    Image.new("RGB", (36, 48), "red").save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def test_fotos_fecha_siete_y_publicacion_privada(conn, user):
    admin = conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()["id"]
    initial = copa.estado_publico(conn)
    assert len(initial["mvps"]) == 6
    fixture = next(row for row in copa.panel_admin(conn, admin)["fixtures"] if row["home"] == "Argentina")
    player = next(row for row in copa.panel_admin(conn, admin)["players"]["Japón"] if row["number"] == "13")
    request = {"fixture_id": fixture["id"], "country": "Japón", "player_id": player["id"], "image": _foto()}
    with pytest.raises(s.HTTPError) as unauthorized:
        copa.guardar_jugador_del_partido(conn, user["id"], request)
    assert unauthorized.value.status == 403
    with pytest.raises(s.ErrorValidacion, match="resultado final"):
        copa.guardar_jugador_del_partido(conn, admin, request)
    copa.guardar_resultado(conn, admin, {"fixture_id": fixture["id"], "homeGoals": 1,
                                     "awayGoals": 2, "revision": 0, "goals": []})
    before = copa.estado_publico(conn)
    with pytest.raises(s.ErrorValidacion, match="plantilla"):
        copa.guardar_jugador_del_partido(conn, admin, {**request, "player_id": "s:0"})
    with pytest.raises(s.ErrorValidacion, match="foto"):
        copa.guardar_jugador_del_partido(conn, admin, {**request, "image": base64.b64encode(b"fake").decode()})
    result = copa.guardar_jugador_del_partido(conn, admin, request)
    assert "Sebastián Taipe" in result["message"]
    after = copa.estado_publico(conn)
    award = next(row for row in after["mvps"] if row["fixture_id"] == fixture["id"])
    assert award["player_id"] == player["id"] and award["photo_url"].startswith("/api/copa-mvp/photos/")
    photo_id = int(award["photo_url"].split("/")[-1].split("?")[0])
    assert copa.foto_jugador_del_partido(conn, photo_id).startswith(b"\xff\xd8")
    assert after["standings"] == before["standings"]
    assert after["scorers"] == before["scorers"]
    copa.guardar_jugador_del_partido(conn, admin, request)
    assert conn.execute("SELECT count(*) AS n FROM copa_mvp").fetchone()["n"] == 1
