from pathlib import Path

import services as s


ROOT = Path(__file__).resolve().parents[1]


def test_cuadrangular_aparece_y_permite_inscribir(conn, user):
    conn.execute((ROOT / "sql/migrations/028_cuadrangular_navideno.sql").read_text(encoding="utf8"))
    torneo = conn.execute(
        "SELECT * FROM torneos WHERE nombre='Cuadrangular Navideño 2026'"
    ).fetchone()

    assert torneo["costo"] == 0
    assert torneo["cupos"] == 4
    assert torneo["abierto"] is True
    assert "12 y 19 de diciembre" in torneo["descripcion"]

    orden = s.inscribir_torneo(conn, user["id"], {
        "torneo_id": torneo["id"],
        "equipo": "Equipo Navideño",
        "acepta_reglamento": True,
    })
    creada = conn.execute("SELECT * FROM ordenes WHERE id=%s", (orden["id"],)).fetchone()
    equipo = conn.execute("SELECT * FROM equipos WHERE orden_id=%s", (orden["id"],)).fetchone()
    pago = conn.execute("SELECT * FROM pagos WHERE orden_id=%s", (orden["id"],)).fetchone()

    assert orden["gratuita"] is True
    assert creada["monto"] == 0
    assert creada["estado"] == "PAGADA"
    assert creada["descripcion"] == "Cuadrangular Navideño 2026 · Equipo Navideño"
    assert equipo["estado"] == "CONFIRMADO"
    assert pago is None
