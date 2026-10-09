-- Alumnos acordados fuera de la web y cobros reales de Súper Chaca.
-- No altera inscripciones, mensualidades ni precios de la página pública.
SET LOCAL lock_timeout = '5s';
CREATE TABLE IF NOT EXISTS alumnos_chaca_manuales (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  alumno varchar(100) NOT NULL CHECK (length(trim(alumno)) BETWEEN 2 AND 100),
  categoria varchar(6) NOT NULL CHECK (categoria IN ('Sub-6','Sub-8','Sub-10','Sub-12','Sub-14','Sub-16','Sub-18')),
  cedula varchar(10) UNIQUE CHECK (cedula IS NULL OR validar_cedula(cedula)),
  telefono_representante varchar(17) NOT NULL CHECK (telefono_representante ~ '^\+?[0-9]{7,16}$'),
  fecha_ingreso date NOT NULL,
  registrado_por bigint NOT NULL REFERENCES usuarios(id),
  creado_en timestamptz NOT NULL DEFAULT current_timestamp
);
CREATE INDEX IF NOT EXISTS idx_alumnos_chaca_manuales_nombre ON alumnos_chaca_manuales(alumno);

CREATE TABLE IF NOT EXISTS pagos_chaca_manuales (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  alumno_id bigint NOT NULL REFERENCES alumnos_chaca_manuales(id),
  tipo varchar(12) NOT NULL CHECK (tipo IN ('INSCRIPCION','MENSUALIDAD')),
  periodo date CHECK (periodo IS NULL OR extract(day FROM periodo) = 1),
  monto numeric(10,2) NOT NULL CHECK (monto > 0),
  metodo varchar(13) NOT NULL CHECK (metodo IN ('EFECTIVO','TRANSFERENCIA')),
  registrado_por bigint NOT NULL REFERENCES usuarios(id),
  pagado_en timestamptz NOT NULL DEFAULT current_timestamp,
  CONSTRAINT pago_chaca_periodo_check CHECK (
    (tipo='INSCRIPCION' AND periodo IS NULL) OR
    (tipo='MENSUALIDAD' AND periodo IS NOT NULL)
  )
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pago_chaca_inscripcion
  ON pagos_chaca_manuales(alumno_id) WHERE tipo='INSCRIPCION';
CREATE UNIQUE INDEX IF NOT EXISTS uq_pago_chaca_mensualidad
  ON pagos_chaca_manuales(alumno_id,periodo) WHERE tipo='MENSUALIDAD';
CREATE INDEX IF NOT EXISTS idx_pagos_chaca_manuales_fecha ON pagos_chaca_manuales(pagado_en DESC);
