# Prueba diseño del correo

"""Comprobar contenido, PDF, permisos y datos no confiables sin usar Gmail."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from io import BytesIO

import pytest
from pypdf import PdfReader

import comprobantes as c
import correos as mail
import services as s
from manage import cedula_demo


def fila(datos=None):
    return {'id':987, 'creado_en':datetime(2026,8,31,15,0,tzinfo=timezone.utc),
            'asunto':'Confirmación Arena Castell', 'destinatario':'cliente@arena.test',
            'cuerpo':'Gracias por elegir Arena Castell. Comprobante de tu registro.',
            'comprobante':datos}


def configuracion():
    return mail.ConfiguracionSMTP('smtp.gmail.com',587,'remitente@arena.test','CLAVE_QUE_NO_DEBE_APARECER')


def mensaje_de_orden(conn, user, orden):
    datos = c.datos_comprobante(conn, orden['id'], user['id'])
    return mail.crear_mensaje(fila(datos), configuracion())


@pytest.mark.parametrize('tipo,total', [('HORA','27.00'),('CUMPLEANOS','75.00'),('TORNEO','30.00'),('ESCUELA','50.00'),('MENSUALIDAD','50.00')])
def test_html_y_pdf_reflejan_el_pago_de_cada_servicio(conn,user,pay_data,tipo,total):
    hoy = datetime.now(s.TZ).date()
    if tipo in {'HORA','CUMPLEANOS'}:
        orden = s.reservar(conn,user['id'], {'cancha_id':1,'tipo_evento':tipo,'fecha':str(hoy+timedelta(days=2)),
                                            'hora':'12:00','horas':3 if tipo=='CUMPLEANOS' else 1})
    elif tipo == 'TORNEO':
        torneo = conn.execute("SELECT id FROM torneos WHERE nombre='Pasochoa Cup · Sexta edición'").fetchone()['id']
        conn.execute('UPDATE torneos SET fecha_inicio=current_date+30 WHERE id=%s',(torneo,))
        orden = s.inscribir_torneo(conn,user['id'],{'torneo_id':torneo,'equipo':'Equipo de ejemplo','acepta_reglamento':True})
    else:
        horario = next(h['id'] for h in s.catalogo(conn)['horarios_chaca'] if h['categoria']=='Sub-12')
        orden = s.inscribir_escuela(conn,user['id'],{'alumno':'Alumno de ejemplo','cedula':cedula_demo(987),
                'nacimiento':str(date(hoy.year-10,1,1)), 'categoria':'Sub-12','horario_id':horario,'consentimiento':True})
        if tipo == 'MENSUALIDAD':
            s.pagar(conn,user['id'],orden['id'],pay_data)
            escuela = s.detalle_orden(conn,user['id'],orden['id'])['escuela']['id']
            siguiente = (hoy.replace(day=1)+timedelta(days=32)).replace(day=1)
            orden = s.renovar_escuela(conn,user['id'],escuela,{'periodo':siguiente.strftime('%Y-%m')})
    s.pagar(conn,user['id'],orden['id'],pay_data)
    # Conserva el precio guardado
    conn.execute('UPDATE canchas SET tarifa_hora=99,tarifa_cumpleanos=99')
    conn.execute('UPDATE torneos SET costo=99')
    mensaje = mensaje_de_orden(conn,user,orden)
    mensaje = BytesParser(policy=policy.default).parsebytes(mensaje.as_bytes())
    html = mensaje.get_body(preferencelist=('html',)).get_content()
    assert '$'+total in html and str(orden['id']) in html
    assert mensaje.get_body(preferencelist=('plain',)).get_content().startswith('Gracias')
    pdfs = list(mensaje.iter_attachments())
    assert len(pdfs)==1 and pdfs[0].get_content_type()=='application/pdf'
    reader = PdfReader(BytesIO(pdfs[0].get_content()))
    assert len(reader.pages)==1
    texto = reader.pages[0].extract_text()
    assert '$'+total in texto and str(orden['id']) in texto and user['nombre'] in texto
    assert user['cedula'] not in texto and user['cedula'] not in html
    assert 'CLAVE_QUE_NO_DEBE_APARECER' not in html
    imagenes = [p for p in mensaje.walk() if p.get_content_maintype()=='image']
    assert len(imagenes)==1 and imagenes[0]['Content-ID']==f'<{c.LOGO_CID}>'
    assert imagenes[0].get_content_disposition()=='inline'


def test_no_se_generan_comprobantes_de_otro_titular_o_sin_pago(conn,user):
    orden = s.inscribir_torneo(conn,user['id'],{'torneo_id':1,'equipo':'Equipo privado','acepta_reglamento':True})
    with pytest.raises(ValueError):
        c.datos_comprobante(conn,orden['id'],user['id'])
    s.pagar(conn,user['id'],orden['id'],{'metodo':'TRANSFERENCIA','acepta_simulacion':True})
    with pytest.raises(ValueError):
        c.datos_comprobante(conn,orden['id'],user['id']+900)


class Enlaces(HTMLParser):
    def __init__(self):
        super().__init__(); self.hrefs=[]; self.scripts=0; self.imagenes=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='a': self.hrefs.append(attrs.get('href'))
        if tag=='script': self.scripts+=1
        if tag=='img': self.imagenes.append(attrs.get('src'))


def test_escapa_nombres_y_textos_en_html_y_pdf():
    datos = c.ejemplo_comprobante(datetime.now(timezone.utc))
    peligro = '<img src="https://no-cargar.example/privado"> & <script>robar()</script>'
    datos.update(cliente=peligro, descripcion=peligro+' '+('NombreLargo'*20), detalles=[('Equipo',peligro)])
    contexto = c.contexto_correo(fila(datos),'https://arena.example')
    html = c.renderizar_html(contexto)
    parser=Enlaces(); parser.feed(html)
    assert parser.scripts==0 and parser.imagenes==[f'cid:{c.LOGO_CID}']
    assert '&lt;script&gt;' in html and '&amp;' in html
    reader = PdfReader(BytesIO(c.crear_pdf(contexto)))
    assert reader.pages and 'robar()' in ''.join(p.extract_text() for p in reader.pages)


def test_recuperacion_tiene_boton_valido_sin_pdf_y_no_acepta_otro_dominio(monkeypatch):
    monkeypatch.setenv('PUBLIC_BASE_URL','https://arena.example')
    row = fila()
    row.update(vence_en=datetime.now(timezone.utc)+timedelta(minutes=30),
               cuerpo='Abre https://arena.example/pages/restablecer_contrasena.html#token=token_seguro-123')
    mensaje = mail.crear_mensaje(row,configuracion())
    html = mensaje.get_body(preferencelist=('html',)).get_content()
    parser=Enlaces(); parser.feed(html)
    assert parser.hrefs==['https://arena.example/pages/restablecer_contrasena.html#token=token_seguro-123']
    assert list(mensaje.iter_attachments())==[]
    row['cuerpo']='https://otro.example/pages/restablecer_contrasena.html#token=token_seguro-123'
    assert c.contexto_correo(row,'https://arena.example')['url_accion'] is None


def test_correo_de_prueba_muestra_ejemplo_y_pdf_solo_para_el_remitente(monkeypatch):
    config=configuracion()
    monkeypatch.setattr(mail.ConfiguracionSMTP,'desde_entorno',lambda:config)
    enviados=[]
    monkeypatch.setattr(mail,'enviar_smtp',lambda row,config:enviados.append(row))
    mail.enviar_prueba()
    assert len(enviados)==1 and enviados[0]['destinatario']==config.usuario
    assert enviados[0]['prueba'] and not enviados[0].get('orden_id')
    mensaje=mail.crear_mensaje(enviados[0],config)
    assert 'datos de ejemplo' in mensaje.get_body(preferencelist=('html',)).get_content()
    pdf=list(mensaje.iter_attachments())[0]
    assert 'VISTA PREVIA' in PdfReader(BytesIO(pdf.get_content())).pages[0].extract_text()


def test_fallo_del_diseno_no_envia_correo_incompleto_y_permite_reintento(conn,user,pay_data,monkeypatch,caplog):
    monkeypatch.setenv('SMTP_ENABLED','true')
    monkeypatch.setattr(mail.ConfiguracionSMTP,'desde_entorno',lambda:configuracion())
    orden=s.reservar(conn,user['id'],{'cancha_id':1,'tipo_evento':'HORA',
        'fecha':str(datetime.now(s.TZ).date()+timedelta(days=2)),'hora':'12:00','horas':1})
    s.pagar(conn,user['id'],orden['id'],pay_data)
    conn.commit()
    renderizar=mail.renderizar_html
    def fallar(contexto):
        raise mail.TemplateError('DATO_PRIVADO_QUE_NO_DEBE_QUEDAR_EN_LOGS')
    monkeypatch.setattr(mail,'renderizar_html',fallar)
    monkeypatch.setattr(mail.smtplib,'SMTP',lambda *a,**kw:pytest.fail('No enviar un correo incompleto'))
    assert mail.procesar_pendientes()['fallidos']==1
    fila=conn.execute('SELECT * FROM correo_salida WHERE orden_id=%s',(orden['id'],)).fetchone()
    assert fila['estado_envio']=='PENDIENTE' and fila['ultimo_error']=='CONTENIDO_CORREO'
    assert fila['intentos']==1 and 'DATO_PRIVADO' not in caplog.text
    assert s.detalle_orden(conn,user['id'],orden['id'])['estado']=='PAGADA'
    monkeypatch.setattr(mail,'renderizar_html',renderizar)
    enviados=[]
    monkeypatch.setattr(mail,'enviar_smtp',lambda row,config:enviados.append(mail.crear_mensaje(row,config)))
    conn.execute('UPDATE correo_salida SET proximo_intento=current_timestamp WHERE id=%s',(fila['id'],))
    conn.commit()
    assert mail.procesar_pendientes()['enviados']==1
    assert len(enviados)==1 and list(enviados[0].iter_attachments())[0].get_content_type()=='application/pdf'
