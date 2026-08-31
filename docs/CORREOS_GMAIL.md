# Cómo configurar Gmail

Arena Castell envía confirmaciones de reservas, inscripciones, mensualidades y recuperación de contraseña. Jinja2 prepara el diseño HTML y ReportLab crea el comprobante PDF. El envío sigue usando Gmail con las bibliotecas `smtplib`, `email` y `ssl` de Python, sin Flask.

Si ya recibiste el correo de prueba, conserva tu cuenta y clave de Gmail. Para usar el nuevo diseño, detén el servidor con Ctrl+C e instala las dependencias actualizadas:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Este cambio no necesita scripts nuevos de PostgreSQL. Luego ejecuta `test-email`, como se explica abajo.

## Preparar Google

1. Inicia sesión con la cuenta desde la que quieres enviar los mensajes.
2. Abre [Seguridad de Google](https://myaccount.google.com/security) y activa la verificación en dos pasos.
3. Entra en [Contraseñas de aplicación](https://myaccount.google.com/apppasswords), escribe “Arena Castell” como nombre y crea una clave.
4. Guarda esa clave en `.env`. No uses la contraseña normal de Gmail ni la compartas en mensajes o capturas.

Google puede limitar esta opción en cuentas de organizaciones o con ciertas protecciones activadas. Si no aparece, consulta al administrador de la cuenta; no desactives la seguridad para forzar el acceso. Al cambiar la contraseña principal de Google, se revocan las contraseñas de aplicación. [Ayuda de Google](https://support.google.com/accounts/answer/185833?hl=es).

## Completar `.env`

Edita las líneas que ya existen. No borres la conexión de PostgreSQL ni repitas las mismas variables.

```dotenv
SMTP_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=tu_correo@gmail.com
SMTP_PASSWORD=TU_CONTRASENA_DE_APLICACION
MAIL_FROM_NAME=ARENA CASTELL
PUBLIC_BASE_URL=
```

Reemplaza el correo y la clave de ejemplo. Los mensajes salen desde `SMTP_USER` hacia la dirección registrada en cada cuenta. Si tu archivo todavía tiene `MAIL_FROM`, esa variable antigua ya no se usa.

El puerto 587 usa STARTTLS. También se admite el puerto 465 con `SMTP_SECURITY=ssl`. La conexión debe mantener el cifrado y la comprobación del certificado. [Configuración SMTP de Google](https://knowledge.workspace.google.com/admin/gmail/send-email-from-a-printer-scanner-or-app?hl=es).

## Revisar la base

El script 03 actual ya incluye los campos de correo. Si creaste la base con esa versión, no necesitas otra actualización.

Solo para una base anterior: abre Query Tool sobre `arena_castell` y ejecuta [el script 11](../sql/pgadmin/11_actualizar_correo_smtp.sql). Añade los campos sin borrar datos. No vuelvas a crear las tablas.

## Probar el envío

Desde la carpeta principal del proyecto:

```powershell
.\.venv\Scripts\python.exe manage.py check-email
```

Este comando revisa la configuración, pero no se conecta a Gmail ni manda mensajes. Para enviar una prueba a tu propia cuenta, ejecuta:

```powershell
.\.venv\Scripts\python.exe manage.py test-email
```

La segunda orden sí manda un correo real, solo a la cuenta configurada en `SMTP_USER`. Muestra el nuevo diseño y adjunta un PDF marcado como vista previa, con datos de ejemplo. No crea una reserva, inscripción ni pago en la base. Revisa entrada y spam, abre el PDF y comprueba la vista en tu celular. Después inicia o reinicia Python:

```powershell
.\.venv\Scripts\python.exe server.py
```

El servidor busca correos pendientes cada 10 segundos y debe permanecer abierto para enviarlos. Las nuevas confirmaciones llevan un comprobante PDF; también se puede imprimir el comprobante desde la página. Los correos que ya llegaron a Gmail no cambian.

## Diseño y comprobante

El correo tiene el logo, los datos del servicio, el importe y un botón para consultar la operación. El logo va incluido en el mensaje: no necesita cargar una imagen desde tu computadora. También se incluye una versión en texto para los lectores que no muestran HTML.

La plantilla está en `templates/correos/mensaje.html`. Los textos y datos se preparan en `comprobantes.py`. Jinja2 escapa lo que escriben los usuarios para que un nombre no se convierta en código HTML. Antes de crear el PDF también se escapan esos textos.

El importe sale del pago guardado, no de la tarifa actual. Se consulta solo la operación del titular del correo. La cédula se muestra parcialmente y los PDF se crean en memoria, sin guardar datos personales en una carpeta pública. El servidor tampoco permite descargar las plantillas ni los archivos Python.

El adjunto se llama **Comprobante de registro**. No es una factura tributaria ni demuestra por sí solo que un banco recibió dinero; la administración debe comprobar el abono. Los correos de recuperación tienen un botón para cambiar la contraseña y no llevan PDF.

## Estados del correo

El administrador puede revisarlos en **Admin → Envío de correos**.

| Estado | Qué significa |
|---|---|
| LOCAL | Se guardó cuando el envío estaba apagado. No se mandará después por activar Gmail. |
| PENDIENTE | Está esperando envío o reintento. |
| ENVIADO | El servidor de correo lo aceptó. Todavía puede terminar en spam o rebotar. |
| ERROR | Fallaron los cinco intentos. Hay que revisar la causa. |
| CANCELADO | Cambió el correo de la cuenta o el enlace ya no es válido. |

Después de un fallo se espera 1, 2, 4 y 8 minutos entre reintentos. La reserva o inscripción no se borra si falla el correo. Si el proceso se cierra justo después de enviarlo y antes de guardar el resultado, podría llegar duplicado.

`AUTENTICACION_SMTP` indica un problema de cuenta o clave. `DESTINATARIO_RECHAZADO` pide revisar el correo del destinatario. Ante errores de TLS o conexión, revisa red y configuración sin desactivar el cifrado.

`CONTENIDO_CORREO` significa que no se pudo preparar el diseño o el PDF. Revisa la instalación de dependencias, la plantilla y el logo. No hace falta cambiar la clave de Gmail por ese error. La operación permanece guardada y no se envía un mensaje incompleto.

## Enlaces y claves

Si `PUBLIC_BASE_URL` queda vacío, los enlaces usan `APP_ORIGIN`. Una dirección como `http://127.0.0.1:8765` solo funciona en el mismo equipo del servidor. Para abrir los enlaces desde otros dispositivos hace falta alojar la página con HTTPS y poner su dirección pública en esa variable.

Los enlaces de recuperación vencen en 30 minutos y solo funcionan una vez. No aparecen en los reportes del administrador ni en el historial de operaciones.

No subas `.env` a GitHub. Como la carpeta está en OneDrive, revisa también quién puede acceder a esa copia. El envío de correos no conecta los pagos con un banco.
