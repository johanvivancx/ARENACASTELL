-- Ejecutar en una base ya existente para habilitar el registro de gastos.
-- Es idempotente y no modifica los pagos anteriores.
BEGIN;
SET LOCAL lock_timeout = '5s';
CREATE TABLE IF NOT EXISTS gastos (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  categoria varchar(12) NOT NULL CHECK (categoria IN ('RESERVAS','TORNEOS','SUPER_CHACA')),
  concepto varchar(180) NOT NULL CHECK (length(trim(concepto)) >= 3),
  monto numeric(12,2) NOT NULL CHECK (monto > 0),
  fecha_gasto date NOT NULL,
  registrado_por bigint NOT NULL REFERENCES usuarios(id),
  creado_en timestamptz NOT NULL DEFAULT current_timestamp,
  anulado_en timestamptz,
  anulado_por bigint REFERENCES usuarios(id),
  motivo_anulacion varchar(250),
  CONSTRAINT gastos_anulacion_check CHECK (
    (anulado_en IS NULL AND anulado_por IS NULL AND motivo_anulacion IS NULL)
    OR (anulado_en IS NOT NULL AND anulado_por IS NOT NULL AND motivo_anulacion IS NOT NULL)
  )
);
CREATE INDEX IF NOT EXISTS idx_gastos_fecha ON gastos(fecha_gasto DESC,id DESC);
COMMIT;
