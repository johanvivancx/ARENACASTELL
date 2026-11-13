-- Añade el número deportivo sin borrar ni reemplazar jugadores existentes.
ALTER TABLE jugadores
  ADD COLUMN IF NOT EXISTS numero_camiseta integer;

-- Los registros anteriores conservan un número válido basado en su orden de lista.
UPDATE jugadores
SET numero_camiseta = posicion
WHERE numero_camiseta IS NULL;

ALTER TABLE jugadores
  ALTER COLUMN numero_camiseta SET NOT NULL;

ALTER TABLE jugadores
  DROP CONSTRAINT IF EXISTS jugadores_numero_camiseta_check;

ALTER TABLE jugadores
  ADD CONSTRAINT jugadores_numero_camiseta_check
  CHECK (numero_camiseta BETWEEN 1 AND 99);

CREATE UNIQUE INDEX IF NOT EXISTS uq_jugadores_equipo_camiseta
  ON jugadores(equipo_id, numero_camiseta);
