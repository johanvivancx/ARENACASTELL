"""Conexiones cortas y transacciones PostgreSQL; nunca se usa SQLite."""
import os
from contextlib import contextmanager
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


@contextmanager
def conectar():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Configura DATABASE_URL en .env; consulta README.md.")
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=5,
                         options="-c timezone=America/Guayaquil -c statement_timeout=10000") as conn:
        yield conn
