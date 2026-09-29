-- Actualiza las tarifas de Súper Chaca. No modifica órdenes ni pagos anteriores.
BEGIN;

-- Cobra mensualidades sin duplicar
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
