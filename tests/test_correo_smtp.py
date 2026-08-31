from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import smtplib
import ssl
import pytest

import correos as mail
import services as s
from db import ROOT
from io import BytesIO
from pypdf import PdfReader


@pytest.fixture
def smtp(monkeypatch):
    values = {"SMTP_ENABLED":"true", "SMTP_HOST":"smtp.gmail.com", "SMTP_PORT":"587",
              "SMTP_SECURITY":"starttls", "SMTP_USER":"arena@example.com",
              "SMTP_PASSWORD":"abcd efgh ijkl mnop", "PUBLIC_BASE_URL":"https://arena.example.com"}
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    delivered = []
    monkeypatch.setattr(mail, "enviar_smtp", lambda row, config: delivered.append(dict(row)))
    return delivered


def reservation(conn, user):
    return s.reservar(conn, user['id'], {
        'cancha_id':conn.execute('SELECT id FROM canchas LIMIT 1').fetchone()['id'],
        'fecha':(datetime.now(s.TZ)+timedelta(days=3)).date().isoformat(),
        'hora':'10:00', 'horas':1, 'tipo_evento':'HORA'})


def test_pago_solo_envia_despues_de_commit_y_no_duplica(conn,user,pay_data,smtp):
    order=reservation(conn,user)
    s.pagar(conn,user['id'],order['id'],pay_data)
    assert mail.procesar_pendientes()['enviados']==0
    assert not smtp
    conn.commit()
    assert mail.procesar_pendientes()['enviados']==1
    assert smtp[0]['destinatario']==user['email']
    assert 'Reserva:' in smtp[0]['cuerpo'] and str(order['id']) in smtp[0]['cuerpo']
    message=mail.crear_mensaje(smtp[0],mail.ConfiguracionSMTP.desde_entorno())
    attachment=list(message.iter_attachments())[0]
    assert attachment.get_filename().endswith('.pdf')
    assert attachment.get_content_type()=='application/pdf'
    texto=''.join(p.extract_text() for p in PdfReader(BytesIO(attachment.get_content())).pages)
    assert 'ARENA CASTELL' in texto and str(order['id']) in texto and '$27.00' in texto
    assert '$27.00' in message.get_body(preferencelist=('html',)).get_content()
    s.pagar(conn,user['id'],order['id'],pay_data);conn.commit()
    assert mail.procesar_pendientes()['enviados']==0
    assert len(smtp)==1
    assert s.detalle_orden(conn,user['id'],order['id'])['correo']['estado_envio']=='ENVIADO'


def test_rollback_no_deja_correo_para_enviar(conn,user,pay_data,smtp):
    conn.commit()
    order=reservation(conn,user)
    s.pagar(conn,user['id'],order['id'],pay_data)
    conn.rollback()
    assert mail.procesar_pendientes()['enviados']==0
    assert not smtp


def test_fallo_gmail_no_revierte_pago_y_reintento_conserva_message_id(conn,user,pay_data,smtp,monkeypatch,caplog):
    order=reservation(conn,user);s.pagar(conn,user['id'],order['id'],pay_data);conn.commit()
    def fail(row, config):
        raise smtplib.SMTPAuthenticationError(535,b'SECRETO_NO_PUBLICAR')
    monkeypatch.setattr(mail,'enviar_smtp',fail)
    assert mail.procesar_pendientes()['fallidos']==1
    row=conn.execute('SELECT * FROM correo_salida').fetchone()
    identifier=mail.crear_mensaje(row,mail.ConfiguracionSMTP.desde_entorno())['Message-ID']
    assert row['intentos']==1 and row['ultimo_error']=='AUTENTICACION_SMTP'
    assert 'SECRETO_NO_PUBLICAR' not in caplog.text
    assert conn.execute('SELECT estado FROM ordenes WHERE id=%s',(order['id'],)).fetchone()['estado']=='PAGADA'
    assert mail.procesar_pendientes()['fallidos']==0  # Respeta el tiempo de espera.
    conn.execute("UPDATE correo_salida SET proximo_intento=current_timestamp-interval '1 second'");conn.commit()
    monkeypatch.setattr(mail,'enviar_smtp',lambda row,config:smtp.append(dict(row)))
    assert mail.procesar_pendientes()['enviados']==1
    assert mail.crear_mensaje(smtp[0],mail.ConfiguracionSMTP.desde_entorno())['Message-ID']==identifier


