-- Prepara reservas y cédulas
-- Ejecuta después del anterior
BEGIN;

-- Evita horarios cruzados
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Valida cédulas ecuatorianas
CREATE FUNCTION validar_cedula(cedula text) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE total integer := 0; digito integer; i integer;
BEGIN
  IF cedula !~ '^[0-9]{10}$' THEN RETURN false; END IF;
  IF substring(cedula,1,2)::integer NOT BETWEEN 1 AND 24
     OR substring(cedula,3,1)::integer > 5 THEN RETURN false; END IF;
  FOR i IN 1..9 LOOP
    digito := substring(cedula,i,1)::integer;
    IF i % 2 = 1 THEN digito := digito * 2; END IF;
    IF digito > 9 THEN digito := digito - 9; END IF;
    total := total + digito;
  END LOOP;
  RETURN (10 - total % 10) % 10 = substring(cedula,10,1)::integer;
END; $$;

COMMIT;
