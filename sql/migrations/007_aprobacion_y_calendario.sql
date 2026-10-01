-- Transferencias con aprobación, tarifas de escuela y calendario de Pasochoa Cup.
-- Conserva usuarios, reservas y pagos anteriores. Ejecutar con respaldo previo.
BEGIN;
SET LOCAL lock_timeout = '5s';

ALTER TABLE ordenes ADD COLUMN IF NOT EXISTS metodo_previsto varchar(16);
ALTER TABLE ordenes ADD COLUMN IF NOT EXISTS referencia_transferencia varchar(100);
ALTER TABLE ordenes ADD COLUMN IF NOT EXISTS motivo_rechazo_transferencia varchar(250);
ALTER TABLE ordenes ADD COLUMN IF NOT EXISTS revision_pago integer NOT NULL DEFAULT 0;
ALTER TABLE ordenes DROP CONSTRAINT IF EXISTS ordenes_metodo_previsto_check;
ALTER TABLE ordenes ADD CONSTRAINT ordenes_metodo_previsto_check
  CHECK (metodo_previsto IS NULL OR metodo_previsto IN ('EFECTIVO','TRANSFERENCIA'));
ALTER TABLE ordenes DROP CONSTRAINT IF EXISTS ordenes_revision_pago_check;
ALTER TABLE ordenes ADD CONSTRAINT ordenes_revision_pago_check CHECK (revision_pago >= 0);

ALTER TABLE pagos ADD COLUMN IF NOT EXISTS confirmado_por bigint REFERENCES usuarios(id);
ALTER TABLE pagos DROP CONSTRAINT IF EXISTS pagos_simulado_check;
ALTER TABLE pagos DROP CONSTRAINT IF EXISTS pagos_confirmacion_check;
ALTER TABLE pagos ADD CONSTRAINT pagos_confirmacion_check CHECK (simulado OR confirmado_por IS NOT NULL);

ALTER TABLE torneos ADD COLUMN IF NOT EXISTS inscripcion_desde date;
ALTER TABLE torneos ADD COLUMN IF NOT EXISTS inscripcion_hasta date;
ALTER TABLE torneos DROP CONSTRAINT IF EXISTS torneos_fechas_inscripcion_check;
ALTER TABLE torneos ADD CONSTRAINT torneos_fechas_inscripcion_check CHECK (
  (inscripcion_desde IS NULL OR inscripcion_desde < fecha_inicio)
  AND (inscripcion_hasta IS NULL OR inscripcion_hasta < fecha_inicio)
  AND (inscripcion_desde IS NULL OR inscripcion_hasta IS NULL OR inscripcion_desde <= inscripcion_hasta)
);

INSERT INTO torneos(nombre,descripcion,fecha_inicio,costo,cupos,max_jugadores,visible,abierto,inscripcion_desde,inscripcion_hasta)
VALUES ('Pasochoa Cup · Sexta edición',
  'Torneo de fútbol infantojuvenil. Inscripciones del 1 al 30 de abril de 2027. Inicio: 1 de mayo de 2027.',
  DATE '2027-05-01',30,16,20,true,true,DATE '2027-04-01',DATE '2027-04-30')
ON CONFLICT (nombre) DO UPDATE SET
  fecha_inicio=EXCLUDED.fecha_inicio,inscripcion_desde=EXCLUDED.inscripcion_desde,
  inscripcion_hasta=EXCLUDED.inscripcion_hasta,descripcion=EXCLUDED.descripcion;

-- Solo ajusta solicitudes de escuela aún no cobradas; nunca reescribe pagos históricos.
UPDATE ordenes o SET monto=CASE WHEN tipo='ESCUELA' THEN 65 ELSE 30 END
WHERE tipo IN ('ESCUELA','MENSUALIDAD') AND estado='PENDIENTE'
  AND NOT EXISTS (SELECT 1 FROM pagos p WHERE p.orden_id=o.id);

CREATE OR REPLACE FUNCTION controlar_cupo_torneo() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE torneo torneos;
BEGIN
  IF NEW.estado = 'CONFIRMADO' THEN
    SELECT * INTO torneo FROM torneos WHERE id=NEW.torneo_id FOR UPDATE;
    IF NOT torneo.abierto OR torneo.fecha_inicio <= current_date
       OR (torneo.inscripcion_desde IS NOT NULL AND current_date < torneo.inscripcion_desde)
       OR (torneo.inscripcion_hasta IS NOT NULL AND current_date > torneo.inscripcion_hasta) THEN
      RAISE EXCEPTION 'Las inscripciones de este torneo están cerradas.' USING ERRCODE='23514';
    END IF;
    IF (SELECT count(*) FROM equipos WHERE torneo_id=NEW.torneo_id AND estado='CONFIRMADO' AND id IS DISTINCT FROM NEW.id) >= torneo.cupos THEN
      RAISE EXCEPTION 'El torneo ya no tiene cupos.' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END; $$;

CREATE OR REPLACE PROCEDURE cobrar_mensualidad(p_orden uuid, p_metodo text)
LANGUAGE plpgsql AS $$
DECLARE orden ordenes; cuota mensualidades; ingreso date;
BEGIN
  SELECT * INTO orden FROM ordenes WHERE id=p_orden FOR UPDATE;
  IF orden.id IS NULL OR orden.tipo NOT IN ('ESCUELA','MENSUALIDAD') THEN
    RAISE EXCEPTION 'La orden no corresponde a Súper Chaca.' USING ERRCODE='23514';
  END IF;
  IF orden.estado = 'PAGADA' THEN RETURN; END IF;
  IF (orden.tipo = 'ESCUELA' AND orden.monto <> 65)
     OR (orden.tipo = 'MENSUALIDAD' AND orden.monto <> 30) THEN
    RAISE EXCEPTION 'La inscripción cuesta $65 y la mensualidad $30.' USING ERRCODE='23514';
  END IF;
  SELECT * INTO cuota FROM mensualidades WHERE orden_id=p_orden FOR UPDATE;
  IF cuota.id IS NULL THEN RAISE EXCEPTION 'No existe mensualidad.' USING ERRCODE='23514'; END IF;
  SELECT fecha_inscripcion INTO ingreso FROM inscripciones_chaca WHERE id=cuota.inscripcion_id FOR UPDATE;
  IF cuota.periodo < date_trunc('month',ingreso)::date OR cuota.periodo > (date_trunc('month',current_date)+interval '1 month')::date THEN
    RAISE EXCEPTION 'Solo se admiten períodos desde el ingreso hasta el próximo mes.' USING ERRCODE='23514';
  END IF;
  INSERT INTO pagos(orden_id,monto,metodo,referencia) VALUES(p_orden,orden.monto,p_metodo,'SIM-' || p_orden::text);
  UPDATE ordenes SET estado='PAGADA' WHERE id=p_orden;
  UPDATE inscripciones_chaca SET estado='ACTIVA' WHERE id=cuota.inscripcion_id;
END; $$;

COMMIT;
