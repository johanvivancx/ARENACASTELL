"""Diseño de correos con Jinja2 y comprobantes PDF con ReportLab."""
from datetime import datetime
from decimal import Decimal
from html import escape
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import re

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

ROOT = Path(__file__).resolve().parent
LOGO = ROOT / 'assets/logo-arena-castell.jpg'
LOGO_CID = 'logo-arena-castell'
TZ = ZoneInfo('America/Guayaquil')
ENV = Environment(loader=FileSystemLoader(ROOT / 'templates/correos'),
                  autoescape=select_autoescape(['html']), undefined=StrictUndefined)
METODOS = {'TRANSFERENCIA': 'Transferencia bancaria', 'DEBITO': 'Tarjeta de débito', 'CREDITO': 'Tarjeta de crédito'}
TITULOS = {'RESERVA': 'Tu reserva está confirmada', 'TORNEO': 'Tu equipo ya está inscrito',
           'ESCUELA': 'Bienvenido a Súper Chaca', 'MENSUALIDAD': 'Mensualidad registrada'}
SERVICIOS = {'RESERVA': 'Reserva de cancha', 'TORNEO': 'Inscripción de torneo',
             'ESCUELA': 'Inscripción a Súper Chaca', 'MENSUALIDAD': 'Mensualidad de Súper Chaca'}


def moneda(value):
    return f'${Decimal(value):,.2f}'


def fecha(value):
    if isinstance(value, datetime):
        value = value.astimezone(TZ)
        return value.strftime('%d/%m/%Y · %H:%M')
    return value.strftime('%d/%m/%Y')


