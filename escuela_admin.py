"""Registro privado de alumnos y cobros manuales de Súper Chaca."""

from datetime import datetime, timedelta, date
from decimal import Decimal, InvalidOperation
import re

from models import ErrorValidacion, Usuario, texto, validar_cedula
from services import (TZ, HTTPError, es_propietario_administracion, exigir_administrador,
                      fecha, limitar_acceso, numero, METHODS)

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
        """SELECT id,fecha_ingreso FROM alumnos_chaca_manuales
           WHERE id=%s AND retirado_en IS NULL AND prueba_anulada_en IS NULL FOR UPDATE""", (alumno_id,)
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
           sc.estado,sc.retirado_en,u.telefono AS telefono_representante,
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
                 "fecha_ingreso": r["fecha_inscripcion"],
                 "estado": "RETIRADO" if r["retirado_en"] else r["estado"],
                 "inscripcion_pagada": r["inscripcion_monto"] is not None,
                 "inscripcion_monto": r["inscripcion_monto"], "inscripcion_metodo": r["inscripcion_metodo"],
                 "mes_pagado": r["mes_monto"] is not None,
                 "mes_monto": r["mes_monto"], "mes_metodo": r["mes_metodo"]} for r in rows]
    rows = conn.execute(
        """SELECT a.id,a.alumno,a.categoria,a.cedula,a.telefono_representante,
           a.fecha_ingreso,a.retirado_en,a.prueba_anulada_en,autor.nombre AS registrado_por,
           pi.monto AS inscripcion_monto,pi.metodo AS inscripcion_metodo,
           autor_inscripcion.nombre AS inscripcion_registrada_por,
           pm.monto AS mes_monto,pm.metodo AS mes_metodo,
           autor_mes.nombre AS mes_registrado_por
           FROM alumnos_chaca_manuales a
           JOIN usuarios autor ON autor.id=a.registrado_por
           LEFT JOIN pagos_chaca_manuales pi ON pi.alumno_id=a.id AND pi.tipo='INSCRIPCION'
             AND pi.anulado_en IS NULL
           LEFT JOIN usuarios autor_inscripcion ON autor_inscripcion.id=pi.registrado_por
           LEFT JOIN pagos_chaca_manuales pm ON pm.alumno_id=a.id
             AND pm.tipo='MENSUALIDAD' AND pm.periodo=%s AND pm.anulado_en IS NULL
           LEFT JOIN usuarios autor_mes ON autor_mes.id=pm.registrado_por
           WHERE a.fecha_ingreso < (%s + interval '1 month')::date
           ORDER BY a.alumno,a.id""", (period, period)
    ).fetchall()
    students.extend({"id": f"manual:{r['id']}", "origen": "MANUAL", "alumno": r["alumno"],
                     "categoria": r["categoria"], "cedula": r["cedula"],
                     "telefono_representante": r["telefono_representante"],
                     "fecha_ingreso": r["fecha_ingreso"],
                     "estado": "PRUEBA_ANULADA" if r["prueba_anulada_en"] else
                               "RETIRADO" if r["retirado_en"] else "ACTIVA",
                     "registrado_por": r["registrado_por"],
                     "inscripcion_pagada": r["inscripcion_monto"] is not None,
                     "inscripcion_monto": r["inscripcion_monto"], "inscripcion_metodo": r["inscripcion_metodo"],
                     "inscripcion_registrada_por": r["inscripcion_registrada_por"],
                     "mes_pagado": r["mes_monto"] is not None,
                     "mes_monto": r["mes_monto"], "mes_metodo": r["mes_metodo"],
                     "mes_registrado_por": r["mes_registrado_por"]} for r in rows)
    history = {student["id"]: [] for student in students}
    for payment in conn.execute(
        """SELECT alumno_id,tipo,periodo,monto,metodo,pagado_en,anulado_en
           FROM pagos_chaca_manuales ORDER BY pagado_en,id"""
    ).fetchall():
        key = f'manual:{payment["alumno_id"]}'
        if key in history:
            history[key].append({k: payment[k] for k in ("tipo", "periodo", "monto", "metodo", "pagado_en", "anulado_en")})
    for payment in conn.execute(
        """SELECT sc.id AS alumno_id,'INSCRIPCION' AS tipo,NULL::date AS periodo,
           p.monto,p.metodo,p.pagado_en
           FROM inscripciones_chaca sc JOIN pagos p ON p.orden_id=sc.orden_id
           JOIN ordenes o ON o.id=sc.orden_id
           WHERE p.simulado=false AND o.estado='PAGADA'
           UNION ALL
           SELECT m.inscripcion_id AS alumno_id,'MENSUALIDAD' AS tipo,m.periodo,
           p.monto,p.metodo,p.pagado_en
           FROM mensualidades m JOIN inscripciones_chaca sc ON sc.id=m.inscripcion_id
           JOIN pagos p ON p.orden_id=m.orden_id
           JOIN ordenes o ON o.id=m.orden_id
           WHERE p.simulado=false AND o.estado='PAGADA' AND m.orden_id<>sc.orden_id
           ORDER BY pagado_en"""
    ).fetchall():
        key = f'web:{payment["alumno_id"]}'
        if key in history:
            history[key].append({k: payment[k] for k in ("tipo", "periodo", "monto", "metodo", "pagado_en")})
    for student in students:
        student["historial_pagos"] = history[student["id"]]
    return {"periodo": period.strftime("%Y-%m"), "alumnos": students}


