"""Servidor HTTP estándar + archivos HTML + API JSON.

Escucha en loopback localmente y en el puerto asignado por el alojamiento
cuando está presente PORT. HTTPS se termina en el proxy del alojamiento.
"""

from datetime import date, datetime, time
from decimal import Decimal
from functools import partial
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote
import hmac
import ipaddress
import json
import logging
import os
import re
import uuid
import psycopg

from db import conectar, preparar_control_financiero, preparar_resultados_copa, preparar_movimientos_copa, preparar_escuela_manual, preparar_actividad_administrativa, ROOT
from models import ErrorValidacion
import services as s
import copa
import copa_caja
import escuela_admin
import correos

STATIC = ROOT
ORIGIN = os.environ.get("APP_ORIGIN", "http://127.0.0.1:8765").rstrip("/")

# Publica solo archivos permitidos
# Protege archivos privados
PUBLIC_FILES = {"/index.html": ROOT / "index.html"}
for page in (ROOT / "pages").glob("*.html"):
    if page.resolve().parent == (ROOT / "pages").resolve():
        PUBLIC_FILES["/pages/" + page.name] = page
for asset in (ROOT / "assets").rglob("*"):
    relative = asset.relative_to(ROOT).as_posix()
    if (
        asset.is_file()
        and asset.suffix.lower()
        in {
            ".css",
            ".js",
            ".jpg",
            ".jpeg",
            ".png",
            ".svg",
            ".webp",
            ".ico",
            ".woff",
            ".woff2",
            ".ttf",
        }
        and not any(part.startswith(".") for part in asset.relative_to(ROOT).parts)
        and asset.resolve().is_relative_to((ROOT / "assets").resolve())
    ):
        PUBLIC_FILES["/" + relative] = asset
LEGACY_PAGES = {"/" + page.name: "/pages/" + page.name for page in (ROOT / "pages").glob("*.html")}
CLEAN_PAGES = {path.removesuffix(".html"): path for path in PUBLIC_FILES if path.startswith("/pages/") and path.endswith(".html")}


# Convierte datos para JSON
def json_default(value):
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, (Decimal, uuid.UUID)):
        return str(value)
    raise TypeError(type(value).__name__)


