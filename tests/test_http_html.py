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
        assert request('/api/history')[0]==200
        assert request('/api/auth/logout',{},session['csrf'])[0]==403
        assert request('/api/auth/logout',{},registered['csrf'])[0]==200
        assert request('/api/history')[0]==401


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
        assert status==200 and body.startswith(b'<!DOCTYPE html>')
        assert 'script-src' in headers['Content-Security-Policy']
        assert request('/')[1]==body
        for page in (STATIC/'pages').glob('*.html'):
            assert request('/pages/'+page.name)[1]==page.read_bytes()
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
        for order,method in [(reserva,'TRANSFERENCIA'),(torneo,'DEBITO'),(escuela,'CREDITO')]:
            assert request(f"/api/orders/{order['id']}/pay",{'metodo':method,'acepta_simulacion':True},csrf)[0]==200
            status,detail,_=request(f"/api/orders/{order['id']}")
            assert status==200 and detail['estado']=='PAGADA' and detail['pago']['simulado']
        _,activity,_=request('/api/history')
        assert len(activity['ordenes'])==3 and len(activity['correos'])==3
        assert activity['escuela'][0]['estado']=='ACTIVA'
        team=next(o['equipo_id'] for o in activity['ordenes'] if o['tipo']=='TORNEO')
        assert request(f'/api/teams/{team}/players',{'nombre':'Jugador HTTP','cedula':cedula_demo(502)},csrf)[0]==200
        assert len(request(f'/api/teams/{team}')[1]['jugadores'])==1
        assert 'máximo 20' in next(c['cuerpo'] for c in activity['correos'] if 'lista de jugadores' in c['cuerpo'])


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
        assert text.startswith('<!DOCTYPE html>'),path.name
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
