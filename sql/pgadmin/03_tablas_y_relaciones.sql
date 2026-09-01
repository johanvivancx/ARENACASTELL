-- Crea tablas y relaciones
-- Ejecuta después del anterior
BEGIN;

-- Guarda cuentas y roles
CREATE TABLE usuarios (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre varchar(100) NOT NULL CHECK (length(trim(nombre)) BETWEEN 2 AND 100),
  cedula varchar(10) NOT NULL UNIQUE CHECK (validar_cedula(cedula)),
  email varchar(254) NOT NULL UNIQUE CHECK (email = lower(email) AND email ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'),
  telefono varchar(10) NOT NULL CHECK (telefono ~ '^09[0-9]{8}$'),
  password_hash text NOT NULL CHECK (length(password_hash) >= 60),
  rol varchar(10) NOT NULL DEFAULT 'CLIENTE' CHECK (rol IN ('CLIENTE','ADMIN')),
  session_version integer NOT NULL DEFAULT 1 CHECK (session_version > 0),
  creado_en timestamptz NOT NULL DEFAULT current_timestamp
);

-- Guarda canchas y tarifas
CREATE TABLE canchas (
  id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre varchar(80) NOT NULL UNIQUE,
  tarifa_hora numeric(8,2) NOT NULL CHECK (tarifa_hora > 0),
  tarifa_evento numeric(8,2) NOT NULL CHECK (tarifa_evento > 0),
  tarifa_cumpleanos numeric(8,2) NOT NULL CHECK (tarifa_cumpleanos > 0)
);

-- Guarda torneos disponibles
CREATE TABLE torneos (
  id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre varchar(100) NOT NULL UNIQUE,
  descripcion text NOT NULL,
  fecha_inicio date NOT NULL,
  costo numeric(8,2) NOT NULL CHECK (costo > 0),
  cupos integer NOT NULL DEFAULT 16 CHECK (cupos BETWEEN 2 AND 64),
  max_jugadores integer NOT NULL DEFAULT 20 CHECK (max_jugadores BETWEEN 1 AND 20),
  visible boolean NOT NULL DEFAULT true,
  abierto boolean NOT NULL DEFAULT true
);

-- Une usuarios con servicios
CREATE TABLE ordenes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id bigint NOT NULL REFERENCES usuarios(id),
  tipo varchar(20) NOT NULL CHECK (tipo IN ('RESERVA','TORNEO','ESCUELA','MENSUALIDAD')),
  metodo_previsto varchar(16) CHECK (metodo_previsto IS NULL OR metodo_previsto = 'EFECTIVO'),
  descripcion varchar(250) NOT NULL,
  monto numeric(10,2) NOT NULL CHECK (monto > 0),
  estado varchar(12) NOT NULL DEFAULT 'PENDIENTE' CHECK (estado IN ('PENDIENTE','PAGADA','CANCELADA')),
  creado_en timestamptz NOT NULL DEFAULT current_timestamp
);

CREATE INDEX idx_orden_usuario ON ordenes(usuario_id, creado_en DESC);

-- Guarda horarios reservados
CREATE TABLE reservas (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  orden_id uuid NOT NULL UNIQUE REFERENCES ordenes(id),
  cancha_id integer NOT NULL REFERENCES canchas(id),
  tipo_evento varchar(12) NOT NULL CHECK (tipo_evento IN ('HORA','EVENTO','CUMPLEANOS')),
  inicio timestamptz NOT NULL,
  fin timestamptz NOT NULL,
  estado varchar(12) NOT NULL DEFAULT 'PENDIENTE' CHECK (estado IN ('PENDIENTE','CONFIRMADA','CANCELADA')),
  CHECK (fin > inicio AND fin - inicio <= interval '6 hours'),
  CHECK (extract(epoch FROM fin-inicio)::bigint % 3600 = 0),
  CONSTRAINT reservas_sin_solapamiento EXCLUDE USING gist (
    cancha_id WITH =, tstzrange(inicio,fin,'[)') WITH &&
  ) WHERE (estado = 'CONFIRMADA')
);

-- Guarda equipos inscritos
CREATE TABLE equipos (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  orden_id uuid NOT NULL UNIQUE REFERENCES ordenes(id),
  torneo_id integer NOT NULL REFERENCES torneos(id),
  nombre varchar(80) NOT NULL CHECK (length(trim(nombre)) BETWEEN 2 AND 80),
  estado varchar(12) NOT NULL DEFAULT 'PENDIENTE' CHECK (estado IN ('PENDIENTE','CONFIRMADO','CANCELADO'))
);

CREATE UNIQUE INDEX uq_equipo_nombre ON equipos(torneo_id, lower(nombre)) WHERE estado <> 'CANCELADO';

-- Guarda jugadores por equipo
CREATE TABLE jugadores (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  equipo_id bigint NOT NULL REFERENCES equipos(id),
  nombre varchar(100) NOT NULL CHECK (length(trim(nombre)) BETWEEN 2 AND 100),
  cedula varchar(10) NOT NULL CHECK (validar_cedula(cedula)),
  posicion integer NOT NULL CHECK (posicion BETWEEN 1 AND 20),
  UNIQUE(equipo_id, cedula), UNIQUE(equipo_id, posicion)
);

