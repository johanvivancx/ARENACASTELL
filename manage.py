"""Utilidades locales: inicialización, administrador y correo SMTP."""

import argparse
import getpass
import sys
from pathlib import Path
from db import conectar, ROOT
from models import Administrador, Cliente, ErrorValidacion
import correos


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
    sub.add_parser(
        "create-admin", help="Crear un administrador; la contraseña se solicita sin mostrarla"
    )
    sub.add_parser("create-demo", help="Crear dos cuentas ficticias para evaluación")
    sub.add_parser("check-email", help="Validar la configuración SMTP sin enviar ni mostrar claves")
    sub.add_parser("test-email", help="Enviar un correo de prueba a tu propia cuenta SMTP_USER")
    sub.add_parser("send-emails", help="Procesar hasta diez correos pendientes con SMTP")
    mailbox = sub.add_parser("outbox", help="Consultar mensajes como operador local")
    mailbox.add_argument("--email", required=True)
    args = parser.parse_args()
    try:
        if args.command == "check-email":
            correos.ConfiguracionSMTP.desde_entorno()
            print(
                "Configuración SMTP válida. No se inició sesión ni se envió correo. Ejecuta test-email para comprobar Gmail."
            )
            return
        if args.command == "test-email":
            correos.enviar_prueba()
            print(
                "El servidor SMTP aceptó el correo de prueba dirigido a tu propia cuenta. Revisa entrada y spam."
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
            elif args.command == "init-db":
                if conn.execute("SELECT to_regclass('public.usuarios') AS existente").fetchone()[
                    "existente"
                ]:
                    parser.error(
                        "La base ya tiene tablas del proyecto. No se sobrescribió ningún dato."
                    )
                conn.execute((ROOT / "sql/schema.sql").read_text(encoding="utf8"))
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
                user = Administrador(
                    input("Nombre: "), input("Correo: "), input("Cédula: "), input("Celular: ")
                )
                password = getpass.getpass("Contraseña (mínimo 10 caracteres): ")
                if password != getpass.getpass("Confirmar contraseña: "):
                    parser.error("Las contraseñas no coinciden.")
                user.set_password(password)
                insert_user(conn, user)
                print("Administrador creado. Inicia sesión desde el sitio.")
            elif args.command == "create-demo":
                for index, (clase, nombre, email, password) in enumerate(
                    [
                        (
                            Administrador,
                            "Administrador Demo",
                            "admin@arena.test",
                            "CastellAdmin!2026",
                        ),
                        (
                            Cliente,
                            "Cliente Demostración",
                            "cliente@arena.test",
                            "CastellCliente!2026",
                        ),
                    ],
                    1,
                ):
                    user = clase(nombre, email, cedula_demo(index), "0990000000")
                    user.set_password(password)
                    if not conn.execute(
                        "SELECT id FROM usuarios WHERE email=%s", (email,)
                    ).fetchone():
                        insert_user(conn, user)
                print(
                    "Cuentas ficticias disponibles. Credenciales en INICIAR.md; solo para demostración local."
                )
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


def cedula_demo(index):
    base = "17" + f"{index:07d}"
    total = 0
    for i, value in enumerate(base):
        number = int(value) * (2 if i % 2 == 0 else 1)
        total += number - 9 if number > 9 else number
    return base + str((10 - total % 10) % 10)


def insert_user(conn, user):
    conn.execute(
        """INSERT INTO usuarios(nombre,email,cedula,telefono,password_hash,rol)
        VALUES(%s,%s,%s,%s,%s,%s)""",
        (user.nombre, user.email, user.cedula, user.telefono, user.get_password_hash(), user.rol),
    )


if __name__ == "__main__":
    main()
