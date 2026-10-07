"""Casos de uso y transacciones. El navegador no decide precios ni permisos."""

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
from correos import encolar_correo, habilitado, url_publica
import hashlib
import os
import re
import secrets
import uuid

from models import (
    Cliente,
    Usuario,
    ReservaCancha,
    InscripcionTorneo,
    InscripcionSuperChaca,
    ErrorValidacion,
    texto,
    validar_cedula,
)

TZ = ZoneInfo("America/Guayaquil")
METHODS = {"TRANSFERENCIA", "EFECTIVO"}
EXPENSE_CATEGORIES = {"RESERVAS", "TORNEOS", "SUPER_CHACA"}


# Representa errores de solicitud
class HTTPError(Exception):
    # Guarda código y mensaje
    def __init__(self, status, message):
        self.status, self.message = status, message


# Protege tokens con hash
def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


# Valida numeros recibidos
def numero(value, field, minimum=1, maximum=2**31 - 1):
    try:
        n = int(str(value))
    except (ValueError, TypeError):
        raise ErrorValidacion(f"{field}: selecciona un número válido.") from None
    if not minimum <= n <= maximum:
        raise ErrorValidacion(f"{field}: elige un valor entre {minimum} y {maximum}.")
    return n


# Valida fechas recibidas
def fecha(value):
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ErrorValidacion("Selecciona una fecha válida.") from None


# Valida identificadores recibidos
def identificador(value):
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise ErrorValidacion("La referencia de la operación no es válida.") from None


# Oculta datos privados
def usuario_publico(row):
    return (
        {k: row[k] for k in ("id", "nombre", "email", "cedula", "telefono", "rol")} if row else None
    )


# Exige una sesion activa
def exigir_usuario(session):
    if not session or not session.get("usuario_id"):
        raise HTTPError(
            401, "Inicia sesión para continuar. Tus opciones permanecen en esta página."
        )
    return session["usuario_id"]


# Crea una sesion segura
def nueva_sesion(conn, usuario_id=None, anterior=None):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    if anterior:
        conn.execute("DELETE FROM sesiones WHERE token_hash=%s", (anterior,))
    conn.execute(
        "INSERT INTO sesiones(token_hash,usuario_id,csrf_token) VALUES(%s,%s,%s)",
        (sha(token), usuario_id, csrf),
    )
    return token, {"token_hash": sha(token), "usuario_id": usuario_id, "csrf_token": csrf}


# Busca la sesion actual
def obtener_sesion(conn, token):
    if not token or len(token) > 100:
        return None
    return conn.execute(
        "SELECT * FROM sesiones WHERE token_hash=%s AND vence_en>current_timestamp", (sha(token),)
    ).fetchone()


# Frena intentos repetidos
def limitar_acceso(conn, key):
    # Conserva intentos fallidos
    row = conn.execute(
        """INSERT INTO intentos_acceso(clave) VALUES(%s)
      ON CONFLICT(clave) DO UPDATE SET
      intentos=CASE WHEN intentos_acceso.inicio < current_timestamp-interval '15 minutes' THEN 1 ELSE intentos_acceso.intentos+1 END,
      inicio=CASE WHEN intentos_acceso.inicio < current_timestamp-interval '15 minutes' THEN current_timestamp ELSE intentos_acceso.inicio END
      RETURNING intentos""",
        (sha(key),),
    ).fetchone()
    conn.commit()
    if row["intentos"] > 10:
        raise HTTPError(
            429, "Se han realizado varios intentos. Espera 15 minutos y vuelve a intentar."
        )


# Crea una cuenta cliente
def registrar(conn, data):
    user = Cliente(
        data.get("nombre"),
        data.get("email"),
        str(data.get("cedula", "")),
        str(data.get("telefono", "")),
    )
    user.set_password(data.get("password"))
    if data.get("password") != data.get("confirmacion"):
        raise ErrorValidacion("Las contraseñas no coinciden.")
    if data.get("consentimiento") is not True:
        raise ErrorValidacion("Acepta el tratamiento de datos de tu cuenta.")
    return conn.execute(
        """INSERT INTO usuarios(nombre,email,cedula,telefono,password_hash)
       VALUES(%s,%s,%s,%s,%s) RETURNING *""",
        (user.nombre, user.email, user.cedula, user.telefono, user.get_password_hash()),
    ).fetchone()


# Comprueba correo y contraseña
def iniciar_sesion(conn, data):
    email = str(data.get("email", "")).strip().lower()[:254]
    row = conn.execute("SELECT * FROM usuarios WHERE email=%s", (email,)).fetchone()
    if row:
        valid = Usuario.desde_fila(row).verificar_password(data.get("password", ""))
    else:
        # Mantiene tiempos parecidos
        hashlib.pbkdf2_hmac(
            "sha256", str(data.get("password", ""))[:128].encode(), b"arena-login-dummy", 600_000
        )
        valid = False
    if not valid:
        raise HTTPError(401, "El correo o la contraseña no coinciden.")
    return row


