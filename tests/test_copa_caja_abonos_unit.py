from datetime import date
from decimal import Decimal

import pytest

import copa_caja as caja
from models import ErrorValidacion


class Result:
    def __init__(self, rows=None, row=None):
        self.rows = rows or []
        self.row = row

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, debts, payments):
        self.debts = debts
        self.payments = payments
        self.inserts = []

    def execute(self, query, params=None):
        compact = " ".join(query.split())
        if "FROM copa_bar_deudas d JOIN usuarios" in compact:
            return Result(rows=self.debts)
        if "FROM copa_bar_abonos a JOIN usuarios" in compact:
            return Result(rows=self.payments)
        if compact.startswith("SELECT pg_advisory_xact_lock"):
            return Result()
        if compact.startswith("INSERT INTO copa_movimientos"):
            self.inserts.append(("movimiento", params))
            return Result(row={"id": 80})
        if compact.startswith("INSERT INTO copa_bar_abonos"):
            self.inserts.append(("abono", params))
            return Result(row={"id": 40})
        raise AssertionError(f"Consulta inesperada: {compact}")


def debt(identifier, amount, name="Johan Vivanco"):
    return {"id": identifier, "fecha": date(2026, 10, 25), "nombre": name,
            "monto": Decimal(amount), "concepto": "Consumo", "creado_en": None,
            "cobrada_en": None, "registrado_por_nombre": "Admin", "cobrada_por_nombre": None}


def payment(identifier, amount, name="Johan Vivanco"):
    return {"id": identifier, "fecha": date(2026, 10, 25), "nombre": name,
            "monto": Decimal(amount), "creado_en": None, "registrado_por_nombre": "Admin"}


def test_distribuye_abonos_sobre_fiados_antiguos_y_calcula_total():
    conn = FakeConnection([debt(2, "5.00"), debt(1, "6.00")], [payment(1, "4.00")])
    state = caja._estado_deudas_bar(conn)
    rows = {row["id"]: row for row in state["deudas"]}
    assert state["pendiente"] == Decimal("7.00")
    assert state["deudores"] == [{"nombre": "Johan Vivanco", "pendiente": Decimal("7.00"), "deudas": 2}]
    assert (rows[1]["abonado"], rows[1]["pendiente"]) == (Decimal("4.00"), Decimal("2.00"))
    assert (rows[2]["abonado"], rows[2]["pendiente"]) == (Decimal("0.00"), Decimal("5.00"))


def test_registrar_abono_crea_ingreso_sin_cambiar_fiados(monkeypatch):
    monkeypatch.setattr(caja, "exigir_administrador", lambda conn, uid: None)
    conn = FakeConnection([debt(1, "11.00")], [])
    result = caja.registrar_abono_bar(conn, 7, {
        "fecha": "2026-10-25", "nombre": "  JOHAN   VIVANCO ", "monto": "4.00"})
    assert result == {"id": 40, "message": "Abono registrado. A Johan Vivanco le quedan $7.00."}
    assert [kind for kind, _ in conn.inserts] == ["movimiento", "abono"]
    assert conn.inserts[0][1][1] == Decimal("4.00")
    assert conn.inserts[1][1][1:3] == ("Johan Vivanco", Decimal("4.00"))


def test_rechaza_abono_mayor_al_total_pendiente(monkeypatch):
    monkeypatch.setattr(caja, "exigir_administrador", lambda conn, uid: None)
    conn = FakeConnection([debt(1, "11.00")], [])
    with pytest.raises(ErrorValidacion, match="superar lo pendiente"):
        caja.registrar_abono_bar(conn, 7, {
            "fecha": "2026-10-25", "nombre": "Johan Vivanco", "monto": "11.01"})
    assert conn.inserts == []
