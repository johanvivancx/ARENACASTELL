# Scripts para pgAdmin

La explicación completa está en [Crear la base en pgAdmin](../../docs/PGADMIN_PASO_A_PASO.md).

Para una base nueva se ejecutan los pasos `01` al `07` en orden. Los pasos `08` y `09` agregan datos ficticios y son opcionales. El paso `10` sirve para revisar las validaciones.

Si `arena_castell` ya tiene información, no repitas los archivos que crean tablas. Guarda un respaldo y usa solo la actualización necesaria:

- `11`: campos para correos.
- `12`: tarifas y cumpleaños de 3 horas.
- `13`: Pasochoa Cup sexta edición.
- `14`: efectivo y tarjeta de crédito/débito.

Cuando termines, vuelve a la carpeta principal y ejecuta:

```powershell
.\.venv\Scripts\python.exe manage.py check-db
```
