# Publicar Arena Castell en el dominio

La página que ya funciona en GitHub Pages puede mostrarse con `https://arenacastell.com/`. El archivo `CNAME` de la carpeta principal indica a GitHub cuál es el dominio. El inicio, los resultados, las tablas, los goleadores y las fotos se publican desde el repositorio actual.

## Conectar el dominio

1. Sube manualmente los cambios del proyecto a `main`. Revisa `git diff --cached --name-only`: `.env`, respaldos, Excel y vocalías no deben aparecer.
2. En el repositorio de GitHub abre **Settings → Pages**. Comprueba que la publicación se hace desde `main` y `/ (root)`. En **Custom domain** escribe `arenacastell.com` y pulsa **Save**.
3. En Cloudflare entra en **Domains → arenacastell.com → DNS → Records**. Crea cuatro registros tipo `A`, todos con nombre `@`:

   | Tipo | Nombre | Dirección IPv4 |
   | --- | --- | --- |
   | A | @ | 185.199.108.153 |
   | A | @ | 185.199.109.153 |
   | A | @ | 185.199.110.153 |
   | A | @ | 185.199.111.153 |

   Deja cada registro en **DNS only** (nube gris) mientras GitHub verifica el dominio y emite el certificado. Si hay registros `A` de `@` hacia otro sitio, quítalos para que no interfieran.
4. Para usar también `www.arenacastell.com`, crea un registro `CNAME` con nombre `www` y destino `johanvivancx.github.io` (sin `/ARENACASTELL`), también en **DNS only**.
5. En **GitHub → Settings → Pages**, cuando el dominio esté verificado, activa **Enforce HTTPS**. Comprueba `https://arenacastell.com/` y `https://arenacastell.com/pages/torneos.html` desde el celular.

GitHub indica que la propagación DNS puede tardar hasta 24 horas. Si GitHub crea un commit automático al guardar el dominio, ejecuta `git pull --ff-only origin main` en tu computadora antes de trabajar de nuevo.

Guías oficiales: [dominio personalizado](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site) y [HTTPS](https://docs.github.com/en/pages/getting-started-with-github-pages/securing-your-github-pages-site-with-https).

En el dominio se verán las páginas informativas y el torneo. Las cuentas, reservas, pagos, administración y correos necesitan alojar Python y PostgreSQL. Cuando contrates ese alojamiento, cambiaremos el destino del dominio y probaremos las funciones allí.

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

Completa los datos y guarda la contraseña de forma privada. Para cargar el código actualizado, detén el servidor con Ctrl+C y vuelve a ejecutar:

```powershell
.\.venv\Scripts\python.exe manage.py check-db
.\.venv\Scripts\python.exe server.py
```

El alojamiento de Python y PostgreSQL se configurará después de contratarlo.
