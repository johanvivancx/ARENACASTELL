-- PostgreSQL 18. Ejecutar en una base vacía; no elimina datos existentes.
BEGIN;
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE FUNCTION validar_cedula(cedula text) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE total integer := 0; digito integer; i integer;
BEGIN
  IF cedula !~ '^[0-9]{10}$' THEN RETURN false; END IF;
  IF substring(cedula,1,2)::integer NOT BETWEEN 1 AND 24
     OR substring(cedula,3,1)::integer > 5 THEN RETURN false; END IF;
  FOR i IN 1..9 LOOP
    digito := substring(cedula,i,1)::integer;
    IF i % 2 = 1 THEN digito := digito * 2; END IF;
    IF digito > 9 THEN digito := digito - 9; END IF;
    total := total + digito;
  END LOOP;
  RETURN (10 - total % 10) % 10 = substring(cedula,10,1)::integer;
END; $$;

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
CREATE TABLE canchas (
  id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre varchar(80) NOT NULL UNIQUE,
  tarifa_hora numeric(8,2) NOT NULL CHECK (tarifa_hora > 0),
  tarifa_evento numeric(8,2) NOT NULL CHECK (tarifa_evento > 0),
  tarifa_cumpleanos numeric(8,2) NOT NULL CHECK (tarifa_cumpleanos > 0)
);
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
CREATE FUNCTION controlar_reserva() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE hora_inicio timestamp; hora_fin timestamp;
BEGIN
  -- Los cumpleaños nuevos se reservan como paquete de tres horas.
  -- Cambiar solo el estado de una reserva anterior conserva su duración original.
  IF NEW.tipo_evento = 'CUMPLEANOS' AND NEW.fin - NEW.inicio <> interval '3 hours' THEN
    IF TG_OP = 'INSERT' THEN
      RAISE EXCEPTION 'El paquete de cumpleaños tiene una duración de 3 horas.' USING ERRCODE='23514';
    ELSIF (NEW.tipo_evento, NEW.inicio, NEW.fin) IS DISTINCT FROM (OLD.tipo_evento, OLD.inicio, OLD.fin) THEN
      RAISE EXCEPTION 'El paquete de cumpleaños tiene una duración de 3 horas.' USING ERRCODE='23514';
    END IF;
  END IF;
  hora_inicio := NEW.inicio AT TIME ZONE 'America/Guayaquil';
  hora_fin := NEW.fin AT TIME ZONE 'America/Guayaquil';
  IF NEW.estado <> 'CANCELADA' THEN
    IF NEW.inicio <= current_timestamp OR NEW.inicio > current_timestamp + interval '90 days' THEN
      RAISE EXCEPTION 'Elige una fecha futura dentro de los próximos 90 días.' USING ERRCODE='23514';
    END IF;
    IF hora_inicio::date <> hora_fin::date OR hora_inicio::time < time '08:00'
       OR hora_fin::time > time '23:00' OR extract(minute FROM hora_inicio) <> 0
       OR extract(second FROM hora_inicio) <> 0 THEN
      RAISE EXCEPTION 'La cancha atiende de 08:00 a 23:00, en horas completas.' USING ERRCODE='23514';
    END IF;
  END IF;
  IF NEW.estado = 'CONFIRMADA' AND EXISTS (
    SELECT 1 FROM reservas r WHERE r.cancha_id = NEW.cancha_id
      AND r.id IS DISTINCT FROM NEW.id AND r.estado = 'CONFIRMADA'
      AND tstzrange(r.inicio,r.fin,'[)') && tstzrange(NEW.inicio,NEW.fin,'[)')
  ) THEN
    RAISE EXCEPTION 'Ese horario acaba de ocuparse. Selecciona otro.' USING ERRCODE='23P01';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER trg_controlar_reserva BEFORE INSERT OR UPDATE ON reservas
FOR EACH ROW EXECUTE FUNCTION controlar_reserva();

CREATE TABLE equipos (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  orden_id uuid NOT NULL UNIQUE REFERENCES ordenes(id),
  torneo_id integer NOT NULL REFERENCES torneos(id),
  nombre varchar(80) NOT NULL CHECK (length(trim(nombre)) BETWEEN 2 AND 80),
  estado varchar(12) NOT NULL DEFAULT 'PENDIENTE' CHECK (estado IN ('PENDIENTE','CONFIRMADO','CANCELADO'))
);
CREATE UNIQUE INDEX uq_equipo_nombre ON equipos(torneo_id, lower(nombre)) WHERE estado <> 'CANCELADO';
CREATE FUNCTION controlar_cupo_torneo() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE torneo torneos;
BEGIN
  IF NEW.estado = 'CONFIRMADO' THEN
    SELECT * INTO torneo FROM torneos WHERE id=NEW.torneo_id FOR UPDATE;
    IF NOT torneo.abierto OR torneo.fecha_inicio <= current_date THEN
      RAISE EXCEPTION 'Las inscripciones de este torneo están cerradas.' USING ERRCODE='23514';
    END IF;
    IF (SELECT count(*) FROM equipos WHERE torneo_id=NEW.torneo_id AND estado='CONFIRMADO' AND id IS DISTINCT FROM NEW.id) >= torneo.cupos THEN
      RAISE EXCEPTION 'El torneo ya no tiene cupos.' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER trg_cupo_torneo BEFORE INSERT OR UPDATE ON equipos
