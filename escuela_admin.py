"""Registro privado de alumnos y cobros manuales de Súper Chaca."""

from datetime import datetime, timedelta, date
from decimal import Decimal, InvalidOperation
import re

from models import ErrorValidacion, texto, validar_cedula
from services import TZ, exigir_administrador, fecha, numero, METHODS

CATEGORIAS = {"Sub-6", "Sub-8", "Sub-10", "Sub-12", "Sub-14", "Sub-16", "Sub-18"}


def _periodo(value):
    try:
        period = date.fromisoformat(f"{value}-01")
    except (ValueError, TypeError):
        raise ErrorValidacion("Selecciona un mes válido.") from None
    if not date(2020, 1, 1) <= period <= date(2100, 12, 1):
        raise ErrorValidacion("Selecciona un mes entre 2020 y 2100.")
    return period


def _monto(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ErrorValidacion("Ingresa un monto válido.") from None
    if not amount.is_finite() or amount <= 0 or amount > Decimal("9999.99") or amount.as_tuple().exponent < -2:
        raise ErrorValidacion("Ingresa un monto mayor que cero, con máximo dos decimales.")
    return amount


def _metodo(value):
    if value not in METHODS:
        raise ErrorValidacion("Selecciona efectivo o transferencia.")
    return value


def registrar_alumno(conn, admin_uid, data):
    exigir_administrador(conn, admin_uid)
    alumno = texto(data.get("alumno"), "Nombre completo del alumno", 2, 100)
    categoria = data.get("categoria")
    if categoria not in CATEGORIAS:
        raise ErrorValidacion("Selecciona una categoría válida.")
    cedula = str(data.get("cedula") or "").strip() or None
    if cedula and not validar_cedula(cedula):
        raise ErrorValidacion("Revisa la cédula del alumno o déjala vacía.")
    telefono = str(data.get("telefono_representante") or "").strip()
    if not re.fullmatch(r"\+?[0-9]{7,16}", telefono):
        raise ErrorValidacion("Ingresa el teléfono del representante con 7 a 16 dígitos.")
    ingreso = fecha(data.get("fecha_ingreso"))
    if not date(2020, 1, 1) <= ingreso <= datetime.now(TZ).date():
        raise ErrorValidacion("La fecha de ingreso debe estar entre 2020 y hoy.")
    paid = data.get("inscripcion_pagada") is True
    if data.get("inscripcion_pagada") not in (True, False):
        raise ErrorValidacion("Indica si ya se pagó la inscripción.")
    amount = _monto(data.get("monto_inscripcion")) if paid else None
    method = _metodo(data.get("metodo_inscripcion")) if paid else None
    if cedula and conn.execute(
        "SELECT id FROM inscripciones_chaca WHERE cedula=%s", (cedula,)
    ).fetchone():
        raise ErrorValidacion("Esta cédula ya está registrada desde la web.")
    row = conn.execute(
        """INSERT INTO alumnos_chaca_manuales
           (alumno,categoria,cedula,telefono_representante,fecha_ingreso,registrado_por)
           VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""",
        (alumno, categoria, cedula, telefono, ingreso, admin_uid),
    ).fetchone()
    if paid:
        conn.execute(
            """INSERT INTO pagos_chaca_manuales
               (alumno_id,tipo,monto,metodo,registrado_por)
               VALUES(%s,'INSCRIPCION',%s,%s,%s)""",
            (row["id"], amount, method, admin_uid),
        )
    return {"id": row["id"], "message": "Alumno registrado. " + ("Inscripción cobrada." if paid else "Inscripción pendiente.")}


def registrar_pago(conn, admin_uid, data):
    exigir_administrador(conn, admin_uid)
    alumno_id = numero(data.get("alumno_id"), "Alumno")
    student = conn.execute(
        "SELECT id,fecha_ingreso FROM alumnos_chaca_manuales WHERE id=%s FOR UPDATE", (alumno_id,)
    ).fetchone()
    if not student:
        raise ErrorValidacion("Selecciona un alumno registrado manualmente.")
    kind = data.get("tipo")
    if kind not in ("INSCRIPCION", "MENSUALIDAD"):
        raise ErrorValidacion("Selecciona inscripción o mensualidad.")
    period = _periodo(data.get("periodo")) if kind == "MENSUALIDAD" else None
    if period:
        following = (datetime.now(TZ).date().replace(day=1) + timedelta(days=32)).replace(day=1)
        if period < student["fecha_ingreso"].replace(day=1) or period > following:
            raise ErrorValidacion("El mes debe ser desde el ingreso del alumno hasta el próximo mes.")
    amount, method = _monto(data.get("monto")), _metodo(data.get("metodo"))
    existing = conn.execute(
        """SELECT id FROM pagos_chaca_manuales WHERE alumno_id=%s AND tipo=%s
           AND periodo IS NOT DISTINCT FROM %s""", (alumno_id, kind, period)
    ).fetchone()
    if existing:
        raise ErrorValidacion("Este concepto y mes ya figuran como pagados; no se duplicó el ingreso.")
    row = conn.execute(
        """INSERT INTO pagos_chaca_manuales
           (alumno_id,tipo,periodo,monto,metodo,registrado_por)
           VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""",
        (alumno_id, kind, period, amount, method, admin_uid),
    ).fetchone()
    return {"id": row["id"], "message": "Pago registrado en Súper Chaca."}


def resumen(conn, admin_uid, value=None):
    exigir_administrador(conn, admin_uid)
    period = _periodo(value or datetime.now(TZ).strftime("%Y-%m"))
    rows = conn.execute(
        """SELECT sc.id,sc.alumno,sc.categoria,sc.cedula,sc.fecha_inscripcion,
           sc.estado,u.telefono AS telefono_representante,
           p0.monto AS inscripcion_monto,p0.metodo AS inscripcion_metodo,
           pm.monto AS mes_monto,pm.metodo AS mes_metodo
           FROM inscripciones_chaca sc
           JOIN ordenes o0 ON o0.id=sc.orden_id
           JOIN usuarios u ON u.id=o0.usuario_id
           LEFT JOIN pagos p0 ON p0.orden_id=o0.id AND p0.simulado=false AND o0.estado='PAGADA'
           LEFT JOIN mensualidades m ON m.inscripcion_id=sc.id AND m.periodo=%s
           LEFT JOIN ordenes om ON om.id=m.orden_id
           LEFT JOIN pagos pm ON pm.orden_id=m.orden_id AND pm.simulado=false AND om.estado='PAGADA'
           WHERE sc.fecha_inscripcion < (%s + interval '1 month')::date
           ORDER BY sc.alumno,sc.id""", (period, period)
    ).fetchall()
    students = [{"id": f"web:{r['id']}", "origen": "WEB", "alumno": r["alumno"],
                 "categoria": r["categoria"], "cedula": r["cedula"],
                 "telefono_representante": r["telefono_representante"],
                 "fecha_ingreso": r["fecha_inscripcion"], "estado": r["estado"],
                 "inscripcion_pagada": r["inscripcion_monto"] is not None,
                 "inscripcion_monto": r["inscripcion_monto"], "inscripcion_metodo": r["inscripcion_metodo"],
                 "mes_pagado": r["mes_monto"] is not None,
                 "mes_monto": r["mes_monto"], "mes_metodo": r["mes_metodo"]} for r in rows]
    rows = conn.execute(
        """SELECT a.id,a.alumno,a.categoria,a.cedula,a.telefono_representante,
           a.fecha_ingreso,pi.monto AS inscripcion_monto,pi.metodo AS inscripcion_metodo,
           pm.monto AS mes_monto,pm.metodo AS mes_metodo
           FROM alumnos_chaca_manuales a
           LEFT JOIN pagos_chaca_manuales pi ON pi.alumno_id=a.id AND pi.tipo='INSCRIPCION'
           LEFT JOIN pagos_chaca_manuales pm ON pm.alumno_id=a.id
             AND pm.tipo='MENSUALIDAD' AND pm.periodo=%s
           WHERE a.fecha_ingreso < (%s + interval '1 month')::date
           ORDER BY a.alumno,a.id""", (period, period)
    ).fetchall()
    students.extend({"id": f"manual:{r['id']}", "origen": "MANUAL", "alumno": r["alumno"],
                     "categoria": r["categoria"], "cedula": r["cedula"],
                     "telefono_representante": r["telefono_representante"],
                     "fecha_ingreso": r["fecha_ingreso"], "estado": "ACTIVA",
                     "inscripcion_pagada": r["inscripcion_monto"] is not None,
                     "inscripcion_monto": r["inscripcion_monto"], "inscripcion_metodo": r["inscripcion_metodo"],
                     "mes_pagado": r["mes_monto"] is not None,
                     "mes_monto": r["mes_monto"], "mes_metodo": r["mes_metodo"]} for r in rows)
    return {"periodo": period.strftime("%Y-%m"), "alumnos": students}
