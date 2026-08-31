# Pruebas del proyecto

La última ejecución completa terminó con **65 pruebas aprobadas**. Se usaron Python 3.14.6 y PostgreSQL 18.6 en una base de prueba separada.

## Qué comprueban

| Parte | Casos revisados |
|---|---|
| Cédula | Números con formato o verificador incorrecto, tanto en Python como en SQL. |
| Clases | Herencia, contraseña privada y cálculo de costos de cada servicio. |
| Cuentas | Registro como cliente, inicio de sesión y acceso al perfil. |
| Reservas | Horarios válidos, cruces, reservas seguidas, solicitudes simultáneas y cumpleaños de 3 horas. |
| Torneos | Sexta edición de Pasochoa Cup: pago de $30, máximo 16 equipos, cierre al comenzar y script que no duplica ni reabre la convocatoria. Límites de 15 o 20 jugadores según el torneo. |
| Escuela | Edades de 4 a 17 años, categoría, horario y mensualidad de $50. |
| Pagos | Tarifas de $27, $30 y $25 por hora según el servicio, rechazo de duplicados y conservación de importes anteriores. |
| Permisos | Historial de cada titular y reportes solo para el administrador. |
| Recuperación | Enlace de un solo uso, vencimiento y cierre de sesiones anteriores. |
| Correo | Envío después de guardar, reintentos, TLS, estados y cancelación de enlaces inválidos. |
| Páginas | Enlaces locales, etiquetas, idioma e identificación de campos. |
| Archivos privados | Rechazo de rutas que intentan descargar `.env`, Python o SQL. |

Las pruebas de correo bloquean las conexiones externas. Comprueban la lógica del envío, pero no demuestran que una cuenta real de Gmail esté configurada. Eso se revisa con `manage.py test-email` después de guardar la clave localmente.

## Ejecutar las pruebas

Desde la carpeta principal:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

El usuario de PostgreSQL usado por las pruebas necesita permiso para crear una base temporal. Se puede configurar `TEST_DATABASE_ADMIN_URL` en el entorno para usar una cuenta distinta de la aplicación. No publiques esa dirección si contiene una contraseña.

La prueba crea una base con nombre `test_arena_...` y elimina solo esa base al terminar. No limpia las tablas de `arena_castell`.

## Revisión de colores

Estas son algunas combinaciones medidas en el diseño:

| Combinación | Contraste |
|---|---:|
| Texto principal sobre fondo gris oscuro | 16.44:1 |
| Texto secundario sobre panel gris | 8.47:1 |
| Texto oscuro sobre botón plateado | 12.99:1 |
| Borde del formulario sobre fondo oscuro | 4.86:1 |
| Borde de foco sobre el control | 9.08:1 |

Estas medidas no sustituyen revisar cada pantalla. Falta comprobar el uso con lector de pantalla y hacer una revisión completa en distintos tamaños de pantalla. Los pasos están en [ACCESIBILIDAD.md](ACCESIBILIDAD.md).

Se revisaron Inicio, Reservas, Torneos y el formulario de reserva en Chrome con anchos de 1360 y 390 píxeles. No hubo desbordes horizontales ni imágenes rotas. Se comprobó el menú móvil, el cambio entre servicios y el total de $75 del cumpleaños. Las cinco fotos de Pasochoa Cup cargaron correctamente.

También se revisó la sexta edición en esos dos tamaños. Desde una cuenta de prueba se completó
la inscripción, revisión, pago de $30, confirmación e historial. El cupo disponible bajó de 16
a 15 y el administrador vio la operación y su importe. No hubo errores de JavaScript.
Se comprobó que la página desactiva la inscripción si no existe la convocatoria, está cerrada
o tiene sus cupos completos. No se usaron cuentas personales ni se enviaron correos reales.

## Qué no está probado todavía

No se ha realizado un cobro bancario: no hay una pasarela integrada. Tampoco se ha confirmado aquí la entrega de correo desde la cuenta personal. Las pruebas automáticas no sustituyen probar la página en un celular ni comprobar su uso desde Internet.

El diagrama de la base se revisó en sus cuatro páginas. Las guías y el código deben seguir usando los mismos nombres de tablas, campos y archivos.
