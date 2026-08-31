# Tablas y relaciones de la base

Este diagrama muestra las 15 tablas de Arena Castell. Los nombres son los mismos que se usan en los scripts SQL y en Python.

La versión [PDF](DIAGRAMA_ENTIDAD_RELACION.pdf) está separada en cuatro páginas para que se lea mejor: reservas y pagos, torneos, escuela y acceso a la cuenta.

## Cómo leerlo

- **PK:** clave primaria; identifica un registro.
- **FK:** clave foránea; conecta con otra tabla.
- **UK o UQ:** valor o combinación que no se puede repetir.
- **1:N:** un registro puede relacionarse con varios. Por ejemplo, un usuario puede tener varias órdenes.
- **0..1:** la relación es opcional y admite como máximo un registro.

```mermaid
erDiagram
  usuarios ||--o{ ordenes : realiza
  canchas ||--o{ reservas : dispone
  ordenes ||--o| reservas : origina
  ordenes ||--o| pagos : recibe
  torneos ||--o{ equipos : agrupa
  ordenes ||--o| equipos : inscribe
  equipos ||--o{ jugadores : registra
  ordenes ||--o| inscripciones_chaca : crea
  horarios_chaca ||--o{ inscripciones_chaca : ofrece
  inscripciones_chaca ||--o{ mensualidades : genera
  ordenes ||--o| mensualidades : financia
  usuarios ||--o{ correo_salida : recibe
  ordenes o|--o{ correo_salida : documenta
  usuarios ||--o{ restablecimientos : solicita
  usuarios o|--o{ sesiones : accede
  usuarios {
    bigint id PK
    varchar nombre
    varchar cedula UK
    varchar email UK
    varchar telefono
    text password_hash
    varchar rol
    integer session_version
    timestamptz creado_en
  }
  canchas {
    integer id PK
    varchar nombre UK
    numeric tarifa_hora
    numeric tarifa_evento
    numeric tarifa_cumpleanos
  }
  torneos {
    integer id PK
    varchar nombre UK
    text descripcion
    date fecha_inicio
    numeric costo
    integer cupos
    integer max_jugadores
    boolean visible
    boolean abierto
  }
  ordenes {
    uuid id PK
    bigint usuario_id FK
    varchar tipo
    varchar descripcion
    numeric monto
    varchar estado
    timestamptz creado_en
  }
  reservas {
    bigint id PK
    uuid orden_id FK,UK
    integer cancha_id FK
    varchar tipo_evento
    timestamptz inicio
    timestamptz fin
    varchar estado
  }
  equipos {
    bigint id PK
    uuid orden_id FK,UK
    integer torneo_id FK
    varchar nombre
    varchar estado
  }
  jugadores {
    bigint id PK
    bigint equipo_id FK
    varchar nombre
    varchar cedula
    integer posicion
  }
  horarios_chaca {
    integer id PK
    varchar categoria
    varchar dias
    boolean activo
    time inicio
    time fin
  }
  inscripciones_chaca {
    bigint id PK
    uuid orden_id FK,UK
    varchar alumno
    varchar cedula UK
    date nacimiento
    date fecha_inscripcion
    varchar categoria FK
    integer horario_id FK
    varchar estado
  }
  mensualidades {
    bigint id PK
    uuid orden_id FK,UK
    bigint inscripcion_id FK
    date periodo
  }
  pagos {
    bigint id PK
    uuid orden_id FK,UK
    numeric monto
    varchar metodo
    varchar referencia UK
    boolean simulado
    timestamptz pagado_en
  }
  correo_salida {
    bigint id PK
    bigint usuario_id FK
    uuid orden_id FK
    varchar asunto
    text cuerpo
    timestamptz creado_en
    varchar destinatario
    varchar estado_envio
    smallint intentos
    timestamptz proximo_intento
    timestamptz enviado_en
    varchar ultimo_error
    timestamptz vence_en
  }
  restablecimientos {
    char token_hash PK
    bigint usuario_id FK
    timestamptz vence_en
    boolean usado
  }
  intentos_acceso {
    char clave PK
    integer intentos
    timestamptz inicio
  }
  sesiones {
    char token_hash PK
    bigint usuario_id FK
    varchar csrf_token
    timestamptz vence_en
  }
```

En la escuela, `horario_id` y `categoria` forman una clave foránea compuesta. Esto obliga a elegir un horario de la categoría correcta.

`intentos_acceso` no se conecta a un usuario porque también cuenta intentos antes de iniciar sesión. Las contraseñas se guardan como hash. Los correos de recuperación contienen enlaces de acceso, por eso la base y sus copias deben mantenerse privadas.

Las restricciones completas están en [el script de tablas](../sql/pgadmin/03_tablas_y_relaciones.sql). El diagrama explica las relaciones; no reemplaza los CHECK y triggers de la base.
