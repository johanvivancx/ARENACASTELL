-- Conserva quién realizó cada acción administrativa nueva, sin guardar contraseñas ni formularios.
SET LOCAL lock_timeout = '5s';
CREATE TABLE IF NOT EXISTS actividad_administrativa (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  administrador_id bigint NOT NULL REFERENCES usuarios(id),
  administrador_nombre varchar(100) NOT NULL,
  administrador_email varchar(254) NOT NULL,
  accion varchar(100) NOT NULL,
  referencia varchar(100),
  creado_en timestamptz NOT NULL DEFAULT current_timestamp
);
CREATE INDEX IF NOT EXISTS idx_actividad_administrativa_fecha
  ON actividad_administrativa(creado_en DESC,id DESC);
