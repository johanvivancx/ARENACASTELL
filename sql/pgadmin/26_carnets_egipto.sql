-- Egipto: los 15 carnets originales ($7,50) ya estaban cubiertos;
-- dos carnets nuevos elevan el total a 17 ($8,50) y dejan $1 pendiente.
-- Solo corrige el estado importado, sin sobrescribir ajustes posteriores.
UPDATE copa_inscripciones_equipos SET
  carnets_cantidad=17,
  carnets_inicial=7.50,
  carnets_completos_inicial=false,
  nota='15 carnets anteriores cubiertos por $7,50; dos carnets nuevos por $1 pendiente. Inscripción completa.'
WHERE equipo='Egipto'
  AND carnets_cantidad=15
  AND carnets_inicial=0
  AND carnets_completos_inicial=true
  AND COALESCE((SELECT sum(monto) FROM copa_inscripciones_pagos
                WHERE equipo='Egipto' AND concepto='CARNETS' AND anulado_en IS NULL),0) <= 1;
