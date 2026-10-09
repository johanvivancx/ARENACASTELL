# Prueba estructura HTML

from contextlib import contextmanager
from http.cookiejar import CookieJar
from http.server import ThreadingHTTPServer
from html.parser import HTMLParser
from pathlib import Path
from threading import Thread
from urllib.request import build_opener,HTTPCookieProcessor,Request
from urllib.error import HTTPError
from urllib.parse import urlsplit,unquote
import json
import server
import pytest
from server import Handler,STATIC
from manage import cedula_demo
from datetime import datetime,timedelta,date
import services as s


@contextmanager
def client():
    httpd=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=httpd.serve_forever,daemon=True);thread.start()
    opener=build_opener(HTTPCookieProcessor(CookieJar()))
    base=f'http://127.0.0.1:{httpd.server_port}'
    def request(path,data=None,csrf=None,method=None):
        headers={}
        if data is not None:headers['Content-Type']='application/json'
        if csrf:headers['X-CSRF-Token']=csrf
        req=Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
        try:r=opener.open(req,timeout=15)
        except HTTPError as error:r=error
        raw=r.read()
        return r.status, json.loads(raw) if 'application/json' in r.headers.get('Content-Type','') else raw, r.headers
    try:yield request
    finally:httpd.shutdown();httpd.server_close();thread.join(timeout=3)


def test_http_csrf_auth_et_controle_acces(conn):
    conn.commit()
    with client() as request:
        status,session,headers=request('/api/session')
        assert status==200 and session['usuario'] is None
        assert 'HttpOnly' in headers['Set-Cookie'] and 'SameSite=Lax' in headers['Set-Cookie']
        data={'nombre':'HTTP Usuario','cedula':cedula_demo(55),'telefono':'0990000000','email':'http@arena.test','password':'HTTPClaveSegura!','confirmacion':'HTTPClaveSegura!','consentimiento':True,'rol':'ADMIN'}
        assert request('/api/auth/register',data)[0]==403
        status,registered,_=request('/api/auth/register',data,session['csrf'])
        assert status==200 and registered['usuario']['rol']=='CLIENTE'
        assert 'password_hash' not in registered['usuario']
        assert request('/api/admin/reports')[0]==403
        manual={'cliente':'Prueba manual','cancha_id':1,'tipo_evento':'HORA',
                'fecha':str(datetime.now(s.TZ).date()+timedelta(days=3)),
                'hora':'12:00','horas':1}
        assert request('/api/admin/reservations',manual)[0]==403
        assert request('/api/admin/reservations',manual,registered['csrf'])[0]==403
        expense={'categoria':'TORNEOS','concepto':'Trofeos','monto':'10.50',
                 'fecha_gasto':str(datetime.now(s.TZ).date())}
        assert request('/api/admin/expenses',expense,registered['csrf'])[0]==403
        assert request('/api/admin/copa-fixtures')[0]==403
        assert request('/api/admin/copa-results',{'fixture_id':'7:Argentina:Japón'},registered['csrf'])[0]==403
        assert request('/api/copa-castell')[0]==200
        assert request('/api/history')[0]==200
        assert request('/api/auth/logout',{},session['csrf'])[0]==403
        assert request('/api/auth/logout',{},registered['csrf'])[0]==200
        assert request('/api/history')[0]==401


def test_https_cookie_y_cabeceras_de_seguridad(conn, monkeypatch):
    conn.commit()
    monkeypatch.setattr(server, 'ORIGIN', 'https://arenacastell.com')
    monkeypatch.setenv('COOKIE_SECURE', 'false')
    with client() as request:
        status, _, headers = request('/api/session')
        assert status == 200
        assert 'Secure' in headers['Set-Cookie']
        assert headers['Strict-Transport-Security'] == 'max-age=15552000'


def test_ip_de_cliente_solo_usa_proxy_en_alojamiento(monkeypatch):
    handler = object.__new__(Handler)
    handler.client_address = ('127.0.0.1', 1234)
    handler.headers = {'X-Forwarded-For': '203.0.113.8, 192.0.2.1'}
    monkeypatch.delenv('PORT', raising=False)
    assert handler.client_ip() == '127.0.0.1'
    monkeypatch.setenv('PORT', '10000')
    assert handler.client_ip() == '203.0.113.8'
    handler.headers = {'X-Forwarded-For': 'invalid'}
    assert handler.client_ip() == '127.0.0.1'


