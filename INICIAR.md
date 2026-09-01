# Cómo iniciar Arena Castell

Abre la carpeta `arena-castell` en Visual Studio Code. Los comandos de esta guía se ejecutan en su terminal.

## 1. Preparar la base

Necesitas PostgreSQL y pgAdmin4. Sigue [los pasos de pgAdmin](docs/PGADMIN_PASO_A_PASO.md) para crear `arena_castell` y ejecutar los scripts del 1 al 7.

Si ya ejecutaste un paso correctamente, no lo repitas. Tampoco ejecutes `manage.py init-db` ni `sql/schema.sql` sobre esas mismas tablas.

Si tu base ya tenía las tarifas anteriores, ejecuta el paso 12 para actualizar los precios y el paquete de cumpleaños. Ese paso conserva las reservas y los pagos existentes.

## 2. Preparar Python

Si actualizaste a las opciones de transferencia, efectivo y tarjeta, ejecuta primero
`sql/pgadmin/14_metodos_pago.sql` sobre la base existente, después de guardar un respaldo.
No repitas la creación de tablas. Consulta [Pagos y contacto](docs/PAGOS_Y_CONTACTO.md).

El proyecto usa Python 3.14. Si todavía no tienes la carpeta `.venv`, créala:

```powershell
py -3.14 -m venv .venv
```

Instala las dependencias:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

No hace falta activar el entorno si usas los comandos completos de esta guía. Si ya tenías el proyecto, vuelve a ejecutar la instalación cuando cambie `requirements.txt`. Ahora incluye Jinja2 para los correos y ReportLab para los PDF. Conserva tu `.env` y reinicia el servidor después de instalar.

## 3. Configurar la conexión

Si no tienes `.env`, copia la plantilla. Este comando conserva el archivo si ya existe:

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

Abre `.env` y completa `DATABASE_URL`. Este ejemplo supone que usas el usuario `postgres` y el puerto `5432`:

```dotenv
DATABASE_URL=postgresql://postgres:TU_CLAVE_POSTGRESQL@127.0.0.1:5432/arena_castell
APP_ORIGIN=http://127.0.0.1:8765
COOKIE_SECURE=false
```

Usa tus propios datos de PostgreSQL. Esa clave no es la contraseña de tu cuenta de la página. Si contiene caracteres como `@`, `#`, `:` o `/`, hay que codificarlos en la dirección de conexión. No compartas `.env` ni capturas que muestren su contenido.

Comprueba la conexión:

```powershell
.\.venv\Scripts\python.exe manage.py check-db
```

## 4. Crear el administrador

```powershell
.\.venv\Scripts\python.exe manage.py create-admin
```

La terminal pedirá nombre, correo, cédula, celular y contraseña. Usa esos datos para iniciar sesión en la web. Las cuentas creadas desde el formulario público siempre son clientes.

## 5. Abrir la página

```powershell
.\.venv\Scripts\python.exe server.py
```

Abre [http://127.0.0.1:8765/](http://127.0.0.1:8765/). Mantén la terminal abierta. Para detener el servidor, pulsa Ctrl+C. Cuando cambies la configuración o archivos Python, vuelve a iniciarlo.

Si abres `index.html` con doble clic, podrás ver las páginas informativas, pero no iniciar sesión ni guardar reservas.

## Correo y pruebas

Para activar los envíos, sigue [la guía de Gmail](docs/CORREOS_GMAIL.md). Con `SMTP_ENABLED=false` no se mandan correos externos.

Las [pruebas del proyecto](docs/VERIFICACION.md) usan una base aparte. No necesitas crear cuentas de prueba para usar tu propio administrador. Si quieres cargar los ejemplos del paso 8 de SQL, recuerda que son personas ficticias.

## Si aparece un error

| Problema | Qué revisar |
|---|---|
| No conecta con PostgreSQL | Que el servicio esté iniciado y que usuario, clave, puerto y base sean correctos. |
| Falta una tabla o función | El orden de los scripts. No borres la base para volver a empezar. |
| El puerto está ocupado | Detén la otra ejecución de Python o cambia el puerto en `APP_ORIGIN`. |
| El correo no llega | La contraseña de aplicación, el panel de correos y la carpeta de spam. |
| Un enlace del correo no abre en otro equipo | Las direcciones `127.0.0.1` solo funcionan en el equipo del servidor. |

No expongas este servidor directamente a Internet. El alojamiento público requiere otra configuración.