def datos_comprobante(conn, orden_id, usuario_id):
    """Consultar solo el pago del titular del mensaje; no tomar tarifas actuales."""
    dato = conn.execute('''SELECT o.id AS orden_id,o.tipo,o.descripcion,
        u.nombre AS cliente,u.cedula,p.id AS pago_id,p.monto,p.metodo,p.pagado_en
        FROM ordenes o JOIN usuarios u ON u.id=o.usuario_id
        JOIN pagos p ON p.orden_id=o.id
        WHERE o.id=%s AND o.usuario_id=%s AND o.estado='PAGADA' ''', (orden_id, usuario_id)).fetchone()
    if not dato:
        raise ValueError('No existe un pago confirmado para el titular del correo.')
    dato = dict(dato)
    dato.update(detalles=[], cantidad='1', unitario=dato['monto'], indicacion='', prueba=False)
    if dato['tipo'] == 'RESERVA':
        reserva = conn.execute('''SELECT r.*,c.nombre AS cancha FROM reservas r
            JOIN canchas c ON c.id=r.cancha_id WHERE r.orden_id=%s''', (orden_id,)).fetchone()
        horas = int((reserva['fin']-reserva['inicio']).total_seconds() // 3600)
        inicio, fin = reserva['inicio'].astimezone(TZ), reserva['fin'].astimezone(TZ)
        tipo = {'HORA':'Por hora', 'EVENTO':'Evento deportivo', 'CUMPLEANOS':'Cumpleaños'}[reserva['tipo_evento']]
        dato.update(cantidad=f'{horas} h', unitario=dato['monto']/horas,
                    detalles=[('Cancha', reserva['cancha']), ('Actividad', tipo),
                              ('Día', fecha(inicio.date())), ('Horario', f'{inicio:%H:%M} a {fin:%H:%M}'),
                              ('Duración', f'{horas} hora' if horas == 1 else f'{horas} horas')],
                    indicacion='Te esperamos en Arena Castell. Contamos con parqueadero privado y servicio de bar.')
    elif dato['tipo'] == 'TORNEO':
        equipo = conn.execute('''SELECT e.nombre,t.nombre AS torneo,t.fecha_inicio,t.max_jugadores
            FROM equipos e JOIN torneos t ON t.id=e.torneo_id WHERE e.orden_id=%s''', (orden_id,)).fetchone()
        dato.update(detalles=[('Torneo', equipo['torneo']), ('Equipo', equipo['nombre']),
                              ('Inicio', fecha(equipo['fecha_inicio'])), ('Lista', f"Hasta {equipo['max_jugadores']} jugadores")],
                    indicacion=f"Completa la lista de hasta {equipo['max_jugadores']} jugadores en Mi actividad > Gestionar equipo antes del inicio del torneo.")
    else:
        escuela = conn.execute('''SELECT sc.alumno,sc.categoria,m.periodo,h.dias,h.inicio,h.fin
            FROM mensualidades m JOIN inscripciones_chaca sc ON sc.id=m.inscripcion_id
            JOIN horarios_chaca h ON h.id=sc.horario_id WHERE m.orden_id=%s''', (orden_id,)).fetchone()
        dato.update(detalles=[('Alumno', escuela['alumno']), ('Categoría', escuela['categoria']),
                              ('Jornada', escuela['dias']), ('Horario', f"{escuela['inicio']:%H:%M} a {escuela['fin']:%H:%M}"),
                              ('Mensualidad', escuela['periodo'].strftime('%m/%Y'))],
                    indicacion='La escuela confirmará el grupo y horario definitivo. Puedes consultar tus mensualidades desde Mi actividad.')
    return dato


def ejemplo_comprobante(creado_en):
    """Datos ficticios solo para el comando test-email y las vistas previas."""
    return {'orden_id': None, 'tipo':'TORNEO', 'descripcion':'Pasochoa Cup · Sexta edición',
            'cliente':'Cliente de ejemplo', 'cedula':'', 'pago_id':None, 'monto':Decimal('30'),
            'metodo':'TRANSFERENCIA', 'pagado_en':creado_en, 'cantidad':'1', 'unitario':Decimal('30'),
            'detalles':[('Equipo','Equipo de ejemplo'), ('Inicio','30/09/2026'), ('Lista','Hasta 20 jugadores')],
            'indicacion':'En una inscripción real, aquí aparecerán las indicaciones para completar la lista de jugadores.',
            'prueba':True}


def contexto_correo(row, base_url):
    dato = row.get('comprobante')
    if row.get('prueba'):
        dato = ejemplo_comprobante(row['creado_en'])
    contexto = dict(asunto=row['asunto'], titulo=row['asunto'], preencabezado='Un mensaje de Arena Castell para ti.',
                    saludo='', parrafos=row['cuerpo'].splitlines(), comprobante=None, detalles=[],
                    url_accion=None, texto_accion='', indicacion='', prueba=False,
                    pie='Amaguaña · Quito, Ecuador', logo_src=f'cid:{LOGO_CID}')
    if dato:
        cedula = dato.get('cedula') or ''
        cedula = cedula[:2] + '******' + cedula[-2:] if len(cedula) == 10 else ''
        comprobante = {'codigo':f"AC-{dato['pago_id']:06d}" if dato['pago_id'] is not None else 'VISTA PREVIA',
                       'fecha':fecha(dato['pagado_en']), 'cliente':dato['cliente'], 'cedula':cedula,
                       'servicio':SERVICIOS[dato['tipo']], 'descripcion':dato['descripcion'],
                       'metodo':METODOS[dato['metodo']], 'cantidad':dato['cantidad'],
                       'unitario':moneda(dato['unitario']), 'total':moneda(dato['monto']),
                       'orden_id':str(dato['orden_id']) if dato['orden_id'] else ''}
        contexto.update(titulo='Así se verá tu confirmación' if dato['prueba'] else TITULOS[dato['tipo']],
                        preencabezado='Correo de prueba: diseño y PDF de Arena Castell.' if dato['prueba'] else f"{comprobante['servicio']} · {comprobante['codigo']} · {comprobante['total']}",
                        saludo=f"Hola, {dato['cliente']}.", parrafos=[], comprobante=comprobante,
                        detalles=dato['detalles'], indicacion=dato['indicacion'], prueba=dato['prueba'],
                        url_accion=base_url+'/pages/mis_reservas_inscripciones.html' if dato['prueba'] else base_url+f"/pages/confirmacion.html?orden={dato['orden_id']}",
                        texto_accion='Ir a Mi actividad' if dato['prueba'] else 'Ver mi comprobante')
    elif row.get('vence_en'):
        # La recuperación ya guarda su enlace en texto. Solo aceptar la ruta y origen de la aplicación.
        for link in re.findall(r'https?://[^\s<>]+', row['cuerpo']):
            url, base = urlsplit(link), urlsplit(base_url)
            if ((url.scheme, url.netloc) == (base.scheme, base.netloc)
                    and url.path == '/pages/restablecer_contrasena.html' and not url.query
                    and re.fullmatch(r'token=[A-Za-z0-9_-]+', url.fragment)):
                contexto.update(titulo='Recupera el acceso a tu cuenta',
                                preencabezado='Cambia tu contraseña con este enlace de un solo uso.',
                                parrafos=['Recibimos una solicitud para cambiar tu contraseña.',
                                          'El enlace vence en 30 minutos y solo puede usarse una vez.',
                                          'Si no lo solicitaste, puedes ignorar este mensaje.'],
                                url_accion=link, texto_accion='Cambiar mi contraseña')
                break
    return contexto


def renderizar_html(contexto):
    return ENV.get_template('mensaje.html').render(**contexto)


def crear_pdf(contexto):
    """Crear en memoria; no guardar datos personales en carpetas públicas."""
    dato = contexto['comprobante']
    if not dato:
        raise ValueError('El PDF necesita datos de una operación.')
    buffer = BytesIO()
    tinta, gris, linea = colors.HexColor('#171717'), colors.HexColor('#565656'), colors.HexColor('#dedede')
    normal = ParagraphStyle('Normal', fontName='Helvetica', fontSize=10, leading=15, textColor=tinta, spaceAfter=5)
    pequeno = ParagraphStyle('Pequeno', parent=normal, fontSize=8, leading=12, textColor=gris)
    titulo = ParagraphStyle('Titulo', parent=normal, fontName='Helvetica-Bold', fontSize=23, leading=28, spaceAfter=12)
    negrita = ParagraphStyle('Negrita', parent=normal, fontName='Helvetica-Bold')
    derecha = ParagraphStyle('Derecha', parent=normal, alignment=TA_RIGHT)
    total = ParagraphStyle('Total', parent=derecha, fontName='Helvetica-Bold', fontSize=21, leading=27)
    blanco = ParagraphStyle('Blanco', parent=negrita, textColor=colors.white, fontSize=9)

    def p(text, style=normal):
        # ReportLab interpreta etiquetas XML; todos los valores externos se escapan.
        return Paragraph(escape(str(text)).replace('\n', '<br/>'), style)

    ancho = A4[0]-88
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=44, rightMargin=44,
                            topMargin=133, bottomMargin=65, title='Comprobante de registro - Arena Castell',
                            author='ARENA CASTELL', pageCompression=1)

    def cabecera(canvas, document):
        canvas.saveState()
        canvas.setFillColor(tinta)
        canvas.rect(0, A4[1]-102, A4[0], 102, fill=1, stroke=0)
        canvas.drawImage(str(LOGO), 44, A4[1]-86, width=66, height=62, preserveAspectRatio=True, mask='auto')
        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 19)
        canvas.drawString(124, A4[1]-45, 'ARENA CASTELL')
        canvas.setFont('Helvetica', 9)
        canvas.drawString(124, A4[1]-64, 'CANCHA SINTÉTICA - AMAGUAÑA')
        canvas.setStrokeColor(linea)
        canvas.line(44, 48, A4[0]-44, 48)
        canvas.setFillColor(gris)
        canvas.setFont('Helvetica', 8)
        canvas.drawString(44, 32, 'ARENA CASTELL | Amaguaña, Quito, Ecuador')
        canvas.drawRightString(A4[0]-44, 32, f'Página {document.page}')
        canvas.restoreState()

    story = [p('COMPROBANTE DE REGISTRO', pequeno), p(dato['codigo'], titulo)]
    if contexto['prueba']:
        story.extend([p('VISTA PREVIA - Datos de ejemplo. No corresponde a una operación.', negrita), Spacer(1, 8)])
    filas = [('Titular', dato['cliente']), ('Fecha del registro', dato['fecha']+' (Ecuador)'),
             ('Método de pago', dato['metodo'])]
    if dato['cedula']:
        filas.append(('Cédula', dato['cedula']))
    filas.extend(contexto['detalles'])
    tabla = Table([[p(k, pequeno), p(v)] for k, v in filas], colWidths=[126, ancho-126], hAlign='LEFT')
    tabla.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),
                              ('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),5),
                              ('BOTTOMPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,-1),0.4,linea)]))
    story.extend([tabla, Spacer(1, 24)])
    servicio = Table([
        [p('Servicio', blanco),p('Cant.', blanco),p('V. unitario', blanco),p('Importe', blanco)],
        [[p(dato['servicio'], negrita),p(dato['descripcion'], pequeno)], p(dato['cantidad']),
         p(dato['unitario'], derecha),p(dato['total'], derecha)],
    ], colWidths=[ancho-212, 42, 85, 85], hAlign='LEFT', repeatRows=1)
    servicio.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),tinta),('VALIGN',(0,0),(-1,-1),'TOP'),
                                 ('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),12),
                                 ('LINEBELOW',(0,1),(-1,1),0.6,linea)]))
    story.extend([KeepTogether([servicio, Spacer(1,14),p('IMPORTE REGISTRADO', ParagraphStyle('LabelTotal',parent=pequeno,alignment=TA_RIGHT)),
                               p(dato['total'], total)]), Spacer(1,18),p(contexto['indicacion']), Spacer(1,10)])
    if dato['orden_id']:
        story.append(p('Operación: '+dato['orden_id'], pequeno))
    story.append(p('Conserva este comprobante para consultar tu registro. La verificación del abono corresponde a la administración.', pequeno))
    doc.build(story, onFirstPage=cabecera, onLaterPages=cabecera)
    return buffer.getvalue()