def test_limite_de_sesiones_anonimas_por_cliente(conn):
    for _ in range(3):
        s.limitar_acceso(conn, 'security-test-session', max_attempts=3)
    with pytest.raises(s.HTTPError) as error:
        s.limitar_acceso(conn, 'security-test-session', max_attempts=3)
    assert error.value.status == 429


def test_restablecimiento_de_password_tiene_limite_http(conn):
    conn.commit()
    with client() as request:
        _, session, _ = request('/api/session')
        payload = {'token': 'no-valido', 'password': 'ClaveSegura!2026',
                   'confirmacion': 'ClaveSegura!2026'}
        for _ in range(10):
            assert request('/api/auth/reset', payload, session['csrf'])[0] == 400
        assert request('/api/auth/reset', payload, session['csrf'])[0] == 429


def test_http_archivos_privados_y_html(conn):
    conn.commit()
    with client() as request:
        for path in ['/server.py','/.env','/.env.example','/.git/HEAD','/README.md','/configurar_bd.py',
                     '/sql/schema.sql','/../.env','/pages/../.env','/assets/%2e%2e/.env',
                     '/pages/%2e%2e%5c.env','/assets/','/pages/',
                     '/comprobantes.py','/templates/correos/mensaje.html']:
            assert request(path)[0]==404
            assert request(path,method='HEAD')[0]==404
        status,body,headers=request('/index.html')
        assert status==200 and body.lower().startswith(b'<!doctype html>')
        assert 'script-src' in headers['Content-Security-Policy']
        assert request('/')[1]==body
        for page in (STATIC/'pages').glob('*.html'):
            assert request('/pages/'+page.name)[1]==page.read_bytes()
            assert request('/pages/'+page.stem)[1]==page.read_bytes()
            assert request('/pages/'+page.stem,method='HEAD')[0]==200
        assert request('/assets/styles.css')[0]==200
        assert request('/assets/app.js')[0]==200
        assert request('/reservas.html')[1]==(STATIC/'pages/reservas.html').read_bytes()
        assert request('/api/catalog')[0]==200


def test_http_tres_flujos_completos(conn,user):
    conn.commit()
    with client() as request:
        _,session,_=request('/api/session')
        status,session,_=request('/api/auth/login',{'email':user['email'],'password':'PruebaSegura!2026'},session['csrf'])
        assert status==200
        csrf=session['csrf'];today=datetime.now(s.TZ).date()
        status,reserva,_=request('/api/reservations',{'cancha_id':1,'tipo_evento':'CUMPLEANOS','fecha':str(today+timedelta(days=5)),'hora':'12:00','horas':3},csrf)
        assert status==200
        assert request(f"/api/orders/{reserva['id']}")[1]['monto']=='75.00'
        status,torneo,_=request('/api/tournaments',{'torneo_id':1,'equipo':'Equipo HTTP','acepta_reglamento':True},csrf)
        assert status==200
        _,catalogo,_=request('/api/catalog')
        horario=next(h['id'] for h in catalogo['horarios_chaca'] if h['categoria']=='Sub-12')
        status,escuela,_=request('/api/school',{'alumno':'Alumno HTTP','cedula':cedula_demo(501),'nacimiento':str(date(today.year-10,1,1)),'categoria':'Sub-12','horario_id':horario,'consentimiento':True},csrf)
        assert status==200
        for order,method in [(reserva,'TRANSFERENCIA'),(torneo,'TRANSFERENCIA'),(escuela,'TRANSFERENCIA')]:
            assert request(f"/api/orders/{order['id']}/pay",{'metodo':method,'acepta_simulacion':True,'referencia_transferencia':'HTTP-REFERENCIA'},csrf)[0]==200
            status,detail,_=request(f"/api/orders/{order['id']}")
            assert status==200 and detail['estado']=='PENDIENTE' and detail['pago'] is None
            aid=conn.execute("SELECT id FROM usuarios WHERE email='revision@arena.test'").fetchone()['id']
            s.revisar_transferencia(conn,aid,order['id'],{'revision':detail['revision_pago']},aprobar=True)
            conn.commit()
            status,detail,_=request(f"/api/orders/{order['id']}")
            assert status==200 and detail['estado']=='PAGADA' and not detail['pago']['simulado']
        _,activity,_=request('/api/history')
        assert len(activity['ordenes'])==3 and len(activity['correos'])==3
        assert activity['escuela'][0]['estado']=='ACTIVA'
        team=next(o['equipo_id'] for o in activity['ordenes'] if o['tipo']=='TORNEO')
        assert request(f'/api/teams/{team}/players',{'nombre':'Jugador HTTP','cedula':cedula_demo(502)},csrf)[0]==200
        assert len(request(f'/api/teams/{team}')[1]['jugadores'])==1
        assert 'máximo 20' in next(c['cuerpo'] for c in activity['correos'] if 'lista de jugadores' in c['cuerpo'])


