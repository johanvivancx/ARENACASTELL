-- Colombia: $7 es el total de 14 carnets, no el saldo pendiente.
-- Conserva cualquier ajuste posterior hecho por administración y evita dejar
-- pagos nuevos por encima del total corregido.
UPDATE copa_inscripciones_equipos SET
  carnets_cantidad=14,
  nota='14 carnets tras el retiro de dos jugadores: total $7, abonados $3 y pendientes $4. Inscripción $25 pendiente.'
WHERE equipo='Colombia'
  AND carnets_cantidad=20 AND carnets_inicial=3
  AND COALESCE((SELECT sum(monto) FROM copa_inscripciones_pagos
                WHERE equipo='Colombia' AND concepto='CARNETS' AND anulado_en IS NULL),0) <= 4;
