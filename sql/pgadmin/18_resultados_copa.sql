-- Alternativa manual para la base existente. Idempotente.
BEGIN;
SET LOCAL lock_timeout = '5s';
CREATE TABLE IF NOT EXISTS copa_resultados (
  fixture_id varchar(100) PRIMARY KEY,
  fecha smallint NOT NULL CHECK (fecha BETWEEN 1 AND 30),
  local varchar(50) NOT NULL,
  visitante varchar(50) NOT NULL CHECK (visitante <> local),
  goles_local smallint NOT NULL CHECK (goles_local BETWEEN 0 AND 99),
  goles_visitante smallint NOT NULL CHECK (goles_visitante BETWEEN 0 AND 99),
  revision integer NOT NULL DEFAULT 0 CHECK (revision >= 0),
  registrado_por bigint NOT NULL REFERENCES usuarios(id),
  actualizado_en timestamptz NOT NULL DEFAULT current_timestamp
);
CREATE TABLE IF NOT EXISTS copa_goles (
  fixture_id varchar(100) NOT NULL REFERENCES copa_resultados(fixture_id) ON DELETE CASCADE,
  equipo varchar(50) NOT NULL,
  jugador_clave varchar(255) NOT NULL,
  jugador_nombre varchar(100) NOT NULL,
  dorsal varchar(3) NOT NULL DEFAULT '',
  goles smallint NOT NULL CHECK (goles BETWEEN 1 AND 99),
  PRIMARY KEY (fixture_id,jugador_clave)
);
COMMIT;
