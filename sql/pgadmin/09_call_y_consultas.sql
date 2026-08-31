-- Requiere los datos ficticios del paso 8.
-- CALL modifica filas reales de la base; el cobro monetario sigue siendo simulado.
CALL cobrar_mensualidad('10000000-0000-4000-8000-000000000001','TRANSFERENCIA');

-- Repetir el CALL no duplica el pago.
CALL cobrar_mensualidad('10000000-0000-4000-8000-000000000001','TRANSFERENCIA');

SELECT * FROM vista_reporte_administrador ORDER BY pagado_en DESC;
SELECT * FROM vista_mensualidades_escuela;
SELECT * FROM vista_ocupacion_cancha;

-- Una reserva pendiente todavía no ocupa la cancha; el panel Admin sí la muestra.
SELECT u.nombre,r.inicio,r.fin,r.estado AS reserva,o.estado AS pago,o.monto
FROM reservas r JOIN ordenes o ON o.id=r.orden_id
JOIN usuarios u ON u.id=o.usuario_id ORDER BY r.inicio;