# Atiende solicitudes del navegador
class Handler(SimpleHTTPRequestHandler):
    server_version = "ArenaCastell"

    def setup(self):
        # Evita que una conexión incompleta retenga un hilo indefinidamente.
        self.request.settimeout(15)
        super().setup()

    # Define la carpeta pública
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    # Agrega cabeceras de seguridad
    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if urlsplit(ORIGIN).scheme == "https":
            self.send_header("Strict-Transport-Security", "max-age=15552000")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src https://www.google.com; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
        )
        super().end_headers()

    def client_ip(self):
        # En Render todo tráfico público pasa por su proxy; el primer X-Forwarded-For
        # identifica al cliente. Fuera de ese entorno no se confía en ese encabezado.
        if os.environ.get("PORT"):
            forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
            try:
                return str(ipaddress.ip_address(forwarded))
            except ValueError:
                pass
        return self.client_address[0]

    # Registra solicitudes sin claves
    def log_message(self, fmt, *args):
        # Oculta datos del registro
        logging.info("%s %s", self.command, urlsplit(self.path).path)

    # Bloquea listas de archivos
    def list_directory(self, path):
        self.send_error(404)
        return None

    # Atiende consultas GET
    def do_GET(self):
        if urlsplit(self.path).path.startswith("/api/"):
            return self.api()
        return super().do_GET()

    # Protege archivos privados
    def send_head(self):
        url = urlsplit(self.path)
        path = unquote(url.path)
        if path in LEGACY_PAGES:
            # Conserva enlaces anteriores
            destination = LEGACY_PAGES[path] + ("?" + url.query if url.query else "")
            self.send_response(301)
            self.send_header("Location", destination)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        public_path = "/index.html" if path == "/" else CLEAN_PAGES.get(path, path)
        allowed = PUBLIC_FILES.get(public_path)
        if not allowed or not allowed.is_file():
            self.send_error(404)
            return None
        if path == "/" or path in CLEAN_PAGES:
            self.path = public_path + ("?" + url.query if url.query else "")
        if Path(self.translate_path(self.path)).resolve() != allowed.resolve():
            self.send_error(404)
            return None
        return super().send_head()

    # Atiende solicitudes POST
    def do_POST(self):
        return self.api()

    # Devuelve respuestas JSON
    def send_json(self, status, body, cookie=None):
        payload = json.dumps(body, default=json_default, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        if cookie:
            secure = urlsplit(ORIGIN).scheme == "https" or os.environ.get("COOKIE_SECURE", "false").lower() == "true"
            flags = "; Secure" if secure else ""
            self.send_header(
                "Set-Cookie",
                f"arena_session={cookie}; Path=/; HttpOnly; SameSite=Lax; Max-Age=28800{flags}",
            )
        self.end_headers()
        self.wfile.write(payload)

    # Dirige las rutas API
    def api(self):
        cookie_out = None
        try:
            path = urlsplit(self.path).path.rstrip("/")
            params = {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}
            data = {}
            if self.command == "POST":
                if self.headers.get_content_type() != "application/json":
                    raise s.HTTPError(415, "El formulario debe enviarse como JSON.")
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    raise s.HTTPError(400, "Solicitud inválida.") from None
                if not 1 <= length <= 32768:
                    raise s.HTTPError(413, "El formulario es demasiado grande o está vacío.")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise s.HTTPError(400, "El formulario no tiene el formato esperado.")
            cookies = SimpleCookie()
            cookies.load(self.headers.get("Cookie", ""))
            token = cookies["arena_session"].value if "arena_session" in cookies else ""
            with conectar() as conn:
                session = s.obtener_sesion(conn, token)
                if self.command == "GET" and path == "/api/session":
                    if not session:
                        s.limitar_acceso(conn, "session:" + self.client_ip(), max_attempts=60)
                        cookie_out, session = s.nueva_sesion(conn)
                    user = (
                        conn.execute(
                            "SELECT * FROM usuarios WHERE id=%s", (session["usuario_id"],)
                        ).fetchone()
                        if session["usuario_id"]
                        else None
                    )
                    result = {
                        "usuario": s.usuario_publico(user),
                        "csrf": session["csrf_token"],
                        "simulacion": True,
                    }
                else:
                    if self.command == "POST":
                        csrf = self.headers.get("X-CSRF-Token", "")
                        if not session or not hmac.compare_digest(csrf, session["csrf_token"]):
                            raise s.HTTPError(
                                403,
                                "La sesión del formulario venció. Recarga la página y vuelve a intentar.",
                            )
                        if self.headers.get("Origin") not in (None, ORIGIN):
                            raise s.HTTPError(403, "El origen del formulario no está permitido.")
                    if self.command == "POST" and path in (
                        "/api/auth/login",
                        "/api/auth/register",
                        "/api/auth/forgot",
                        "/api/auth/reset",
                    ):
                        s.limitar_acceso(conn, "auth:" + self.client_ip() + path)
                        if path in ("/api/auth/login", "/api/auth/forgot"):
                            email = str(data.get("email", "")).strip().lower()[:254]
                            if email:
                                s.limitar_acceso(conn, path + ":" + email, max_attempts=20)
                    if path == "/api/auth/register" and self.command == "POST":
                        user = s.registrar(conn, data)
                        cookie_out, session = s.nueva_sesion(
                            conn, user["id"], session["token_hash"]
                        )
                        result = {"usuario": s.usuario_publico(user), "csrf": session["csrf_token"]}
                    elif path == "/api/auth/login" and self.command == "POST":
                        user = s.iniciar_sesion(conn, data)
                        cookie_out, session = s.nueva_sesion(
                            conn, user["id"], session["token_hash"]
                        )
                        result = {"usuario": s.usuario_publico(user), "csrf": session["csrf_token"]}
                    elif path == "/api/auth/logout" and self.command == "POST":
                        cookie_out, session = s.nueva_sesion(conn, anterior=session["token_hash"])
                        result = {"message": "Sesión cerrada.", "csrf": session["csrf_token"]}
                    elif path == "/api/auth/forgot" and self.command == "POST":
                        result = s.solicitar_restablecimiento(conn, data)
                    elif path == "/api/auth/reset" and self.command == "POST":
                        result = s.restablecer_password(conn, data)
                    elif path == "/api/catalog" and self.command == "GET":
                        result = s.catalogo(conn)
                    elif path == "/api/availability" and self.command == "GET":
                        result = s.disponibilidad(conn, params)
                    elif path == "/api/copa-castell" and self.command == "GET":
                        result = copa.estado_publico(conn)
                    else:
                        uid = s.exigir_usuario(session)
                        result = self.private_route(conn, uid, path, data, params)
                        if self.command == "POST" and path.startswith("/api/admin/"):
                            s.registrar_actividad_admin(conn, uid, path, result)
            self.send_json(200, result, cookie_out)
        except (ErrorValidacion, json.JSONDecodeError, UnicodeDecodeError) as error:
            self.send_json(
                400,
                {
                    "error": (
                        str(error)
                        if isinstance(error, ErrorValidacion)
                        else "No pudimos leer el formulario."
                    )
                },
            )
        except s.HTTPError as error:
            self.send_json(error.status, {"error": error.message})
        except psycopg.IntegrityError as error:
            if error.sqlstate == "23P01":
                message = "Ese horario acaba de ocuparse. No se registró ningún pago; selecciona otro horario."
            elif error.sqlstate == "23505":
                message = "Este registro ya existe. Revisa el correo, cédula, nombre del equipo o período e intenta nuevamente."
            elif error.diag.message_primary and error.diag.message_primary.startswith(
                (
                    "Elige ",
                    "La cancha ",
                    "Un equipo ",
                    "Primero ",
                    "El torneo ",
                    "Las inscripciones ",
                    "Solo se ",
                )
            ):
                message = error.diag.message_primary
            else:
                message = "Los datos no cumplen las reglas del servicio. Revisa fechas, categoría y valores del formulario."
            self.send_json(409, {"error": message})
        except (psycopg.OperationalError, RuntimeError):
            self.send_json(
                503,
                {
                    "error": "No pudimos conectar con PostgreSQL. El operador debe revisar DATABASE_URL y que la base esté iniciada."
                },
            )
        except Exception:
            logging.exception("Error interno al procesar %s", urlsplit(self.path).path)
            self.send_json(
                500,
                {
                    "error": "No se completó la operación. Tus cambios no se guardaron; intenta otra vez."
                },
            )

    # Protege rutas del cliente
    def private_route(self, conn, uid, path, data, params):
        method = self.command
        if path == "/api/reservations" and method == "POST":
            return s.reservar(conn, uid, data)
        if path == "/api/tournaments" and method == "POST":
            return s.inscribir_torneo(conn, uid, data)
        if path == "/api/school" and method == "POST":
            return s.inscribir_escuela(conn, uid, data)
        if path == "/api/history" and method == "GET":
            return s.historial(conn, uid)
        if path == "/api/profile" and method == "POST":
            return s.actualizar_perfil(conn, uid, data)
        if path == "/api/admin/reports" and method == "GET":
            return s.reportes(conn, uid, params)
        if path == "/api/admin/school" and method == "GET":
            return escuela_admin.resumen(conn, uid, params.get("periodo"))
        if path == "/api/admin/school/students" and method == "POST":
            return escuela_admin.registrar_alumno(conn, uid, data)
        if path == "/api/admin/school/payments" and method == "POST":
            return escuela_admin.registrar_pago(conn, uid, data)
        if path == "/api/admin/admins" and method == "POST":
            return s.crear_administrador(conn, uid, data, self.client_ip())
        if match := re.fullmatch(r"/api/admin/emails/(\d+)/queue-receipt", path):
            if method == "POST":
                return s.reencolar_comprobante(conn, uid, match[1])
        if path == "/api/admin/test-data-preview" and method == "GET":
            return {"resumen": s.resumen_datos_prueba(conn, uid)}
        if path == "/api/admin/test-data-reset" and method == "POST":
            return s.limpiar_datos_prueba(conn, uid, data, self.client_ip())
        if path == "/api/admin/copa-fixtures" and method == "GET":
            return copa.panel_admin(conn, uid)
        if path == "/api/admin/copa-caja" and method == "GET":
            return copa_caja.resumen(conn, uid, params.get("semana"))
        if path == "/api/admin/copa-caja" and method == "POST":
            return copa_caja.registrar(conn, uid, data)
        if path == "/api/admin/copa-bar-deudas" and method == "POST":
            return copa_caja.registrar_deuda_bar(conn, uid, data)
        if match := re.fullmatch(r"/api/admin/copa-bar-deudas/(\d+)/collect", path):
            if method == "POST":
                return copa_caja.cobrar_deuda_bar(conn, uid, match[1], data)
        if match := re.fullmatch(r"/api/admin/copa-caja/(\d+)/void", path):
            if method == "POST":
                return copa_caja.anular(conn, uid, match[1], data)
        if path == "/api/admin/copa-results" and method == "POST":
            return copa.guardar_resultado(conn, uid, data)
        if path == "/api/admin/expenses" and method == "POST":
            return s.registrar_gasto(conn, uid, data)
        if match := re.fullmatch(r"/api/admin/expenses/(\d+)/void", path):
            if method == "POST":
                return s.anular_gasto(conn, uid, match[1], data)
        if path == "/api/admin/reservations" and method == "POST":
            return s.registrar_reserva_manual(conn, uid, data)
        if path == "/api/admin/reservation-availability" and method == "GET":
            s.exigir_administrador(conn, uid)
            return s.disponibilidad(conn, params, incluir_horas_pasadas=True)
        if match := re.fullmatch(r"/api/admin/reservations/([^/]+)/cancel", path):
            if method == "POST":
                return s.cancelar_reserva_manual(conn, uid, match[1])
        if match := re.fullmatch(r"/api/admin/orders/([^/]+)/(approve-transfer|reject-transfer)", path):
            if method == "POST":
                return s.revisar_transferencia(conn, uid, match[1], data, aprobar=match[2] == "approve-transfer")
        if match := re.fullmatch(r"/api/admin/orders/([^/]+)/collect-cash", path):
            if method == "POST":
                return s.cobrar_efectivo(conn, uid, match[1])
        if match := re.fullmatch(r"/api/orders/([^/]+)(/pay)?", path):
            if match[2] and method == "POST":
                return s.pagar(conn, uid, match[1], data)
            if not match[2] and method == "GET":
                return s.detalle_orden(conn, uid, match[1])
        if match := re.fullmatch(r"/api/teams/(\d+)(/players|/remove)?", path):
            if not match[2] and method == "GET":
                return s.lista_equipo(conn, uid, match[1])
            if match[2] == "/players" and method == "POST":
                return s.agregar_jugador(conn, uid, match[1], data)
            if match[2] == "/remove" and method == "POST":
                return s.retirar_jugador(conn, uid, match[1], data)
        if match := re.fullmatch(r"/api/school/(\d+)/renew", path):
            if method == "POST":
                return s.renovar_escuela(conn, uid, match[1], data)
        raise s.HTTPError(404, "No encontramos esa operación.")


# El alojamiento asigna PORT; sin esa variable conservamos el puerto local.
def direccion_escucha():
    port = os.environ.get("PORT")
    if port is not None:
        port = int(port)
        if not 1 <= port <= 65535:
            raise ValueError("PORT debe estar entre 1 y 65535.")
        return "0.0.0.0", port
    return "127.0.0.1", int(urlsplit(ORIGIN).port or 8765)


# Inicia el servidor
def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    preparar_control_financiero()
    preparar_resultados_copa()
    preparar_movimientos_copa()
    preparar_escuela_manual()
    preparar_actividad_administrativa()
    httpd = ThreadingHTTPServer(direccion_escucha(), Handler)
    print(f"ARENA CASTELL · {ORIGIN} · HTML + Python + PostgreSQL", flush=True)
    print("Ctrl+C para detener. La configuración está explicada en INICIAR.md.", flush=True)
    worker = correos.iniciar_trabajador() if correos.habilitado() else None
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        if worker:
            worker[0].set()
            worker[1].join(timeout=2)


if __name__ == "__main__":
    main()
