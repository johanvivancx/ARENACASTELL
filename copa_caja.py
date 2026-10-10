"""Libro de caja operativo de Copa Castell; separado de pagos web e inscripciones."""
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import re

from models import ErrorValidacion, Usuario, texto
from services import HTTPError, TZ, es_propietario_administracion, exigir_administrador, fecha, limitar_acceso, numero
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


def _monto_opcional(value):
    if value in (None, "", "0", "0.0", "0.00", 0):
        return CERO
    return _monto(value)


def _clave_deudor(name):
    return " ".join(name.split()).casefold()


def _fecha(value):
    day = fecha(value)
    if not date(2026, 1, 1) <= day <= datetime.now(TZ).date():
        raise ErrorValidacion("Usa una fecha de 2026 hasta hoy.")
    return day


def _movimientos(conn):
    return conn.execute("""SELECT m.id,m.fecha,m.tipo,m.cuenta,m.destino,m.area,m.monto,m.concepto,
        m.fixture_id,m.equipo,m.monto_efectivo,m.monto_transferencia,
        m.registrado_por,autor.nombre AS registrado_por_nombre,m.creado_en,
        m.anulado_en,m.anulado_por,anulador.nombre AS anulado_por_nombre,m.motivo_anulacion
        FROM copa_movimientos m JOIN usuarios autor ON autor.id=m.registrado_por
        LEFT JOIN usuarios anulador ON anulador.id=m.anulado_por
        ORDER BY m.fecha,m.id""").fetchall()


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


def _saldos_vocalia(rows):
    """Separa el saldo conocido del importe histórico sin medio de pago."""
    cash = transfer = unknown = CERO
    unknown_count = 0
    for row in rows:
        if row["anulado_en"] or row["cuenta"] != "VOCALIAS" or row["tipo"] not in ("INGRESO", "GASTO"):
            continue
        sign = 1 if row["tipo"] == "INGRESO" else -1
        if row["monto_efectivo"] is None:
            unknown += sign * row["monto"]
            unknown_count += 1
        else:
            cash += sign * row["monto_efectivo"]
            transfer += sign * row["monto_transferencia"]
    return {"efectivo": cash, "transferencia": transfer, "sin_desglose": unknown,
            "movimientos_sin_desglose": unknown_count,
            "total": cash + transfer + unknown}


