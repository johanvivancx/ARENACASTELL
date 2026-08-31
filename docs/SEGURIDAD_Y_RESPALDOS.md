# Seguridad y copias de la base

## Cuentas y permisos

Los clientes solo pueden ver sus reservas e inscripciones. El administrador puede consultar los registros del complejo. Estos permisos se revisan en Python; no dependen solo de esconder botones.

La contraseña se guarda como un hash, no como texto legible. Las sesiones duran ocho horas. Los formularios usan un token CSRF y los enlaces de recuperación vencen en 30 minutos. Al cambiar la contraseña se cierran las sesiones anteriores.

El navegador no recibe claves de PostgreSQL ni de Gmail. Las consultas SQL usan parámetros para separar los datos recibidos del código de la consulta.

## Archivos privados

No subas `.env`, copias de la base ni archivos con datos personales a GitHub. `.gitignore` los excluye, pero hay que revisar cada commit. Si guardas el proyecto en OneDrive, controla quién tiene acceso a esa carpeta.

El servidor solo publica `index.html`, los HTML de `pages/` y los recursos permitidos de `assets/`. Los archivos Python, SQL y de configuración no se pueden descargar desde las rutas del sitio.

## Usuario de PostgreSQL

El usuario que crea las tablas puede tener permisos de administración. Para el uso habitual de la página conviene una cuenta con permisos limitados. [sql/permisos.sql](../sql/permisos.sql) sirve de guía para preparar `arena_app`; hay que crear ese rol y asignarle su contraseña antes de aplicar los permisos.

Cliente y Administrador son roles de la página. No son cuentas distintas de PostgreSQL. No compartas la cuenta de conexión de la base con los clientes.

## Hacer una copia en pgAdmin

1. Haz clic derecho en la base `arena_castell` y elige **Backup**.
2. Selecciona el formato **Custom**.
3. Guarda el archivo con una fecha, por ejemplo `arena-2026-08-31.backup`, fuera de las carpetas públicas.
4. Comprueba que pgAdmin indique que terminó sin errores.

Antes de cambiar tablas o cargar datos, guarda una copia. Si la página empieza a usarse a diario, haz copias frecuentes y conserva más de una fecha. No se ha configurado una copia automática.

## Probar una restauración

Crea otra base vacía, por ejemplo `arena_restauracion_prueba`. Haz clic derecho sobre ella, elige **Restore** y selecciona el archivo de respaldo. Revisa las tablas y algunos registros después de restaurar.

No hagas la prueba sobre la base que estás usando: podrías mezclar o sobrescribir datos. Guarda los respaldos con acceso limitado, porque contienen información de las cuentas.

## Antes de publicar la página

El servidor actual escucha en `127.0.0.1`, para trabajar desde el mismo equipo. Publicar el repositorio en GitHub no pone Python ni PostgreSQL en Internet.

Para que otras personas usen el sistema desde fuera hace falta preparar el alojamiento, HTTPS y las claves del servidor. Con HTTPS se debe activar `COOKIE_SECURE=true`. Los pagos todavía no están conectados a un banco. El correo puede enviarse después de configurar Gmail y comprobar la cuenta.
