-- PASO 14. Ejecutar en arena_castell, después de guardar un respaldo.
-- Nuevos métodos de pago. Crear un respaldo antes de actualizar la base.
-- Conserva usuarios, órdenes y pagos anteriores. Puede ejecutarse otra vez.
BEGIN;
ALTER TABLE ordenes ADD COLUMN IF NOT EXISTS metodo_previsto varchar(16);
ALTER TABLE ordenes DROP CONSTRAINT IF EXISTS ordenes_metodo_previsto_check;
ALTER TABLE ordenes ADD CONSTRAINT ordenes_metodo_previsto_check
  CHECK (metodo_previsto IS NULL OR metodo_previsto = 'EFECTIVO');
ALTER TABLE pagos DROP CONSTRAINT IF EXISTS pagos_metodo_check;
ALTER TABLE pagos ADD CONSTRAINT pagos_metodo_check
  CHECK (metodo IN ('TRANSFERENCIA','EFECTIVO','TARJETA','DEBITO','CREDITO'));
COMMENT ON COLUMN ordenes.metodo_previsto IS
  'EFECTIVO indica intención de pago en cancha; no equivale a cobro ni confirma horarios o cupos.';
COMMIT;
