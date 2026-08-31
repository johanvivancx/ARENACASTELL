# Guía para explicar el proyecto

Esta guía me sirve para ordenar la exposición. No hace falta memorizarla; lo importante es poder mostrar qué hace la página y cómo se guardan los datos.

## Presentación

“Mi proyecto se llama Arena Castell. Es una página para una cancha sintética de Amaguaña. Permite organizar reservas, inscripciones a torneos y alumnos de la escuela Súper Chaca. Cada cliente tiene su historial y el administrador puede revisar los registros desde un solo lugar.”

## Qué mostrar

1. Abrir el inicio y enseñar los tres servicios, las fotos y la información de contacto.
2. Iniciar sesión como cliente y crear una reserva para una fecha futura.
3. Registrar el pago y mostrar el comprobante en Mi actividad.
4. Intentar otra reserva en el mismo horario para mostrar cómo se evita el cruce.
5. Inscribir un alumno de prueba y explicar cómo se eligen categoría y horario.
6. Entrar como administrador y mostrar reservas, pagos, mensualidades y correos.

La Copa actual ya está en juego y no admite inscripciones nuevas. Para explicar el registro de equipos se puede mostrar el código y las pruebas con una convocatoria ficticia; no hay que reabrir la Copa. Usa datos ficticios para no mostrar información personal durante la exposición.

## Preguntas que debo poder responder

| Pregunta | Explicación sencilla |
|---|---|
| ¿Qué hace HTML? | Muestra la estructura y los formularios de las páginas. |
| ¿Para qué se usa Python? | Revisa los datos, calcula los costos y trabaja con PostgreSQL. |
| ¿Dónde se guardan los registros? | En las tablas de PostgreSQL; no en el HTML. |
| ¿Dónde se usa herencia? | Cliente y Administrador heredan de Usuario. |
| ¿Dónde se usa polimorfismo? | Cada servicio tiene su propio método calcular_costo, y crear_orden lo llama de la misma manera. |
| ¿Qué hace el validador de cédula? | Revisa el formato y el dígito verificador. No consulta el Registro Civil. |
| ¿Para qué sirve un trigger? | Revisa una regla cuando se inserta o cambia un registro, como evitar un horario ocupado. |
| ¿Qué hace el procedimiento? | Registra una mensualidad de $50 y evita repetir el pago. Se ejecuta con CALL. |
| ¿Para qué sirven las vistas? | Reúnen datos de varias tablas para mostrar reportes. |
| ¿Se realizan cobros bancarios? | No. Se registra la operación, pero todavía no hay conexión con un banco. |
| ¿Se envían correos? | El código está preparado para Gmail; hay que configurar la cuenta y probar el envío. |

## Antes de exponer

Revisar que PostgreSQL y Python estén iniciados. Tener a mano los diagramas y un ejemplo de cada operación. No mostrar `.env`, contraseñas ni enlaces de recuperación. Si algo todavía está pendiente, explicar qué falta sin presentarlo como terminado.
