-- Usa datos del paso ocho
-- Ejecuta el procedimiento guardado
CALL cobrar_mensualidad('10000000-0000-4000-8000-000000000001','TRANSFERENCIA');

-- Evita pagos duplicados
CALL cobrar_mensualidad('10000000-0000-4000-8000-000000000001','TRANSFERENCIA');

SELECT * FROM vista_reporte_administrador ORDER BY pagado_en DESC;
SELECT * FROM vista_mensualidades_escuela;
SELECT * FROM vista_ocupacion_cancha;

-- Muestra reservas pendientes
SELECT u.nombre,r.inicio,r.fin,r.estado AS reserva,o.estado AS pago,o.monto
FROM reservas r JOIN ordenes o ON o.id=r.orden_id
JOIN usuarios u ON u.id=o.usuario_id ORDER BY r.inicio;
