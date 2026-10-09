-- Desglose de cobros de vocalías y cuentas pendientes del bar.
SET LOCAL lock_timeout = '5s';
ALTER TABLE copa_movimientos
  ADD COLUMN IF NOT EXISTS monto_efectivo numeric(12,2),
  ADD COLUMN IF NOT EXISTS monto_transferencia numeric(12,2);
ALTER TABLE copa_movimientos
  DROP CONSTRAINT IF EXISTS copa_vocalia_desglose;
ALTER TABLE copa_movimientos
  ADD CONSTRAINT copa_vocalia_desglose CHECK (
    (monto_efectivo IS NULL AND monto_transferencia IS NULL)
    OR (tipo='INGRESO' AND cuenta='VOCALIAS'
        AND monto_efectivo >= 0 AND monto_transferencia >= 0
        AND monto_efectivo + monto_transferencia = monto)
  );

CREATE TABLE IF NOT EXISTS copa_bar_deudas (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fecha date NOT NULL,
  nombre varchar(120) NOT NULL CHECK (length(trim(nombre)) >= 2),
  monto numeric(12,2) NOT NULL CHECK (monto > 0),
  concepto varchar(180) NOT NULL CHECK (length(trim(concepto)) >= 3),
  registrado_por bigint NOT NULL REFERENCES usuarios(id),
  creado_en timestamptz NOT NULL DEFAULT current_timestamp,
  cobrada_en timestamptz,
  cobrada_por bigint REFERENCES usuarios(id),
  movimiento_cobro_id bigint REFERENCES copa_movimientos(id),
  CONSTRAINT copa_bar_deuda_cobro CHECK (
    (cobrada_en IS NULL AND cobrada_por IS NULL AND movimiento_cobro_id IS NULL)
    OR (cobrada_en IS NOT NULL AND cobrada_por IS NOT NULL AND movimiento_cobro_id IS NOT NULL)
  )
);
CREATE INDEX IF NOT EXISTS idx_copa_bar_deudas_fecha ON copa_bar_deudas(fecha DESC,id DESC);
