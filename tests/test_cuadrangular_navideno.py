from pathlib import Path

import services as s


ROOT = Path(__file__).resolve().parents[1]


def test_cuadrangular_aparece_y_permite_inscribir(conn, user):
    conn.execute((ROOT / "sql/migrations/028_cuadrangular_navideno.sql").read_text(encoding="utf8"))
    torneo = conn.execute(
        "SELECT * FROM torneos WHERE nombre='Cuadrangular Navideño 2026'"
    ).fetchone()

    assert torneo["costo"] == 0
    assert torneo["cupos"] == 6
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


def test_admin_elimina_equipo_gratuito_de_prueba_y_libera_cupo(conn, user):
    conn.execute((ROOT / "sql/migrations/028_cuadrangular_navideno.sql").read_text(encoding="utf8"))
    torneo = conn.execute(
        "SELECT * FROM torneos WHERE nombre='Cuadrangular Navideño 2026'"
    ).fetchone()
    orden = s.inscribir_torneo(conn, user["id"], {
        "torneo_id": torneo["id"],
        "equipo": "Equipo Temporal",
        "acepta_reglamento": True,
    })
    equipo = conn.execute("SELECT * FROM equipos WHERE orden_id=%s", (orden["id"],)).fetchone()
    s.agregar_jugador(conn, user["id"], equipo["id"], {
        "nombre": "Jugador Temporal",
        "cedula": "1753114394",
        "numero_camiseta": 10,
    })
    admin_id = conn.execute(
        "SELECT id FROM usuarios WHERE email='revision@arena.test'"
    ).fetchone()["id"]

    result = s.eliminar_equipo_prueba(
        conn, admin_id, equipo["id"], {"confirmacion": "Equipo Temporal"}
    )

    assert "cupo volvió" in result["message"]
    assert conn.execute("SELECT estado FROM equipos WHERE id=%s", (equipo["id"],)).fetchone()["estado"] == "CANCELADO"
    assert conn.execute("SELECT estado FROM ordenes WHERE id=%s", (orden["id"],)).fetchone()["estado"] == "CANCELADA"
    assert conn.execute("SELECT count(*) AS n FROM jugadores WHERE equipo_id=%s", (equipo["id"],)).fetchone()["n"] == 0
    navidad = next(row for row in s.catalogo(conn)["torneos"] if row["nombre"] == "Cuadrangular Navideño 2026")
    assert navidad["disponibles"] == 6
    assert s.historial(conn, user["id"])["ordenes"] == []
    report = s.reportes(conn, admin_id, {})
    assert all(row["id"] != equipo["id"] for row in report["equipos_torneo"])


def test_no_elimina_equipo_con_cobro_real(conn, user, pay_data):
    orden = s.inscribir_torneo(conn, user["id"], {
        "torneo_id": 1,
        "equipo": "Equipo Pagado",
        "acepta_reglamento": True,
    })
    s.pagar(conn, user["id"], orden["id"], pay_data)
    detalle = s.detalle_orden(conn, user["id"], orden["id"])
    admin_id = conn.execute(
        "SELECT id FROM usuarios WHERE email='revision@arena.test'"
    ).fetchone()["id"]
    s.revisar_transferencia(
        conn, admin_id, orden["id"], {"revision": detalle["revision_pago"]}, aprobar=True
    )
    equipo = conn.execute("SELECT * FROM equipos WHERE orden_id=%s", (orden["id"],)).fetchone()

    import pytest
    with pytest.raises(s.ErrorValidacion, match="cobro relacionado"):
        s.eliminar_equipo_prueba(
            conn, admin_id, equipo["id"], {"confirmacion": "Equipo Pagado"}
        )

    assert conn.execute("SELECT estado FROM equipos WHERE id=%s", (equipo["id"],)).fetchone()["estado"] == "CONFIRMADO"
