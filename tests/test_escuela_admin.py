"""Alumnos manuales, seguimiento mensual y cobros de Súper Chaca."""

from datetime import datetime, date, timedelta
from decimal import Decimal

import pytest

import escuela_admin as school
import services as s
from db import preparar_escuela_manual
from models import Usuario
from manage import cedula_demo
from conftest import confirmar_transferencia


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


def test_retirar_conserva_historial_y_anular_prueba_excluye_ingresos(conn, user, monkeypatch):
    admin = conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()["id"]
    today = datetime.now(s.TZ).date()
    student = school.registrar_alumno(conn, admin, {"alumno": "Alumno de Prueba",
        "categoria": "Sub-10", "telefono_representante": "0991234567",
        "fecha_ingreso": str(today), "inscripcion_pagada": True,
        "monto_inscripcion": "65.00", "metodo_inscripcion": "EFECTIVO"})
    school.registrar_pago(conn, admin, {"alumno_id": student["id"], "tipo": "MENSUALIDAD",
        "periodo": today.strftime("%Y-%m"), "monto": "24.00", "metodo": "TRANSFERENCIA"})
    before = s.reportes(conn, admin, {})
    assert before["finanzas"]["SUPER_CHACA"]["ingresos"] == Decimal("89")
    with pytest.raises(s.HTTPError):
        school.cambiar_estado_alumno(conn, user["id"], "manual", student["id"], "retire")
    school.cambiar_estado_alumno(conn, admin, "manual", student["id"], "retire")
    archived = next(row for row in school.resumen(conn, admin)["alumnos"] if row["id"] == f'manual:{student["id"]}')
    assert archived["estado"] == "RETIRADO" and len(archived["historial_pagos"]) == 2
    assert s.reportes(conn, admin, {})["finanzas"]["SUPER_CHACA"]["ingresos"] == Decimal("89")
    with pytest.raises(s.ErrorValidacion):
        school.registrar_pago(conn, admin, {"alumno_id": student["id"], "tipo": "MENSUALIDAD",
            "periodo": today.strftime("%Y-%m"), "monto": "30", "metodo": "EFECTIVO"})
    school.cambiar_estado_alumno(conn, admin, "manual", student["id"], "restore")
    assert next(row for row in school.resumen(conn, admin)["alumnos"] if row["id"] == f'manual:{student["id"]}')["estado"] == "ACTIVA"

    monkeypatch.setenv("ADMIN_OWNER_EMAIL", "revision@arena.test")
    monkeypatch.setenv("ADMIN_CREATION_SECRET", "clave-de-pruebas-de-mas-de-veinte-caracteres")
    owner = Usuario.desde_fila(conn.execute("SELECT * FROM usuarios WHERE id=%s", (admin,)).fetchone())
    owner.set_password("PruebaSegura!2026")
    conn.execute("UPDATE usuarios SET password_hash=%s WHERE id=%s", (owner.get_password_hash(), admin))
    preview = school.vista_previa_prueba(conn, admin, student["id"])
    assert preview["cantidad"] == 2 and preview["total"] == Decimal("89")
    request = {"confirmacion": "ANULAR PRUEBA", "password_actual": "PruebaSegura!2026",
               "cantidad": preview["cantidad"], "total": str(preview["total"])}
    with pytest.raises(s.HTTPError):
        school.anular_prueba(conn, user["id"], student["id"], request)
    with pytest.raises(s.HTTPError) as stale:
        school.anular_prueba(conn, admin, student["id"], {**request, "total": "65.00"})
    assert stale.value.status == 409
    school.anular_prueba(conn, admin, student["id"], request)
    after = s.reportes(conn, admin, {})
    assert after["finanzas"]["SUPER_CHACA"]["ingresos"] == 0
    assert not any(p["pago_id"].startswith("chaca-") for p in after["pagos"])
    annulled = next(row for row in school.resumen(conn, admin)["alumnos"] if row["id"] == f'manual:{student["id"]}')
    assert annulled["estado"] == "PRUEBA_ANULADA"
    assert all(payment["anulado_en"] for payment in annulled["historial_pagos"])
    assert conn.execute("SELECT count(*) AS n FROM pagos_chaca_manuales").fetchone()["n"] == 2


def test_retiro_de_alumno_web_preserva_pagos_y_bloquea_renovacion(conn, user, pay_data):
    admin = conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()["id"]
    today = datetime.now(s.TZ).date()
    schedule = conn.execute("SELECT id FROM horarios_chaca WHERE categoria='Sub-12' ORDER BY id LIMIT 1").fetchone()
    order = s.inscribir_escuela(conn, user["id"], {
        "alumno": "Alumno Web", "cedula": cedula_demo(802),
        "nacimiento": str(date(today.year - 10, 1, 1)), "categoria": "Sub-12",
        "horario_id": schedule["id"], "consentimiento": True})
    confirmar_transferencia(conn, user["id"], order["id"], pay_data)
    inscription = s.detalle_orden(conn, user["id"], order["id"])["escuela"]
    before = s.reportes(conn, admin, {})["finanzas"]["SUPER_CHACA"]["ingresos"]
    school.cambiar_estado_alumno(conn, admin, "web", inscription["id"], "retire")
    archived = next(row for row in school.resumen(conn, admin)["alumnos"] if row["id"] == f'web:{inscription["id"]}')
    assert archived["estado"] == "RETIRADO" and len(archived["historial_pagos"]) == 1
    assert s.reportes(conn, admin, {})["finanzas"]["SUPER_CHACA"]["ingresos"] == before
    history = s.historial(conn, user["id"])["escuela"]
    assert history[0]["estado_visible"] == "RETIRADO"
    following = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    with pytest.raises(s.ErrorValidacion):
        s.renovar_escuela(conn, user["id"], inscription["id"], {"periodo": following.strftime("%Y-%m")})
    school.cambiar_estado_alumno(conn, admin, "web", inscription["id"], "restore")
    assert s.renovar_escuela(conn, user["id"], inscription["id"], {"periodo": following.strftime("%Y-%m")})["id"]
