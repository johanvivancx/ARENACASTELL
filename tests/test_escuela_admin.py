"""Alumnos manuales, seguimiento mensual y cobros de Súper Chaca."""

from datetime import datetime
from decimal import Decimal

import pytest

import escuela_admin as school
import services as s
from db import preparar_escuela_manual


def test_migracion_escuela_manual_repetible(conn):
    preparar_escuela_manual()
    preparar_escuela_manual()
    assert conn.execute("SELECT to_regclass('public.alumnos_chaca_manuales') AS tabla").fetchone()["tabla"] == "alumnos_chaca_manuales"


def test_alumno_manual_meses_y_finanzas(conn, user):
    admin = conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()["id"]
    today = datetime.now(s.TZ).date()
    month = today.strftime("%Y-%m")
    data = {"alumno": "María del Campo", "categoria": "Sub-12", "cedula": "",
            "telefono_representante": "0991234567", "fecha_ingreso": str(today),
            "inscripcion_pagada": True, "monto_inscripcion": "45.00",
            "metodo_inscripcion": "TRANSFERENCIA"}
    with pytest.raises(s.HTTPError) as denied:
        school.registrar_alumno(conn, user["id"], data)
    assert denied.value.status == 403
    first = school.registrar_alumno(conn, admin, data)
    second = school.registrar_alumno(conn, admin, {**data, "alumno": "Juan del Campo",
        "inscripcion_pagada": False})
    initial = school.resumen(conn, admin, month)["alumnos"]
    paid_enrollment = next(row for row in initial if row["id"] == f"manual:{first['id']}")
    assert paid_enrollment["cedula"] is None
    assert paid_enrollment["inscripcion_pagada"] and not paid_enrollment["mes_pagado"]
    assert not next(row for row in initial if row["id"] == f"manual:{second['id']}")["inscripcion_pagada"]

    school.registrar_pago(conn, admin, {"alumno_id": first["id"], "tipo": "MENSUALIDAD",
        "periodo": month, "monto": "24.00", "metodo": "EFECTIVO"})
    updated = school.resumen(conn, admin, month)["alumnos"]
    paid_month = next(row for row in updated if row["id"] == f"manual:{first['id']}")
    assert paid_month["mes_pagado"] and paid_month["mes_monto"] == Decimal("24.00")
    assert paid_month["mes_metodo"] == "EFECTIVO"
    assert not next(row for row in updated if row["id"] == f"manual:{second['id']}")["mes_pagado"]
    with pytest.raises(s.ErrorValidacion):
        school.registrar_pago(conn, admin, {"alumno_id": first["id"], "tipo": "MENSUALIDAD",
            "periodo": month, "monto": "24", "metodo": "EFECTIVO"})
    school.registrar_pago(conn, admin, {"alumno_id": second["id"], "tipo": "INSCRIPCION",
        "monto": "30", "metodo": "TRANSFERENCIA"})
    finance = s.reportes(conn, admin, {})
    assert finance["finanzas"]["SUPER_CHACA"]["inscripciones"] == Decimal("75")
    assert finance["finanzas"]["SUPER_CHACA"]["mensualidades"] == Decimal("24")
    assert finance["finanzas"]["GENERAL"]["ingresos"] == Decimal("99")
    assert len(finance["pagos"]) == 3


def test_valida_monto_y_mes_sin_crear_cobro(conn):
    admin = conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()["id"]
    today = datetime.now(s.TZ).date()
    student = school.registrar_alumno(conn, admin, {"alumno": "Alumno Prueba",
        "categoria": "Sub-10", "telefono_representante": "0991234567",
        "fecha_ingreso": str(today), "inscripcion_pagada": False})
    month = today.strftime("%Y-%m")
    for amount in ("0", "-1", "1.234", "NaN"):
        with pytest.raises(s.ErrorValidacion):
            school.registrar_pago(conn, admin, {"alumno_id": student["id"],
                "tipo": "MENSUALIDAD", "periodo": month,
                "monto": amount, "metodo": "EFECTIVO"})
    with pytest.raises(s.ErrorValidacion):
        school.registrar_pago(conn, admin, {"alumno_id": student["id"],
            "tipo": "MENSUALIDAD", "periodo": "2020-01",
            "monto": "20", "metodo": "EFECTIVO"})
    assert conn.execute("SELECT count(*) AS n FROM pagos_chaca_manuales").fetchone()["n"] == 0
