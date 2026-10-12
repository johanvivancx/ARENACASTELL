-- Conserva el rastro de pagos web de prueba sin incluirlos en ingresos.
SET LOCAL lock_timeout = '5s';
ALTER TABLE inscripciones_chaca
  ADD COLUMN IF NOT EXISTS prueba_anulada_en timestamptz,
  ADD COLUMN IF NOT EXISTS prueba_anulada_por bigint REFERENCES usuarios(id);
ALTER TABLE pagos
  ADD COLUMN IF NOT EXISTS anulado_en timestamptz,
  ADD COLUMN IF NOT EXISTS anulado_por bigint REFERENCES usuarios(id);

CREATE OR REPLACE VIEW vista_mensualidades_escuela AS
SELECT sc.id AS inscripcion_id, sc.alumno, sc.categoria, u.nombre AS representante,
  u.email, sc.estado, count(p.id) AS cuotas_pagadas, coalesce(sum(p.monto),0) AS total_pagado,
  max(m.periodo) FILTER (WHERE p.id IS NOT NULL) AS ultimo_periodo,
  coalesce(bool_or(m.periodo=date_trunc('month',current_date)::date AND p.id IS NOT NULL),false) AS mes_actual_pagado
FROM inscripciones_chaca sc JOIN ordenes origen ON origen.id=sc.orden_id
JOIN usuarios u ON u.id=origen.usuario_id LEFT JOIN mensualidades m ON m.inscripcion_id=sc.id
LEFT JOIN ordenes om ON om.id=m.orden_id
LEFT JOIN pagos p ON p.orden_id=m.orden_id AND p.anulado_en IS NULL AND om.estado='PAGADA'
GROUP BY sc.id, u.nombre, u.email;
