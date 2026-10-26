-- Acuerdo de Colombia: inscripción sin cobro y $6,50 adicionales de carnets en efectivo.
-- Puede repetirse: la referencia única evita duplicar el cobro.
SET LOCAL lock_timeout = '5s';
ALTER TABLE copa_inscripciones_equipos
  ADD COLUMN IF NOT EXISTS inscripcion_acuerdo boolean NOT NULL DEFAULT false;
ALTER TABLE copa_inscripciones_pagos
  ADD COLUMN IF NOT EXISTS referencia varchar(100);
CREATE UNIQUE INDEX IF NOT EXISTS idx_copa_inscripciones_pago_referencia
  ON copa_inscripciones_pagos(referencia);

UPDATE copa_inscripciones_equipos SET
  inscripcion_completa_inicial=true,
  inscripcion_acuerdo=true,
  nota='Inscripción completa por acuerdo, sin cobro. Carnets: $3 anteriores + $6,50 en efectivo el 23/10/2026; total recibido $9,50. Carnets completos.'
WHERE equipo='Colombia';

INSERT INTO copa_inscripciones_pagos
  (equipo,concepto,fecha,efectivo,transferencia,registrado_por,referencia)
SELECT 'Colombia','CARNETS',DATE '2026-10-23',6.50,0,id,
       'ACUERDO-COLOMBIA-CARNETS-2026-10-23'
FROM usuarios WHERE rol='ADMIN' ORDER BY id LIMIT 1
ON CONFLICT (referencia) DO NOTHING;