# Crea enlace de recuperación
def solicitar_restablecimiento(conn, data):
    email = str(data.get("email", "")).strip().lower()[:254]
    user = conn.execute("SELECT id,email FROM usuarios WHERE email=%s", (email,)).fetchone()
    if user:
        token = secrets.token_urlsafe(32)
        conn.execute("UPDATE restablecimientos SET usado=true WHERE usuario_id=%s", (user["id"],))
        conn.execute(
            "INSERT INTO restablecimientos(token_hash,usuario_id,vence_en) VALUES(%s,%s,current_timestamp+interval '30 minutes')",
            (sha(token), user["id"]),
        )
        conn.execute(
            """UPDATE correo_salida SET estado_envio='CANCELADO',ultimo_error='ENLACE_REEMPLAZADO'
            WHERE usuario_id=%s AND orden_id IS NULL AND estado_envio='PENDIENTE'""",
            (user["id"],),
        )
        origin = url_publica()
        encolar_correo(
            conn,
            user["id"],
            user["email"],
            "Restablecer tu contraseña",
            f"Solicitaste restablecer tu contraseña de ARENA CASTELL.\n\nAbre {origin}/pages/restablecer_contrasena.html#token={token}\n\nEl enlace vence en 30 minutos y solo puede usarse una vez. Si no lo solicitaste, ignora este mensaje.",
            expires=datetime.now(TZ) + timedelta(minutes=30),
        )
    return {
        "message": (
            "Si el correo está registrado, recibirás un enlace para recuperar tu contraseña. Revisa también la carpeta de spam."
            if habilitado()
            else "Si el correo está registrado, tu solicitud quedó registrada. Comunícate con Arena Castell para recuperar tu acceso."
        )
    }


# Cambia la contraseña olvidada
def restablecer_password(conn, data):
    if data.get("password") != data.get("confirmacion"):
        raise ErrorValidacion("Las contraseñas no coinciden.")
    reset = conn.execute(
        """SELECT * FROM restablecimientos WHERE token_hash=%s
       AND NOT usado AND vence_en>current_timestamp FOR UPDATE""",
        (sha(str(data.get("token", ""))),),
    ).fetchone()
    if not reset:
        raise ErrorValidacion("El enlace ya no es válido. Solicita uno nuevo.")
    row = conn.execute(
        "SELECT * FROM usuarios WHERE id=%s FOR UPDATE", (reset["usuario_id"],)
    ).fetchone()
    user = Usuario.desde_fila(row)
    user.set_password(data.get("password"))
    conn.execute(
        "UPDATE usuarios SET password_hash=%s,session_version=session_version+1 WHERE id=%s",
        (user.get_password_hash(), user.id),
    )
    conn.execute("UPDATE restablecimientos SET usado=true WHERE usuario_id=%s", (user.id,))
    conn.execute(
        """UPDATE correo_salida SET estado_envio='CANCELADO',ultimo_error='ENLACE_UTILIZADO'
        WHERE usuario_id=%s AND orden_id IS NULL AND estado_envio='PENDIENTE'""",
        (user.id,),
    )
    conn.execute("DELETE FROM sesiones WHERE usuario_id=%s", (user.id,))
    return {"message": "Contraseña actualizada. Inicia sesión con tu nueva contraseña."}


# Consulta servicios disponibles
def catalogo(conn):
    return {
        "canchas": conn.execute("SELECT * FROM canchas ORDER BY id").fetchall(),
        "horarios_chaca": conn.execute(
            "SELECT * FROM horarios_chaca WHERE activo ORDER BY categoria,id"
        ).fetchall(),
        "torneos": conn.execute(
            """SELECT t.*, t.cupos-count(e.id) AS disponibles FROM torneos t
              LEFT JOIN equipos e ON e.torneo_id=t.id AND e.estado='CONFIRMADO'
              WHERE t.visible GROUP BY t.id ORDER BY t.fecha_inicio"""
        ).fetchall(),
        "inscripcion_chaca": str(InscripcionSuperChaca.INSCRIPCION),
        "mensualidad": str(InscripcionSuperChaca.MENSUALIDAD),
        "hoy": datetime.now(TZ).date(),
        "limite": datetime.now(TZ).date() + timedelta(days=89),
    }


# Busca horarios libres
def disponibilidad(conn, data):
    day = fecha(data.get("fecha"))
    cid = numero(data.get("cancha", 1), "Cancha")
    duration = numero(data.get("horas", 1), "Duración", 1, 6)
    rows = conn.execute(
        """SELECT inicio,fin FROM reservas WHERE cancha_id=%s AND estado='CONFIRMADA'
       AND (inicio AT TIME ZONE 'America/Guayaquil')::date=%s""",
        (cid, day),
    ).fetchall()
    slots = []
    now = datetime.now(TZ)
    for hour in range(8, 24 - duration):
        start = datetime.combine(day, datetime.min.time(), TZ) + timedelta(hours=hour)
        end = start + timedelta(hours=duration)
        available = now < start <= now + timedelta(days=90) and not any(
            start < r["fin"] and end > r["inicio"] for r in rows
        )
        slots.append({"hora": f"{hour:02}:00", "disponible": available})
    return {"horarios": slots}


# Usa costos polimórficos
def crear_orden(conn, uid, kind, description, service):
    return conn.execute(
        """INSERT INTO ordenes(usuario_id,tipo,descripcion,monto)
      VALUES(%s,%s,%s,%s) RETURNING *""",
        (uid, kind, description, service.calcular_costo()),
    ).fetchone()


# Crea una reserva pendiente
def reservar(conn, uid, data):
    court = conn.execute(
        "SELECT * FROM canchas WHERE id=%s", (numero(data.get("cancha_id", 1), "Cancha"),)
    ).fetchone()
    if not court:
        raise ErrorValidacion("La cancha seleccionada no existe.")
    duration = numero(data.get("horas"), "Duración", 1, 6)
    service = ReservaCancha(duration, data.get("tipo_evento"), court)
    day = fecha(data.get("fecha"))
    hour = str(data.get("hora", ""))
    if hour not in [f"{h:02}:00" for h in range(8, 23)]:
        raise ErrorValidacion("Selecciona una hora de inicio.")
    start = datetime.combine(day, datetime.strptime(hour, "%H:%M").time(), TZ)
    end = start + timedelta(hours=duration)
    order = crear_orden(
        conn, uid, "RESERVA", f"{court['nombre']} · {day:%d/%m/%Y} · {hour} · {duration} h", service
    )
    conn.execute(
        """INSERT INTO reservas(orden_id,cancha_id,tipo_evento,inicio,fin)
       VALUES(%s,%s,%s,%s,%s)""",
        (order["id"], court["id"], data.get("tipo_evento"), start, end),
    )
    return {"id": order["id"]}