def test_http_admin_registra_reserva_manual_y_ocupa_horario(conn):
    admin=s.registrar(conn,{'nombre':'Operador HTTP','cedula':cedula_demo(752),
        'telefono':'0990000000','email':'manual-http@arena.test',
        'password':'ClaveOperador!2026','confirmacion':'ClaveOperador!2026','consentimiento':True})
    conn.execute("UPDATE usuarios SET rol='ADMIN' WHERE id=%s",(admin['id'],))
    conn.commit()
    with client() as request:
        _,session,_=request('/api/session')
        status,session,_=request('/api/auth/login',
            {'email':'manual-http@arena.test','password':'ClaveOperador!2026'},session['csrf'])
        assert status==200 and session['usuario']['rol']=='ADMIN'
        day=str(datetime.now(s.TZ).date()+timedelta(days=4))
        data={'cliente':'Cliente de WhatsApp','telefono':'0991234567',
              'cancha_id':1,'tipo_evento':'HORA','fecha':day,'hora':'14:00','horas':2,'monto':'25.00'}
        status,order,_=request('/api/admin/reservations',data,session['csrf'])
        assert status==200
        assert conn.execute('SELECT monto FROM ordenes WHERE id=%s',(order['id'],)).fetchone()['monto']==25
        _,reports,_=request('/api/admin/reports')
        assert any(row['orden_id']==order['id'] and row['manual'] and row['estado']=='CONFIRMADA'
                   and row['registrado_por']=='Operador HTTP'
                   for row in reports['reservas'])
        assert any(row['administrador_nombre']=='Operador HTTP' and
                   row['accion']=='Registró una reserva manual' and row['referencia']==order['id']
                   for row in reports['actividad_admin'])
        _,slots,_=request(f'/api/availability?fecha={day}&cancha=1&horas=1')
        assert not next(slot for slot in slots['horarios'] if slot['hora']=='14:00')['disponible']
        assert request(f"/api/admin/reservations/{order['id']}/cancel",{})[0]==403
        assert request(f"/api/admin/reservations/{order['id']}/cancel",{},session['csrf'])[0]==200
        _,reports,_=request('/api/admin/reports')
        assert any(row['accion']=='Anuló una reserva manual' and
                   row['administrador_nombre']=='Operador HTTP' for row in reports['actividad_admin'])
        _,slots,_=request(f'/api/availability?fecha={day}&cancha=1&horas=1')
        assert next(slot for slot in slots['horarios'] if slot['hora']=='14:00')['disponible']
        _,preview,_=request('/api/admin/test-data-preview')
        assert preview['resumen']['ordenes']==1
        conn.commit()  # Libera la lectura de esta conexión antes del bloqueo exclusivo.
        assert request('/api/admin/test-data-reset',{'confirmacion':'BORRAR DATOS DE PRUEBA',
            'password':'ClaveOperador!2026','resumen':preview['resumen']})[0]==403
        status,removed,_=request('/api/admin/test-data-reset',{'confirmacion':'BORRAR DATOS DE PRUEBA',
            'password':'ClaveOperador!2026','resumen':preview['resumen']},session['csrf'])
        assert status==200 and removed['eliminados']['ordenes']==1
        assert request('/api/admin/test-data-preview')[1]['resumen']['ordenes']==0


