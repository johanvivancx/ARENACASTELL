-- Crea tres reportes
-- Ejecuta después del anterior
BEGIN;

-- Reporta pagos registrados
CREATE VIEW vista_reporte_administrador AS
SELECT p.id AS pago_id, p.pagado_en, u.id AS usuario_id, u.nombre, u.email,
  o.id AS orden_id, o.tipo, o.descripcion, p.monto, p.metodo, p.referencia,
  c.nombre AS cancha, r.inicio AS reserva_inicio, t.nombre AS torneo,
  e.nombre AS equipo, sc.alumno, m.periodo, p.simulado
FROM pagos p JOIN ordenes o ON o.id=p.orden_id JOIN usuarios u ON u.id=o.usuario_id
LEFT JOIN reservas r ON r.orden_id=o.id LEFT JOIN canchas c ON c.id=r.cancha_id
LEFT JOIN equipos e ON e.orden_id=o.id LEFT JOIN torneos t ON t.id=e.torneo_id
LEFT JOIN mensualidades m ON m.orden_id=o.id LEFT JOIN inscripciones_chaca sc ON sc.id=m.inscripcion_id;

-- Reporta mensualidades escolares
CREATE VIEW vista_mensualidades_escuela AS
SELECT sc.id AS inscripcion_id, sc.alumno, sc.categoria, u.nombre AS representante,
  u.email, sc.estado, count(p.id) AS cuotas_pagadas, coalesce(sum(p.monto),0) AS total_pagado,
  max(m.periodo) FILTER (WHERE p.id IS NOT NULL) AS ultimo_periodo,
  coalesce(bool_or(m.periodo=date_trunc('month',current_date)::date AND p.id IS NOT NULL),false) AS mes_actual_pagado
FROM inscripciones_chaca sc JOIN ordenes origen ON origen.id=sc.orden_id
JOIN usuarios u ON u.id=origen.usuario_id LEFT JOIN mensualidades m ON m.inscripcion_id=sc.id
LEFT JOIN pagos p ON p.orden_id=m.orden_id
GROUP BY sc.id, u.nombre, u.email;

-- Reporta ocupación mensual
CREATE VIEW vista_ocupacion_cancha AS
SELECT c.id, c.nombre, date_trunc('month',r.inicio AT TIME ZONE 'America/Guayaquil')::date AS mes,
  count(r.id) AS reservas, coalesce(sum(extract(epoch FROM r.fin-r.inicio)/3600),0) AS horas,
  coalesce(sum(p.monto),0) AS ingresos_simulados
FROM canchas c LEFT JOIN reservas r ON r.cancha_id=c.id AND r.estado='CONFIRMADA'
LEFT JOIN pagos p ON p.orden_id=r.orden_id GROUP BY c.id,c.nombre,mes;

COMMIT;
