-- Permite retirar un fiado equivocado sin perder la auditoría de quién lo anuló.
SET LOCAL lock_timeout = '5s';
ALTER TABLE copa_bar_deudas
  ADD COLUMN IF NOT EXISTS anulado_en timestamptz,
  ADD COLUMN IF NOT EXISTS anulado_por bigint REFERENCES usuarios(id),
  ADD COLUMN IF NOT EXISTS motivo_anulacion varchar(250);
ALTER TABLE copa_bar_deudas DROP CONSTRAINT IF EXISTS copa_bar_deuda_anulacion;
ALTER TABLE copa_bar_deudas ADD CONSTRAINT copa_bar_deuda_anulacion CHECK (
  (anulado_en IS NULL AND anulado_por IS NULL AND motivo_anulacion IS NULL)
  OR (anulado_en IS NOT NULL AND anulado_por IS NOT NULL AND motivo_anulacion IS NOT NULL)
);
