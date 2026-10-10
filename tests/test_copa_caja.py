"""Escenarios de caja que evitan ingresos duplicados y pagos de vocalía inflados."""
from datetime import datetime
from decimal import Decimal

import pytest

import copa
import copa_caja as caja
from models import ErrorValidacion, Usuario
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
    assert all(row['registrado_por_nombre']=='Administrador de pruebas' for row in data['movimientos'])
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


def test_vocalia_dividida_cuenta_un_solo_cobro(conn):
    admin = _admin(conn)
    fixture = next(iter(copa.catalogo()[0].values()))
    team = fixture["home"]
    _save(conn, admin, "INGRESO", "VOCALIAS", "10", fixture_id=fixture["id"],
          equipo=team, monto_efectivo="4", monto_transferencia="6")
    result = caja.resumen(conn, admin)
    assert result["saldos"]["VOCALIAS"] == Decimal("10")
    assert result["vocalias_efectivo"] == Decimal("4")
    assert result["vocalias_transferencia"] == Decimal("6")
    fixture_week = caja.resumen(conn, admin, fixture["date"])
    assert next(x for x in fixture_week["vocalias"] if x["equipo"] == team)["pendiente"] == 0
    with pytest.raises(ErrorValidacion):
        _save(conn, admin, "INGRESO", "VOCALIAS", "10", fixture_id=fixture["id"],
              equipo=fixture["away"], monto_efectivo="4", monto_transferencia="5")


def test_vocalia_saldos_por_medio_y_clasificacion_de_gasto_anterior(conn):
    admin = _admin(conn)
    fixture = next(iter(copa.catalogo()[0].values()))
    _save(conn, admin, "INGRESO", "VOCALIAS", "10", fixture_id=fixture["id"],
          equipo=fixture["home"], monto_efectivo="4", monto_transferencia="6")
    _save(conn, admin, "INGRESO", "VOCALIAS", "10", fixture_id=fixture["id"],
          equipo=fixture["away"], monto_efectivo="8", monto_transferencia="2")
    _save(conn, admin, "GASTO", "VOCALIAS", "12", area="VOCALIAS",
          monto_efectivo="7", monto_transferencia="5")
    split = caja.resumen(conn, admin)["vocalias_saldos"]
    assert (split["efectivo"], split["transferencia"], split["total"]) == (5, 3, 8)
    with pytest.raises(ErrorValidacion):
        _save(conn, admin, "GASTO", "VOCALIAS", "4", area="VOCALIAS",
              monto_efectivo="0", monto_transferencia="4")
    old = conn.execute("""INSERT INTO copa_movimientos
        (fecha,tipo,cuenta,area,monto,concepto,registrado_por)
        VALUES(%s,'GASTO','VOCALIAS','VOCALIAS',3,'Gasto anterior',%s) RETURNING id""",
        (datetime.now(TZ).date(), admin)).fetchone()["id"]
    before = caja.resumen(conn, admin)["vocalias_saldos"]
    assert before["total"] == 5 and before["movimientos_sin_desglose"] == 1
    caja.desglosar_vocalia(conn, admin, old, {"monto_efectivo": "2", "monto_transferencia": "1"})
    after = caja.resumen(conn, admin)["vocalias_saldos"]
    assert (after["efectivo"], after["transferencia"], after["total"]) == (3, 2, 5)
    assert after["movimientos_sin_desglose"] == 0
    with pytest.raises(ErrorValidacion):
        caja.desglosar_vocalia(conn, admin, old, {"monto_efectivo": "2", "monto_transferencia": "1"})


def test_deuda_bar_no_es_ingreso_hasta_cobrar_y_no_se_cobra_dos_veces(conn):
    admin = _admin(conn)
    debt = caja.registrar_deuda_bar(conn, admin, {
        "fecha": datetime.now(TZ).date().isoformat(), "nombre": "Cliente del bar",
        "monto": "8.50", "concepto": "Comida y cervezas"})
    before = caja.resumen(conn, admin)
    assert before["saldos"]["BAR"] == 0
    assert before["bar_deuda_pendiente"] == Decimal("8.50")
    caja.cobrar_deuda_bar(conn, admin, debt["id"], {"fecha": datetime.now(TZ).date().isoformat()})
    after = caja.resumen(conn, admin)
    assert after["saldos"]["BAR"] == Decimal("8.50")
    assert after["bar_deuda_pendiente"] == 0
    with pytest.raises(ErrorValidacion):
        caja.cobrar_deuda_bar(conn, admin, debt["id"], {"fecha": datetime.now(TZ).date().isoformat()})


def test_limpieza_de_vocalias_incluye_anulados_y_conserva_las_otras_cajas(conn, monkeypatch):
    admin = _admin(conn)
    monkeypatch.setenv("ADMIN_OWNER_EMAIL", "revision@arena.test")
    monkeypatch.setenv("ADMIN_CREATION_SECRET", "clave-de-pruebas-de-mas-de-veinte-caracteres")
    owner = Usuario.desde_fila(conn.execute("SELECT * FROM usuarios WHERE id=%s", (admin,)).fetchone())
    owner.set_password("PruebaSegura!2026")
    conn.execute("UPDATE usuarios SET password_hash=%s WHERE id=%s", (owner.get_password_hash(), admin))
    fixture = next(iter(copa.catalogo()[0].values()))
    first = _save(conn, admin, "INGRESO", "VOCALIAS", "10", fixture_id=fixture["id"],
                  equipo=fixture["home"])
    _save(conn, admin, "INGRESO", "VOCALIAS", "10", fixture_id=fixture["id"],
          equipo=fixture["away"])
    caja.anular(conn, admin, first, {"motivo": "Recuento de prueba"})
    _save(conn, admin, "INGRESO", "BAR", "5")
    preview = caja.vista_previa_limpieza_vocalias(conn, admin)
    assert (preview["total"], preview["activos"], preview["anulados"]) == (2, 1, 1)
    with pytest.raises(HTTPError):
        caja.limpiar_historial_vocalias(conn, admin,
            {"confirmacion": "BORRAR VOCALIAS", "password": "incorrecta", "resumen": preview})
    result = caja.limpiar_historial_vocalias(conn, admin,
        {"confirmacion": "BORRAR VOCALIAS", "password": "PruebaSegura!2026", "resumen": preview})
    assert result["eliminados"] == 2
    assert caja.vista_previa_limpieza_vocalias(conn, admin)["total"] == 0
    assert caja.resumen(conn, admin)["saldos"]["BAR"] == Decimal("5")
