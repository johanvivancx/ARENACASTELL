# Crear la base en pgAdmin4

La base se llama `arena_castell`. Los scripts están en `sql/pgadmin` y se ejecutan uno por uno. No borres una base que ya tenga datos para repetir la instalación.

## Orden de los scripts

| Paso | Archivo | Qué hace |
|---|---|---|
| 1 | `01_crear_base.sql` | Crea la base. Se ejecuta desde Query Tool de `postgres`, con Auto-commit activado. |
| 2 | `02_extension_y_cedula.sql` | Prepara la extensión y la función de cédula. |
| 3 | `03_tablas_y_relaciones.sql` | Crea las 15 tablas y sus relaciones. |
| 4 | `04_triggers.sql` | Agrega las reglas de reservas, equipos, jugadores y pagos. |
| 5 | `05_procedimientos.sql` | Crea el procedimiento de mensualidad. |
| 6 | `06_vistas.sql` | Crea los tres reportes. |
| 7 | `07_catalogo.sql` | Carga la cancha con las tarifas actuales, la Copa y los horarios. |
| 8, opcional | `08_datos_de_prueba_opcionales.sql` | Agrega personas y operaciones ficticias para probar. |
| 9, después del 8 | `09_call_y_consultas.sql` | Ejecuta el procedimiento con CALL y consulta los reportes. |
| 10 | `10_comprobar_validaciones.sql` | Comprueba la cédula y los elementos creados. |
| 11, solo para una versión anterior | `11_actualizar_correo_smtp.sql` | Agrega los campos de correo si todavía no existen. |
| 12, si ya tenías la base creada | `12_actualizar_tarifas_reservas.sql` | Actualiza las tarifas y la regla de 3 horas para cumpleaños. Conserva las órdenes y pagos anteriores. |

Después del paso 1, actualiza Databases y abre un nuevo Query Tool sobre **arena_castell**. Los pasos restantes se ejecutan ahí, no en `postgres`.

Para cada paso, reemplaza el texto del editor por el nuevo script y ejecútalo completo. Espera el resultado antes de pasar al siguiente. Si un bloque termina correctamente con `COMMIT`, sus cambios quedaron guardados. Si aparece un error, no sigas ejecutando otros scripts hasta revisarlo.

Los pasos 2 al 6 crean lo mismo que `sql/schema.sql`. Usa una sola forma de instalación: no ejecutes después ese archivo completo ni `manage.py init-db` sobre las tablas que acabas de crear.

## Qué revisar

En **Schemas → public** deben aparecer las tablas, funciones, procedimientos y vistas. La función `validar_cedula` comprueba diez dígitos, provincia y módulo 10. No consulta el Registro Civil.

El paso 8 es opcional y se ejecuta una sola vez. Sus nombres y cédulas son ficticios; no representan personas cuya identidad se haya verificado. Si no quieres esos ejemplos en tu base, puedes omitir los pasos 8 y 9 y probar luego con registros propios.

El paso 11 no hace falta si creaste las tablas con el script 03 actual, que ya incluye los campos de correo.

Ejecuta el paso 12 si usaste una versión anterior del paso 04 o si la cancha conserva las tarifas anteriores.
Puedes ejecutarlo después del 07 aunque omitas los ejemplos 08 y 09. No borra datos ni cambia los importes
de órdenes existentes. Una instalación que use los pasos 04 y 07 actuales ya incluye estos cambios.

## Conectar la página

Después del paso 7, y del 12 si estás actualizando una base anterior, sigue [INICIAR.md](../INICIAR.md) para completar `.env`, comprobar la conexión y crear tu administrador.

La conexión funciona así: la página envía una solicitud a Python y Python consulta PostgreSQL. VS Code sirve para editar y ejecutar el proyecto; pgAdmin permite administrar la base.

No compartas la contraseña de PostgreSQL ni el archivo `.env`. Para activar el envío desde tu correo, sigue [la guía de Gmail](CORREOS_GMAIL.md).
