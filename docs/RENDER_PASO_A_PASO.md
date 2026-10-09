# Preparar Python y PostgreSQL en Render

La web pública sigue en Cloudflare Pages durante esta preparación. No cambies los DNS de `arenacastell.com` hasta probar todas las funciones en la URL temporal de Render. Un `git push` a `main` actualiza Cloudflare Pages; después de crear el Web Service también iniciará un despliegue en Render.

## 1. Crear PostgreSQL

En Render, elige **New → Postgres** y la región **Virginia (US East)**. El Web Service debe usar la misma región para conectarse por la red privada. Para pruebas sin datos reales puedes empezar con Free; la base gratuita caduca a los 30 días y no tiene respaldos. Para datos reales elige un plan de pago con copias de seguridad. Guarda el nombre del servicio y, en la sección **Connect**, identifica la **Internal Database URL**. No compartas esa URL: contiene una contraseña.

Si quieres conservar usuarios y operaciones de la base que tienes en tu computadora, primero hay que hacer un respaldo y planear la migración. **No ejecutes `init-db` ni `seed` en una base que ya tenga datos.**

## 2. Crear el Web Service

Selecciona tu repositorio de Arena Castell con esta configuración:

| Campo | Valor |
| --- | --- |
| Name | `arenacastell-api` (o un nombre disponible) |
| Language | `Python 3` |
| Branch | `main` |
| Region | `Virginia (US East)` |
| Root Directory | vacío |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python server.py` |
| Compute | Free para pruebas; plan de pago al publicar para usuarios reales |

En **Environment Variables**, agrega `DATABASE_URL` con la URL **interna** de Postgres, `APP_ORIGIN` con la dirección HTTPS exacta del Web Service (por ejemplo `https://arenacastell-api.onrender.com` si ese es el nombre que Render asigna), `COOKIE_SECURE=true` y `SMTP_ENABLED=false`. No agregues `PORT`: Render lo asigna automáticamente. Si aún no conoces la URL definitiva del servicio, corrige `APP_ORIGIN` inmediatamente después de crearlo y redepliega antes de probar formularios.

No uses **Add from .env**: el `.env` local contiene la dirección y contraseña de tu PostgreSQL local. No agregues Secret Files ni Disk para esta configuración; los datos persistentes van en Postgres. Los correos se habilitan después de probar una cuenta SMTP de producción.

## 3. Preparar la base y probar

Desde el Shell del Web Service, después de verificar que `DATABASE_URL` apunta a la base correcta:

```sh
python manage.py init-db
python manage.py seed
python manage.py check-db
python manage.py create-admin
```

Estos comandos de inicialización son **solo para una base nueva y vacía**. `create-admin` pide los datos y la contraseña por consola; no los pongas en GitHub ni en mensajes. Si la base se migró desde tu computadora, usa únicamente `python manage.py check-db` y verifica que estén los usuarios y las operaciones esperadas.

Abre la URL `*.onrender.com` y comprueba inicio, catálogo, registro, inicio de sesión, reservas, inscripciones, pagos pendientes y panel administrativo. Verifica también que no se pueda acceder a `/server.py`, `/.env` ni a `/sql/schema.sql`. No cambies el dominio hasta que los flujos estén comprobados. En Render Free los puertos SMTP 25, 465 y 587 están bloqueados: usa la API HTTPS de Resend descrita en `INICIAR.md` y mantén `SMTP_ENABLED=false`. Solo configura SMTP si cambias el Web Service a una instancia que permita esos puertos.

## 4. Cambiar el dominio cuando todo esté listo

Cuando el servicio completo funcione, agrega `arenacastell.com` como dominio personalizado del Web Service y cambia el DNS en Cloudflare siguiendo las instrucciones que muestre Render. Actualiza `APP_ORIGIN=https://arenacastell.com`, conserva `COOKIE_SECURE=true` y comprueba HTTPS, inicio de sesión, formularios y redirecciones. Hasta ese momento la web pública en Cloudflare Pages permanece intacta.
