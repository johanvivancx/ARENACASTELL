# Prueba opciones administrativas

from datetime import datetime, timedelta
import pytest
from manage import cedula_demo, insert_user
from models import Administrador
import services as s


def test_admin_ve_pendientes_y_pagadas_cliente_solo_lo_suyo(conn,user,pay_data):
    other=s.registrar(conn,{'nombre':'Otra Persona','email':'otra@arena.test','cedula':cedula_demo(910),
        'telefono':'0990000000','password':'OtraClaveSegura!','confirmacion':'OtraClaveSegura!', 'consentimiento':True})
    admin=Administrador('Administrador Prueba','operador@arena.test',cedula_demo(911),'0990000000')
    admin.set_password('AdministradorSeguro!')
    insert_user(conn,admin)
    aid=conn.execute("SELECT id FROM usuarios WHERE email='operador@arena.test'").fetchone()['id']
    day=str(datetime.now(s.TZ).date()+timedelta(days=3))
    first=s.reservar(conn,user['id'],{'cancha_id':1,'tipo_evento':'HORA','fecha':day,'hora':'10:00','horas':1})
    second=s.reservar(conn,other['id'],{'cancha_id':1,'tipo_evento':'EVENTO','fecha':day,'hora':'12:00','horas':2})
    s.pagar(conn,user['id'],first['id'],pay_data)
    report=s.reportes(conn,aid,{})
    assert {r['estado_pago'] for r in report['reservas']}=={'PAGADA','PENDIENTE'}
    assert {o['id'] for o in report['operaciones']}=={first['id'],second['id']}
    assert len(report['pagos'])==1 and len(report['reservas'])==2
    s.solicitar_restablecimiento(conn,{'email':user['email']})
    mail_report=s.reportes(conn,aid,{})['correos']
    assert len(mail_report)==2
    assert all('cuerpo' not in row for row in mail_report)
    assert '#token=' not in str(mail_report)
    assert {o['id'] for o in s.historial(conn,user['id'])['ordenes']}=={first['id']}
    assert {o['id'] for o in s.historial(conn,other['id'])['ordenes']}=={second['id']}
    with pytest.raises(s.HTTPError) as forbidden:
        s.reportes(conn,user['id'],{})
    assert forbidden.value.status==403
