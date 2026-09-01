# Pagos y contacto

La pantalla de pago presenta tres opciones: transferencia bancaria, efectivo en la cancha y tarjeta de crédito/débito. Las imágenes se guardan en `assets/contacto/`. Los datos de la cuenta aparecen al seleccionar transferencia. Los enlaces de WhatsApp y Facebook de Arena Castell están en el pie de las páginas; la sección de Pasochoa Cup incluye su propia página de Facebook.

## Actualizar una base existente

1. Detener el servidor Python con Ctrl+C.
2. Guardar un respaldo de `arena_castell` desde pgAdmin, fuera del repositorio.
3. Abrir Query Tool sobre **arena_castell** y ejecutar completo `sql/pgadmin/14_metodos_pago.sql`.
4. Comprobar la conexión con `.\.venv\Scripts\python.exe manage.py check-db`.
5. Iniciar `.\.venv\Scripts\python.exe server.py` y actualizar el navegador con Ctrl+F5.

No repetir la creación de tablas. El paso 14 conserva los pagos de débito y crédito anteriores y puede ejecutarse otra vez. En una instalación vacía, los scripts 03 y el esquema completo ya incluyen los cambios.

## Efectivo al acercarse a la cancha

Elegir efectivo solo guarda `ordenes.metodo_previsto = 'EFECTIVO'`. La orden y su reserva o inscripción permanecen pendientes. No se inserta un pago, no se genera comprobante ni se envía una confirmación de cobro.

La persona debe coordinar con la cancha y acercarse antes del horario solicitado. Una solicitud pendiente no ocupa horarios ni consume cupos. La web lo indica al elegir efectivo y en Mi actividad.

Después de recibir el dinero, el administrador entra en **Admin → Efectivo pendiente en cancha → Registrar efectivo recibido**. Debe confirmar que lo recibió. El servidor comprueba el rol, la orden y la disponibilidad antes de registrar el pago. Una repetición no duplica el pago. Si el horario ya se ocupó, no se registra el cobro en el sistema: el operador debe acordar otra opción con el cliente.

El mismo recorrido permite registrar efectivo para reserva, torneo, escuela y mensualidad. Los reportes de pagos solo incluyen el importe después del registro del cobro.

## Transferencia y tarjeta

Se conserva el alcance del sistema: registra la operación, pero **no conecta con un banco ni procesa tarjetas**. La administración debe verificar los abonos. No se solicitan números de tarjeta, CVV ni claves bancarias.

`TARJETA` representa la opción conjunta de crédito/débito. `DEBITO` y `CREDITO` siguen admitidos para conservar los registros anteriores. Los correos, PDF, historial y reportes reconocen esos métodos y `EFECTIVO`.

## Pruebas

`tests/test_metodos_pago.py` comprueba efectivo pendiente, permisos de cobro, duplicados, conflictos de horario, torneo y escuela, métodos anteriores, comprobantes y repetición de la migración. Estas pruebas deben ejecutarse en una base separada y con SMTP bloqueado, como las demás pruebas del proyecto.
