"""Libro de caja operativo de Copa Castell; separado de pagos web e inscripciones."""
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import re

from models import ErrorValidacion, texto
from services import HTTPError, TZ, exigir_administrador, fecha, numero
from copa import catalogo

CUENTAS = ("DISPONIBLE", "BAR", "ENTRADAS", "VOCALIAS")
CERO = Decimal("0.00")
ESPERADO_VOCALIA = Decimal("10.00")


def _monto(value):
    raw = str(value or "")
    if not re.fullmatch(r"\d{1,7}(?:\.\d{1,2})?", raw):
        raise ErrorValidacion("Monto: escribe dólares con hasta dos decimales.")
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        raise ErrorValidacion("Monto inválido.") from None
    if amount <= 0:
        raise ErrorValidacion("El monto debe ser mayor que cero.")
    return amount


def _fecha(value):
    day = fecha(value)
    if not date(2026, 1, 1) <= day <= datetime.now(TZ).date():
        raise ErrorValidacion("Usa una fecha de 2026 hasta hoy.")
    return day


def _movimientos(conn):
    return conn.execute("""SELECT id,fecha,tipo,cuenta,destino,area,monto,concepto,
        fixture_id,equipo,registrado_por,creado_en,anulado_en,anulado_por,motivo_anulacion
        FROM copa_movimientos ORDER BY fecha,id""").fetchall()


def _saldos(rows):
    balances = {account: CERO for account in CUENTAS}
    for row in rows:
        if row["anulado_en"]:
            continue
        amount = row["monto"]
        if row["tipo"] == "APERTURA":
            balances["DISPONIBLE"] += amount
        elif row["tipo"] == "TRASPASO":
            balances["DISPONIBLE"] -= amount
            balances[row["destino"]] += amount
        elif row["tipo"] == "INGRESO":
            balances[row["cuenta"]] += amount
        else:
            balances[row["cuenta"]] -= amount
    return balances


def resumen(conn, admin_uid, semana=None):
    exigir_administrador(conn, admin_uid)
    start = fecha(semana) if semana else datetime.now(TZ).date()
    start -= timedelta(days=start.weekday())
    end = start + timedelta(days=7)
    rows = _movimientos(conn)
    balances = _saldos(rows)
    weekly = [r for r in rows if start <= r["fecha"] < end]
    income = {area: CERO for area in ("BAR", "ENTRADAS", "VOCALIAS")}
    expenses = {area: CERO for area in ("BAR", "ENTRADAS", "VOCALIAS", "GENERAL")}
    transfers = {area: CERO for area in ("BAR", "ENTRADAS")}
    daily = {}
    for row in weekly:
        if row["anulado_en"]:
            continue
        day = daily.setdefault(row["fecha"], {
            "BAR": {"caja": CERO, "ingreso": CERO, "gasto": CERO},
            "ENTRADAS": {"caja": CERO, "ingreso": CERO, "gasto": CERO},
            "VOCALIAS": {"caja": CERO, "ingreso": CERO, "gasto": CERO}})
        if row["tipo"] == "INGRESO":
            income[row["cuenta"]] += row["monto"]
            day[row["cuenta"]]["ingreso"] += row["monto"]
        elif row["tipo"] == "GASTO":
            expenses[row["area"]] += row["monto"]
            if row["area"] in day:
                day[row["area"]]["gasto"] += row["monto"]
        elif row["tipo"] == "TRASPASO":
            transfers[row["destino"]] += row["monto"]
            day[row["destino"]]["caja"] += row["monto"]
    fixtures, _ = catalogo()
    payments = {}
    for row in rows:
        if not row["anulado_en"] and row["tipo"] == "INGRESO" and row["cuenta"] == "VOCALIAS":
            key = (row["fixture_id"], row["equipo"])
            payments[key] = payments.get(key, CERO) + row["monto"]
    # Solo partidos programados para la semana seleccionada; el reprogramado usa la fecha nueva.
    due = []
    for fixture in fixtures.values():
        day = date.fromisoformat(fixture["date"])
        if not start <= day < end:
            continue
        for team in (fixture["home"], fixture["away"]):
            paid = payments.get((fixture["id"], team), CERO)
            due.append({"fixture_id": fixture["id"], "equipo": team,
                        "esperado": ESPERADO_VOCALIA, "pagado": paid,
                        "pendiente": max(CERO, ESPERADO_VOCALIA - paid)})
    return {"semana": start, "hasta": end - timedelta(days=1),
            "saldos": balances, "saldo_total": sum(balances.values(), CERO),
            "ingresos": income, "gastos": expenses, "caja_entregada": transfers,
            "dias": [{"fecha": day, **daily[day]} for day in sorted(daily, reverse=True)],
            "movimientos": list(reversed(weekly)), "vocalias": due,
            "vocalias_esperadas": sum((r["esperado"] for r in due), CERO),
            "vocalias_pendientes": sum((r["pendiente"] for r in due), CERO),
            "partidos": [{"id": f["id"], "date": f["date"], "home": f["home"],
                          "away": f["away"], "round": f["round"]} for f in fixtures.values()]}