def registrar_reserva_manual(conn, admin_uid, data):
    """Bloquea un horario acordado fuera de la web, sin registrar un cobro ficticio."""
    exigir_administrador(conn, admin_uid)
    cliente = texto(data.get("cliente"), "Nombre de contacto", 2, 70)
    telefono = str(data.get("telefono", "")).strip()
    if telefono and not re.fullmatch(r"\+?[0-9]{7,15}", telefono):
        raise ErrorValidacion("Celular: escribe de 7 a 15 dígitos, con + opcional.")
    # Un cliente antiguo puede omitir el importe; solo el formulario administrativo
    # nuevo permite pactar un valor distinto al calculado por la tarifa pública.
    raw_monto = data.get("monto")
    monto = None
    if raw_monto is not None:
        raw_monto = str(raw_monto).strip()
        if not re.fullmatch(r"\d{1,4}(?:\.\d{1,2})?", raw_monto):
            raise ErrorValidacion("Pago a recibir: escribe dólares con hasta dos decimales.")
        monto = Decimal(raw_monto)
        if monto <= 0:
            raise ErrorValidacion("El pago a recibir debe ser mayor que cero.")
    order = reservar(conn, admin_uid, data)
    descripcion = (
        f"Reserva manual · {cliente} · {telefono or 'sin celular'} · "
        f"{data['fecha']} {data['hora']}"
    )
    conn.execute(
        "UPDATE ordenes SET descripcion=%s, metodo_previsto='EFECTIVO', "
        "monto=COALESCE(%s, monto) WHERE id=%s",
        (descripcion, monto, order["id"]),
    )
    # El índice de exclusión de PostgreSQL impide dos reservas confirmadas solapadas.
    conn.execute(
        "UPDATE reservas SET estado='CONFIRMADA' WHERE orden_id=%s",
        (order["id"],),
    )
    return {"id": order["id"], "message": "Reserva registrada. El horario quedó ocupado; el cobro sigue pendiente."}


def cancelar_reserva_manual(conn, admin_uid, oid):
    """Libera un horario manual aún no cobrado, conservando el registro anulado."""
    exigir_administrador(conn, admin_uid)
    order = conn.execute(
        "SELECT * FROM ordenes WHERE id=%s FOR UPDATE", (identificador(oid),)
    ).fetchone()
    if not order or order["tipo"] != "RESERVA" or not order["descripcion"].startswith("Reserva manual · "):
        raise HTTPError(404, "No encontramos esa reserva manual.")
    if order["estado"] != "PENDIENTE":
        raise ErrorValidacion("Solo puedes anular reservas manuales pendientes de cobro.")
    reservation = conn.execute(
        "SELECT estado FROM reservas WHERE orden_id=%s FOR UPDATE", (order["id"],)
    ).fetchone()
    if not reservation or reservation["estado"] != "CONFIRMADA":
        raise ErrorValidacion("La reserva ya no ocupa ese horario.")
    conn.execute("UPDATE reservas SET estado='CANCELADA' WHERE orden_id=%s", (order["id"],))
    conn.execute("UPDATE ordenes SET estado='CANCELADA' WHERE id=%s", (order["id"],))
    return {"id": order["id"], "message": "Reserva manual anulada. El horario vuelve a estar disponible."}


# Crea un equipo pendiente
def inscribir_torneo(conn, uid, data):
    tournament = conn.execute(
        "SELECT * FROM torneos WHERE id=%s FOR UPDATE", (numero(data.get("torneo_id"), "Torneo"),)
    ).fetchone()
    if (
        not tournament
        or not tournament["abierto"]
        or tournament["fecha_inicio"] <= datetime.now(TZ).date()
        or (tournament.get("inscripcion_desde") and datetime.now(TZ).date() < tournament["inscripcion_desde"])
        or (tournament.get("inscripcion_hasta") and datetime.now(TZ).date() > tournament["inscripcion_hasta"])
    ):
        raise ErrorValidacion("Las inscripciones de este torneo están cerradas.")
    name = texto(data.get("equipo"), "Nombre del equipo", 2, 80)
    if data.get("acepta_reglamento") is not True:
        raise ErrorValidacion("Acepta las condiciones de inscripción del torneo.")
    order = crear_orden(
        conn,
        uid,
        "TORNEO",
        f"{tournament['nombre']} · {name}",
        InscripcionTorneo(tournament["costo"], max_jugadores=tournament["max_jugadores"]),
    )
    conn.execute(
        "INSERT INTO equipos(orden_id,torneo_id,nombre) VALUES(%s,%s,%s)",
        (order["id"], tournament["id"], name),
    )
    return {"id": order["id"]}


