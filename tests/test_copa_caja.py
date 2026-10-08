"""Escenarios de caja que evitan ingresos duplicados y pagos de vocalía inflados."""
from datetime import datetime
from decimal import Decimal

import pytest

import copa
import copa_caja as caja
from models import ErrorValidacion
from services import HTTPError, TZ


def _admin(conn):
    return conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()["id"]


def _save(conn, admin, kind, account, amount, **extra):
    return caja.registrar(conn, admin, {"tipo": kind, "cuenta": account,
        "monto": amount, "fecha": datetime.now(TZ).date().isoformat(),
        "concepto": extra.pop("concepto", "Movimiento de prueba"), **extra})["id"]


def test_traspaso_no_inventa_ingreso_y_gasto_disponible_no_descuenta_dos_veces(conn):
    admin = _admin(conn)
    _save(conn, admin, "APERTURA", "DISPONIBLE", "100")
    _save(conn, admin, "TRASPASO", "DISPONIBLE", "20", destino="BAR")
    _save(conn, admin, "INGRESO", "BAR", "35")
    _save(conn, admin, "GASTO", "DISPONIBLE", "12", area="BAR", concepto="Compra de cerveza")
    data = caja.resumen(conn, admin)
    assert data["saldos"] == {"DISPONIBLE": Decimal("68"), "BAR": Decimal("55"),
        "ENTRADAS": Decimal("0"), "VOCALIAS": Decimal("0")}
    assert data["saldo_total"] == Decimal("123")
    assert data["ingresos"]["BAR"] == Decimal("35")
    assert data["gastos"]["BAR"] == Decimal("12")
    assert data["caja_entregada"]["BAR"] == Decimal("20")


def test_vocalia_admite_parciales_hasta_diez_y_no_toca_inscripciones(conn):
    admin = _admin(conn)
    fixture = next(iter(copa.catalogo()[0].values()))
    team = fixture["home"]
    _save(conn, admin, "INGRESO", "VOCALIAS", "4", fixture_id=fixture["id"], equipo=team)
    _save(conn, admin, "INGRESO", "VOCALIAS", "6", fixture_id=fixture["id"], equipo=team)
    with pytest.raises(ErrorValidacion):
        _save(conn, admin, "INGRESO", "VOCALIAS", "1", fixture_id=fixture["id"], equipo=team)
    assert caja.resumen(conn, admin)["saldos"]["VOCALIAS"] == Decimal("10")
    assert conn.execute("SELECT count(*) AS n FROM pagos").fetchone()["n"] == 0


def test_no_permite_gastar_mas_de_caja_ni_anular_origen_que_dejaria_negativo(conn):
    admin = _admin(conn)
    opening = _save(conn, admin, "APERTURA", "DISPONIBLE", "20")
    _save(conn, admin, "TRASPASO", "DISPONIBLE", "15", destino="ENTRADAS")
    with pytest.raises(ErrorValidacion):
        _save(conn, admin, "GASTO", "DISPONIBLE", "6", area="GENERAL")
    with pytest.raises(ErrorValidacion):
        caja.anular(conn, admin, opening, {"motivo": "Se anotó mal"})


def test_solo_administrador_puede_ver_o_guardar_caja(conn, user):
    uid = user["id"]
    with pytest.raises(HTTPError) as read_error:
        caja.resumen(conn, uid)
    with pytest.raises(HTTPError) as write_error:
        _save(conn, uid, "APERTURA", "DISPONIBLE", "10")
    assert read_error.value.status == write_error.value.status == 403