def registrar(conn, admin_uid, data):
    exigir_administrador(conn, admin_uid)
    # Serializa altas/anulaciones para no permitir saldos negativos con dos peticiones simultáneas.
    conn.execute("SELECT pg_advisory_xact_lock(20491007)")
    kind = str(data.get("tipo", ""))
    account = str(data.get("cuenta", ""))
    target = str(data.get("destino", "")) or None
    area = str(data.get("area", "")) or None
    if kind not in {"APERTURA", "TRASPASO", "INGRESO", "GASTO"} or account not in CUENTAS:
        raise ErrorValidacion("Selecciona un movimiento y una cuenta válidos.")
    amount = _monto(data.get("monto"))
    day = _fecha(data.get("fecha"))
    concept = texto(data.get("concepto"), "Concepto", 3, 180)
    fixture_id = str(data.get("fixture_id", "")) or None
    team = str(data.get("equipo", "")) or None
    if kind == "APERTURA":
        if account != "DISPONIBLE" or target or area or fixture_id or team:
            raise ErrorValidacion("El saldo inicial solo pertenece a Dinero disponible.")
        if any(not row["anulado_en"] for row in _movimientos(conn)):
            raise ErrorValidacion("El saldo inicial se registra una vez, antes de los demás movimientos.")
    elif kind == "TRASPASO":
        if account != "DISPONIBLE" or target not in {"BAR", "ENTRADAS"} or area or fixture_id or team:
            raise ErrorValidacion("La caja entregada sale de Disponible y va al bar o a entradas.")
    elif kind == "INGRESO":
        if account == "DISPONIBLE" or target or area:
            raise ErrorValidacion("Registra ventas en bar o entradas; la vocalía se registra por equipo.")
        if account == "VOCALIAS":
            fixture = catalogo()[0].get(fixture_id)
            if not fixture or team not in (fixture["home"], fixture["away"]):
                raise ErrorValidacion("Selecciona un equipo de un partido programado.")
            paid = conn.execute("""SELECT COALESCE(sum(monto),0) AS total FROM copa_movimientos
                 WHERE tipo='INGRESO' AND cuenta='VOCALIAS' AND fixture_id=%s AND equipo=%s AND anulado_en IS NULL""",
                 (fixture_id, team)).fetchone()["total"]
            if paid + amount > ESPERADO_VOCALIA:
                raise ErrorValidacion(f"Ese equipo ya pagó {paid}; la vocalía esperada es $10.")
        elif fixture_id or team:
            raise ErrorValidacion("Solo las vocalías se asocian a partido y equipo.")
    else:
        if target or team or area not in {"BAR", "ENTRADAS", "VOCALIAS", "GENERAL"}:
            raise ErrorValidacion("El gasto requiere una actividad válida.")
        if account == "DISPONIBLE" and area not in {"BAR", "ENTRADAS", "GENERAL"}:
            raise ErrorValidacion("Disponible no financia vocalías directamente.")
        if account != "DISPONIBLE" and area != account:
            raise ErrorValidacion("Selecciona la misma actividad que paga el gasto.")
        if fixture_id and (account != "VOCALIAS" or fixture_id not in catalogo()[0]):
            raise ErrorValidacion("Ese partido no corresponde al gasto de vocalías.")
    if kind in {"TRASPASO", "GASTO"} and _saldos(_movimientos(conn))[account] < amount:
        raise ErrorValidacion("No hay saldo suficiente en la cuenta que paga. Revisa la caja disponible.")
    row = conn.execute("""INSERT INTO copa_movimientos
        (fecha,tipo,cuenta,destino,area,monto,concepto,fixture_id,equipo,registrado_por)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (day,kind,account,target,area,amount,concept,fixture_id,team,admin_uid)).fetchone()
    return {"id": row["id"], "message": "Movimiento de Copa Castell registrado."}


def anular(conn, admin_uid, movement_id, data):
    exigir_administrador(conn, admin_uid)
    conn.execute("SELECT pg_advisory_xact_lock(20491007)")
    reason = texto(data.get("motivo"), "Motivo de anulación", 3, 250)
    mid = numero(movement_id, "Movimiento")
    row = conn.execute("SELECT * FROM copa_movimientos WHERE id=%s FOR UPDATE", (mid,)).fetchone()
    if not row:
        raise HTTPError(404, "No encontramos ese movimiento.")
    if row["anulado_en"]:
        raise ErrorValidacion("Este movimiento ya está anulado.")
    conn.execute("""UPDATE copa_movimientos SET anulado_en=current_timestamp,
        anulado_por=%s,motivo_anulacion=%s WHERE id=%s""", (admin_uid,reason,mid))
    if any(amount < 0 for amount in _saldos(_movimientos(conn)).values()):
        raise ErrorValidacion("No se puede anular: dejaría una caja con saldo negativo. Corrige primero los movimientos posteriores.")
    return {"id": mid, "message": "Movimiento anulado; el historial se conserva."}