# Crea una inscripción escolar
def inscribir_escuela(conn, uid, data):
    born = fecha(data.get("nacimiento"))
    today = datetime.now(TZ).date()
    service = InscripcionSuperChaca(born, data.get("categoria"), today)
    name = texto(data.get("alumno"), "Nombre del alumno")
    cedula = str(data.get("cedula", ""))
    if not validar_cedula(cedula):
        raise ErrorValidacion("Revisa la cédula ecuatoriana del alumno.")
    if data.get("consentimiento") is not True:
        raise ErrorValidacion("El representante debe autorizar la inscripción del alumno.")
    order = crear_orden(
        conn, uid, "ESCUELA", f"Súper Chaca · {name} · {service.categoria}", service
    )
    schedule = numero(data.get("horario_id"), "Horario de entrenamiento")
    if not conn.execute(
        "SELECT id FROM horarios_chaca WHERE id=%s AND categoria=%s AND activo",
        (schedule, service.categoria),
    ).fetchone():
        raise ErrorValidacion("Selecciona un horario disponible para la categoría del alumno.")
    inscription = conn.execute(
        """INSERT INTO inscripciones_chaca(orden_id,alumno,cedula,nacimiento,categoria,horario_id)
      VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""",
        (order["id"], name, cedula, born, service.categoria, schedule),
    ).fetchone()
    conn.execute(
        "INSERT INTO mensualidades(orden_id,inscripcion_id,periodo) VALUES(%s,%s,%s)",
        (order["id"], inscription["id"], today.replace(day=1)),
    )
    return {"id": order["id"]}


# Protege operaciones ajenas
def orden_usuario(conn, uid, oid, lock=False):
    sql = "SELECT * FROM ordenes WHERE id=%s AND usuario_id=%s" + (" FOR UPDATE" if lock else "")
    order = conn.execute(sql, (identificador(oid), uid)).fetchone()
    if not order:
        raise HTTPError(404, "No encontramos esa operación en tu cuenta.")
    return order


# Consulta una operación propia
def detalle_orden(conn, uid, oid):
    order = orden_usuario(conn, uid, oid)
    order["pago"] = conn.execute(
        "SELECT metodo,referencia,pagado_en,monto,simulado FROM pagos WHERE orden_id=%s",
        (order["id"],),
    ).fetchone()
    order["reserva"] = conn.execute(
        "SELECT * FROM reservas WHERE orden_id=%s", (order["id"],)
    ).fetchone()
    order["equipo"] = conn.execute(
        "SELECT * FROM equipos WHERE orden_id=%s", (order["id"],)
    ).fetchone()
    order["escuela"] = conn.execute(
        """SELECT sc.*,m.periodo,h.dias,h.inicio,h.fin FROM mensualidades m JOIN inscripciones_chaca sc
        ON sc.id=m.inscripcion_id JOIN horarios_chaca h ON h.id=sc.horario_id WHERE m.orden_id=%s""",
        (order["id"],),
    ).fetchone()
    order["correo"] = conn.execute(
        """SELECT destinatario,estado_envio,enviado_en FROM correo_salida
        WHERE orden_id=%s ORDER BY id DESC LIMIT 1""",
        (order["id"],),
    ).fetchone()
    return order


# El cliente informa cómo pagará; solo administración confirma el dinero recibido.
def pagar(conn, uid, oid, data):
    method = data.get("metodo")
    if method not in METHODS:
        raise ErrorValidacion(
            "Selecciona transferencia bancaria o pago en cancha."
        )
    if data.get("acepta_registro", data.get("acepta_simulacion")) is not True:
        raise ErrorValidacion("Confirma que deseas registrar esta operación.")
    order = orden_usuario(conn, uid, oid, lock=True)
    if order["estado"] == "PAGADA":
        return {
            "id": order["id"],
            "message": "Esta operación ya estaba confirmada; no se duplicó el pago.",
        }
    if order["estado"] != "PENDIENTE":
        raise ErrorValidacion("La operación ya no está pendiente.")
    reference = texto(data.get("referencia_transferencia"), "Referencia de transferencia", 3, 100) if method == "TRANSFERENCIA" else None
    if order["metodo_previsto"] != method or order.get("referencia_transferencia") != reference:
        conn.execute(
            """UPDATE ordenes SET metodo_previsto=%s,referencia_transferencia=%s,
            motivo_rechazo_transferencia=NULL,revision_pago=revision_pago+1 WHERE id=%s""",
            (method, reference, order["id"]),
        )
    return {
        "id": order["id"], "pendiente": True,
        "message": "Transferencia pendiente de revisión por la administración." if method == "TRANSFERENCIA"
        else "Pago en cancha pendiente. La administración confirmará cuando reciba el dinero.",
    }


