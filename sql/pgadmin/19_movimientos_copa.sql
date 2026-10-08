-- Caja operativa de Copa Castell, independiente de inscripciones y otras actividades.
CREATE TABLE IF NOT EXISTS copa_movimientos (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fecha date NOT NULL,
  tipo varchar(15) NOT NULL CHECK (tipo IN ('APERTURA','TRASPASO','INGRESO','GASTO')),
  cuenta varchar(12) NOT NULL CHECK (cuenta IN ('DISPONIBLE','BAR','ENTRADAS','VOCALIAS')),
  destino varchar(12) CHECK (destino IN ('BAR','ENTRADAS')),
  area varchar(12) CHECK (area IN ('BAR','ENTRADAS','VOCALIAS','GENERAL')),
  monto numeric(12,2) NOT NULL CHECK (monto > 0),
  concepto varchar(180) NOT NULL CHECK (length(trim(concepto)) >= 3),
  fixture_id varchar(100),
  equipo varchar(50),
  registrado_por bigint NOT NULL REFERENCES usuarios(id),
  creado_en timestamptz NOT NULL DEFAULT current_timestamp,
  anulado_en timestamptz,
  anulado_por bigint REFERENCES usuarios(id),
  motivo_anulacion varchar(250),
  CONSTRAINT copa_movimiento_tipo CHECK (
    (tipo='APERTURA' AND cuenta='DISPONIBLE' AND destino IS NULL AND area IS NULL AND fixture_id IS NULL AND equipo IS NULL)
    OR (tipo='TRASPASO' AND cuenta='DISPONIBLE' AND destino IS NOT NULL AND area IS NULL AND fixture_id IS NULL AND equipo IS NULL)
    OR (tipo='INGRESO' AND cuenta IN ('BAR','ENTRADAS','VOCALIAS') AND destino IS NULL AND area IS NULL
        AND ((cuenta='VOCALIAS' AND fixture_id IS NOT NULL AND equipo IS NOT NULL)
             OR (cuenta<>'VOCALIAS' AND fixture_id IS NULL AND equipo IS NULL)))
    OR (tipo='GASTO' AND destino IS NULL AND area IS NOT NULL AND equipo IS NULL)
  ),
  CONSTRAINT copa_movimiento_anulacion CHECK (
    (anulado_en IS NULL AND anulado_por IS NULL AND motivo_anulacion IS NULL)
    OR (anulado_en IS NOT NULL AND anulado_por IS NOT NULL AND motivo_anulacion IS NOT NULL)
  )
);
CREATE INDEX IF NOT EXISTS idx_copa_movimientos_fecha ON copa_movimientos(fecha DESC,id DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_copa_apertura_activa ON copa_movimientos(tipo) WHERE tipo='APERTURA' AND anulado_en IS NULL;