FOR EACH ROW EXECUTE FUNCTION controlar_cupo_torneo();

CREATE TABLE jugadores (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  equipo_id bigint NOT NULL REFERENCES equipos(id),
  nombre varchar(100) NOT NULL CHECK (length(trim(nombre)) BETWEEN 2 AND 100),
  cedula varchar(10) NOT NULL CHECK (validar_cedula(cedula)),
  posicion integer NOT NULL CHECK (posicion BETWEEN 1 AND 20),
  UNIQUE(equipo_id, cedula), UNIQUE(equipo_id, posicion)
);
CREATE OR REPLACE FUNCTION limitar_jugadores() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE estado_equipo text; limite integer;
BEGIN
  -- Bloquear primero el torneo y luego el equipo conserva el mismo orden
  -- que la confirmación del pago y serializa los últimos puestos de la lista.
  SELECT t.max_jugadores INTO limite FROM torneos t JOIN equipos e ON e.torneo_id=t.id
    WHERE e.id=NEW.equipo_id FOR SHARE OF t;
  SELECT estado INTO estado_equipo FROM equipos WHERE id=NEW.equipo_id FOR UPDATE;
  IF estado_equipo <> 'CONFIRMADO' THEN
    RAISE EXCEPTION 'Primero completa el pago del equipo.' USING ERRCODE='23514';
  END IF;
  IF TG_OP = 'INSERT' OR NEW.equipo_id <> OLD.equipo_id THEN
    SELECT n INTO NEW.posicion FROM generate_series(1,limite) n
      WHERE NOT EXISTS (SELECT 1 FROM jugadores WHERE equipo_id=NEW.equipo_id AND posicion=n)
      ORDER BY n LIMIT 1;
    IF NEW.posicion IS NULL THEN
      RAISE EXCEPTION 'Este torneo admite como máximo % jugadores por equipo.', limite USING ERRCODE='23514';
    END IF;
  END IF;
  IF NEW.posicion > limite THEN
    RAISE EXCEPTION 'La posición supera el límite de % jugadores de este torneo.', limite USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER trg_limitar_jugadores BEFORE INSERT OR UPDATE ON jugadores
FOR EACH ROW EXECUTE FUNCTION limitar_jugadores();

CREATE OR REPLACE FUNCTION proteger_limite_torneo() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM equipos e JOIN jugadores j ON j.equipo_id=e.id
             WHERE e.torneo_id=NEW.id AND j.posicion>NEW.max_jugadores) THEN
    RAISE EXCEPTION 'No se puede reducir el límite: hay listas registradas que lo superan.' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER trg_proteger_limite BEFORE UPDATE OF max_jugadores ON torneos
FOR EACH ROW EXECUTE FUNCTION proteger_limite_torneo();

CREATE TABLE horarios_chaca (
  id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  categoria varchar(6) NOT NULL CHECK (categoria IN ('Sub-6','Sub-8','Sub-10','Sub-12','Sub-14','Sub-16','Sub-18')),
  dias varchar(80) NOT NULL,
  activo boolean NOT NULL DEFAULT true,
  inicio time NOT NULL,
  fin time NOT NULL CHECK (fin>inicio),
  UNIQUE(categoria,dias,inicio), UNIQUE(id,categoria)
);
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
CREATE TABLE mensualidades (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  orden_id uuid NOT NULL UNIQUE REFERENCES ordenes(id),
  inscripcion_id bigint NOT NULL REFERENCES inscripciones_chaca(id),
  periodo date NOT NULL CHECK (extract(day FROM periodo) = 1),
  UNIQUE(inscripcion_id,periodo)
);
CREATE TABLE pagos (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  orden_id uuid NOT NULL UNIQUE REFERENCES ordenes(id),
  monto numeric(10,2) NOT NULL CHECK (monto > 0),
  metodo varchar(16) NOT NULL CHECK (metodo IN ('TRANSFERENCIA','EFECTIVO','TARJETA','DEBITO','CREDITO')),
  referencia varchar(64) NOT NULL UNIQUE,
  simulado boolean NOT NULL DEFAULT true CHECK (simulado),
  pagado_en timestamptz NOT NULL DEFAULT current_timestamp
);
CREATE FUNCTION validar_pago() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE orden ordenes;
BEGIN
  SELECT * INTO orden FROM ordenes WHERE id=NEW.orden_id FOR UPDATE;
  IF orden.estado <> 'PENDIENTE' OR NEW.monto <> orden.monto THEN
    RAISE EXCEPTION 'El pago debe coincidir con el valor de una orden pendiente.' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER trg_validar_pago BEFORE INSERT ON pagos FOR EACH ROW EXECUTE FUNCTION validar_pago();