def _confirmar_pago(conn, admin_uid, order, method):
    """Se llama con la orden bloqueada, después de revisar su estado y modalidad."""
    exigir_administrador(conn, admin_uid)
    if order["estado"] != "PENDIENTE":
        raise ErrorValidacion("La operación ya no está pendiente.")
    uid = order["usuario_id"]
    if order["tipo"] in ("ESCUELA", "MENSUALIDAD"):
        conn.execute("CALL cobrar_mensualidad(%s,%s)", (order["id"], method))
    else:
        if order["tipo"] == "RESERVA":
            # Ordena reservas simultáneas
            # Conserva la regla SQL
            conn.execute(
                "SELECT c.id FROM canchas c JOIN reservas r ON r.cancha_id=c.id WHERE r.orden_id=%s FOR UPDATE OF c",
                (order["id"],),
            )
            reservation = conn.execute(
                "SELECT estado FROM reservas WHERE orden_id=%s", (order["id"],)
            ).fetchone()
            if not reservation or reservation["estado"] == "CANCELADA":
                raise ErrorValidacion("La reserva ya no está disponible para cobrar.")
            if reservation["estado"] == "PENDIENTE":
                conn.execute(
                    "UPDATE reservas SET estado='CONFIRMADA' WHERE orden_id=%s", (order["id"],)
                )
        elif order["tipo"] == "TORNEO":
            # Protege el último cupo
            conn.execute(
                "SELECT t.id FROM torneos t JOIN equipos e ON e.torneo_id=t.id WHERE e.orden_id=%s FOR UPDATE OF t",
                (order["id"],),
            )
            conn.execute("UPDATE equipos SET estado='CONFIRMADO' WHERE orden_id=%s", (order["id"],))
        conn.execute(
            "INSERT INTO pagos(orden_id,monto,metodo,referencia) VALUES(%s,%s,%s,%s)",
            (order["id"], order["monto"], method, f"AC-{order['id']}"),
        )
        conn.execute("UPDATE ordenes SET estado='PAGADA' WHERE id=%s", (order["id"],))
    conn.execute(
        "UPDATE pagos SET simulado=false,confirmado_por=%s,referencia=%s WHERE orden_id=%s",
        (admin_uid, f"AC-{order['id']}", order["id"]),
    )
    user = conn.execute("SELECT nombre,email FROM usuarios WHERE id=%s", (uid,)).fetchone()
    receipt = detalle_orden(conn, uid, order["id"])
    body = (
        f"Hola {user['nombre']}.\n\nGracias por elegir ARENA CASTELL.\n"
        f"{order['descripcion']}\nImporte registrado: ${order['monto']:.2f}\n"
        f"Método registrado: {method}\nOperación: {order['id']}\n"
        f"Fecha del registro: {receipt['pago']['pagado_en'].astimezone(TZ):%d/%m/%Y %H:%M} (Ecuador)\n"
    )
    if receipt["reserva"]:
        r = receipt["reserva"]
        body += f"Reserva: {r['inicio'].astimezone(TZ):%d/%m/%Y %H:%M} a {r['fin'].astimezone(TZ):%H:%M}.\n"
    if receipt["equipo"]:
        body += f"Equipo: {receipt['equipo']['nombre']}\n"
    if receipt["escuela"]:
        sc = receipt["escuela"]
        body += (
            f"Alumno: {sc['alumno']} · {sc['categoria']}\n"
            f"Horario: {sc['dias']}, {sc['inicio']:%H:%M} a {sc['fin']:%H:%M}\n"
            f"Mensualidad: {sc['periodo']:%m/%Y}\n"
        )
    body += (
        f"\nConsulta tus registros en {url_publica()}/pages/mis_reservas_inscripciones.html\n"
        "La administración confirmó el pago. Adjuntamos tu comprobante de registro en PDF.\n"
    )
    if order["tipo"] == "TORNEO":
        limit = conn.execute(
            "SELECT t.max_jugadores FROM torneos t JOIN equipos e ON e.torneo_id=t.id WHERE e.orden_id=%s",
            (order["id"],),
        ).fetchone()["max_jugadores"]
        body += f"\nDebes registrar la lista de jugadores (máximo {limit}) desde Mi actividad > Gestionar equipo antes del inicio del torneo."
    encolar_correo(conn, uid, user["email"], "Confirmación Arena Castell", body, order["id"])
    return {"id": order["id"], "message": "Pago registrado."}


# Exige rol administrador
def exigir_administrador(conn, uid):
    row = conn.execute("SELECT * FROM usuarios WHERE id=%s", (uid,)).fetchone()
    if not row or not Usuario.desde_fila(row).puede_administrar():
        raise HTTPError(403, "Esta sección está disponible solo para administradores.")


# Registra efectivo recibido
def cobrar_efectivo(conn, admin_uid, oid):
    """Solo el administrador registra el efectivo que recibió en la cancha."""
    exigir_administrador(conn, admin_uid)
    order = conn.execute(
        "SELECT * FROM ordenes WHERE id=%s FOR UPDATE", (identificador(oid),)
    ).fetchone()
    if not order:
        raise HTTPError(404, "No encontramos esa operación.")
    if order["estado"] == "PAGADA":
        payment = conn.execute(
            "SELECT metodo FROM pagos WHERE orden_id=%s", (order["id"],)
        ).fetchone()
        if payment and payment["metodo"] == "EFECTIVO":
            return {
                "id": order["id"],
                "message": "El efectivo ya estaba registrado; no se duplicó el pago.",
            }
        raise ErrorValidacion("La operación ya tiene un pago con otro método.")
    if order["metodo_previsto"] != "EFECTIVO":
        raise ErrorValidacion("Esta operación no tiene un pago en efectivo pendiente.")
    return _confirmar_pago(conn, admin_uid, order, "EFECTIVO")


def revisar_transferencia(conn, admin_uid, oid, data, *, aprobar):
    exigir_administrador(conn, admin_uid)
    order = conn.execute("SELECT * FROM ordenes WHERE id=%s FOR UPDATE", (identificador(oid),)).fetchone()
    if not order:
        raise HTTPError(404, "No encontramos esa operación.")
    revision = numero(data.get("revision"), "Revisión del pago", 0)
    if revision != order["revision_pago"]:
        raise HTTPError(409, "El cliente cambió la solicitud. Actualiza el panel y revisa los datos nuevamente.")
    if order["estado"] == "PAGADA":
        payment = conn.execute("SELECT metodo FROM pagos WHERE orden_id=%s", (order["id"],)).fetchone()
        if aprobar and payment and payment["metodo"] == "TRANSFERENCIA":
            return {"id": order["id"], "message": "La transferencia ya estaba aprobada; no se duplicó el pago."}
        raise ErrorValidacion("La operación ya tiene un pago registrado.")
    if order["estado"] != "PENDIENTE" or order["metodo_previsto"] != "TRANSFERENCIA":
        raise ErrorValidacion("No hay una transferencia pendiente de revisión para esta operación.")
    if aprobar:
        return _confirmar_pago(conn, admin_uid, order, "TRANSFERENCIA")
    reason = texto(data.get("motivo"), "Motivo del rechazo", 3, 250)
    conn.execute(
        """UPDATE ordenes SET metodo_previsto=NULL,motivo_rechazo_transferencia=%s,
        revision_pago=revision_pago+1 WHERE id=%s""", (reason, order["id"]),
    )
    return {"id": order["id"], "message": "Transferencia rechazada. El cliente puede corregirla desde su actividad."}


