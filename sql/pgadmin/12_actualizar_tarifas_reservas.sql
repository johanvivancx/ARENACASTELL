-- Actualiza tarifas y cumpleaños
-- Actualiza una base anterior
-- Conserva valores anteriores
BEGIN;

INSERT INTO canchas(nombre,tarifa_hora,tarifa_evento,tarifa_cumpleanos)
VALUES ('Cancha principal · Fútbol 7',27.00,30.00,25.00)
ON CONFLICT (nombre) DO UPDATE SET
  tarifa_hora=EXCLUDED.tarifa_hora,
  tarifa_evento=EXCLUDED.tarifa_evento,
  tarifa_cumpleanos=EXCLUDED.tarifa_cumpleanos;

-- Valida cada reserva
CREATE OR REPLACE FUNCTION controlar_reserva() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE hora_inicio timestamp; hora_fin timestamp;
BEGIN
  -- Exige tres horas
  -- Conserva reservas anteriores
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

COMMIT;

SELECT nombre, tarifa_hora, tarifa_cumpleanos, tarifa_evento FROM canchas ORDER BY id;
