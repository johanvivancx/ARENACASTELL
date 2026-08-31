import os
from pathlib import Path
import sys
import uuid
import pytest
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import db  # Carga .env, sin establecer ninguna conexión.
from manage import cedula_demo
import services as s


@pytest.fixture(scope="session")
def database_url():
    original = os.environ.get("TEST_DATABASE_ADMIN_URL") or os.environ.get("DATABASE_URL")
    if not original:
        pytest.skip("Configura DATABASE_URL con un rol local que pueda crear la base aislada de pruebas.")
    config=conninfo_to_dict(original)
    name="test_arena_"+uuid.uuid4().hex[:12]
    admin=make_conninfo(**{**config,"dbname":"postgres"})
    url=make_conninfo(**{**config,"dbname":name})
    with psycopg.connect(admin,autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    with psycopg.connect(url) as conn:
        # Verificar los mismos pasos independientes que se ejecutan en pgAdmin.
        for step in sorted((ROOT/"sql/pgadmin").glob('*.sql')):
            if step.name[:2] in {'02','03','04','05','06'}:
                conn.execute(step.read_text(encoding='utf8'))
    yield url
    # Se elimina únicamente la base aleatoria que esta fixture creó.
    assert name.startswith("test_arena_") and len(name)==23
    with psycopg.connect(admin,autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def conn(database_url,monkeypatch):
    monkeypatch.setenv("DATABASE_URL",database_url)
    with psycopg.connect(database_url,row_factory=dict_row,options="-c timezone=America/Guayaquil") as connection:
        assert connection.info.dbname.startswith("test_arena_")
        connection.execute("TRUNCATE usuarios,torneos,canchas,horarios_chaca,intentos_acceso RESTART IDENTITY CASCADE")
        connection.execute((ROOT/"sql/seed.sql").read_text(encoding="utf8"))
        connection.execute("UPDATE torneos SET nombre='Torneo de prueba', fecha_inicio=current_date+30, abierto=true, max_jugadores=20 WHERE id=1")
        connection.commit()
        yield connection


@pytest.fixture
def user(conn):
    return s.registrar(conn,{
        "nombre":"Persona de Prueba","email":"prueba@arena.test","cedula":cedula_demo(101),
        "telefono":"0990000000","password":"PruebaSegura!2026","confirmacion":"PruebaSegura!2026","consentimiento":True})


@pytest.fixture
def pay_data():
    return {"metodo":"TRANSFERENCIA","acepta_simulacion":True}


@pytest.fixture(autouse=True)
def impedir_envios_reales(monkeypatch):
    import correos
    monkeypatch.setenv("SMTP_ENABLED","false")
    def blocked(*args,**kwargs):
        raise AssertionError("Las pruebas no pueden conectar a un servidor SMTP real.")
    monkeypatch.setattr(correos.smtplib,"SMTP",blocked)
    monkeypatch.setattr(correos.smtplib,"SMTP_SSL",blocked)
