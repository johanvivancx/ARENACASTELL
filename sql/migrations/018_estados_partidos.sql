-- Los resultados anteriores siguen siendo finales; los nuevos pueden publicarse en vivo.
ALTER TABLE copa_resultados
  ADD COLUMN IF NOT EXISTS estado varchar(12) NOT NULL DEFAULT 'FINALIZADO';

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'copa_resultados_estado_check'
      AND conrelid = 'copa_resultados'::regclass
  ) THEN
    ALTER TABLE copa_resultados ADD CONSTRAINT copa_resultados_estado_check
      CHECK (estado IN ('EN_JUEGO', 'FINALIZADO'));
  END IF;
END $$;
