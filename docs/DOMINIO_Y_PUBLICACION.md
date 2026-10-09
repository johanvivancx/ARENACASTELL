# Publicar Arena Castell en el dominio

El dominio `arenacastell.com` mostrará la parte pública desde Cloudflare Pages. GitHub guardará el código y Cloudflare publicará una nueva versión cuando hagas `push` a `main`. La página estará alojada en Cloudflare, no en GitHub Pages. El inicio, los resultados, las tablas, los goleadores y las fotos se pueden publicar ahora.

## Preparar los archivos

El exportador prepara únicamente los archivos que deben ser públicos. Puedes probarlo desde la carpeta del proyecto con:

```powershell
.\.venv\Scripts\python.exe tools\exportar_publico.py
```

Esto crea `public/` con HTML, CSS, JavaScript e imágenes. No copia `.env`, Python, SQL, Excel, vocalías ni respaldos. La carpeta `public/` está excluida de Git. Cloudflare ejecutará el mismo exportador en cada despliegue.

## Conectar Cloudflare Pages con GitHub

1. Antes de crear el proyecto, sube a GitHub `tools/exportar_publico.py` y esta guía mediante tus comandos habituales de `git add`, `git commit` y `git push`. Comprueba que `.env` no esté entre los archivos preparados para el commit. No necesitas subir la carpeta `public/`.
2. En la pantalla de Cloudflare **Make something new**, elige **Connect GitHub**. Autoriza únicamente el repositorio de Arena Castell si GitHub te ofrece esa opción. Selecciona **Pages** como tipo de proyecto y `main` como rama de producción.
3. Configura **Framework preset: None**, **Build command: `python tools/exportar_publico.py`** y **Build output directory: `public`**. Deja el directorio raíz en la raíz del repositorio. Si Cloudflare intenta instalar dependencias de Python innecesarias, agrega la variable de compilación `SKIP_DEPENDENCY_INSTALL=true`; el exportador usa solo la biblioteca estándar.
4. Pulsa **Save and Deploy**. Abre la dirección `*.pages.dev` que entregue Cloudflare y comprueba el inicio y el torneo desde el celular. No conectes todavía el dominio si esa prueba falla.
5. En el proyecto de Pages abre **Custom domains → Set up a domain**. Escribe `arenacastell.com` y continúa. El dominio debe figurar en la misma cuenta de Cloudflare. Si hay registros `A` anteriores que apuntan a GitHub (`185.199.*.153`), elimina solamente esos registros cuando Cloudflare te lo indique; conserva los demás registros de correo o verificación.
6. Cuando el dominio figure activo, abre `https://arenacastell.com/` y `https://arenacastell.com/pages/torneos.html`.

En cada actualización de la página, haz tu `git push origin main` manualmente. Cloudflare preparará y publicará la nueva versión automáticamente. GitHub sirve como origen del código; las visitas a la página se atienden desde Cloudflare.

Después de verificar que el dominio funciona, retira el antiguo sitio de GitHub Pages desde el repositorio sin borrar el código: en la sección **GitHub Pages** usa **Unpublish site**. El archivo `CNAME` que apuntaba el repositorio al dominio se elimina en el siguiente commit.

Guías oficiales: [integración con Git](https://developers.cloudflare.com/pages/get-started/git-integration/), [dominio personalizado](https://developers.cloudflare.com/pages/configuration/custom-domains/) y [retirar GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/unpublishing-a-github-pages-site).

Las cuentas, reservas, pagos, administración y correos necesitan alojar Python y PostgreSQL. La preparación de Render, sin cambiar todavía el dominio ni la web pública, está en [RENDER_PASO_A_PASO.md](RENDER_PASO_A_PASO.md).

## Pagos y calendario

Antes de ejecutar este código con una base existente, guarda un respaldo y aplica `sql/pgadmin/16_aprobacion_y_calendario.sql` desde Query Tool conectado a `arena_castell`. No vuelvas a crear las tablas. Este archivo puede repetirse y conserva pagos anteriores.

- Una transferencia queda pendiente con su referencia. El administrador debe comprobar el movimiento en su banco antes de aprobarla en **Administración → Transferencias por revisar**. También puede rechazarla con un motivo.
- No se confirma la reserva ni el cupo hasta aprobar el cobro. Si el horario ya fue ocupado, no se completa la aprobación; corresponde resolver el dinero recibido con el cliente.
- El efectivo se confirma al cobrarlo en cancha.
- Súper Chaca cuesta $65 al inscribirse y $30 por mensualidad. La inscripción incluye el primer mes, dos uniformes y una mochila pequeña.
- Pasochoa Cup abre inscripciones del 1 al 30 de abril de 2027 e inicia el 1 de mayo de 2027.

Los pagos históricos no se convierten automáticamente en pagos verificados.

## Crear administrador y reiniciar

Desde la carpeta del proyecto:

```powershell
.\.venv\Scripts\python.exe manage.py create-admin
```

Para crear un administrador en la base publicada de Render desde tu equipo, usa `manage.py create-admin --render`. El comando pedirá la **External Database URL** de Render de forma oculta y confirmará el destino. `create-admin` sin esa opción utiliza la base de tu `.env` local.

Completa los datos y guarda la contraseña de forma privada. Para cargar el código actualizado, detén el servidor con Ctrl+C y vuelve a ejecutar:

```powershell
.\.venv\Scripts\python.exe manage.py check-db
.\.venv\Scripts\python.exe server.py
```

El alojamiento de Python y PostgreSQL se configurará después de contratarlo.
