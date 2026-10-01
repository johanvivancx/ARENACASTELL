"""El cliente solicita la revisión; solo un administrador puede confirmar el abono."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
import pytest
import services as s
from test_http_html import client


def admin_id(conn):
    return conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()['id']


def order(conn,user):
    return s.reservar(conn,user['id'],{'cancha_id':1,'tipo_evento':'HORA','horas':1,
        'hora':'10:00','fecha':str(datetime.now(s.TZ).date()+timedelta(days=5))})


def request_transfer(conn,user,oid,reference='BANCO-123'):
    result=s.pagar(conn,user['id'],oid,{'metodo':'TRANSFERENCIA','acepta_registro':True,
        'referencia_transferencia':reference,'aprobado':True,'efectivo_recibido':True,'rol':'ADMIN'})
    assert result['pendiente']
    return s.detalle_orden(conn,user['id'],oid)['revision_pago']


def test_transferencia_no_confirma_ni_envia_y_solo_admin_aprueba(conn,user):
    oid=order(conn,user)['id']
    revision=request_transfer(conn,user,oid)
    assert request_transfer(conn,user,oid)==revision
    detail=s.detalle_orden(conn,user['id'],oid)
    assert detail['estado']=='PENDIENTE' and detail['reserva']['estado']=='PENDIENTE'
    assert detail['pago'] is None and detail['correo'] is None
    with pytest.raises(s.HTTPError) as forbidden:
        s.revisar_transferencia(conn,user['id'],oid,{'revision':revision},aprobar=True)
    assert forbidden.value.status==403
    s.revisar_transferencia(conn,admin_id(conn),oid,{'revision':revision},aprobar=True)
    detail=s.detalle_orden(conn,user['id'],oid)
    assert detail['estado']=='PAGADA' and not detail['pago']['simulado']
    assert conn.execute('SELECT confirmado_por FROM pagos WHERE orden_id=%s',(oid,)).fetchone()['confirmado_por']==admin_id(conn)
    assert conn.execute('SELECT count(*) AS n FROM correo_salida').fetchone()['n']==1


def test_rechazo_visible_y_no_aprueba_una_referencia_que_cambio(conn,user):
    oid=order(conn,user)['id']; revision=request_transfer(conn,user,oid)
    s.revisar_transferencia(conn,admin_id(conn),oid,{'revision':revision,'motivo':'No consta el abono'},aprobar=False)
    detail=s.detalle_orden(conn,user['id'],oid)
    assert detail['estado']=='PENDIENTE' and detail['pago'] is None
    assert detail['motivo_rechazo_transferencia']=='No consta el abono'
    revised=request_transfer(conn,user,oid,'BANCO-CORREGIDO')
    assert revised>revision
    with pytest.raises(s.HTTPError) as stale:
        s.revisar_transferencia(conn,admin_id(conn),oid,{'revision':revision},aprobar=True)
    assert stale.value.status==409
    s.revisar_transferencia(conn,admin_id(conn),oid,{'revision':revised},aprobar=True)


def test_dos_aprobaciones_concurrentes_no_duplican(conn,user,database_url):
    oid=order(conn,user)['id']; revision=request_transfer(conn,user,oid); aid=admin_id(conn)
    conn.commit()
    def approve(_):
        with psycopg.connect(database_url,row_factory=dict_row) as c:
            return s.revisar_transferencia(c,aid,oid,{'revision':revision},aprobar=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert len(list(pool.map(approve,range(2))))==2
    assert conn.execute('SELECT count(*) AS n FROM pagos').fetchone()['n']==1
    assert conn.execute('SELECT count(*) AS n FROM correo_salida').fetchone()['n']==1


def test_api_cliente_no_puede_aprobar_y_admin_necesita_csrf(conn,user):
    from models import Usuario
    aid=admin_id(conn)
    row=conn.execute('SELECT * FROM usuarios WHERE id=%s',(aid,)).fetchone()
    administrator=Usuario.desde_fila(row); administrator.set_password('RevisionAdmin2027!')
    conn.execute('UPDATE usuarios SET password_hash=%s WHERE id=%s',(administrator.get_password_hash(),aid))
    oid=order(conn,user)['id']; revision=request_transfer(conn,user,oid); conn.commit()
    with client() as request:
        _,session,_=request('/api/session')
        _,session,_=request('/api/auth/login',{'email':user['email'],'password':'PruebaSegura!2026'},session['csrf'])
        path=f'/api/admin/orders/{oid}/approve-transfer'
        assert request(path,{'revision':revision},session['csrf'])[0]==403
        _,session,_=request('/api/auth/login',{'email':'revision@arena.test','password':'RevisionAdmin2027!'},session['csrf'])
        assert request(path,{'revision':revision})[0]==403
        assert request(path,{'revision':revision},session['csrf'])[0]==200
        assert request(path,{'revision':revision},session['csrf'])[0]==200
    assert conn.execute('SELECT count(*) AS n FROM pagos').fetchone()['n']==1


@pytest.mark.parametrize('start,end,allowed',[(1,10,False),(0,0,True),(-10,-1,False)])
def test_ventana_inscripcion_se_aplica_en_api_y_sql(conn,user,start,end,allowed):
    oid=s.inscribir_torneo(conn,user['id'],{'torneo_id':1,'equipo':'Equipo pendiente','acepta_reglamento':True})['id']
    conn.execute('UPDATE torneos SET inscripcion_desde=current_date+%s,inscripcion_hasta=current_date+%s WHERE id=1',(start,end))
    data={'torneo_id':1,'equipo':'Otro equipo','acepta_reglamento':True}
    if allowed:
        s.inscribir_torneo(conn,user['id'],data)
        conn.execute("UPDATE equipos SET estado='CONFIRMADO' WHERE orden_id=%s",(oid,))
    else:
        with pytest.raises(s.ErrorValidacion): s.inscribir_torneo(conn,user['id'],data)
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.transaction(): conn.execute("UPDATE equipos SET estado='CONFIRMADO' WHERE orden_id=%s",(oid,))


def test_migracion_repetible_conserva_pago_y_actualiza_calendario(conn,user):
    from conftest import confirmar_transferencia
    oid=order(conn,user)['id']
    confirmar_transferencia(conn,user['id'],oid,{'metodo':'TRANSFERENCIA','acepta_registro':True})
    previous=dict(s.detalle_orden(conn,user['id'],oid)['pago']); conn.commit()
    script=Path(__file__).resolve().parents[1]/'sql/migrations/007_aprobacion_y_calendario.sql'
    for _ in range(2): conn.execute(script.read_text(encoding='utf-8'))
    assert s.detalle_orden(conn,user['id'],oid)['pago']==previous
    t=conn.execute("SELECT * FROM torneos WHERE nombre='Pasochoa Cup · Sexta edición'").fetchone()
    assert str(t['inscripcion_desde'])=='2027-04-01'
    assert str(t['inscripcion_hasta'])=='2027-04-30'
    assert str(t['fecha_inicio'])=='2027-05-01'
