"""Servidor educativo sin Flask: HTTP estándar + archivos HTML + API JSON.

Solo escucha en loopback. Para Internet se necesita un servidor de producción,
HTTPS y una revisión de seguridad; no es una pasarela de pagos real.
"""

from datetime import date, datetime, time
from decimal import Decimal
from functools import partial
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote
import hmac
import json
import logging
import os
import re
import uuid
import psycopg

from db import conectar, ROOT
from models import ErrorValidacion
import services as s
import correos

STATIC = ROOT
ORIGIN = os.environ.get("APP_ORIGIN", "http://127.0.0.1:8765").rstrip("/")

# Lista explícita de recursos públicos. La raíz también contiene Python y .env:
# nunca se sirve completa, aunque index.html esté junto a esos archivos.
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


def json_default(value):
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, (Decimal, uuid.UUID)):
        return str(value)
    raise TypeError(type(value).__name__)


class Handler(SimpleHTTPRequestHandler):
    server_version = "ArenaCastell"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src https://www.google.com; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
        )
        super().end_headers()

    def log_message(self, fmt, *args):
        # No registrar contraseñas, cookies ni parámetros de recuperación.
        logging.info("%s %s", self.command, urlsplit(self.path).path)

    def list_directory(self, path):
        self.send_error(404)
        return None

    def do_GET(self):
        if urlsplit(self.path).path.startswith("/api/"):
            return self.api()
        return super().do_GET()

    def send_head(self):
        url = urlsplit(self.path)
        path = unquote(url.path)
        if path in LEGACY_PAGES:
            # Mantener enlaces antiguos, incluidos los de recuperación de cuenta.
            destination = LEGACY_PAGES[path] + ("?" + url.query if url.query else "")
            self.send_response(301)
            self.send_header("Location", destination)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        public_path = "/index.html" if path == "/" else path
        allowed = PUBLIC_FILES.get(public_path)
        if not allowed or not allowed.is_file():
            self.send_error(404)
            return None
        if path == "/":
            self.path = "/index.html" + ("?" + url.query if url.query else "")
        if Path(self.translate_path(self.path)).resolve() != allowed.resolve():
            self.send_error(404)
            return None
        return super().send_head()

    def do_POST(self):
        return self.api()

    def send_json(self, status, body, cookie=None):
        payload = json.dumps(body, default=json_default, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        if cookie:
            flags = "; Secure" if os.environ.get("COOKIE_SECURE", "false").lower() == "true" else ""
            self.send_header(
                "Set-Cookie",
                f"arena_session={cookie}; Path=/; HttpOnly; SameSite=Lax; Max-Age=28800{flags}",
            )
        self.end_headers()
        self.wfile.write(payload)

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
                    ):
                        s.limitar_acceso(conn, self.client_address[0] + path)
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
                    else:
                        uid = s.exigir_usuario(session)
                        result = self.private_route(conn, uid, path, data, params)
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


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    port = int(urlsplit(ORIGIN).port or 8765)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"ARENA CASTELL · {ORIGIN} · HTML + Python + PostgreSQL", flush=True)
    print("Ctrl+C para detener. Configuración del correo en docs/CORREOS_GMAIL.md.", flush=True)
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
