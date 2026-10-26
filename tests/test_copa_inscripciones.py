"""Inscripción y carnets de la Copa: saldos, medios de pago y aislamiento."""
from decimal import Decimal

import pytest

import copa_inscripciones as ci
import copa_caja
from models import ErrorValidacion
from services import HTTPError


def _admin(conn):
    return conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()["id"]


def _team(state, name):
    return next(row for row in state["equipos"] if row["equipo"] == name)


def test_saldos_iniciales_de_la_hoja_y_carnets_por_jugador(conn):
    state = ci.resumen(conn, _admin(conn))
    assert len(state["equipos"]) == 15
    assert state["inscripcion_unitaria"] == Decimal("25")
    assert state["carnet_unitario"] == Decimal("0.50")
    assert _team(state, "Uruguay")["inscripcion"]["pendiente"] == Decimal("7.50")
    assert _team(state, "Venezuela")["inscripcion"]["pendiente"] == 0
    assert _team(state, "Venezuela")["carnets"]["pendiente"] == Decimal("7.50")
    assert _team(state, "Marruecos")["inscripcion"]["pendiente"] == Decimal("10")
    assert _team(state, "Marruecos")["carnets"]["pendiente"] == Decimal("4")
    assert _team(state, "Colombia")["inscripcion"]["pendiente"] == 0
    assert _team(state, "Colombia")["inscripcion"]["acuerdo"] is True
    assert _team(state, "Colombia")["carnets"]["pendiente"] == 0
    assert _team(state, "Colombia")["carnets"]["abono_inicial"] == Decimal("3")
    assert _team(state, "Colombia")["carnets"]["cobrado_nuevo"] == Decimal("6.50")
    assert _team(state, "Colombia")["carnets_cantidad"] == 14
    assert _team(state, "Egipto")["carnets_cantidad"] == 17
    assert _team(state, "Egipto")["carnets"]["abono_inicial"] == Decimal("7.50")
    assert _team(state, "Egipto")["carnets"]["pendiente"] == Decimal("1")
    assert _team(state, "Egipto")["inscripcion"]["pendiente"] == 0
    assert _team(state, "Francia")["carnets"]["pendiente"] == Decimal("7")
    assert state["cobrado_efectivo"] == Decimal("6.50")
    assert state["cobrado_transferencia"] == 0


def test_cobro_parcial_mixto_no_se_duplica_en_vocalias(conn, user):
    admin = _admin(conn)
    payload = {"equipo": "Uruguay", "concepto": "INSCRIPCION", "fecha": "2026-10-10",
               "efectivo": "4", "transferencia": "3.50"}
    with pytest.raises(HTTPError) as denied:
        ci.registrar_pago(conn, user["id"], payload)
    assert denied.value.status == 403
    before = copa_caja.resumen(conn, admin)
    saved = ci.registrar_pago(conn, admin, payload)
    after = ci.resumen(conn, admin)
    assert _team(after, "Uruguay")["inscripcion"]["pendiente"] == 0
    assert after["cobrado_efectivo"] == Decimal("10.50")
    assert after["cobrado_transferencia"] == Decimal("3.50")
    assert copa_caja.resumen(conn, admin)["saldo_total"] == before["saldo_total"]
    with pytest.raises(ErrorValidacion, match="supera"):
        ci.registrar_pago(conn, admin, payload)
    ci.anular_pago(conn, admin, saved["id"], {"motivo": "Cobro duplicado"})
    restored = ci.resumen(conn, admin)
    assert _team(restored, "Uruguay")["inscripcion"]["pendiente"] == Decimal("7.50")
    assert restored["cobrado_efectivo"] == Decimal("6.50")
    assert restored["cobrado_transferencia"] == 0
    assert next(row for row in restored["pagos"] if row["id"] == saved["id"])["anulado_en"] is not None


def test_cantidad_carnets_ajustable_sin_bajar_de_lo_cobrado(conn):
    admin = _admin(conn)
    ci.ajustar_carnets(conn, admin, {"equipo": "Francia", "cantidad": 16})
    assert _team(ci.resumen(conn, admin), "Francia")["carnets"]["pendiente"] == Decimal("8")
    with pytest.raises(ErrorValidacion):
        ci.ajustar_carnets(conn, admin, {"equipo": "Marruecos", "cantidad": 5})


