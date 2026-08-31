from pathlib import Path


def test_ejemplos_sql_pgadmin_y_call_real_sin_duplicar(conn):
    folder=Path(__file__).resolve().parents[1]/'sql/pgadmin'
    for step in sorted(folder.glob('*.sql')):
        if step.name[:2] in {'07','08','09','10'}:
            conn.execute(step.read_text(encoding='utf8'))
    result=conn.execute("SELECT count(*) AS cantidad,sum(monto) AS monto FROM pagos WHERE orden_id='10000000-0000-4000-8000-000000000001'").fetchone()
    assert result['cantidad']==1 and result['monto']==50
    assert conn.execute("SELECT estado FROM inscripciones_chaca WHERE orden_id='10000000-0000-4000-8000-000000000001'").fetchone()['estado']=='ACTIVA'
    assert conn.execute("SELECT estado FROM reservas WHERE orden_id='10000000-0000-4000-8000-000000000002'").fetchone()['estado']=='PENDIENTE'
