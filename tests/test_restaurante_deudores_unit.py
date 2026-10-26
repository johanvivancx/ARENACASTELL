from datetime import date
from decimal import Decimal

import pytest

import restaurante_deudores as restaurante
from models import ErrorValidacion


class Resultado:
    def __init__(self, filas=None, fila=None):
        self.filas = filas or []
        self.fila = fila

    def fetchall(self):
        return self.filas

    def fetchone(self):
        return self.fila


class ConexionFalsa:
    def __init__(self, deudas, abonos):
        self.deudas = deudas
        self.abonos = abonos
        self.inserciones = []

    def execute(self, consulta, parametros=None):
        compacta = " ".join(consulta.split())
        if "FROM restaurante_deudas d JOIN usuarios" in compacta:
            return Resultado(filas=self.deudas)
        if "FROM restaurante_abonos a JOIN usuarios" in compacta:
            return Resultado(filas=self.abonos)
        if compacta.startswith("SELECT pg_advisory_xact_lock"):
            return Resultado()
        if compacta.startswith("SELECT DISTINCT nombre FROM restaurante_deudas"):
            return Resultado(filas=[{"nombre": fila["nombre"]} for fila in self.deudas])
        if compacta.startswith("INSERT INTO restaurante_deudas"):
            self.inserciones.append(("deuda", parametros))
            return Resultado(fila={"id": 10})
        if compacta.startswith("INSERT INTO restaurante_abonos"):
            self.inserciones.append(("abono", parametros))
            return Resultado(fila={"id": 20})
        raise AssertionError(f"Consulta inesperada: {compacta}")


def deuda(identifier, monto, nombre="Johan Vivanco"):
    return {"id": identifier, "fecha": date(2026, 10, 25), "nombre": nombre,
            "monto": Decimal(monto), "concepto": "Almuerzo", "creado_en": None,
            "registrado_por_nombre": "Admin"}


def abono(identifier, monto, metodo, nombre="Johan Vivanco"):
    return {"id": identifier, "fecha": date(2026, 10, 26), "nombre": nombre,
            "monto": Decimal(monto), "metodo": metodo, "creado_en": None,
            "registrado_por_nombre": "Admin"}


def test_calcula_pendiente_y_separa_abonos_por_forma_de_pago():
    conn = ConexionFalsa([deuda(1, "8.00"), deuda(2, "5.00")],
                         [abono(1, "3.00", "EFECTIVO"), abono(2, "2.00", "TRANSFERENCIA")])
    estado = restaurante._estado(conn)
    assert estado["total_deudas"] == Decimal("8.00")
    assert estado["cobrado_efectivo"] == Decimal("3.00")
    assert estado["cobrado_transferencia"] == Decimal("2.00")
    assert estado["deudores"] == [{"nombre": "Johan Vivanco", "pendiente": Decimal("8.00"), "deudas": 2}]
    filas = {fila["id"]: fila for fila in estado["deudas"]}
    assert (filas[1]["abonado"], filas[1]["pendiente"]) == (Decimal("5.00"), Decimal("3.00"))
    assert filas[2]["pendiente"] == Decimal("5.00")


def test_registra_abono_con_metodo_sin_tocar_la_deuda(monkeypatch):
    monkeypatch.setattr(restaurante, "exigir_administrador", lambda conn, uid: None)
    conn = ConexionFalsa([deuda(1, "11.00")], [])
    resultado = restaurante.registrar_abono(conn, 7, {
        "fecha": "2026-10-26", "nombre": "Johan Vivanco", "monto": "4.00", "metodo": "TRANSFERENCIA"})
    assert resultado["message"] == "Abono registrado. A Johan Vivanco le quedan $7.00."
    assert conn.inserciones == [("abono", (date(2026, 10, 26), "Johan Vivanco", Decimal("4.00"), "TRANSFERENCIA", 7))]


def test_rechaza_abono_mayor_y_forma_de_pago_invalida(monkeypatch):
    monkeypatch.setattr(restaurante, "exigir_administrador", lambda conn, uid: None)
    conn = ConexionFalsa([deuda(1, "11.00")], [])
    with pytest.raises(ErrorValidacion, match="superar"):
        restaurante.registrar_abono(conn, 7, {
            "fecha": "2026-10-26", "nombre": "Johan Vivanco", "monto": "12", "metodo": "EFECTIVO"})
    with pytest.raises(ErrorValidacion, match="efectivo o transferencia"):
        restaurante.registrar_abono(conn, 7, {
            "fecha": "2026-10-26", "nombre": "Johan Vivanco", "monto": "4", "metodo": "TARJETA"})
    assert conn.inserciones == []
