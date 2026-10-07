# Prueba opciones administrativas

from datetime import datetime, timedelta
import pytest
import psycopg
from manage import cedula_demo, insert_user
from models import Administrador
import services as s
from conftest import confirmar_transferencia


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
    confirmar_transferencia(conn,user['id'],first['id'],pay_data)
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


def test_reserva_manual_bloquea_horario_sin_inventar_un_pago(conn,user):
    admin_id=conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()['id']
    day=str(datetime.now(s.TZ).date()+timedelta(days=3))
    data={'cliente':'Contacto WhatsApp','telefono':'0991234567','cancha_id':1,
          'tipo_evento':'HORA','fecha':day,'hora':'12:00','horas':2}
    with pytest.raises(s.HTTPError) as forbidden:
        s.registrar_reserva_manual(conn,user['id'],data)
    assert forbidden.value.status==403
    assert conn.execute("SELECT count(*) AS n FROM reservas").fetchone()['n']==0

    order=s.registrar_reserva_manual(conn,admin_id,data)
    row=conn.execute("""SELECT r.estado AS reserva,o.estado AS pago,o.metodo_previsto,
                        o.descripcion FROM reservas r JOIN ordenes o ON o.id=r.orden_id
                        WHERE o.id=%s""",(order['id'],)).fetchone()
    assert (row['reserva'],row['pago'],row['metodo_previsto'])==('CONFIRMADA','PENDIENTE','EFECTIVO')
    assert 'Contacto WhatsApp' in row['descripcion']
    assert conn.execute("SELECT count(*) AS n FROM pagos").fetchone()['n']==0
    availability=s.disponibilidad(conn,{'fecha':day,'cancha':1,'horas':1})
    assert not next(slot for slot in availability['horarios'] if slot['hora']=='12:00')['disponible']
    assert not next(slot for slot in availability['horarios'] if slot['hora']=='13:00')['disponible']
    report=s.reportes(conn,admin_id,{})
    assert report['reservas'][0]['manual'] is True
    assert report['resumen']['pagos']==0 and len(report['efectivo_pendiente'])==1

    with pytest.raises(psycopg.IntegrityError):
        with conn.transaction():
            s.registrar_reserva_manual(conn,admin_id,{**data,'cliente':'Otro contacto','hora':'13:00'})
    assert conn.execute("SELECT count(*) AS n FROM reservas").fetchone()['n']==1

    s.cobrar_efectivo(conn,admin_id,order['id'])
    assert conn.execute("SELECT count(*) AS n FROM pagos").fetchone()['n']==1
    assert s.reportes(conn,admin_id,{})['resumen']['reservas']==1
    with pytest.raises(s.ErrorValidacion):
        s.cancelar_reserva_manual(conn,admin_id,order['id'])

    second=s.registrar_reserva_manual(conn,admin_id,{**data,'hora':'16:00'})
    assert not next(slot for slot in s.disponibilidad(conn,{'fecha':day,'cancha':1,'horas':1})['horarios']
                    if slot['hora']=='16:00')['disponible']
    with pytest.raises(s.HTTPError) as forbidden:
        s.cancelar_reserva_manual(conn,user['id'],second['id'])
    assert forbidden.value.status==403
    s.cancelar_reserva_manual(conn,admin_id,second['id'])
    assert next(slot for slot in s.disponibilidad(conn,{'fecha':day,'cancha':1,'horas':1})['horarios']
                if slot['hora']=='16:00')['disponible']
    report=s.reportes(conn,admin_id,{})
    assert any(row['orden_id']==second['id'] and row['estado']=='CANCELADA' for row in report['reservas'])
    assert all(row['orden_id']!=second['id'] for row in report['efectivo_pendiente'])
