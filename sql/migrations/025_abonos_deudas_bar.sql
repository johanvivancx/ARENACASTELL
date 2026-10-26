-- Abonos parciales de los fiados del bar, sin modificar las deudas históricas.
SET LOCAL lock_timeout = '5s';
CREATE TABLE IF NOT EXISTS copa_bar_abonos (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fecha date NOT NULL,
  nombre varchar(120) NOT NULL CHECK (length(trim(nombre)) >= 2),
  monto numeric(12,2) NOT NULL CHECK (monto > 0),
  movimiento_id bigint NOT NULL UNIQUE REFERENCES copa_movimientos(id),
  registrado_por bigint NOT NULL REFERENCES usuarios(id),
  creado_en timestamptz NOT NULL DEFAULT current_timestamp
);
CREATE INDEX IF NOT EXISTS idx_copa_bar_abonos_nombre_fecha
  ON copa_bar_abonos(nombre,fecha DESC,id DESC);