CREATE PROCEDURE cobrar_mensualidad(p_orden uuid, p_metodo text)
LANGUAGE plpgsql AS $$
DECLARE orden ordenes; cuota mensualidades; ingreso date;
BEGIN
  SELECT * INTO orden FROM ordenes WHERE id=p_orden FOR UPDATE;
  IF orden.id IS NULL OR orden.tipo NOT IN ('ESCUELA','MENSUALIDAD') OR orden.monto <> 50 THEN
    RAISE EXCEPTION 'La mensualidad es de $50.' USING ERRCODE='23514';
  END IF;
  IF orden.estado = 'PAGADA' THEN RETURN; END IF;
  SELECT * INTO cuota FROM mensualidades WHERE orden_id=p_orden FOR UPDATE;
  IF cuota.id IS NULL THEN RAISE EXCEPTION 'No existe mensualidad.' USING ERRCODE='23514'; END IF;
  SELECT fecha_inscripcion INTO ingreso FROM inscripciones_chaca WHERE id=cuota.inscripcion_id FOR UPDATE;
  IF cuota.periodo < date_trunc('month',ingreso)::date OR cuota.periodo > (date_trunc('month',current_date)+interval '1 month')::date THEN
    RAISE EXCEPTION 'Solo se admiten períodos desde el ingreso hasta el próximo mes.' USING ERRCODE='23514';
  END IF;
  INSERT INTO pagos(orden_id,monto,metodo,referencia) VALUES(p_orden,50,p_metodo,'SIM-' || p_orden::text);
  UPDATE ordenes SET estado='PAGADA' WHERE id=p_orden;
  UPDATE inscripciones_chaca SET estado='ACTIVA' WHERE id=cuota.inscripcion_id;
END; $$;

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
CREATE TABLE restablecimientos (
  token_hash char(64) PRIMARY KEY,
  usuario_id bigint NOT NULL REFERENCES usuarios(id),
  vence_en timestamptz NOT NULL,
  usado boolean NOT NULL DEFAULT false
);
CREATE TABLE intentos_acceso (
  clave char(64) PRIMARY KEY,
  intentos integer NOT NULL DEFAULT 1 CHECK (intentos > 0),
  inicio timestamptz NOT NULL DEFAULT current_timestamp
);
CREATE TABLE sesiones (
  token_hash char(64) PRIMARY KEY,
  usuario_id bigint REFERENCES usuarios(id) ON DELETE CASCADE,
  csrf_token varchar(64) NOT NULL,
  vence_en timestamptz NOT NULL DEFAULT current_timestamp + interval '8 hours'
);
CREATE INDEX idx_sesiones_usuario ON sesiones(usuario_id);

CREATE VIEW vista_reporte_administrador AS
SELECT p.id AS pago_id, p.pagado_en, u.id AS usuario_id, u.nombre, u.email,
  o.id AS orden_id, o.tipo, o.descripcion, p.monto, p.metodo, p.referencia,
  c.nombre AS cancha, r.inicio AS reserva_inicio, t.nombre AS torneo,
  e.nombre AS equipo, sc.alumno, m.periodo, p.simulado
FROM pagos p JOIN ordenes o ON o.id=p.orden_id JOIN usuarios u ON u.id=o.usuario_id
LEFT JOIN reservas r ON r.orden_id=o.id LEFT JOIN canchas c ON c.id=r.cancha_id
LEFT JOIN equipos e ON e.orden_id=o.id LEFT JOIN torneos t ON t.id=e.torneo_id
LEFT JOIN mensualidades m ON m.orden_id=o.id LEFT JOIN inscripciones_chaca sc ON sc.id=m.inscripcion_id;

CREATE VIEW vista_mensualidades_escuela AS
SELECT sc.id AS inscripcion_id, sc.alumno, sc.categoria, u.nombre AS representante,
  u.email, sc.estado, count(p.id) AS cuotas_pagadas, coalesce(sum(p.monto),0) AS total_pagado,
  max(m.periodo) FILTER (WHERE p.id IS NOT NULL) AS ultimo_periodo,
  coalesce(bool_or(m.periodo=date_trunc('month',current_date)::date AND p.id IS NOT NULL),false) AS mes_actual_pagado
FROM inscripciones_chaca sc JOIN ordenes origen ON origen.id=sc.orden_id
JOIN usuarios u ON u.id=origen.usuario_id LEFT JOIN mensualidades m ON m.inscripcion_id=sc.id
LEFT JOIN pagos p ON p.orden_id=m.orden_id
GROUP BY sc.id, u.nombre, u.email;

CREATE VIEW vista_ocupacion_cancha AS
SELECT c.id, c.nombre, date_trunc('month',r.inicio AT TIME ZONE 'America/Guayaquil')::date AS mes,
  count(r.id) AS reservas, coalesce(sum(extract(epoch FROM r.fin-r.inicio)/3600),0) AS horas,
  coalesce(sum(p.monto),0) AS ingresos_simulados
FROM canchas c LEFT JOIN reservas r ON r.cancha_id=c.id AND r.estado='CONFIRMADA'
LEFT JOIN pagos p ON p.orden_id=r.orden_id GROUP BY c.id,c.nombre,mes;
COMMIT;
