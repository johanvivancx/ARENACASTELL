"""Utilidades locales: inicialización, administrador y correo SMTP."""

import argparse
import getpass
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
from db import conectar, ROOT
from models import Administrador, ErrorValidacion
import correos


# Ejecuta comandos administrativos
def main():
    parser = argparse.ArgumentParser(description="Administración local de ARENA CASTELL, sin Flask")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="Inicializar el esquema en una base vacía")
    sub.add_parser("seed", help="Cargar catálogo inicial")
    sub.add_parser(
        "update-catalog", help="Actualizar el esquema y catálogo de flyers sin borrar operaciones"
    )
    sub.add_parser(
        "check-db", help="Verificar conexión, tablas y registros sin mostrar credenciales"
    )
    create_admin = sub.add_parser(
        "create-admin", help="Crear un administrador; la contraseña se solicita sin mostrarla"
    )
    create_admin.add_argument(
        "--render", action="store_true",
        help="Pedir la URL externa de Render en privado, sin cambiar el archivo .env"
    )
    sub.add_parser("check-email", help="Validar la configuración de correo sin enviar ni mostrar claves")
    sub.add_parser("test-email", help="Enviar un correo de prueba a SMTP_USER o MAIL_TEST_TO")
    sub.add_parser("send-emails", help="Procesar hasta diez correos pendientes")
    mailbox = sub.add_parser("outbox", help="Consultar mensajes como operador local")
    mailbox.add_argument("--email", required=True)
    args = parser.parse_args()
    previous_database_url = os.environ.get("DATABASE_URL")
    try:
        if args.command == "create-admin" and args.render:
            remote_url = getpass.getpass("External Database URL de Render (no se mostrará): ").strip()
            parsed = urlsplit(remote_url)
            if (parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname
                    or not parsed.hostname.endswith(".render.com") or not parsed.path.strip("/")):
                parser.error("La URL debe ser la External Database URL de PostgreSQL en Render.")
            os.environ["DATABASE_URL"] = remote_url
        if args.command == "check-email":
            correos.configuracion_envio()
            print(
                "Configuración de correo válida. No se inició sesión ni se envió correo. Ejecuta test-email para comprobar la entrega."
            )
            return
        if args.command == "test-email":
            correos.enviar_prueba()
            print(
                "El proveedor aceptó el correo de prueba. Revisa la entrada, spam y posibles rebotes."
            )
            return
        if args.command == "send-emails":
            print(correos.procesar_pendientes())
            return
        with conectar() as conn:
            if args.command == "check-db":
                current = conn.execute(
                    "SELECT current_database() AS base, current_user AS usuario"
                ).fetchone()
                print(
                    f"Conexión correcta: base {current['base']}, usuario PostgreSQL {current['usuario']}."
                )
                row = conn.execute(
                    "SELECT (SELECT count(*) FROM usuarios) AS usuarios, (SELECT count(*) FROM reservas) AS reservas, (SELECT count(*) FROM pagos) AS pagos"
                ).fetchone()
                print(
                    f"Registros: {row['usuarios']} usuarios, {row['reservas']} reservas, {row['pagos']} pagos simulados."
                )
                demo = conn.execute(
                    "SELECT count(*) AS total FROM usuarios WHERE email IN (%s, %s)",
                    ("admin@arena.test", "cliente@arena.test"),
                ).fetchone()["total"]
                if demo:
                    print(
                        "ADVERTENCIA: hay cuentas de demostración con claves antiguas conocidas. "
                        "Elimínalas o cambia sus contraseñas antes de publicar esta base."
                    )
            elif args.command == "init-db":
                if conn.execute("SELECT to_regclass('public.usuarios') AS existente").fetchone()[
                    "existente"
                ]:
                    parser.error(
                        "La base ya tiene tablas del proyecto. No se sobrescribió ningún dato."
                    )
                conn.execute((ROOT / "sql/schema.sql").read_text(encoding="utf8"))
                conn.execute((ROOT / "sql/migrations/011_vocalias_bar_deudas.sql").read_text(encoding="utf8"))
                conn.execute((ROOT / "sql/migrations/013_escuela_manual.sql").read_text(encoding="utf8"))
                print("Esquema inicializado.")
            elif args.command == "seed":
                conn.execute((ROOT / "sql/seed.sql").read_text(encoding="utf8"))
                print("Catálogo de demostración cargado.")
            elif args.command == "update-catalog":
                conn.execute((ROOT / "sql/migrations/001_flyers.sql").read_text(encoding="utf8"))
                conn.execute((ROOT / "sql/seed.sql").read_text(encoding="utf8"))
                print(
                    "Catálogo actualizado. Se conservaron las órdenes, pagos y listas existentes."
                )
            elif args.command == "create-admin":
                current = conn.execute("SELECT current_database() AS base").fetchone()
                database_host = urlsplit(os.environ.get("DATABASE_URL", "")).hostname or "desconocido"
                print(f"Base de destino: {current['base']} · servidor: {database_host}")
                if input("Escribe CREAR para confirmar este destino: ").strip() != "CREAR":
                    print("Operación cancelada. No se creó ninguna cuenta.")
                    return
                user = Administrador(
                    input("Nombre: "), input("Correo: "), input("Cédula: "), input("Celular: ")
                )
                if conn.execute("SELECT 1 FROM usuarios WHERE email=%s", (user.email,)).fetchone():
                    raise ErrorValidacion("Ya existe una cuenta con ese correo en esta base.")
                password = getpass.getpass("Contraseña (mínimo 10 caracteres): ")
                if password != getpass.getpass("Confirmar contraseña: "):
                    parser.error("Las contraseñas no coinciden.")
                user.set_password(password)
                insert_user(conn, user)
                print("Administrador creado. Inicia sesión desde el sitio.")
            elif args.command == "outbox":
                rows = conn.execute(
                    """SELECT c.asunto,c.cuerpo,c.creado_en,c.estado_envio,c.ultimo_error FROM correo_salida c
                    JOIN usuarios u ON u.id=c.usuario_id WHERE u.email=%s ORDER BY c.creado_en DESC LIMIT 20""",
                    (args.email.strip().lower(),),
                ).fetchall()
                if not rows:
                    print("No hay mensajes para ese correo.")
                for row in rows:
                    print(
                        f"\n{row['creado_en']} · {row['asunto']} · {row['estado_envio']} · {row['ultimo_error'] or ''}\n{row['cuerpo']}"
                    )
    except ErrorValidacion as error:
        print(f"No se completó la operación: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as error:
        print(
            f"No se completó la operación: {type(error).__name__}. Revisa la configuración o los datos.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    finally:
        if args.command == "create-admin" and args.render:
            if previous_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_database_url


# Crea una cédula ficticia
def cedula_demo(index):
    base = "17" + f"{index:07d}"
    total = 0
    for i, value in enumerate(base):
        number = int(value) * (2 if i % 2 == 0 else 1)
        total += number - 9 if number > 9 else number
    return base + str((10 - total % 10) % 10)


# Guarda un usuario local
def insert_user(conn, user):
    conn.execute(
        """INSERT INTO usuarios(nombre,email,cedula,telefono,password_hash,rol)
        VALUES(%s,%s,%s,%s,%s,%s)""",
        (user.nombre, user.email, user.cedula, user.telefono, user.get_password_hash(), user.rol),
    )


if __name__ == "__main__":
    main()
