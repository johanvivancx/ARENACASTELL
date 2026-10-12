"""Inscripciones y carnets de Copa Castell, separados de las cajas operativas."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re

from copa import base
from models import ErrorValidacion
from services import HTTPError, TZ, exigir_administrador, fecha, texto

INSCRIPCION = Decimal("25.00")
CARNET = Decimal("0.50")
CERO = Decimal("0.00")
CONCEPTOS = ("INSCRIPCION", "CARNETS")


def _monto(value):
    raw = str(value or "")
    if not re.fullmatch(r"\d{1,6}(?:\.\d{1,2})?", raw):
        raise ErrorValidacion("Escribe un monto con hasta dos decimales.")
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        raise ErrorValidacion("Monto inválido.") from None
    if amount < 0:
        raise ErrorValidacion("El monto no puede ser negativo.")
    return amount


def _fecha(value):
    day = fecha(value)
    if not date(2026, 1, 1) <= day <= datetime.now(TZ).date():
        raise ErrorValidacion("Indica una fecha de 2026 hasta hoy.")
    return day


def _datos(conn):
    teams = conn.execute("SELECT * FROM copa_inscripciones_equipos ORDER BY equipo").fetchall()
    payments = conn.execute("""SELECT p.id,p.equipo,p.concepto,p.fecha,p.efectivo,p.transferencia,p.monto,
        p.creado_en,p.anulado_en,p.motivo_anulacion,u.nombre AS registrado_por_nombre,
        anulador.nombre AS anulado_por_nombre
        FROM copa_inscripciones_pagos p JOIN usuarios u ON u.id=p.registrado_por
        LEFT JOIN usuarios anulador ON anulador.id=p.anulado_por
        ORDER BY p.fecha DESC,p.id DESC""").fetchall()
    return teams, payments


def _totales(team, payments):
    team_payments = [p for p in payments if p["equipo"] == team["equipo"] and p["anulado_en"] is None]
    values = {}
    for concept in CONCEPTOS:
        expected = INSCRIPCION if concept == "INSCRIPCION" else team["carnets_cantidad"] * CARNET
        initial = team["inscripcion_inicial"] if concept == "INSCRIPCION" else team["carnets_inicial"]
        complete = team["inscripcion_completa_inicial"] if concept == "INSCRIPCION" else team["carnets_completos_inicial"]
        current = sum((p["monto"] for p in team_payments if p["concepto"] == concept), CERO)
        due = max(CERO, expected - (expected if complete else initial) - current)
        values[concept.lower()] = {"esperado": expected, "abono_inicial": initial,
                                   "completo_inicial": complete, "cobrado_nuevo": current,
                                   "pendiente": due}
    return values


def resumen(conn, admin_uid):
    exigir_administrador(conn, admin_uid)
    teams, payments = _datos(conn)
    clubs = {team["country"]: team["club"] for team in base()["teams"]}
    rows = [{"equipo": team["equipo"], "club": clubs.get(team["equipo"], ""),
             "carnets_cantidad": team["carnets_cantidad"], "nota": team["nota"],
             **_totales(team, payments)} for team in teams]
    active = [p for p in payments if p["anulado_en"] is None]
    return {"equipos": rows, "pagos": payments,
            "inscripcion_unitaria": INSCRIPCION, "carnet_unitario": CARNET,
            "pendiente_inscripciones": sum((r["inscripcion"]["pendiente"] for r in rows), CERO),
            "pendiente_carnets": sum((r["carnets"]["pendiente"] for r in rows), CERO),
            "cobrado_efectivo": sum((p["efectivo"] for p in active), CERO),
            "cobrado_transferencia": sum((p["transferencia"] for p in active), CERO)}


def registrar_pago(conn, admin_uid, data):
    exigir_administrador(conn, admin_uid)
    conn.execute("SELECT pg_advisory_xact_lock(20491009)")
    name = str(data.get("equipo", ""))
    concept = str(data.get("concepto", ""))
    if concept not in CONCEPTOS:
        raise ErrorValidacion("Selecciona inscripción o carnets.")
    team = conn.execute("SELECT * FROM copa_inscripciones_equipos WHERE equipo=%s", (name,)).fetchone()
    if not team:
        raise ErrorValidacion("Selecciona un equipo válido.")
    cash, transfer = _monto(data.get("efectivo", "0")), _monto(data.get("transferencia", "0"))
    amount = cash + transfer
    if amount <= 0:
        raise ErrorValidacion("Registra un cobro mayor que cero.")
    day = _fecha(data.get("fecha"))
    payments = conn.execute("""SELECT equipo,concepto,monto,anulado_en FROM copa_inscripciones_pagos
        WHERE equipo=%s""", (name,)).fetchall()
    due = _totales(team, payments)[concept.lower()]["pendiente"]
    if amount > due:
        raise ErrorValidacion(f"El cobro supera los ${due} pendientes de {concept.lower()}.")
    created = conn.execute("""INSERT INTO copa_inscripciones_pagos
        (equipo,concepto,fecha,efectivo,transferencia,registrado_por)
        VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""",
        (name, concept, day, cash, transfer, admin_uid)).fetchone()
    return {"id": created["id"], "message": f"Cobro de {concept.lower()} registrado para {name}."}


def ajustar_carnets(conn, admin_uid, data):
    exigir_administrador(conn, admin_uid)
    conn.execute("SELECT pg_advisory_xact_lock(20491009)")
    name = str(data.get("equipo", ""))
    raw = str(data.get("cantidad", ""))
    if not raw.isdecimal() or not 0 <= int(raw) <= 100:
        raise ErrorValidacion("La cantidad de jugadores debe estar entre 0 y 100.")
    team = conn.execute("SELECT * FROM copa_inscripciones_equipos WHERE equipo=%s FOR UPDATE", (name,)).fetchone()
    if not team:
        raise ErrorValidacion("Selecciona un equipo válido.")
    qty = int(raw)
    paid = conn.execute("""SELECT COALESCE(sum(monto),0) AS total FROM copa_inscripciones_pagos
        WHERE equipo=%s AND concepto='CARNETS' AND anulado_en IS NULL""", (name,)).fetchone()["total"]
    if qty * CARNET < paid + team["carnets_inicial"]:
        raise ErrorValidacion("La nueva cantidad dejaría cobros de carnets por encima de lo esperado.")
    conn.execute("UPDATE copa_inscripciones_equipos SET carnets_cantidad=%s WHERE equipo=%s", (qty, name))
    return {"message": f"Carnets de {name}: {qty} jugadores × $0,50."}


def anular_pago(conn, admin_uid, payment_id, data):
    exigir_administrador(conn, admin_uid)
    conn.execute("SELECT pg_advisory_xact_lock(20491009)")
    reason = texto(data.get("motivo"), "Motivo de anulación", 3, 250)
    row = conn.execute("SELECT id,anulado_en FROM copa_inscripciones_pagos WHERE id=%s FOR UPDATE", (payment_id,)).fetchone()
    if not row:
        raise HTTPError(404, "Cobro no encontrado.")
    if row["anulado_en"]:
        raise ErrorValidacion("Este cobro ya fue anulado.")
    conn.execute("""UPDATE copa_inscripciones_pagos SET anulado_en=current_timestamp,
        anulado_por=%s,motivo_anulacion=%s WHERE id=%s""", (admin_uid, reason, payment_id))
    return {"message": "Cobro anulado. Se conserva en el historial y deja de contar."}
