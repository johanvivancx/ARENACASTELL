# Manual de usuario de Arena Castell

Este manual explica los recorridos principales de la página. Para usar cuentas, reservas y pagos, el servidor de Python y PostgreSQL deben estar activos.

## Entrar a la página

Abre `http://127.0.0.1:8765/` en el navegador de la computadora donde está funcionando el servidor.

Desde el menú puedes entrar a Reservas, Torneos, Súper Chaca, Iniciar sesión y las opciones de contacto. En celular, el menú se abre desde el botón de navegación.

## Crear una cuenta

1. Entra en **Iniciar sesión**.
2. Selecciona **Crear cuenta**.
3. Escribe nombres y apellidos, cédula ecuatoriana, celular y correo.
4. Crea una contraseña de al menos 10 caracteres y repítela.
5. Acepta el aviso de privacidad y guarda el formulario.

El correo y la cédula no se pueden repetir. Si un dato no es válido, la página muestra qué debes corregir.

## Iniciar y cerrar sesión

Para entrar, escribe el correo y la contraseña registrados. Después aparecerán **Mi actividad** y **Mi perfil** en el menú.

Para salir, entra en **Mi perfil** y pulsa **Cerrar sesión**. En una computadora compartida, cierra la sesión cuando termines.

## Reservar la cancha

1. Entra en **Reservas**.
2. Elige reserva por hora, cumpleaños o evento deportivo.
3. Pulsa el botón para continuar.
4. Selecciona cancha, fecha, duración y horario disponible.
5. Revisa el resumen y registra la solicitud.
6. Escoge el método de pago.

Los horarios se muestran para fechas futuras dentro de los próximos 90 días. El cumpleaños es un paquete fijo de 3 horas.

## Métodos de pago

La pantalla presenta tres opciones:

- **Transferencia bancaria:** muestra los datos de la cuenta para realizar la transferencia.
- **Efectivo en la cancha:** deja la operación pendiente hasta que el administrador reciba y registre el dinero.
- **Tarjeta de crédito/débito:** registra una demostración del método, sin pedir número de tarjeta ni CVV.

La página no está conectada a un banco. Antes de finalizar, revisa el servicio, el valor y el método seleccionado.

Una solicitud en efectivo todavía no confirma el horario ni el cupo. La persona debe coordinar con la cancha y acercarse antes de la actividad.

## Inscribir un equipo a un torneo

1. Entra en **Torneos**.
2. Revisa la información y confirma que exista una convocatoria abierta.
3. Pulsa el botón de inscripción.
4. Elige el torneo, escribe el nombre del equipo y acepta las condiciones.
5. Revisa el resumen y registra el método de pago.

Cuando la inscripción queda confirmada, entra en **Mi actividad** y abre **Mi equipo**. Desde ahí puedes añadir o retirar jugadores hasta completar el límite del torneo. Cada jugador necesita nombre y cédula.

Si el torneo ya empezó, está cerrado o no tiene cupos, la página no permite confirmar otra inscripción.

## Inscribir a un alumno en Súper Chaca

1. Entra en **Súper Chaca** y revisa categorías y horarios.
2. Pulsa el botón de inscripción.
3. Escribe los datos del alumno y su fecha de nacimiento.
4. Escoge la categoría y la jornada disponibles.
5. Acepta las condiciones y continúa al pago.

La escuela admite edades de 4 a 17 años. La categoría se comprueba con la fecha de nacimiento. La mensualidad es de $50.

Para pagar otro mes, entra en **Mi actividad**, busca **Mis mensualidades** y usa la opción de renovación disponible.

## Consultar actividad y comprobantes

En **Mi actividad** puedes filtrar por reservas, torneos y Súper Chaca. Cada registro muestra su estado y las opciones que correspondan.

En **Avisos y comprobantes** puedes revisar confirmaciones. La pantalla final también permite imprimir el comprobante. Si el correo está configurado, se envía una copia con un PDF adjunto.

El comprobante registra lo guardado por el sistema. No reemplaza una factura ni demuestra por sí solo que un banco recibió el dinero.

## Actualizar el perfil

En **Mi perfil** puedes cambiar tus datos. Para modificar el correo o la cédula se pide la contraseña actual. Esto evita que otra persona cambie información importante si encuentra una sesión abierta.

## Recuperar la contraseña

1. En la pantalla de inicio de sesión pulsa **Olvidé mi contraseña**.
2. Escribe el correo registrado.
3. Abre el mensaje recibido y entra en el enlace.
4. Escribe y confirma la nueva contraseña.

El enlace vence y solo se puede usar una vez. Si el correo no está activado en el servidor, el administrador deberá revisar el mensaje guardado de forma local.

## Panel del administrador

El enlace **Admin** solo aparece en una cuenta con ese rol. El panel tiene estas partes:

- **Reservas realizadas:** muestra titular, fecha, horario y estado.
- **Todas las operaciones:** reúne reservas, torneos, escuela y mensualidades.
- **Efectivo pendiente en cancha:** permite registrar el dinero recibido.
- **Auditoría de pagos:** muestra método, referencia, valor y fecha.
- **Control de mensualidades:** ayuda a revisar cuotas de Súper Chaca.
- **Ocupación de cancha:** resume reservas y horas por mes.
- **Envío de correos:** muestra mensajes pendientes, enviados o con error.

El filtro de fechas se aplica al reporte de pagos. El botón **Exportar pagos CSV** descarga esa información para revisarla en una hoja de cálculo.

Antes de registrar efectivo, confirma que realmente recibiste el dinero. Si el horario se ocupó mientras la solicitud estaba pendiente, el sistema no debe guardar el cobro y tendrás que acordar otra opción con el cliente.

## Si algo no funciona

- Actualiza la página con `Ctrl+F5` después de cambiar archivos.
- Comprueba que la terminal del servidor siga abierta.
- Si no aparecen datos, ejecuta `manage.py check-db`.
- Si no llega un correo, revisa spam y la sección **Envío de correos**.
- Si una fecha u horario no aparece, revisa que cumpla el rango permitido y que no esté ocupado.
- No compartas contraseñas ni capturas del archivo `.env`.
