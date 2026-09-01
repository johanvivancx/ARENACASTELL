# Arena Castell

Página web para organizar las reservas de la cancha Arena Castell, en Amaguaña. También permite registrar equipos para torneos y alumnos de la escuela de fútbol Súper Chaca.

**Autor: Johan Vivanco. Proyecto individual.**

## Qué se puede hacer

- Crear una cuenta y actualizar los datos personales.
- Reservar la cancha por horas, para cumpleaños o para eventos.
- Inscribir un equipo cuando haya un torneo abierto.
- Inscribir alumnos de 4 a 17 años y registrar sus mensualidades.
- Consultar el historial y los comprobantes de cada cuenta.
- Revisar reservas, pagos y correos desde el panel del administrador.
- Recibir confirmaciones con el logo, los datos del servicio y un comprobante PDF.

Las páginas usan HTML, CSS y JavaScript. Python 3.14 conecta los formularios con PostgreSQL. No se usa Flask. La apariencia es negra y plateada, con letra Arial y fotos de la cancha.

## Cómo abrirlo

El archivo principal es [index.html](index.html). Se puede abrir directamente para ver la información. Para iniciar sesión y guardar datos hay que ejecutar Python y tener la base creada.

Los pasos están en [INICIAR.md](INICIAR.md). La base se prepara con los archivos de [sql/pgadmin](sql/pgadmin), uno por uno.

## Archivos principales

| Archivo o carpeta | Para qué sirve |
|---|---|
| `index.html` | Página de inicio. |
| `pages/` | Las otras 18 páginas. |
| `assets/` | Estilos, JavaScript, logo y fotos. |
| `models.py` | Clases y cálculo de precios. |
| `services.py` | Registro, reservas, inscripciones y pagos. |
| `server.py` | Recibe las solicitudes de la página. |
| `db.py` | Abre la conexión con PostgreSQL. |
| `correos.py` | Envía los correos y registra sus intentos. |
| `comprobantes.py` | Prepara los datos del correo y el PDF adjunto. |
| `templates/correos/` | Diseño HTML del correo, preparado con Jinja2. |
| `manage.py` | Comandos para revisar la base y crear el administrador. |
| `sql/` | Tablas, funciones, triggers, procedimiento y vistas. |
| `tests/` | Pruebas del funcionamiento. |
| `docs/` | Explicaciones y guías. |

## Guías

- [Crear la base en pgAdmin](docs/PGADMIN_PASO_A_PASO.md).
- [Configurar Gmail](docs/CORREOS_GMAIL.md).
- [Actualizar pagos y enlaces de contacto](docs/PAGOS_Y_CONTACTO.md).
- [Subir cambios a GitHub](docs/GIT_GITHUB.md).
- [Cómo funciona el código](docs/ARQUITECTURA.md).
- [Diagramas técnicos: entidad-relación, modelo relacional y clases POO](docs/DIAGRAMAS_PROYECTO.md).
- [Páginas del sitio](docs/PAGINAS.md).
- [Diseño y accesibilidad](docs/ACCESIBILIDAD.md).
- [Datos de las fotos y flyers](docs/CONTENIDO_FLYERS.md).
- [Pruebas realizadas](docs/VERIFICACION.md).
- [Seguridad y copias de la base](docs/SEGURIDAD_Y_RESPALDOS.md).
- [Puntos de la rúbrica](docs/RUBRICA.md).
- [Guía para la exposición](docs/SUSTENTACION.md).

## Qué falta configurar

Los pagos se guardan en la base, pero todavía no están conectados a un banco. No se solicitan números de tarjeta ni CVV. El correo sí puede enviarse mediante Gmail cuando se configure la cuenta en `.env`.

La cancha cuesta $27 por hora y los eventos deportivos $30 por hora. Los cumpleaños tienen un paquete de 3 horas por $75, con decoración. Hay parqueadero privado y servicio de bar.

La Copa Castell se muestra en juego, con inscripciones cerradas. Pasochoa Cup tiene una sección con fotos y el resumen de su quinta edición: 800 niños premiados. La sexta edición empieza el 30 de septiembre de 2026: 16 equipos, $30 por inscripción y hasta 20 jugadores por equipo. Para agregarla a una base ya creada, ejecuta `sql/pgadmin/13_pasochoa_sexta_edicion.sql`. El mapa señala Amaguaña, no una dirección exacta.

El servidor actual funciona en el mismo equipo donde se ejecuta Python. Para publicarlo con acceso desde Internet hace falta preparar el alojamiento y HTTPS. `.env` contiene claves y nunca debe subirse a GitHub.