def test_historial_distingue_dos_cuentas_administradoras(conn):
    for number,name,email in ((760,'Administradora Ana','ana@arena.test'),
                              (761,'Administrador Luis','luis@arena.test')):
        account=s.registrar(conn,{'nombre':name,'cedula':cedula_demo(number),
            'telefono':'0990000000','email':email,'password':'ClaveOperador!2026',
            'confirmacion':'ClaveOperador!2026','consentimiento':True})
        conn.execute("UPDATE usuarios SET rol='ADMIN' WHERE id=%s",(account['id'],))
    conn.commit()
    with client() as request:
        _,session,_=request('/api/session')
        _,ana,_=request('/api/auth/login',{'email':'ana@arena.test',
            'password':'ClaveOperador!2026'},session['csrf'])
        day=str(datetime.now(s.TZ).date()+timedelta(days=3))
        status,booking,_=request('/api/admin/reservations',{'cliente':'Cliente WhatsApp',
            'cancha_id':1,'tipo_evento':'HORA','fecha':day,'hora':'14:00','horas':1},ana['csrf'])
        assert status==200
        _,logged_out,_=request('/api/auth/logout',{},ana['csrf'])
        _,luis,_=request('/api/auth/login',{'email':'luis@arena.test',
            'password':'ClaveOperador!2026'},logged_out['csrf'])
        assert request('/api/admin/expenses',{'categoria':'TORNEOS','concepto':'Trofeos de prueba',
            'monto':'10.00','fecha_gasto':str(datetime.now(s.TZ).date())},luis['csrf'])[0]==200
        _,report,_=request('/api/admin/reports')
        assert next(r for r in report['reservas'] if r['orden_id']==booking['id'])['registrado_por']=='Administradora Ana'
        assert report['gastos'][0]['registrado_por']=='Administrador Luis'
        assert {(r['administrador_nombre'],r['accion']) for r in report['actividad_admin']} >= {
            ('Administradora Ana','Registró una reserva manual'),
            ('Administrador Luis','Registró un gasto')}
        assert all('password' not in str(r).lower() for r in report['actividad_admin'])


def test_http_admin_registra_y_anula_gasto(conn):
    admin=s.registrar(conn,{'nombre':'Operador Gastos','cedula':cedula_demo(753),
        'telefono':'0990000000','email':'gastos-http@arena.test',
        'password':'ClaveOperador!2026','confirmacion':'ClaveOperador!2026','consentimiento':True})
    conn.execute("UPDATE usuarios SET rol='ADMIN' WHERE id=%s",(admin['id'],))
    conn.commit()
    with client() as request:
        _,session,_=request('/api/session')
        status,session,_=request('/api/auth/login',
            {'email':'gastos-http@arena.test','password':'ClaveOperador!2026'},session['csrf'])
        assert status==200
        expense={'categoria':'TORNEOS','concepto':'Trofeos finales','monto':'12.50',
                 'fecha_gasto':str(datetime.now(s.TZ).date())}
        assert request('/api/admin/expenses',expense)[0]==403
        status,created,_=request('/api/admin/expenses',expense,session['csrf'])
        assert status==200
        _,reports,_=request('/api/admin/reports')
        assert reports['finanzas']['TORNEOS']['gastos']=='12.50'
        assert request(f"/api/admin/expenses/{created['id']}/void",{'motivo':'Error'})[0]==403
        status,_,_=request(f"/api/admin/expenses/{created['id']}/void",
                           {'motivo':'Registro duplicado'},session['csrf'])
        assert status==200
        _,reports,_=request('/api/admin/reports')
        assert reports['finanzas']['TORNEOS']['gastos']=='0'
        assert reports['gastos'][0]['motivo_anulacion']=='Registro duplicado'
        assert reports['gastos'][0]['registrado_por']=='Operador Gastos'
        assert reports['gastos'][0]['anulado_por']=='Operador Gastos'
        assert {row['accion'] for row in reports['actividad_admin']} >= {'Registró un gasto','Anuló un gasto'}


def test_http_admin_publica_resultado_copa_y_publico_lo_ve(conn):
    admin=s.registrar(conn,{'nombre':'Operador Copa','cedula':cedula_demo(754),
        'telefono':'0990000000','email':'copa-http@arena.test',
        'password':'ClaveOperador!2026','confirmacion':'ClaveOperador!2026','consentimiento':True})
    conn.execute("UPDATE usuarios SET rol='ADMIN' WHERE id=%s",(admin['id'],))
    conn.commit()
    with client() as request:
        _,session,_=request('/api/session')
        status,session,_=request('/api/auth/login',
            {'email':'copa-http@arena.test','password':'ClaveOperador!2026'},session['csrf'])
        assert status==200
        status,fixtures,_=request('/api/admin/copa-fixtures')
        assert status==200
        fixture=next(m for m in fixtures['fixtures'] if m['home']=='Argentina' and m['away']=='Japón')
        payload={'fixture_id':fixture['id'],'homeGoals':1,'awayGoals':2,'revision':0,'goals':[]}
        assert request('/api/admin/copa-results',payload)[0]==403
        status,saved,_=request('/api/admin/copa-results',payload,session['csrf'])
        assert status==200 and saved['goleadores_pendientes']==3
        assert next(m for m in request('/api/admin/copa-fixtures')[1]['fixtures'] if m['id']==fixture['id'])['result']['registrado_por']=='Operador Copa'
        status,public,_=request('/api/copa-castell')
        assert status==200 and public['goleadoresPendientes']==3
        played=next(m for m in public['matches'] if m.get('id')==fixture['id'])
    assert played['homeGoals']==1 and played['awayGoals']==2


