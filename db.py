"""Conexiones cortas y transacciones PostgreSQL; nunca se usa SQLite."""
import os
import hashlib
from contextlib import contextmanager
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


# Abre la conexión PostgreSQL
@contextmanager
def conectar():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Configura DATABASE_URL en .env; consulta README.md.")
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=5,
                         options="-c timezone=America/Guayaquil -c statement_timeout=10000") as conn:
        yield conn


def preparar_control_financiero():
    """Crea la tabla nueva al iniciar, sin tocar órdenes ni pagos históricos."""
    with conectar() as conn:
        conn.execute((ROOT / "sql/migrations/008_control_financiero.sql").read_text(encoding="utf8"))
        conn.execute((ROOT / "sql/migrations/012_reservas_manuales_hoy.sql").read_text(encoding="utf8"))


def preparar_resultados_copa():
    """Habilita los resultados de Copa Castell sin cambiar el historial base."""
    with conectar() as conn:
        conn.execute((ROOT / "sql/migrations/009_resultados_copa.sql").read_text(encoding="utf8"))
        conn.execute((ROOT / "sql/migrations/018_estados_partidos.sql").read_text(encoding="utf8"))
        conn.execute((ROOT / "sql/migrations/019_programacion_copa.sql").read_text(encoding="utf8"))
        conn.execute((ROOT / "sql/migrations/024_formato_copas.sql").read_text(encoding="utf8"))
        conn.execute((ROOT / "sql/migrations/015_copa_mvp.sql").read_text(encoding="utf8"))


def preparar_movimientos_copa():
    """Crea el libro de caja operativo, separado del control financiero web."""
    with conectar() as conn:
        conn.execute((ROOT / "sql/migrations/010_movimientos_copa.sql").read_text(encoding="utf8"))
        conn.execute((ROOT / "sql/migrations/011_vocalias_bar_deudas.sql").read_text(encoding="utf8"))
        conn.execute((ROOT / "sql/migrations/020_inscripciones_copa.sql").read_text(encoding="utf8"))
        conn.execute((ROOT / "sql/migrations/021_corregir_carnets_colombia.sql").read_text(encoding="utf8"))
        conn.execute((ROOT / "sql/migrations/022_carnets_egipto.sql").read_text(encoding="utf8"))
        conn.execute((ROOT / "sql/migrations/023_anular_fiados_bar.sql").read_text(encoding="utf8"))
        conn.execute((ROOT / "sql/migrations/025_abonos_deudas_bar.sql").read_text(encoding="utf8"))
        conn.execute((ROOT / "sql/migrations/026_acuerdo_colombia.sql").read_text(encoding="utf8"))


def preparar_deudores_restaurante():
    """Crea el registro independiente del restaurante sin tocar cajas existentes."""
    with conectar() as conn:
        conn.execute((ROOT / "sql/migrations/027_deudores_restaurante.sql").read_text(encoding="utf8"))


def preparar_escuela_manual():
    """Crea el registro privado de alumnos y pagos manuales sin tocar cobros web."""
    with conectar() as conn:
        conn.execute((ROOT / "sql/migrations/013_escuela_manual.sql").read_text(encoding="utf8"))
        conn.execute((ROOT / "sql/migrations/016_retiro_alumnos_chaca.sql").read_text(encoding="utf8"))
        conn.execute((ROOT / "sql/migrations/017_anular_inscripcion_web_prueba.sql").read_text(encoding="utf8"))


def preparar_actividad_administrativa():
    """Guarda la autoría de los cambios administrativos futuros."""
    with conectar() as conn:
        conn.execute((ROOT / "sql/migrations/014_actividad_administrativa.sql").read_text(encoding="utf8"))


def preparar_cuadrangular_navideno():
    """Publica el torneo navideño en el catálogo de inscripciones web."""
    with conectar() as conn:
        conn.execute((ROOT / "sql/migrations/028_cuadrangular_navideno.sql").read_text(encoding="utf8"))


def retirar_administrador_comprometido():
    """Revoca la cuenta comprometida sin eliminar sus referencias históricas."""
    compromised_owner_hash = "b58fe7ac12514feabb0ba52adc8917253842ad8ea9fc8f22383d3a8123d2cf9b"
    with conectar() as conn:
        administrators = conn.execute(
            "SELECT id,email FROM usuarios WHERE rol='ADMIN' FOR UPDATE"
        ).fetchall()
        account = next(
            (
                row for row in administrators
                if hashlib.sha256(row["email"].strip().lower().encode()).hexdigest()
                == compromised_owner_hash
            ),
            None,
        )
        if not account:
            return
        account_id = account["id"]
        conn.execute(
            """UPDATE usuarios
               SET rol='CLIENTE',
                   email='cuenta-retirada-' || id || '@invalid.local',
                   password_hash='pbkdf2_sha256$600000$cuenta_retirada_segura$'
                     || repeat('0',64),
                   session_version=session_version+1
               WHERE id=%s""",
            (account_id,),
        )
        conn.execute("DELETE FROM sesiones WHERE usuario_id=%s", (account_id,))
        conn.execute("UPDATE restablecimientos SET usado=true WHERE usuario_id=%s", (account_id,))
        conn.execute(
            """UPDATE correo_salida
               SET estado_envio='CANCELADO',ultimo_error='CUENTA_COMPROMETIDA'
               WHERE usuario_id=%s AND estado_envio IN ('LOCAL','PENDIENTE','ERROR')""",
            (account_id,),
        )
