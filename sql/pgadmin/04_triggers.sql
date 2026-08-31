-- Reservas sin solapamiento, cupos y jugadores de torneo, y validación de pagos.
-- Ejecutar sobre arena_castell, después del paso anterior.
BEGIN;

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

COMMIT;