# Consulta actividad personal
def historial(conn, uid):
    return {
        "ordenes": conn.execute(
            """SELECT o.*,e.id AS equipo_id FROM ordenes o
            LEFT JOIN equipos e ON e.orden_id=o.id WHERE o.usuario_id=%s ORDER BY o.creado_en DESC""",
            (uid,),
        ).fetchall(),
        "escuela": conn.execute(
            """SELECT sc.*,v.mes_actual_pagado,v.ultimo_periodo,v.cuotas_pagadas
            FROM inscripciones_chaca sc JOIN ordenes o ON o.id=sc.orden_id
            JOIN vista_mensualidades_escuela v ON v.inscripcion_id=sc.id WHERE o.usuario_id=%s ORDER BY sc.id""",
            (uid,),
        ).fetchall(),
        "correos": conn.execute(
            """SELECT asunto,cuerpo,creado_en,estado_envio,enviado_en FROM correo_salida WHERE usuario_id=%s
            AND orden_id IS NOT NULL ORDER BY creado_en DESC LIMIT 20""",
            (uid,),
        ).fetchall(),
    }


# Protege equipos ajenos
def equipo_usuario(conn, uid, team_id):
    team = conn.execute(
        """SELECT e.*,t.nombre AS torneo,t.fecha_inicio,t.max_jugadores FROM equipos e JOIN ordenes o ON o.id=e.orden_id
       JOIN torneos t ON t.id=e.torneo_id WHERE e.id=%s AND o.usuario_id=%s""",
        (numero(team_id, "Equipo"), uid),
    ).fetchone()
    if not team:
        raise HTTPError(404, "No encontramos ese equipo en tu cuenta.")
    return team


# Consulta jugadores inscritos
def lista_equipo(conn, uid, team_id):
    team = equipo_usuario(conn, uid, team_id)
    team["jugadores"] = conn.execute(
        "SELECT id,nombre,cedula,posicion FROM jugadores WHERE equipo_id=%s ORDER BY posicion",
        (team["id"],),
    ).fetchall()
    return team


# Agrega un jugador
def agregar_jugador(conn, uid, team_id, data):
    team = equipo_usuario(conn, uid, team_id)
    if team["fecha_inicio"] <= datetime.now(TZ).date():
        raise ErrorValidacion("El torneo comenzó; la lista ya está cerrada.")
    name = texto(data.get("nombre"), "Nombre del jugador")
    cedula = str(data.get("cedula", ""))
    if not validar_cedula(cedula):
        raise ErrorValidacion("Revisa la cédula del jugador.")
    conn.execute(
        "INSERT INTO jugadores(equipo_id,nombre,cedula) VALUES(%s,%s,%s)",
        (team["id"], name, cedula),
    )
    return {"message": "Jugador registrado."}


# Retira un jugador
def retirar_jugador(conn, uid, team_id, data):
    team = equipo_usuario(conn, uid, team_id)
    if team["fecha_inicio"] <= datetime.now(TZ).date():
        raise ErrorValidacion("El torneo comenzó; la lista ya está cerrada.")
    conn.execute(
        "DELETE FROM jugadores WHERE id=%s AND equipo_id=%s",
        (numero(data.get("jugador_id"), "Jugador"), team["id"]),
    )
    return {"message": "Jugador retirado de la lista."}


# Crea otra mensualidad
def renovar_escuela(conn, uid, inscription_id, data):
    inscription = conn.execute(
        """SELECT sc.* FROM inscripciones_chaca sc JOIN ordenes o ON o.id=sc.orden_id
      WHERE sc.id=%s AND o.usuario_id=%s FOR UPDATE OF sc""",
        (numero(inscription_id, "Inscripción"), uid),
    ).fetchone()
    if not inscription or inscription["estado"] != "ACTIVA":
        raise ErrorValidacion("Necesitas una inscripción activa para pagar otra mensualidad.")
    period = fecha(str(data.get("periodo", "")) + "-01")
    current = datetime.now(TZ).date().replace(day=1)
    following = (current + timedelta(days=32)).replace(day=1)
    if not inscription["fecha_inscripcion"].replace(day=1) <= period <= following:
        raise ErrorValidacion("Selecciona un mes desde tu inscripción hasta el próximo mes.")
    existing = conn.execute(
        "SELECT orden_id FROM mensualidades WHERE inscripcion_id=%s AND periodo=%s",
        (inscription["id"], period),
    ).fetchone()
    if existing:
        return {"id": existing["orden_id"]}
    # Conserva la categoría inicial
    service = InscripcionSuperChaca(
        inscription["nacimiento"], inscription["categoria"], inscription["fecha_inscripcion"], renovacion=True
    )
    order = crear_orden(
        conn, uid, "MENSUALIDAD", f"Súper Chaca · {inscription['alumno']} · {period:%m/%Y}", service
    )
    conn.execute(
        "INSERT INTO mensualidades(orden_id,inscripcion_id,periodo) VALUES(%s,%s,%s)",
        (order["id"], inscription["id"], period),
    )
    return {"id": order["id"]}


