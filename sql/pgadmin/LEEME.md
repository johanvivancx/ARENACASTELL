# Scripts para pgAdmin

La explicación completa está en [Crear la base en pgAdmin](../../docs/PGADMIN_PASO_A_PASO.md).

Para una base nueva se ejecutan los pasos `01` al `07` en orden. Los pasos `08` y `09` agregan datos ficticios y son opcionales. El paso `10` sirve para revisar las validaciones.

Si `arena_castell` ya tiene información, no repitas los archivos que crean tablas. Guarda un respaldo y usa solo la actualización necesaria:

- `11`: campos para correos.
- `12`: tarifas y cumpleaños de 3 horas.
- `13`: Pasochoa Cup sexta edición.
- `14`: transferencia y pago en cancha. Conserva pagos históricos con tarjeta.
- `15`: inscripción de Súper Chaca a $65 y mensualidad a $30. Ejecuta este archivo antes de registrar nuevos cobros con las tarifas nuevas. No cambia pagos anteriores.
- `16`: aprobación administrativa de transferencias, tarifas $65/$30 y Pasochoa Cup: inscripciones del 1 al 30 de abril de 2027 e inicio el 1 de mayo. Incluye la corrección del procedimiento de cobro; conserva pagos anteriores. Reinicia el servidor Python después de actualizar la base y el código.
- `20`: alumnos y pagos manuales de Súper Chaca. Se aplica automáticamente al iniciar el servidor actualizado; úsalo en pgAdmin solo si necesitas hacer la migración manualmente.

Cuando termines, vuelve a la carpeta principal y ejecuta:

```powershell
.\.venv\Scripts\python.exe manage.py check-db
```