-- Guarda horarios escolares
CREATE TABLE horarios_chaca (
  id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  categoria varchar(6) NOT NULL CHECK (categoria IN ('Sub-6','Sub-8','Sub-10','Sub-12','Sub-14','Sub-16','Sub-18')),
  dias varchar(80) NOT NULL,
  activo boolean NOT NULL DEFAULT true,
  inicio time NOT NULL,
  fin time NOT NULL CHECK (fin>inicio),
  UNIQUE(categoria,dias,inicio), UNIQUE(id,categoria)
);

-- Guarda alumnos inscritos
CREATE TABLE inscripciones_chaca (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  orden_id uuid NOT NULL UNIQUE REFERENCES ordenes(id),
  alumno varchar(100) NOT NULL CHECK (length(trim(alumno)) BETWEEN 2 AND 100),
  cedula varchar(10) NOT NULL UNIQUE CHECK (validar_cedula(cedula)),
  nacimiento date NOT NULL,
  fecha_inscripcion date NOT NULL DEFAULT current_date,
  categoria varchar(6) NOT NULL CHECK (categoria IN ('Sub-6','Sub-8','Sub-10','Sub-12','Sub-14','Sub-16','Sub-18')),
  horario_id integer NOT NULL,
  FOREIGN KEY(horario_id,categoria) REFERENCES horarios_chaca(id,categoria),
  estado varchar(12) NOT NULL DEFAULT 'PENDIENTE' CHECK (estado IN ('PENDIENTE','ACTIVA','CANCELADA')),
  CHECK (extract(year FROM age(fecha_inscripcion,nacimiento)) BETWEEN 4 AND 17),
  CHECK (categoria = 'Sub-' || (2 * (extract(year FROM age(fecha_inscripcion,nacimiento))::integer / 2 + 1))::text)
);

-- Guarda periodos mensuales
CREATE TABLE mensualidades (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  orden_id uuid NOT NULL UNIQUE REFERENCES ordenes(id),
  inscripcion_id bigint NOT NULL REFERENCES inscripciones_chaca(id),
  periodo date NOT NULL CHECK (extract(day FROM periodo) = 1),
  UNIQUE(inscripcion_id,periodo)
);

-- Guarda pagos simulados
CREATE TABLE pagos (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  orden_id uuid NOT NULL UNIQUE REFERENCES ordenes(id),
  monto numeric(10,2) NOT NULL CHECK (monto > 0),
  metodo varchar(16) NOT NULL CHECK (metodo IN ('TRANSFERENCIA','EFECTIVO','TARJETA','DEBITO','CREDITO')),
  referencia varchar(64) NOT NULL UNIQUE,
  simulado boolean NOT NULL DEFAULT true CHECK (simulado),
  pagado_en timestamptz NOT NULL DEFAULT current_timestamp
);

-- Guarda correos pendientes
CREATE TABLE correo_salida (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  usuario_id bigint NOT NULL REFERENCES usuarios(id),
  orden_id uuid REFERENCES ordenes(id),
  asunto varchar(180) NOT NULL,
  cuerpo text NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT current_timestamp,
  destinatario varchar(254),
  estado_envio varchar(12) NOT NULL DEFAULT 'LOCAL'
    CHECK (estado_envio IN ('LOCAL','PENDIENTE','ENVIADO','ERROR','CANCELADO')),
  intentos smallint NOT NULL DEFAULT 0 CHECK (intentos BETWEEN 0 AND 5),
  proximo_intento timestamptz NOT NULL DEFAULT current_timestamp,
  enviado_en timestamptz,
  ultimo_error varchar(50),
  vence_en timestamptz,
  UNIQUE(orden_id,asunto)
);
CREATE INDEX idx_correo_pendiente ON correo_salida(proximo_intento,id) WHERE estado_envio='PENDIENTE';

-- Guarda enlaces temporales
CREATE TABLE restablecimientos (
  token_hash char(64) PRIMARY KEY,
  usuario_id bigint NOT NULL REFERENCES usuarios(id),
  vence_en timestamptz NOT NULL,
  usado boolean NOT NULL DEFAULT false
);

-- Controla intentos repetidos
CREATE TABLE intentos_acceso (
  clave char(64) PRIMARY KEY,
  intentos integer NOT NULL DEFAULT 1 CHECK (intentos > 0),
  inicio timestamptz NOT NULL DEFAULT current_timestamp
);

-- Guarda sesiones activas
CREATE TABLE sesiones (
  token_hash char(64) PRIMARY KEY,
  usuario_id bigint REFERENCES usuarios(id) ON DELETE CASCADE,
  csrf_token varchar(64) NOT NULL,
  vence_en timestamptz NOT NULL DEFAULT current_timestamp + interval '8 hours'
);

CREATE INDEX idx_sesiones_usuario ON sesiones(usuario_id);

COMMIT;