# Actualiza datos personales
def actualizar_perfil(conn, uid, data):
    row = conn.execute("SELECT * FROM usuarios WHERE id=%s", (uid,)).fetchone()
    user = Cliente(
        data.get("nombre"),
        data.get("email", row["email"]),
        str(data.get("cedula", row["cedula"])),
        str(data.get("telefono", "")),
    )
    if (user.email != row["email"] or user.cedula != row["cedula"]) and not Usuario.desde_fila(
        row
    ).verificar_password(data.get("password_actual", "")):
        raise ErrorValidacion("Para cambiar tu correo o cédula, confirma tu contraseña actual.")
    conn.execute(
        "UPDATE usuarios SET nombre=%s,telefono=%s,email=%s,cedula=%s WHERE id=%s",
        (user.nombre, user.telefono, user.email, user.cedula, uid),
    )
    return {"message": "Tu perfil se actualizó correctamente."}


# Registra un gasto verificable; nunca se descuenta de una orden o pago.
def registrar_gasto(conn, admin_uid, data):
    exigir_administrador(conn, admin_uid)
    categoria = str(data.get("categoria", ""))
    if categoria not in EXPENSE_CATEGORIES:
        raise ErrorValidacion("Selecciona reservas, torneos o Súper Chaca para el gasto.")
    concepto = texto(data.get("concepto"), "Concepto del gasto", 3, 180)
    raw = str(data.get("monto", ""))
    if not re.fullmatch(r"\d{1,7}(?:\.\d{1,2})?", raw):
        raise ErrorValidacion("Monto: escribe dólares con hasta dos decimales.")
    try:
        monto = Decimal(raw)
    except InvalidOperation:
        raise ErrorValidacion("Monto: escribe una cantidad válida.") from None
    if monto <= 0:
        raise ErrorValidacion("El gasto debe ser mayor que cero.")
    dia = fecha(data.get("fecha_gasto"))
    if not date(2000, 1, 1) <= dia <= datetime.now(TZ).date():
        raise ErrorValidacion("La fecha del gasto debe ser de hoy o anterior.")
    row = conn.execute(
        """INSERT INTO gastos(categoria,concepto,monto,fecha_gasto,registrado_por)
           VALUES(%s,%s,%s,%s,%s) RETURNING id""",
        (categoria, concepto, monto, dia, admin_uid),
    ).fetchone()
    return {"id": row["id"], "message": "Gasto registrado en el control financiero."}


def anular_gasto(conn, admin_uid, expense_id, data):
    """Corrige errores conservando el registro y su autoría."""
    exigir_administrador(conn, admin_uid)
    motivo = texto(data.get("motivo"), "Motivo de anulación", 3, 250)
    expense = conn.execute(
        "SELECT id,anulado_en FROM gastos WHERE id=%s FOR UPDATE",
        (numero(expense_id, "Gasto"),),
    ).fetchone()
    if not expense:
        raise HTTPError(404, "No encontramos ese gasto.")
    if expense["anulado_en"]:
        raise ErrorValidacion("Este gasto ya fue anulado.")
    conn.execute(
        """UPDATE gastos SET anulado_en=current_timestamp,anulado_por=%s,
           motivo_anulacion=%s WHERE id=%s""",
        (admin_uid, motivo, expense["id"]),
    )
    return {"id": expense["id"], "message": "Gasto anulado; el saldo fue recalculado."}


# La limpieza conserva cuentas administradoras, catálogos y resultados de Copa.
RESET_TABLES = {
    "clientes": "usuarios WHERE rol='CLIENTE'",
    "ordenes": "ordenes",
    "reservas": "reservas",
    "pagos": "pagos",
    "gastos": "gastos",
    "equipos": "equipos",
    "jugadores": "jugadores",
    "inscripciones": "inscripciones_chaca",
    "mensualidades": "mensualidades",
    "correos": "correo_salida",
}


def resumen_datos_prueba(conn, admin_uid):
    exigir_administrador(conn, admin_uid)
    return {
        name: conn.execute(f"SELECT count(*) AS total FROM {table}").fetchone()["total"]
        for name, table in RESET_TABLES.items()
    }


def limpiar_datos_prueba(conn, admin_uid, data, ip_address=""):
    """Borra datos operativos de prueba en una transacción, conservando el torneo."""
    exigir_administrador(conn, admin_uid)
    limitar_acceso(conn, f"admin-reset:{admin_uid}:{ip_address}")
    if data.get("confirmacion") != "BORRAR DATOS DE PRUEBA":
        raise ErrorValidacion("Escribe BORRAR DATOS DE PRUEBA para confirmar.")
    admin = conn.execute("SELECT * FROM usuarios WHERE id=%s", (admin_uid,)).fetchone()
    if not Usuario.desde_fila(admin).verificar_password(data.get("password", "")):
        raise HTTPError(401, "La contraseña de administrador no coincide.")
    expected = data.get("resumen")
    if not isinstance(expected, dict) or set(expected) != set(RESET_TABLES) or any(
        type(value) is not int or value < 0 for value in expected.values()
    ):
        raise ErrorValidacion("Actualiza la vista previa antes de limpiar los datos.")
    conn.execute("SET LOCAL lock_timeout = '5s'")
    conn.execute(
        "LOCK TABLE usuarios,ordenes,reservas,pagos,gastos,equipos,jugadores,"
        "inscripciones_chaca,mensualidades,correo_salida,restablecimientos,"
        "sesiones,intentos_acceso IN ACCESS EXCLUSIVE MODE"
    )
    current = resumen_datos_prueba(conn, admin_uid)
    if current != expected:
        raise HTTPError(409, "Los registros cambiaron. Actualiza la vista previa antes de continuar.")
    for table in (
        "correo_salida", "jugadores", "mensualidades", "pagos", "gastos",
        "reservas", "equipos", "inscripciones_chaca", "ordenes", "restablecimientos",
    ):
        conn.execute(f"DELETE FROM {table}")
    conn.execute(
        "DELETE FROM sesiones WHERE usuario_id IS NULL "
        "OR usuario_id IN (SELECT id FROM usuarios WHERE rol='CLIENTE')"
    )
    conn.execute("DELETE FROM usuarios WHERE rol='CLIENTE'")
    conn.execute("DELETE FROM intentos_acceso")
    return {
        "eliminados": current,
        "message": "Datos de prueba eliminados. Administradores, catálogos y Copa Castell se conservaron.",
    }


