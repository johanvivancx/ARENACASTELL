-- Retiro conservando cobros; las pruebas anuladas no cuentan como ingresos.
SET LOCAL lock_timeout = '5s';
ALTER TABLE alumnos_chaca_manuales
  ADD COLUMN IF NOT EXISTS retirado_en timestamptz,
  ADD COLUMN IF NOT EXISTS retirado_por bigint REFERENCES usuarios(id),
  ADD COLUMN IF NOT EXISTS prueba_anulada_en timestamptz,
  ADD COLUMN IF NOT EXISTS prueba_anulada_por bigint REFERENCES usuarios(id);
ALTER TABLE pagos_chaca_manuales
  ADD COLUMN IF NOT EXISTS anulado_en timestamptz,
  ADD COLUMN IF NOT EXISTS anulado_por bigint REFERENCES usuarios(id);
ALTER TABLE inscripciones_chaca
  ADD COLUMN IF NOT EXISTS retirado_en timestamptz,
  ADD COLUMN IF NOT EXISTS retirado_por bigint REFERENCES usuarios(id);