def cambiar_estado_alumno(conn, admin_uid, origin, student_id, action):
    """Retirar o reactivar sin modificar las órdenes ni los cobros existentes."""
    exigir_administrador(conn, admin_uid)
    if origin not in ("manual", "web") or action not in ("retire", "restore"):
        raise ErrorValidacion("Acción de alumno no válida.")
    identifier = numero(student_id, "Alumno")
    table = "alumnos_chaca_manuales" if origin == "manual" else "inscripciones_chaca"
    student = conn.execute(f"SELECT * FROM {table} WHERE id=%s FOR UPDATE", (identifier,)).fetchone()
    if not student or (origin == "manual" and student["prueba_anulada_en"]):
        raise HTTPError(404, "No encontramos un alumno que se pueda modificar.")
    if action == "retire":
        if student["retirado_en"]:
            raise ErrorValidacion("El alumno ya está retirado.")
        conn.execute(f"UPDATE {table} SET retirado_en=current_timestamp,retirado_por=%s WHERE id=%s",
                     (admin_uid, identifier))
        return {"id": f"{origin}:{identifier}", "message": f'{student["alumno"]} retirado. Sus pagos siguen en el historial y en las cuentas.'}
    if not student["retirado_en"]:
        raise ErrorValidacion("El alumno ya está activo.")
    conn.execute(f"UPDATE {table} SET retirado_en=NULL,retirado_por=NULL WHERE id=%s", (identifier,))
    return {"id": f"{origin}:{identifier}", "message": f'{student["alumno"]} reactivado. Sus pagos se conservaron.'}


def vista_previa_prueba(conn, admin_uid, student_id):
    exigir_administrador(conn, admin_uid)
    admin = conn.execute("SELECT * FROM usuarios WHERE id=%s", (admin_uid,)).fetchone()
    if not es_propietario_administracion(admin):
        raise HTTPError(403, "Solo la cuenta propietaria puede anular registros de prueba.")
    student = conn.execute(
        "SELECT id,alumno,prueba_anulada_en FROM alumnos_chaca_manuales WHERE id=%s",
        (numero(student_id, "Alumno"),)
    ).fetchone()
    if not student or student["prueba_anulada_en"]:
        raise HTTPError(404, "Ese registro ya no está disponible para anular.")
    totals = conn.execute(
        """SELECT count(*) AS cantidad,coalesce(sum(monto),0) AS total
           FROM pagos_chaca_manuales WHERE alumno_id=%s AND anulado_en IS NULL""",
        (student["id"],)
    ).fetchone()
    return {"alumno": student["alumno"], "cantidad": totals["cantidad"], "total": totals["total"]}


def anular_prueba(conn, admin_uid, student_id, data, ip_address=""):
    """Anula únicamente cobros manuales de la prueba, con autoría y sin borrar filas."""
    preview = vista_previa_prueba(conn, admin_uid, student_id)
    limitar_acceso(conn, f"chaca-void:{admin_uid}:{ip_address}", max_attempts=5)
    if data.get("confirmacion") != "ANULAR PRUEBA":
        raise ErrorValidacion("Escribe ANULAR PRUEBA para confirmar.")
    admin = conn.execute("SELECT * FROM usuarios WHERE id=%s", (admin_uid,)).fetchone()
    if not Usuario.desde_fila(admin).verificar_password(data.get("password_actual", "")):
        raise HTTPError(401, "La contraseña de administrador no coincide.")
    student = conn.execute(
        "SELECT id,prueba_anulada_en FROM alumnos_chaca_manuales WHERE id=%s FOR UPDATE",
        (numero(student_id, "Alumno"),)
    ).fetchone()
    if not student or student["prueba_anulada_en"]:
        raise HTTPError(409, "El registro cambió. Actualiza la vista previa.")
    current = vista_previa_prueba(conn, admin_uid, student_id)
    try:
        expected_total = Decimal(str(data.get("total")))
    except (InvalidOperation, TypeError):
        expected_total = None
    if data.get("cantidad") != current["cantidad"] or expected_total != current["total"]:
        raise HTTPError(409, "Los pagos cambiaron. Actualiza la vista previa antes de continuar.")
    conn.execute(
        """UPDATE pagos_chaca_manuales SET anulado_en=current_timestamp,anulado_por=%s
           WHERE alumno_id=%s AND anulado_en IS NULL""", (admin_uid, student["id"])
    )
    conn.execute(
        """UPDATE alumnos_chaca_manuales SET prueba_anulada_en=current_timestamp,
           prueba_anulada_por=%s,retirado_en=current_timestamp,retirado_por=%s WHERE id=%s""",
        (admin_uid, admin_uid, student["id"])
    )
    return {"id": f'manual:{student["id"]}', "message": f'Registro de prueba de {preview["alumno"]} anulado. {preview["cantidad"]} cobro(s) por ${preview["total"]} quedan fuera de los ingresos, con auditoría.'}