def test_http_admin_registra_alumno_y_cobro_manual_escuela(conn):
    admin=s.registrar(conn,{'nombre':'Operador Escuela','cedula':cedula_demo(755),
        'telefono':'0990000000','email':'escuela-http@arena.test',
        'password':'ClaveOperador!2026','confirmacion':'ClaveOperador!2026','consentimiento':True})
    conn.execute("UPDATE usuarios SET rol='ADMIN' WHERE id=%s",(admin['id'],))
    conn.commit()
    month=datetime.now(s.TZ).strftime('%Y-%m')
    with client() as request:
        _,session,_=request('/api/session')
        status,session,_=request('/api/auth/login',
            {'email':'escuela-http@arena.test','password':'ClaveOperador!2026'},session['csrf'])
        assert status==200
        student={'alumno':'Alumno de prueba','categoria':'Sub-10','cedula':'',
                 'telefono_representante':'0991234567',
                 'fecha_ingreso':str(datetime.now(s.TZ).date()),'inscripcion_pagada':False}
        assert request('/api/admin/school/students',student)[0]==403
        status,created,_=request('/api/admin/school/students',student,session['csrf'])
        assert status==200
        status,school,_=request('/api/admin/school?periodo='+month)
        assert status==200
        row=next(row for row in school['alumnos'] if row['id']==f"manual:{created['id']}")
        assert not row['mes_pagado'] and not row['inscripcion_pagada']
        assert row['registrado_por']=='Operador Escuela'
        payment={'alumno_id':created['id'],'tipo':'MENSUALIDAD','periodo':month,
                 'monto':'24','metodo':'EFECTIVO'}
        status,_,_=request('/api/admin/school/payments',payment,session['csrf'])
        assert status==200
        _,school,_=request('/api/admin/school?periodo='+month)
        row=next(row for row in school['alumnos'] if row['id']==f"manual:{created['id']}")
        assert row['mes_pagado'] and row['mes_monto']=='24.00' and row['mes_metodo']=='EFECTIVO'
        assert row['mes_registrado_por']=='Operador Escuela'
        _,report,_=request('/api/admin/reports')
        assert report['finanzas']['SUPER_CHACA']['mensualidades']=='24.00'


class InspectHTML(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.ids=[];self.labels=[];self.controls=[];self.lang=None;self.main=0;self.h1=0;self.inline=[];self.forms=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        if tag=='html':self.lang=attrs.get('lang')
        if tag=='main':self.main+=1
        if tag=='h1':self.h1+=1
        if tag=='form':self.forms.append(attrs.get('method','get').lower())
        if tag=='label' and 'for' in attrs:self.labels.append(attrs['for'])
        if tag in ('input','select','textarea') and attrs.get('type') not in ('radio','checkbox','hidden'):self.controls.append(attrs.get('id'))
        if tag in ('a','link','script','img'):
            value=attrs.get('href') or attrs.get('src')
            if value:self.links.append(value)
        if any(key.startswith('on') for key in attrs):self.inline.append(tag)


def test_html_semantica_et_enlaces():
    files=[STATIC/'index.html', *(STATIC/'pages').glob('*.html')]
    assert len(files)==19
    assert not (STATIC/'pages/index.html').exists()
    for path in files:
        text=path.read_text(encoding='utf8');document=InspectHTML();document.feed(text)
        assert text.lower().startswith('<!doctype html>'),path.name
        assert document.lang=='es' and document.main==1 and document.h1==1,path.name
        assert len(document.ids)==len(set(document.ids)),f'IDs duplicados en {path.name}'
        assert not document.inline,path.name
        assert all(method=='post' for method in document.forms),f'Evitar datos sensibles en URL: {path.name}'
        for control in document.controls:assert control in document.labels,(path.name,control)
        for value in document.links:
            url=urlsplit(value)
            if url.scheme or url.netloc or not url.path:continue
            target=path.parent/unquote(url.path)
            assert target.is_file(),(path.name,value)
