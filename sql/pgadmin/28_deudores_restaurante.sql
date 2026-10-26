-- Alternativa manual para crear el registro independiente del restaurante Asadero BJ.
CREATE TABLE IF NOT EXISTS restaurante_deudas (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fecha date NOT NULL,
  nombre varchar(120) NOT NULL CHECK (length(trim(nombre)) >= 2),
  monto numeric(12,2) NOT NULL CHECK (monto > 0),
  concepto varchar(180) NOT NULL CHECK (length(trim(concepto)) >= 3),
  registrado_por bigint NOT NULL REFERENCES usuarios(id),
  creado_en timestamptz NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS restaurante_abonos (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fecha date NOT NULL,
  nombre varchar(120) NOT NULL CHECK (length(trim(nombre)) >= 2),
  monto numeric(12,2) NOT NULL CHECK (monto > 0),
  metodo varchar(20) NOT NULL CHECK (metodo IN ('EFECTIVO','TRANSFERENCIA')),
  registrado_por bigint NOT NULL REFERENCES usuarios(id),
  creado_en timestamptz NOT NULL DEFAULT current_timestamp
);

CREATE INDEX IF NOT EXISTS idx_restaurante_deudas_nombre_fecha
  ON restaurante_deudas(nombre,fecha DESC,id DESC);
CREATE INDEX IF NOT EXISTS idx_restaurante_abonos_nombre_fecha
  ON restaurante_abonos(nombre,fecha DESC,id DESC);
