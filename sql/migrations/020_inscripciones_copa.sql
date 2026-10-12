-- Control independiente de inscripción y carnets de los equipos de Copa Castell.
CREATE TABLE IF NOT EXISTS copa_inscripciones_equipos (
  equipo varchar(50) PRIMARY KEY,
  carnets_cantidad integer NOT NULL CHECK (carnets_cantidad BETWEEN 0 AND 100),
  inscripcion_inicial numeric(12,2) NOT NULL DEFAULT 0 CHECK (inscripcion_inicial BETWEEN 0 AND 25),
  carnets_inicial numeric(12,2) NOT NULL DEFAULT 0 CHECK (carnets_inicial >= 0),
  inscripcion_completa_inicial boolean NOT NULL DEFAULT false,
  carnets_completos_inicial boolean NOT NULL DEFAULT false,
  nota varchar(250) NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS copa_inscripciones_pagos (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  equipo varchar(50) NOT NULL REFERENCES copa_inscripciones_equipos(equipo),
  concepto varchar(12) NOT NULL CHECK (concepto IN ('INSCRIPCION','CARNETS')),
  fecha date NOT NULL,
  efectivo numeric(12,2) NOT NULL DEFAULT 0 CHECK (efectivo >= 0),
  transferencia numeric(12,2) NOT NULL DEFAULT 0 CHECK (transferencia >= 0),
  monto numeric(12,2) GENERATED ALWAYS AS (efectivo + transferencia) STORED,
  registrado_por bigint NOT NULL REFERENCES usuarios(id),
  creado_en timestamptz NOT NULL DEFAULT current_timestamp,
  anulado_en timestamptz,
  anulado_por bigint REFERENCES usuarios(id),
  motivo_anulacion varchar(250),
  CHECK (efectivo + transferencia > 0),
  CHECK ((anulado_en IS NULL AND anulado_por IS NULL AND motivo_anulacion IS NULL) OR
         (anulado_en IS NOT NULL AND anulado_por IS NOT NULL AND motivo_anulacion IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_copa_inscripciones_pagos_equipo ON copa_inscripciones_pagos(equipo,fecha,id);

-- La hoja indica estados, pero no fechas ni medios de pago anteriores.
-- Los equipos marcados completos no generan un ingreso ficticio en efectivo o transferencia.
INSERT INTO copa_inscripciones_equipos
  (equipo,carnets_cantidad,inscripcion_inicial,carnets_inicial,
   inscripcion_completa_inicial,carnets_completos_inicial,nota) VALUES
  ('Ecuador',16,0,0,false,true,'Carnets completos según hoja; inscripción sin pago anotado.'),
  ('Brasil',13,0,0,true,true,'Inscripción y carnets completos según hoja.'),
  ('Noruega',20,0,0,true,true,'Inscripción y carnets completos según hoja.'),
  ('Alemania',12,0,0,true,true,'Inscripción y carnets completos según hoja.'),
  ('España',14,18,0,false,false,'Abono de $18 en inscripción; medio de pago anterior desconocido.'),
  ('Uruguay',19,17.50,0,false,true,'Abonos de inscripción $4 + $7,50 + $2 + $4; carnets completos.'),
  ('Cabo Verde',14,0,0,true,true,'Inscripción y carnets completos según hoja.'),
  ('Portugal',20,0,0,false,true,'Carnets completos; inscripción sin pago anotado.'),
  ('Francia',14,0,0,false,false,'Sin pagos anotados en la hoja.'),
  ('Argentina',15,0,0,false,false,'Sin pagos anotados en la hoja.'),
  ('Venezuela',15,0,0,true,false,'Inscripción completa según confirmación del organizador; carnets pendientes.'),
  ('Colombia',20,0,3,false,false,'$3 abonados a carnets y $7 pendientes según el organizador; inscripción $25 pendiente. La plantilla pública actual muestra 16 jugadores.'),
  ('Egipto',15,0,0,true,true,'Carnets completos por $7,50 según hoja; la plantilla web muestra más jugadores.'),
  ('Japón',17,0,0,true,true,'Inscripción y carnets completos según hoja.'),
  ('Marruecos',18,15,5,false,false,'$15 de inscripción y $5 de carnets anotados; medio anterior desconocido.')
ON CONFLICT (equipo) DO NOTHING;
