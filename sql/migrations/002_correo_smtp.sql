-- Ejecutar en Query Tool sobre arena_castell si las tablas ya estaban creadas.
-- No borra mensajes ni datos. Se puede repetir. Los correos previos quedan LOCAL.
-- Si usaste el paso 03 actualizado, estas columnas ya existen.
BEGIN;
ALTER TABLE correo_salida
  ADD COLUMN IF NOT EXISTS destinatario varchar(254),
  ADD COLUMN IF NOT EXISTS estado_envio varchar(12) NOT NULL DEFAULT 'LOCAL'
    CHECK (estado_envio IN ('LOCAL','PENDIENTE','ENVIADO','ERROR','CANCELADO')),
  ADD COLUMN IF NOT EXISTS intentos smallint NOT NULL DEFAULT 0 CHECK (intentos BETWEEN 0 AND 5),
  ADD COLUMN IF NOT EXISTS proximo_intento timestamptz NOT NULL DEFAULT current_timestamp,
  ADD COLUMN IF NOT EXISTS enviado_en timestamptz,
  ADD COLUMN IF NOT EXISTS ultimo_error varchar(50),
  ADD COLUMN IF NOT EXISTS vence_en timestamptz;
CREATE INDEX IF NOT EXISTS idx_correo_pendiente ON correo_salida(proximo_intento,id)
  WHERE estado_envio='PENDIENTE';
COMMIT;