def test_fallo_repetido_se_detiene_a_los_cinco_intentos(conn,user,smtp,monkeypatch):
    mail.encolar_correo(conn,user['id'],user['email'],'Aviso','Contenido');conn.commit()
    def fail(row,config):raise OSError('Sin conexión')
    monkeypatch.setattr(mail,'enviar_smtp',fail)
    for _ in range(5):
        conn.execute('UPDATE correo_salida SET proximo_intento=current_timestamp');conn.commit()
        assert mail.procesar_pendientes()['fallidos']==1
    assert mail.procesar_pendientes()['fallidos']==0
    assert conn.execute('SELECT estado_envio FROM correo_salida').fetchone()['estado_envio']=='ERROR'


def test_activar_smtp_no_envia_mensajes_locales_anteriores(conn,user,smtp,monkeypatch):
    monkeypatch.setenv('SMTP_ENABLED','false')
    mail.encolar_correo(conn,user['id'],user['email'],'Anterior','No enviar');conn.commit()
    monkeypatch.setenv('SMTP_ENABLED','true')
    assert mail.procesar_pendientes()['enviados']==0 and not smtp
    assert conn.execute('SELECT estado_envio FROM correo_salida').fetchone()['estado_envio']=='LOCAL'


def test_recuperacion_reemplazada_y_vencida_no_se_envia(conn,user,smtp):
    result=s.solicitar_restablecimiento(conn,{'email':user['email']})
    assert result==s.solicitar_restablecimiento(conn,{'email':'no-existe@arena.test'})
    s.solicitar_restablecimiento(conn,{'email':user['email']})
    conn.execute("UPDATE correo_salida SET vence_en=current_timestamp-interval '1 minute' WHERE estado_envio='PENDIENTE'")
    conn.commit()
    assert mail.procesar_pendientes()['cancelados']==1 and not smtp
    assert conn.execute("SELECT count(*) AS n FROM correo_salida WHERE estado_envio='CANCELADO'").fetchone()['n']==2
    assert s.historial(conn,user['id'])['correos']==[]  # Nunca exponer tokens en el historial.


def test_recuperacion_valida_enlace_y_destinatario(conn,user,smtp):
    s.solicitar_restablecimiento(conn,{'email':user['email']});conn.commit()
    assert mail.procesar_pendientes()['enviados']==1
    assert 'https://arena.example.com/pages/restablecer_contrasena.html#token=' in smtp[0]['cuerpo']
    assert smtp[0]['destinatario']==user['email']
    assert list(mail.crear_mensaje(smtp[0],mail.ConfiguracionSMTP.desde_entorno()).iter_attachments())==[]


def test_cambio_de_correo_cancela_envio_a_direccion_anterior(conn,user,smtp):
    s.solicitar_restablecimiento(conn,{'email':user['email']})
    conn.execute("UPDATE usuarios SET email='nuevo@arena.test' WHERE id=%s",(user['id'],));conn.commit()
    assert mail.procesar_pendientes()['cancelados']==1 and not smtp


def test_dos_trabajadores_no_envian_la_misma_fila(conn,user,smtp,monkeypatch):
    mail.encolar_correo(conn,user['id'],user['email'],'Aviso','Una sola vez');conn.commit()
    entered,release=Event(),Event()
    def send(row,config):
        entered.set()
        assert release.wait(5)
        smtp.append(row['id'])
    monkeypatch.setattr(mail,'enviar_smtp',send)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first=pool.submit(mail.procesar_pendientes)
        try:
            assert entered.wait(5)
            assert mail.procesar_pendientes()['enviados']==0
        finally:release.set()
        assert first.result()['enviados']==1
    assert len(smtp)==1


