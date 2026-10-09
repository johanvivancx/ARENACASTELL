"""Conexiones cortas y transacciones PostgreSQL; nunca se usa SQLite."""
import os
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


def preparar_resultados_copa():
    """Habilita los resultados de Copa Castell sin cambiar el historial base."""
    with conectar() as conn:
        conn.execute((ROOT / "sql/migrations/009_resultados_copa.sql").read_text(encoding="utf8"))


def preparar_movimientos_copa():
    """Crea el libro de caja operativo, separado del control financiero web."""
    with conectar() as conn:
        conn.execute((ROOT / "sql/migrations/010_movimientos_copa.sql").read_text(encoding="utf8"))
        conn.execute((ROOT / "sql/migrations/011_vocalias_bar_deudas.sql").read_text(encoding="utf8"))
