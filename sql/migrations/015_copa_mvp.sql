-- Fotos de jugadores del partido: persisten en PostgreSQL entre despliegues.
SET LOCAL lock_timeout = '5s';
CREATE TABLE IF NOT EXISTS copa_mvp (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fixture_id varchar(100) NOT NULL UNIQUE,
  equipo varchar(50) NOT NULL,
  jugador_clave varchar(255) NOT NULL,
  jugador_nombre varchar(100) NOT NULL,
  dorsal varchar(3) NOT NULL DEFAULT '',
  foto bytea NOT NULL CHECK (octet_length(foto) BETWEEN 1 AND 2097152),
  registrado_por bigint NOT NULL REFERENCES usuarios(id),
  actualizado_en timestamptz NOT NULL DEFAULT current_timestamp
);