def resumen(conn, admin_uid, semana=None):
    exigir_administrador(conn, admin_uid)
    start = fecha(semana) if semana else datetime.now(TZ).date()
    start -= timedelta(days=start.weekday())
    end = start + timedelta(days=7)
    rows = _movimientos(conn)
    balances = _saldos(rows)
    vocalia_balances = _saldos_vocalia(rows)
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
    vocalia_efectivo = CERO
    vocalia_transferencia = CERO
    vocalia_sin_desglose = CERO
    for row in rows:
        if not row["anulado_en"] and row["tipo"] == "INGRESO" and row["cuenta"] == "VOCALIAS":
            key = (row["fixture_id"], row["equipo"])
            payments[key] = payments.get(key, CERO) + row["monto"]
            if start <= row["fecha"] < end:
                if row["monto_efectivo"] is None:
                    vocalia_sin_desglose += row["monto"]
                else:
                    vocalia_efectivo += row["monto_efectivo"]
                    vocalia_transferencia += row["monto_transferencia"]
    debts = conn.execute("""SELECT d.id,d.fecha,d.nombre,d.monto,d.concepto,d.creado_en,d.cobrada_en,
        autor.nombre AS registrado_por_nombre,cobrador.nombre AS cobrada_por_nombre
        FROM copa_bar_deudas d JOIN usuarios autor ON autor.id=d.registrado_por
        LEFT JOIN usuarios cobrador ON cobrador.id=d.cobrada_por
        ORDER BY d.fecha DESC,d.id DESC""").fetchall()
    pending_debts = [row for row in debts if row["cobrada_en"] is None]
    debtors = {}
    for row in pending_debts:
        key = _clave_deudor(row["nombre"])
        person = debtors.setdefault(key, {"nombre": row["nombre"], "pendiente": CERO, "deudas": 0})
        person["pendiente"] += row["monto"]
        person["deudas"] += 1
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
            "saldo_inicial_registrado": any(r["tipo"] == "APERTURA" and not r["anulado_en"] for r in rows),
            "ingresos": income, "gastos": expenses, "caja_entregada": transfers,
            "dias": [{"fecha": day, **daily[day]} for day in sorted(daily, reverse=True)],
            "movimientos": list(reversed(weekly)), "vocalias": due,
            "vocalias_efectivo": vocalia_efectivo,
            "vocalias_transferencia": vocalia_transferencia,
            "vocalias_sin_desglose": vocalia_sin_desglose,
            "vocalias_saldos": vocalia_balances,
            "bar_deudas": debts,
            "bar_deudores": sorted(debtors.values(), key=lambda item: item["nombre"].casefold()),
            "bar_deuda_pendiente": sum((row["monto"] for row in pending_debts), CERO),
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
    cash = transfer = None
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
            if "monto_efectivo" in data or "monto_transferencia" in data:
                cash = _monto_opcional(data.get("monto_efectivo"))
                transfer = _monto_opcional(data.get("monto_transferencia"))
                if cash + transfer != amount:
                    raise ErrorValidacion("Efectivo y transferencia deben sumar el monto recibido.")
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
        if account == "VOCALIAS":
            if "monto_efectivo" not in data or "monto_transferencia" not in data:
                raise ErrorValidacion("Indica cuánto se pagó en efectivo y por transferencia.")
            cash = _monto_opcional(data.get("monto_efectivo"))
            transfer = _monto_opcional(data.get("monto_transferencia"))
            if cash + transfer != amount:
                raise ErrorValidacion("Efectivo y transferencia deben sumar el gasto.")
            available = _saldos_vocalia(_movimientos(conn))
            if cash > available["efectivo"] or transfer > available["transferencia"]:
                raise ErrorValidacion("No hay saldo suficiente en el medio de pago elegido. Clasifica los movimientos anteriores si corresponde.")
    if kind in {"TRASPASO", "GASTO"} and _saldos(_movimientos(conn))[account] < amount:
        raise ErrorValidacion("No hay saldo suficiente en la cuenta que paga. Revisa la caja disponible.")
    row = conn.execute("""INSERT INTO copa_movimientos
        (fecha,tipo,cuenta,destino,area,monto,concepto,fixture_id,equipo,
         monto_efectivo,monto_transferencia,registrado_por)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (day,kind,account,target,area,amount,concept,fixture_id,team,cash,transfer,admin_uid)).fetchone()
    return {"id": row["id"], "message": "Movimiento de Copa Castell registrado."}


def registrar_deuda_bar(conn, admin_uid, data):
    """Una venta fiada no entra en caja hasta que realmente se cobre."""
    exigir_administrador(conn, admin_uid)
    conn.execute("SELECT pg_advisory_xact_lock(20491007)")
    day = _fecha(data.get("fecha"))
    name = " ".join(texto(data.get("nombre"), "Nombre", 2, 120).split())
    if len(name) < 2:
        raise ErrorValidacion("Escribe el nombre de la persona que debe.")
    for existing in conn.execute("SELECT DISTINCT nombre FROM copa_bar_deudas").fetchall():
        if _clave_deudor(existing["nombre"]) == _clave_deudor(name):
            name = existing["nombre"]
            break
    amount = _monto(data.get("monto"))
    concept = texto(data.get("concepto"), "Productos que debe", 3, 180)
    row = conn.execute("""INSERT INTO copa_bar_deudas
        (fecha,nombre,monto,concepto,registrado_por) VALUES(%s,%s,%s,%s,%s)
        RETURNING id""", (day,name,amount,concept,admin_uid)).fetchone()
    return {"id": row["id"], "message": "Deuda del bar registrada; aún no cuenta como ingreso."}


def cobrar_deuda_bar(conn, admin_uid, debt_id, data):
    """Al saldarla se anota exactamente un ingreso del bar."""
    exigir_administrador(conn, admin_uid)
    conn.execute("SELECT pg_advisory_xact_lock(20491007)")
    did = numero(debt_id, "Deuda")
    debt = conn.execute("SELECT * FROM copa_bar_deudas WHERE id=%s FOR UPDATE", (did,)).fetchone()
    if not debt:
        raise HTTPError(404, "No encontramos esa deuda del bar.")
    if debt["cobrada_en"]:
        raise ErrorValidacion("Esta deuda ya se cobró.")
    day = _fecha(data.get("fecha"))
    movement = conn.execute("""INSERT INTO copa_movimientos
        (fecha,tipo,cuenta,monto,concepto,registrado_por)
        VALUES(%s,'INGRESO','BAR',%s,%s,%s) RETURNING id""",
        (day,debt["monto"],f"Cobro de deuda #{did}: {debt['nombre']}"[:180],admin_uid)).fetchone()
    conn.execute("""UPDATE copa_bar_deudas SET cobrada_en=current_timestamp,
        cobrada_por=%s,movimiento_cobro_id=%s WHERE id=%s""",
        (admin_uid,movement["id"],did))
    return {"id": did, "message": "Deuda cobrada e ingreso del bar registrado."}


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
    if conn.execute("SELECT 1 FROM copa_bar_deudas WHERE movimiento_cobro_id=%s", (mid,)).fetchone():
        raise ErrorValidacion("Este movimiento saldó una deuda del bar y no puede anularse por separado.")
    conn.execute("""UPDATE copa_movimientos SET anulado_en=current_timestamp,
        anulado_por=%s,motivo_anulacion=%s WHERE id=%s""", (admin_uid,reason,mid))
    if any(amount < 0 for amount in _saldos(_movimientos(conn)).values()):
        raise ErrorValidacion("No se puede anular: dejaría una caja con saldo negativo. Corrige primero los movimientos posteriores.")
    split = _saldos_vocalia(_movimientos(conn))
    if split["efectivo"] < 0 or split["transferencia"] < 0:
        raise ErrorValidacion("No se puede anular: dejaría negativo el efectivo o las transferencias de vocalías.")
    return {"id": mid, "message": "Movimiento anulado; el historial se conserva."}


def desglosar_vocalia(conn, admin_uid, movement_id, data):
    """Clasifica el medio de pago de un movimiento antiguo sin cambiar su total."""
    exigir_administrador(conn, admin_uid)
    conn.execute("SELECT pg_advisory_xact_lock(20491007)")
    mid = numero(movement_id, "Movimiento")
    row = conn.execute("SELECT * FROM copa_movimientos WHERE id=%s FOR UPDATE", (mid,)).fetchone()
    if not row or row["cuenta"] != "VOCALIAS" or row["tipo"] not in ("INGRESO", "GASTO"):
        raise HTTPError(404, "No encontramos ese movimiento de vocalías.")
    if row["anulado_en"] or row["monto_efectivo"] is not None:
        raise ErrorValidacion("Solo se puede desglosar un movimiento activo que aún no tenga desglose.")
    cash = _monto_opcional(data.get("monto_efectivo"))
    transfer = _monto_opcional(data.get("monto_transferencia"))
    if cash + transfer != row["monto"]:
        raise ErrorValidacion("Efectivo y transferencia deben sumar el monto original.")
    split = _saldos_vocalia(_movimientos(conn))
    sign = 1 if row["tipo"] == "INGRESO" else -1
    if split["efectivo"] + sign * cash < 0 or split["transferencia"] + sign * transfer < 0:
        raise ErrorValidacion("Este desglose dejaría negativo el efectivo o las transferencias.")
    conn.execute("UPDATE copa_movimientos SET monto_efectivo=%s,monto_transferencia=%s WHERE id=%s",
                 (cash, transfer, mid))
    return {"id": mid, "message": "Medio de pago clasificado; el total del movimiento no cambió."}


def vista_previa_limpieza_vocalias(conn, admin_uid):
    exigir_administrador(conn, admin_uid)
    owner = conn.execute("SELECT * FROM usuarios WHERE id=%s", (admin_uid,)).fetchone()
    if not es_propietario_administracion(owner):
        raise HTTPError(403, "Solo la cuenta propietaria puede vaciar el historial de vocalías.")
    row = conn.execute("""SELECT count(*) AS total,
        count(*) FILTER (WHERE anulado_en IS NULL) AS activos,
        count(*) FILTER (WHERE anulado_en IS NOT NULL) AS anulados,
        COALESCE(max(id),0) AS ultimo_id
        FROM copa_movimientos WHERE cuenta='VOCALIAS'""").fetchone()
    return dict(row)


def limpiar_historial_vocalias(conn, admin_uid, data, ip_address=""):
    """Elimina solo movimientos de VOCALIAS, incluidos los ya anulados."""
    exigir_administrador(conn, admin_uid)
    owner = conn.execute("SELECT * FROM usuarios WHERE id=%s", (admin_uid,)).fetchone()
    if not es_propietario_administracion(owner):
        raise HTTPError(403, "Solo la cuenta propietaria puede vaciar el historial de vocalías.")
    limitar_acceso(conn, f"vocalias-reset:{admin_uid}:{ip_address}", max_attempts=5)
    if data.get("confirmacion") != "BORRAR VOCALIAS":
        raise ErrorValidacion("Escribe BORRAR VOCALIAS para confirmar.")
    if not Usuario.desde_fila(owner).verificar_password(data.get("password", "")):
        raise HTTPError(401, "La contraseña de administrador no coincide.")
    expected = data.get("resumen")
    if not isinstance(expected, dict) or set(expected) != {"total", "activos", "anulados", "ultimo_id"} or any(
        type(value) is not int or value < 0 for value in expected.values()
    ):
        raise ErrorValidacion("Actualiza la vista previa antes de borrar vocalías.")
    conn.execute("SET LOCAL lock_timeout = '5s'")
    conn.execute("SELECT pg_advisory_xact_lock(20491007)")
    conn.execute("LOCK TABLE copa_movimientos IN EXCLUSIVE MODE")
    current = vista_previa_limpieza_vocalias(conn, admin_uid)
    if current != expected:
        raise HTTPError(409, "Los movimientos de vocalías cambiaron. Revisa la vista previa otra vez.")
    deleted = conn.execute("DELETE FROM copa_movimientos WHERE cuenta='VOCALIAS'").rowcount
    return {"id": f"VOCALIAS-{deleted}", "eliminados": deleted,
            "message": f"Se eliminaron {deleted} movimientos de vocalías. Bar, entradas y disponible no se tocaron."}
