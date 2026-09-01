# Crear la base en pgAdmin4

La base del proyecto se llama `arena_castell`. Los scripts están en `sql/pgadmin` y se ejecutan uno por uno. Antes de comenzar, confirma si vas a crear una base nueva o actualizar una que ya tiene datos.

## Base nueva

### 1. Crear `arena_castell`

1. Abre pgAdmin4 y conecta tu servidor de PostgreSQL.
2. Selecciona la base `postgres`.
3. Abre **Query Tool**.
4. Activa **Auto-commit**.
5. Abre y ejecuta completo `sql/pgadmin/01_crear_base.sql`.

Cuando termine, actualiza **Databases**. Debe aparecer `arena_castell`.

### 2. Crear las tablas y reglas

Abre otro Query Tool, esta vez sobre `arena_castell`, y ejecuta estos archivos en orden:

| Paso | Archivo | Resultado |
|---|---|---|
| 02 | `02_extension_y_cedula.sql` | Extensión necesaria y validación de cédula. |
| 03 | `03_tablas_y_relaciones.sql` | Las 15 tablas, claves y restricciones. |
| 04 | `04_triggers.sql` | Reglas para reservas, torneos, jugadores y pagos. |
| 05 | `05_procedimientos.sql` | Procedimiento de mensualidades. |
| 06 | `06_vistas.sql` | Tres vistas para reportes. |
| 07 | `07_catalogo.sql` | Cancha, precios, torneos y horarios de Súper Chaca. |

Reemplaza el contenido del editor antes de abrir el siguiente archivo. Si aparece un error, detente y revisa ese paso. No sigas con los demás hasta corregirlo.

Los pasos `08` y `09` son opcionales. Crean datos ficticios para practicar consultas. No los ejecutes en una base que usarás con información real. El paso `10` sirve para comprobar los objetos y las validaciones.

## Base que ya existe

No ejecutes otra vez los pasos `01` al `07` sobre una base con datos. Primero crea un respaldo y después aplica solo la actualización que te falte:

| Paso | Cuándo se usa |
|---|---|
| 11 | Si la base antigua no tiene los campos de envío de correos. |
| 12 | Si todavía tiene las tarifas anteriores o no controla las 3 horas de cumpleaños. |
| 13 | Si falta Pasochoa Cup sexta edición. |
| 14 | Si faltan efectivo y la opción unificada de tarjeta de crédito/débito. |

Estas actualizaciones están pensadas para conservar los registros anteriores. Aun así, guarda siempre una copia antes de cambiar la estructura.

## Revisar que todo esté creado

En pgAdmin abre **Schemas → public**. Debes encontrar tablas, funciones, procedimientos y vistas.

También puedes ejecutar:

```sql
SELECT current_database();

SELECT count(*) AS tablas
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

SELECT * FROM vista_reporte_administrador LIMIT 5;
SELECT * FROM vista_mensualidades_escuela LIMIT 5;
SELECT * FROM vista_ocupacion_cancha LIMIT 5;
```

La primera consulta debe mostrar `arena_castell`. En una instalación nueva deben existir 15 tablas. Las vistas pueden aparecer vacías mientras no haya operaciones.

## Crear un usuario para la aplicación

Para no usar la cuenta principal de PostgreSQL todos los días, puedes crear `arena_app` desde **Login/Group Roles** en pgAdmin:

1. En **General** escribe `arena_app`.
2. En **Definition** asigna una contraseña propia.
3. En **Privileges** activa únicamente **Can login**. No le des permisos de superusuario ni para crear bases.
4. Guarda el rol.
5. Vuelve al Query Tool de `arena_castell` con la cuenta dueña de la base y ejecuta `sql/permisos.sql`.

Ese archivo permite consultar y guardar datos, pero no borrar tablas ni cambiar la estructura.

## Conectar Python con PostgreSQL

La página no se conecta directamente con pgAdmin. El navegador habla con Python y Python usa `DATABASE_URL` para conectarse a PostgreSQL.

En `.env` coloca tus propios datos:

```dotenv
DATABASE_URL=postgresql://arena_app:TU_CLAVE@127.0.0.1:5432/arena_castell
```

Después ejecuta:

```powershell
.\.venv\Scripts\python.exe manage.py check-db
```

Si todavía no creaste el usuario limitado `arena_app`, puedes conectarte de forma local con un usuario existente y luego preparar los permisos con `sql/permisos.sql`. Nunca subas la clave ni `.env` a GitHub.

## Crear un respaldo

1. Haz clic derecho sobre `arena_castell` y elige **Backup**.
2. Usa formato **Custom**.
3. Guarda el archivo fuera del repositorio, con la fecha en el nombre.
4. Confirma que pgAdmin termine sin errores.

Antes de una presentación conviene guardar una copia y comprobar que el servidor, la base y una cuenta de administrador funcionan en la misma computadora.
