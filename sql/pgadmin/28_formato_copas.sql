-- Ejecutar después de 23_programacion_copa.sql si se actualiza manualmente.
ALTER TABLE copa_partidos_programados
  ADD COLUMN IF NOT EXISTS etapa varchar(12) NOT NULL DEFAULT 'FASE1';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'copa_partidos_etapa_check'
      AND conrelid = 'copa_partidos_programados'::regclass
  ) THEN
    ALTER TABLE copa_partidos_programados ADD CONSTRAINT copa_partidos_etapa_check
      CHECK (etapa IN ('FASE1','GRUPO_A','GRUPO_B','BRONCE','ORO','PLATA'));
  END IF;
END $$;