# Consulta reportes administrativos
def reportes(conn, uid, data):
    exigir_administrador(conn, uid)
    start = fecha(data["desde"]) if data.get("desde") else date(2000, 1, 1)
    end = fecha(data["hasta"]) if data.get("hasta") else datetime.now(TZ).date()
    if start > end:
        raise ErrorValidacion("La fecha inicial debe ser anterior a la final.")
    payments = conn.execute(
        """SELECT * FROM vista_reporte_administrador
       WHERE (pagado_en AT TIME ZONE 'America/Guayaquil')::date BETWEEN %s AND %s ORDER BY pagado_en DESC""",
        (start, end),
    ).fetchall()
    received = conn.execute(
        """SELECT o.tipo,coalesce(sum(p.monto),0) AS total
           FROM pagos p JOIN ordenes o ON o.id=p.orden_id
           WHERE p.simulado=false AND o.estado='PAGADA'
           GROUP BY o.tipo"""
    ).fetchall()
    expenses = conn.execute(
        """SELECT g.id,g.categoria,g.concepto,g.monto,g.fecha_gasto,g.creado_en,
           g.anulado_en,g.motivo_anulacion,u.nombre AS registrado_por,
           a.nombre AS anulado_por
           FROM gastos g JOIN usuarios u ON u.id=g.registrado_por
           LEFT JOIN usuarios a ON a.id=g.anulado_por
           ORDER BY g.fecha_gasto DESC,g.id DESC"""
    ).fetchall()
    incomes = {kind: Decimal("0") for kind in ("RESERVA", "TORNEO", "ESCUELA", "MENSUALIDAD")}
    for row in received:
        incomes[row["tipo"]] = row["total"]
    spent = {category: Decimal("0") for category in EXPENSE_CATEGORIES}
    for row in expenses:
        if row["anulado_en"] is None:
            spent[row["categoria"]] += row["monto"]
    categories = {
        "RESERVAS": incomes["RESERVA"],
        "TORNEOS": incomes["TORNEO"],
        "SUPER_CHACA": incomes["ESCUELA"] + incomes["MENSUALIDAD"],
    }
    finance = {
        category: {"ingresos": income, "gastos": spent[category], "saldo": income - spent[category]}
        for category, income in categories.items()
    }
    finance["GENERAL"] = {
        key: sum((values[key] for values in finance.values()), Decimal("0"))
        for key in ("ingresos", "gastos", "saldo")
    }
    finance["SUPER_CHACA"]["inscripciones"] = incomes["ESCUELA"]
    finance["SUPER_CHACA"]["mensualidades"] = incomes["MENSUALIDAD"]
    return {
        "pagos": payments,
        "gastos": expenses,
        "finanzas": finance,
        "efectivo_pendiente": conn.execute(
            """SELECT o.id,o.descripcion,o.monto,o.creado_en,
                u.nombre AS titular FROM ordenes o JOIN usuarios u ON u.id=o.usuario_id
                WHERE o.estado='PENDIENTE' AND o.metodo_previsto='EFECTIVO'
                ORDER BY o.creado_en,o.id"""
        ).fetchall(),
        "transferencias_pendientes": conn.execute(
            """SELECT o.id,o.descripcion,o.monto,o.creado_en,o.referencia_transferencia,
                o.revision_pago,u.nombre AS titular FROM ordenes o JOIN usuarios u ON u.id=o.usuario_id
                WHERE o.estado='PENDIENTE' AND o.metodo_previsto='TRANSFERENCIA'
                ORDER BY o.creado_en,o.id"""
        ).fetchall(),
        "correos": conn.execute(
            """SELECT id,asunto,destinatario,estado_envio,intentos,ultimo_error,creado_en,enviado_en
                FROM correo_salida ORDER BY creado_en DESC LIMIT 100"""
        ).fetchall(),
        "reservas": conn.execute(
            """SELECT r.id,r.inicio,r.fin,r.tipo_evento,r.estado,
                c.nombre AS cancha,u.nombre AS titular,u.email,u.telefono,
                o.id AS orden_id,o.monto,o.estado AS estado_pago,o.descripcion AS detalle,
                o.descripcion LIKE 'Reserva manual · %' AS manual
                FROM reservas r JOIN canchas c ON c.id=r.cancha_id
                JOIN ordenes o ON o.id=r.orden_id JOIN usuarios u ON u.id=o.usuario_id
                ORDER BY r.inicio DESC,r.id DESC"""
        ).fetchall(),
        "operaciones": conn.execute(
            """SELECT o.id,o.creado_en,o.tipo,o.descripcion,o.monto,o.estado,
                u.nombre AS titular,u.email FROM ordenes o JOIN usuarios u ON u.id=o.usuario_id
                ORDER BY o.creado_en DESC,o.id"""
        ).fetchall(),
        "escuela": conn.execute(
            "SELECT * FROM vista_mensualidades_escuela ORDER BY alumno"
        ).fetchall(),
        "ocupacion": conn.execute(
            "SELECT * FROM vista_ocupacion_cancha ORDER BY mes DESC NULLS LAST"
        ).fetchall(),
        "resumen": {
            "ingresos": sum(p["monto"] for p in payments),
            "pagos": len(payments),
            "reservas": sum(p["tipo"] == "RESERVA" for p in payments),
            "equipos": sum(p["tipo"] == "TORNEO" for p in payments),
        },
    }