def test_carnets_nuevos_de_equipo_pagado_quedan_pendientes(conn):
    admin = _admin(conn)
    ci.ajustar_carnets(conn, admin, {"equipo": "Japón", "cantidad": 19})
    team = _team(ci.resumen(conn, admin), "Japón")
    assert team["carnets"]["abono_inicial"] == Decimal("8.50")
    assert team["carnets"]["pendiente"] == Decimal("1")
    assert team["inscripcion"]["pendiente"] == 0


def test_corrige_egipto_publicado_sin_sobrescribir_ajustes(conn):
    from db import ROOT
    correction = (ROOT / 'sql/migrations/022_carnets_egipto.sql').read_text(encoding='utf8')
    conn.execute("""UPDATE copa_inscripciones_equipos SET carnets_cantidad=15,
        carnets_inicial=0,carnets_completos_inicial=true WHERE equipo='Egipto'""")
    conn.execute(correction)
    conn.execute(correction)
    team = _team(ci.resumen(conn, _admin(conn)), 'Egipto')
    assert team['carnets_cantidad'] == 17
    assert team['carnets']['pendiente'] == Decimal('1')
    conn.execute("UPDATE copa_inscripciones_equipos SET carnets_cantidad=18 WHERE equipo='Egipto'")
    conn.execute(correction)
    assert _team(ci.resumen(conn, _admin(conn)), 'Egipto')['carnets_cantidad'] == 18


def test_migracion_repetible_no_reinicia_pagos(conn):
    admin = _admin(conn)
    ci.registrar_pago(conn, admin, {"equipo": "Francia", "concepto": "CARNETS",
        "fecha": "2026-10-10", "efectivo": "1", "transferencia": "0"})
    conn.commit()
    from db import preparar_movimientos_copa
    preparar_movimientos_copa()
    assert _team(ci.resumen(conn, admin), "Francia")["carnets"]["pendiente"] == Decimal("6")


def test_corrige_solo_colombia_publicada_sin_sobrescribir_ajustes(conn):
    from db import ROOT
    correction = (ROOT / 'sql/migrations/021_corregir_carnets_colombia.sql').read_text(encoding='utf8')
    conn.execute("DELETE FROM copa_inscripciones_pagos WHERE referencia='ACUERDO-COLOMBIA-CARNETS-2026-10-23'")
    conn.execute("""UPDATE copa_inscripciones_equipos SET
        inscripcion_completa_inicial=false,inscripcion_acuerdo=false WHERE equipo='Colombia'""")
    conn.execute("UPDATE copa_inscripciones_equipos SET carnets_cantidad=20 WHERE equipo='Colombia'")
    before = _team(ci.resumen(conn, _admin(conn)), 'Colombia')
    assert before['carnets']['pendiente'] == Decimal('7')
    conn.execute(correction)
    conn.execute(correction)
    after = _team(ci.resumen(conn, _admin(conn)), 'Colombia')
    assert after['carnets_cantidad'] == 14
    assert after['carnets']['pendiente'] == Decimal('4')
    assert after['inscripcion']['pendiente'] == Decimal('25')
    conn.execute("UPDATE copa_inscripciones_equipos SET carnets_cantidad=16 WHERE equipo='Colombia'")
    conn.execute(correction)
    assert _team(ci.resumen(conn, _admin(conn)), 'Colombia')['carnets_cantidad'] == 16


def test_acuerdo_colombia_es_repetible_y_no_inventa_ingreso_de_inscripcion(conn):
    from db import ROOT
    agreement = (ROOT / 'sql/migrations/026_acuerdo_colombia.sql').read_text(encoding='utf8')
    conn.execute(agreement)
    conn.execute(agreement)
    state = ci.resumen(conn, _admin(conn))
    team = _team(state, 'Colombia')
    assert team['inscripcion']['acuerdo'] is True
    assert team['inscripcion']['pendiente'] == 0
    assert team['inscripcion']['cobrado_nuevo'] == 0
    assert team['carnets']['pendiente'] == 0
    assert team['carnets']['cobrado_nuevo'] == Decimal('6.50')
    assert conn.execute("""SELECT count(*) AS total FROM copa_inscripciones_pagos
        WHERE referencia='ACUERDO-COLOMBIA-CARNETS-2026-10-23'""").fetchone()['total'] == 1