@pytest.mark.parametrize('security',['starttls','ssl'])
def test_transporte_tls_antes_de_login_y_contenido_utf8(monkeypatch,security):
    calls=[]
    class SMTP:
        def __init__(self,*args,**kwargs):
            calls.append('connect')
            if 'context' in kwargs:
                assert kwargs['context'].check_hostname and kwargs['context'].verify_mode==ssl.CERT_REQUIRED
                calls.append('ssl')
        def ehlo(self):calls.append('ehlo')
        def starttls(self,context):
            assert context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED
            calls.append('tls')
        def login(self,user,password):
            assert 'tls' in calls or 'ssl' in calls
            calls.append('login')
        def send_message(self,message,from_addr,to_addrs):
            assert 'login' in calls
            assert to_addrs==['cliente@example.com'] and from_addr=='arena@example.com'
            assert 'Amaguaña' in message.get_body(preferencelist=('plain',)).get_content()
            assert b'Content-Type: text/plain; charset="utf-8"' in message.as_bytes()
            calls.append('send');return {}
        def quit(self):calls.append('quit')
        def close(self):pass
    monkeypatch.setattr(mail.smtplib,'SMTP',SMTP)
    monkeypatch.setattr(mail.smtplib,'SMTP_SSL',SMTP)
    config=mail.ConfiguracionSMTP('smtp.gmail.com',587,'arena@example.com','clave',security)
    mail.enviar_smtp({'id':1,'creado_en':datetime.now(timezone.utc),'destinatario':'cliente@example.com',
                     'asunto':'Confirmación','cuerpo':'Súper Chaca · Amaguaña'},config)
    assert calls[-2:]==['send','quit']


def test_sin_tls_no_se_envia_contrasena(monkeypatch):
    class SMTP:
        def __init__(self,*a,**kw):pass
        def ehlo(self):pass
        def starttls(self,context):raise smtplib.SMTPNotSupportedError('Sin TLS')
        def login(self,*a):pytest.fail('No se debe autenticar sin TLS')
        def quit(self):pass
    monkeypatch.setattr(mail.smtplib,'SMTP',SMTP)
    with pytest.raises(smtplib.SMTPNotSupportedError):
        mail.enviar_smtp({'id':1,'creado_en':datetime.now(timezone.utc),'destinatario':'cliente@example.com',
                         'asunto':'Confirmación','cuerpo':'Mensaje'},
                        mail.ConfiguracionSMTP('smtp.gmail.com',587,'arena@example.com','clave'))


def test_configuracion_no_expone_clave_y_rechaza_inyeccion(smtp,monkeypatch):
    config=mail.ConfiguracionSMTP.desde_entorno()
    assert config.password=='abcdefghijklmnop' and config.password not in repr(config)
    with pytest.raises(mail.ConfiguracionCorreoError):mail.direccion('a@example.com\r\nBcc:b@example.com')
    monkeypatch.setenv('SMTP_SECURITY','none')
    with pytest.raises(mail.ConfiguracionCorreoError):mail.ConfiguracionSMTP.desde_entorno()


def test_migracion_conserva_correo_previo_y_es_repetible(conn,user):
    mail.encolar_correo(conn,user['id'],user['email'],'Anterior','Conservar')
    for column in ['destinatario','estado_envio','intentos','proximo_intento','enviado_en','ultimo_error','vence_en']:
        # Nombres estáticos de esta prueba; solo se ejecuta en la BD test_arena_*.
        conn.execute(f'ALTER TABLE correo_salida DROP COLUMN {column}')
    migration=(ROOT/'sql/pgadmin/11_actualizar_correo_smtp.sql').read_text(encoding='utf8')
    conn.execute(migration);conn.execute(migration)
    row=conn.execute('SELECT * FROM correo_salida').fetchone()
    assert row['cuerpo']=='Conservar' and row['estado_envio']=='LOCAL' and row['destinatario'] is None
