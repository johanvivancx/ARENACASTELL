-- Migración de la versión inicial: conserva órdenes, pagos, equipos e inscripciones.
-- Ejecutar con manage.py update-catalog. Se puede repetir sin duplicar filas.
ALTER TABLE torneos ADD COLUMN IF NOT EXISTS max_jugadores integer NOT NULL DEFAULT 20 CHECK (max_jugadores BETWEEN 1 AND 20);
ALTER TABLE torneos ADD COLUMN IF NOT EXISTS visible boolean NOT NULL DEFAULT true;
ALTER TABLE horarios_chaca ADD COLUMN IF NOT EXISTS activo boolean NOT NULL DEFAULT true;
ALTER TABLE horarios_chaca DROP CONSTRAINT IF EXISTS horarios_chaca_categoria_check;
ALTER TABLE horarios_chaca ADD CONSTRAINT horarios_chaca_categoria_check
  CHECK (categoria IN ('Sub-6','Sub-8','Sub-10','Sub-12','Sub-14','Sub-16','Sub-18'));
ALTER TABLE inscripciones_chaca DROP CONSTRAINT IF EXISTS inscripciones_chaca_categoria_check;
ALTER TABLE inscripciones_chaca ADD CONSTRAINT inscripciones_chaca_categoria_check
  CHECK (categoria IN ('Sub-6','Sub-8','Sub-10','Sub-12','Sub-14','Sub-16','Sub-18'));
ALTER TABLE inscripciones_chaca DROP CONSTRAINT IF EXISTS inscripciones_chaca_check;
ALTER TABLE inscripciones_chaca ADD CONSTRAINT inscripciones_chaca_check
  CHECK (extract(year FROM age(fecha_inscripcion,nacimiento)) BETWEEN 4 AND 17);
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
DROP TRIGGER IF EXISTS trg_proteger_limite ON torneos;
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
-- Retirar solo el catálogo ficticio original. Los registros anteriores no se borran.
UPDATE torneos SET visible=false, abierto=false
 WHERE nombre='Copa Castell'
 AND descripcion='Torneo amateur de fútbol 7. Hasta 20 jugadores por equipo.' AND costo=120.00;
UPDATE horarios_chaca SET activo=false
 WHERE (dias='Lunes y miércoles' AND inicio=time '15:00' AND fin=time '16:30')
    OR (dias='Martes y jueves' AND inicio=time '16:30' AND fin=time '18:00');
