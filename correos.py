"""Correo transaccional por SMTP con TLS y una cola persistente en PostgreSQL.

Utiliza SMTP con Jinja2 para HTML y ReportLab para PDF; no requiere Flask.
Un mensaje se envía solamente después de confirmar la transacción que lo creó.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import format_datetime
from threading import Event, Thread
from urllib.parse import urlsplit
import logging
import os
import re
import smtplib
import ssl

from db import conectar
from comprobantes import (
    LOGO,
    LOGO_CID,
    contexto_correo,
    renderizar_html,
    crear_pdf,
    datos_comprobante,
)
from jinja2 import TemplateError
from reportlab.platypus.doctemplate import LayoutError


class ConfiguracionCorreoError(ValueError):
    pass


class ContenidoCorreoError(ValueError):
    pass


def habilitado():
    return os.environ.get("SMTP_ENABLED", "false").strip().lower() == "true"


def direccion(value):
    value = str(value).strip().lower()
    if not re.fullmatch(r"[^\s@<>;,\"]+@[^\s@<>;,\"]+\.[^\s@<>;,\"]+", value) or len(value) > 254:
        raise ConfiguracionCorreoError("Configura una sola dirección de correo válida.")
    return value


def url_publica():
    value = os.environ.get("PUBLIC_BASE_URL", "").strip() or os.environ.get(
        "APP_ORIGIN", "http://127.0.0.1:8765"
    )
    url = urlsplit(value)
    local = url.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in {"", "/"}
        or (url.scheme != "https" and not (local and url.scheme == "http"))
    ):
        raise ConfiguracionCorreoError(
            "PUBLIC_BASE_URL debe ser la dirección HTTPS del sitio, o HTTP local para pruebas."
        )
    return value.rstrip("/")


@dataclass(frozen=True)
class ConfiguracionSMTP:
    host: str
    puerto: int
    usuario: str
    password: str = field(repr=False)
    seguridad: str = "starttls"
    nombre: str = "ARENA CASTELL"

    @classmethod
    def desde_entorno(cls):
        if not habilitado():
            raise ConfiguracionCorreoError(
                "Activa SMTP_ENABLED=true después de configurar tu cuenta."
            )
        host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
        security = os.environ.get("SMTP_SECURITY", "starttls").strip().lower()
        try:
            port = int(os.environ.get("SMTP_PORT", "587"))
        except ValueError:
            raise ConfiguracionCorreoError("SMTP_PORT debe ser un número.") from None
        user = direccion(os.environ.get("SMTP_USER", ""))
        password = os.environ.get("SMTP_PASSWORD", "").strip()
        if host == "smtp.gmail.com":
            password = password.replace(" ", "")  # Google muestra la clave en grupos.
        name = os.environ.get("MAIL_FROM_NAME", "ARENA CASTELL").strip()
        if (
            not host
            or re.search(r"[\s/@]", host)
            or not 1 <= port <= 65535
            or security not in {"starttls", "ssl"}
            or not password
            or "\n" in name
            or "\r" in name
        ):
            raise ConfiguracionCorreoError(
                "Revisa SMTP_HOST, SMTP_PORT, SMTP_SECURITY, SMTP_PASSWORD y MAIL_FROM_NAME."
            )
        url_publica()
        return cls(host, port, user, password, security, name)


def encolar_correo(conn, user_id, email, subject, body, order_id=None, expires=None):
    # LOCAL evita enviar mensajes históricos al activar SMTP posteriormente.
    state = "PENDIENTE" if habilitado() else "LOCAL"
    recipient = direccion(email)
    conn.execute(
        """INSERT INTO correo_salida
        (usuario_id,orden_id,destinatario,asunto,cuerpo,estado_envio,vence_en)
        VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(orden_id,asunto) DO NOTHING""",
        (user_id, order_id, recipient, subject, body, state, expires),
    )


def crear_mensaje(row, config):
    message = EmailMessage()
    message["From"] = Address(display_name=config.nombre, addr_spec=config.usuario)
    message["To"] = direccion(row["destinatario"])
    message["Subject"] = row["asunto"]
    message["Date"] = format_datetime(row["creado_en"])
    stamp = int(row["creado_en"].timestamp() * 1_000_000)
    message["Message-ID"] = f"<arena-{row['id']}-{stamp}@{config.usuario.split('@')[1]}>"
    message.set_content(row["cuerpo"], charset="utf-8")
    try:
        contexto = contexto_correo(row, url_publica())
        message.add_alternative(renderizar_html(contexto), subtype="html", charset="utf-8")
        message.get_payload()[-1].add_related(
            LOGO.read_bytes(),
            maintype="image",
            subtype="jpeg",
            cid=f"<{LOGO_CID}>",
            disposition="inline",
        )
        if contexto["comprobante"]:
            codigo = contexto["comprobante"]["codigo"].replace(" ", "-")
            message.add_attachment(
                crear_pdf(contexto),
                maintype="application",
                subtype="pdf",
                filename=f"comprobante-{codigo}.pdf",
            )
    except (TemplateError, LayoutError, OSError, ValueError, KeyError, TypeError):
        raise ContenidoCorreoError(
            "No se pudo preparar el diseño o el comprobante del correo."
        ) from None
    return message


def enviar_smtp(row, config):
    message = crear_mensaje(row, config)
    context = ssl.create_default_context()  # Verificar certificado y nombre del servidor.
    if config.seguridad == "ssl":
        smtp = smtplib.SMTP_SSL(config.host, config.puerto, timeout=10, context=context)
    else:
        smtp = smtplib.SMTP(config.host, config.puerto, timeout=10)
    try:
        smtp.ehlo()
        if config.seguridad == "starttls":
            smtp.starttls(context=context)  # Si TLS falla, no se autentica ni se envía.
            smtp.ehlo()
        smtp.login(config.usuario, config.password)
        refused = smtp.send_message(
            message, from_addr=config.usuario, to_addrs=[row["destinatario"]]
        )
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    finally:
        # Un fallo al cerrar después de DATA aceptado no debe provocar duplicados.
        try:
            smtp.quit()
        except (OSError, smtplib.SMTPException):
            smtp.close()


def codigo_error(error):
    # Nunca guardar la respuesta completa de SMTP: puede contener datos personales.
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return "AUTENTICACION_SMTP"
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        return "DESTINATARIO_RECHAZADO"
    if isinstance(error, (ssl.SSLError, smtplib.SMTPNotSupportedError)):
        return "TLS_NO_DISPONIBLE"
    if isinstance(error, ConfiguracionCorreoError):
        return "CONFIGURACION_SMTP"
    if isinstance(error, ContenidoCorreoError):
        return "CONTENIDO_CORREO"
    return "CONEXION_SMTP"


def procesar_pendientes(limite=10):
    """Una fila bloqueada por envío; varios procesos no toman la misma fila."""
    totals = {"enviados": 0, "fallidos": 0, "cancelados": 0}
    if not habilitado():
        return totals
    config = ConfiguracionSMTP.desde_entorno()
    for _ in range(min(max(limite, 1), 50)):
        with conectar() as conn:
            row = conn.execute(
                """SELECT c.*,u.email AS email_actual FROM correo_salida c
                JOIN usuarios u ON u.id=c.usuario_id
                WHERE c.estado_envio='PENDIENTE' AND c.intentos<5
                AND c.proximo_intento<=current_timestamp
                ORDER BY c.proximo_intento,c.id LIMIT 1 FOR UPDATE OF c SKIP LOCKED"""
            ).fetchone()
            if not row:
                break
            expired = row["vence_en"] and row["vence_en"] <= datetime.now(timezone.utc)
            if expired or row["destinatario"] != row["email_actual"]:
                conn.execute(
                    "UPDATE correo_salida SET estado_envio='CANCELADO',ultimo_error=%s WHERE id=%s",
                    ("ENLACE_VENCIDO" if expired else "CORREO_CAMBIADO", row["id"]),
                )
                totals["cancelados"] += 1
                continue
            try:
                if row.get("orden_id"):
                    try:
                        row["comprobante"] = datos_comprobante(
                            conn, row["orden_id"], row["usuario_id"]
                        )
                    except ValueError:
                        raise ContenidoCorreoError(
                            "No se encontró el pago del titular del mensaje."
                        ) from None
                enviar_smtp(row, config)
            except (OSError, smtplib.SMTPException, ValueError) as error:
                attempts = row["intentos"] + 1
                code = codigo_error(error)
                conn.execute(
                    """UPDATE correo_salida SET intentos=%s,estado_envio=%s,ultimo_error=%s,
                    proximo_intento=current_timestamp+(%s * interval '1 minute') WHERE id=%s""",
                    (
                        attempts,
                        "ERROR" if attempts >= 5 else "PENDIENTE",
                        code,
                        2 ** (attempts - 1),
                        row["id"],
                    ),
                )
                logging.warning("Correo %s pendiente de revisión: %s", row["id"], code)
                totals["fallidos"] += 1
            else:
                conn.execute(
                    """UPDATE correo_salida SET estado_envio='ENVIADO',intentos=intentos+1,
                    enviado_en=current_timestamp,ultimo_error=NULL WHERE id=%s""",
                    (row["id"],),
                )
                totals["enviados"] += 1
    return totals


def iniciar_trabajador():
    stop = Event()

    def run():
        while not stop.is_set():
            try:
                procesar_pendientes()
            except Exception:
                # No exponer DATABASE_URL, contraseñas, destinatarios ni tokens.
                logging.warning(
                    "Cola de correo pendiente: revisa PostgreSQL y la configuración SMTP."
                )
            stop.wait(10)

    thread = Thread(target=run, name="arena-correos", daemon=True)
    thread.start()
    return stop, thread


def enviar_prueba():
    """Envío explícito desde la terminal, solo a la propia cuenta configurada."""
    config = ConfiguracionSMTP.desde_entorno()
    enviar_smtp(
        {
            "id": "prueba",
            "creado_en": datetime.now(timezone.utc),
            "destinatario": config.usuario,
            "asunto": "Prueba de correo · ARENA CASTELL",
            "prueba": True,
            "cuerpo": "La conexión SMTP de ARENA CASTELL funciona.\nEste mensaje fue solicitado desde manage.py test-email.\nEl diseño y el PDF adjunto usan datos de ejemplo; no corresponden a una operación real.",
        },
        config,
    )
