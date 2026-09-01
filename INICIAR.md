# Iniciar Arena Castell

Esta guía sirve para preparar el proyecto en una computadora con Windows. Los comandos se ejecutan desde la terminal de Visual Studio Code, dentro de la carpeta `ARENACASTELL`.

## Lo que necesitas

- Python 3.14.
- PostgreSQL y pgAdmin4.
- Git, solo si vas a descargar o subir cambios.
- Una cuenta de Gmail con contraseña de aplicación, únicamente si quieres enviar correos.

## 1. Crear la base

Para una instalación nueva, abre pgAdmin4 y sigue [la guía de pgAdmin](docs/PGADMIN_PASO_A_PASO.md). Debes ejecutar los scripts `01` al `07` en el orden indicado.

Si la base ya existe, no repitas los archivos que crean tablas. Guarda un respaldo y revisa en la misma guía cuáles de los pasos `11` al `14` necesitas.

## 2. Preparar Python

Comprueba la versión:

```powershell
python --version
```

Si todavía no existe `.venv`, créalo:

```powershell
py -3.14 -m venv .venv
```

Instala las dependencias:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

No es obligatorio activar el entorno si escribes la ruta completa de Python como en estos ejemplos.

## 3. Preparar `.env`

El archivo `.env` guarda la conexión local y las claves. No debe subirse a GitHub.

Si todavía no existe, copia la plantilla:

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

Abre `.env` y completa tus propios datos. Un ejemplo local es:

```dotenv
DATABASE_URL=postgresql://arena_app:TU_CLAVE@127.0.0.1:5432/arena_castell
APP_ORIGIN=http://127.0.0.1:8765
COOKIE_SECURE=false
SMTP_ENABLED=false
```

La clave de `DATABASE_URL` es la del usuario de PostgreSQL, no la contraseña de una cuenta de la página. Si la clave contiene caracteres especiales como `@`, `#`, `:` o `/`, deben escribirse codificados dentro de la URL.

Comprueba la conexión:

```powershell
.\.venv\Scripts\python.exe manage.py check-db
```

La terminal debe mostrar que la conexión y las tablas están correctas.

## 4. Crear el administrador

Ejecuta:

```powershell
.\.venv\Scripts\python.exe manage.py create-admin
```

La terminal pedirá nombre, correo, cédula, celular y contraseña. La contraseña debe tener al menos 10 caracteres. Después podrás iniciar sesión desde la página.

El formulario público siempre crea clientes. El rol de administrador se crea desde este comando para evitar que cualquier persona se dé permisos.

### Cuentas de demostración opcionales

Solo para una base de prueba local puedes usar:

```powershell
.\.venv\Scripts\python.exe manage.py create-demo
```

Se crean estas cuentas ficticias:

| Rol | Correo | Contraseña |
|---|---|---|
| Administrador | `admin@arena.test` | `CastellAdmin!2026` |
| Cliente | `cliente@arena.test` | `CastellCliente!2026` |

No uses estas claves en una página pública ni con información real.

## 5. Configurar Gmail, si lo vas a usar

Primero activa la verificación en dos pasos de Google y crea una contraseña de aplicación para Arena Castell. No uses la contraseña normal de Gmail.

Completa estas variables en `.env`:

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

Revisa la configuración sin mostrar la clave:

```powershell
.\.venv\Scripts\python.exe manage.py check-email
```

Envía una prueba a la misma cuenta de `SMTP_USER`:

```powershell
.\.venv\Scripts\python.exe manage.py test-email
```

Revisa también la carpeta de spam. Si `SMTP_ENABLED=false`, las operaciones siguen funcionando, pero los mensajes quedan como locales y no se envían.

## 6. Abrir la página

Inicia el servidor:

```powershell
.\.venv\Scripts\python.exe server.py
```

Abre [http://127.0.0.1:8765/](http://127.0.0.1:8765/) y deja la terminal abierta. Para detener el servidor usa `Ctrl+C`.

No abras `index.html` con doble clic ni uses solo Live Server si quieres probar la base. Esas opciones muestran el HTML, pero no ejecutan la API de Python.

## 7. Ejecutar las pruebas

Instala las herramientas de desarrollo y ejecuta pytest:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas crean una base temporal y no deben usar información real. El usuario de PostgreSQL de las pruebas necesita permiso para crear y eliminar esa base temporal.

## Problemas comunes

| Problema | Qué revisar |
|---|---|
| No conecta con PostgreSQL | Servicio iniciado, nombre de la base, usuario, clave y puerto 5432. |
| Falta una tabla o función | Orden de los scripts de pgAdmin. No vuelvas a crear todo sobre una base con datos. |
| El puerto 8765 está ocupado | Cierra la otra ejecución de Python y vuelve a iniciar el servidor. |
| La página abre, pero no guarda | Confirma que entraste por `http://127.0.0.1:8765/` y que Python sigue activo. |
| No aparece un torneo | Revisa que esté visible, abierto, con cupos y con una fecha futura en la base. |
| El correo no llega | Contraseña de aplicación, `SMTP_ENABLED`, spam y panel de correos del administrador. |
| Un enlace del correo no abre en el celular | `127.0.0.1` solo existe en la computadora que ejecuta el servidor. |

Para una publicación real hacen falta un servidor para Python, una base PostgreSQL accesible de forma segura y HTTPS. GitHub Pages por sí solo no ejecuta el backend.
