"""Deudas y abonos del restaurante Asadero BJ, separados de Copa Castell."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re

from models import ErrorValidacion, texto
from services import TZ, exigir_administrador, fecha

CERO = Decimal("0.00")
METODOS = ("EFECTIVO", "TRANSFERENCIA")


def _clave(nombre):
    return " ".join(nombre.split()).casefold()


def _monto(valor):
    bruto = str(valor or "")
    if not re.fullmatch(r"\d{1,7}(?:\.\d{1,2})?", bruto):
        raise ErrorValidacion("Monto: escribe dólares con hasta dos decimales.")
    try:
        monto = Decimal(bruto)
    except InvalidOperation:
        raise ErrorValidacion("Monto inválido.") from None
    if monto <= 0:
        raise ErrorValidacion("El monto debe ser mayor que cero.")
    return monto


def _fecha(valor):
    dia = fecha(valor)
    if not date(2026, 1, 1) <= dia <= datetime.now(TZ).date():
        raise ErrorValidacion("Usa una fecha de 2026 hasta hoy.")
    return dia


def _estado(conn):
    deudas_fuente = conn.execute("""SELECT d.id,d.fecha,d.nombre,d.monto,d.concepto,d.creado_en,
        autor.nombre AS registrado_por_nombre
        FROM restaurante_deudas d JOIN usuarios autor ON autor.id=d.registrado_por
        ORDER BY d.fecha DESC,d.id DESC""").fetchall()
    abonos = conn.execute("""SELECT a.id,a.fecha,a.nombre,a.monto,a.metodo,a.creado_en,
        autor.nombre AS registrado_por_nombre
        FROM restaurante_abonos a JOIN usuarios autor ON autor.id=a.registrado_por
        ORDER BY a.fecha DESC,a.id DESC""").fetchall()
    abonado_por_persona = {}
    for abono in abonos:
        clave = _clave(abono["nombre"])
        abonado_por_persona[clave] = abonado_por_persona.get(clave, CERO) + abono["monto"]
    asignado = {deuda["id"]: CERO for deuda in deudas_fuente}
    grupos = {}
    for deuda in deudas_fuente:
        grupos.setdefault(_clave(deuda["nombre"]), []).append(deuda)
    for clave, deudas_persona in grupos.items():
        restante = abonado_por_persona.get(clave, CERO)
        for deuda in sorted(deudas_persona, key=lambda fila: (fila["fecha"], fila["id"])):
            aplicado = min(deuda["monto"], restante)
            asignado[deuda["id"]] = aplicado
            restante -= aplicado
    deudas = []
    deudores = {}
    for fuente in deudas_fuente:
        deuda = dict(fuente)
        deuda["abonado"] = asignado[deuda["id"]]
        deuda["pendiente"] = max(CERO, deuda["monto"] - deuda["abonado"])
        deudas.append(deuda)
        if deuda["pendiente"] <= 0:
            continue
        clave = _clave(deuda["nombre"])
        persona = deudores.setdefault(clave, {
            "nombre": deuda["nombre"], "pendiente": CERO, "deudas": 0})
        persona["pendiente"] += deuda["pendiente"]
        persona["deudas"] += 1
    return {
        "deudas": deudas,
        "deudores": sorted(deudores.values(), key=lambda fila: fila["nombre"].casefold()),
        "abonos": abonos,
        "total_deudas": sum((fila["pendiente"] for fila in deudas), CERO),
        "cobrado_efectivo": sum((a["monto"] for a in abonos if a["metodo"] == "EFECTIVO"), CERO),
        "cobrado_transferencia": sum((a["monto"] for a in abonos if a["metodo"] == "TRANSFERENCIA"), CERO),
    }


def resumen(conn, admin_uid):
    exigir_administrador(conn, admin_uid)
    return _estado(conn)


def registrar_deuda(conn, admin_uid, datos):
    exigir_administrador(conn, admin_uid)
    conn.execute("SELECT pg_advisory_xact_lock(20491008)")
    dia = _fecha(datos.get("fecha"))
    nombre = " ".join(texto(datos.get("nombre"), "Nombre", 2, 120).split())
    for existente in conn.execute("SELECT DISTINCT nombre FROM restaurante_deudas").fetchall():
        if _clave(existente["nombre"]) == _clave(nombre):
            nombre = existente["nombre"]
            break
    monto = _monto(datos.get("monto"))
    concepto = texto(datos.get("concepto"), "Detalle de la deuda", 3, 180)
    fila = conn.execute("""INSERT INTO restaurante_deudas
        (fecha,nombre,monto,concepto,registrado_por) VALUES(%s,%s,%s,%s,%s)
        RETURNING id""", (dia,nombre,monto,concepto,admin_uid)).fetchone()
    return {"id": fila["id"], "message": "Deuda del restaurante registrada. Todavía no cuenta como dinero recibido."}


def registrar_abono(conn, admin_uid, datos):
    exigir_administrador(conn, admin_uid)
    conn.execute("SELECT pg_advisory_xact_lock(20491008)")
    dia = _fecha(datos.get("fecha"))
    solicitado = " ".join(texto(datos.get("nombre"), "Nombre", 2, 120).split())
    persona = next((fila for fila in _estado(conn)["deudores"]
                    if _clave(fila["nombre"]) == _clave(solicitado)), None)
    if not persona:
        raise ErrorValidacion("Esa persona no tiene una deuda pendiente en el restaurante.")
    monto = _monto(datos.get("monto"))
    if monto > persona["pendiente"]:
        raise ErrorValidacion(f"El abono no puede superar lo pendiente: {persona['pendiente']}.")
    metodo = str(datos.get("metodo") or "").upper()
    if metodo not in METODOS:
        raise ErrorValidacion("Selecciona si el abono fue en efectivo o transferencia.")
    fila = conn.execute("""INSERT INTO restaurante_abonos
        (fecha,nombre,monto,metodo,registrado_por) VALUES(%s,%s,%s,%s,%s)
        RETURNING id""", (dia,persona["nombre"],monto,metodo,admin_uid)).fetchone()
    restante = persona["pendiente"] - monto
    mensaje = (f"Abono registrado. A {persona['nombre']} le quedan ${restante:.2f}."
               if restante else f"Abono registrado. {persona['nombre']} ya no tiene deuda pendiente.")
    return {"id": fila["id"], "message": mensaje}
