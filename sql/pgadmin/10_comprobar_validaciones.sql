-- Comprueba reglas sin guardar
SELECT validar_cedula('1700009200') AS ejemplo_sintetico_valido,
       validar_cedula('0000000000') AS provincia_invalida,
       validar_cedula('123') AS longitud_invalida;

SELECT table_name FROM information_schema.tables
WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name;
SELECT trigger_name,event_manipulation,event_object_table
FROM information_schema.triggers WHERE trigger_schema='public' ORDER BY trigger_name;
SELECT routine_name,routine_type FROM information_schema.routines
WHERE routine_schema='public' AND routine_name IN
 ('validar_cedula','controlar_reserva','controlar_cupo_torneo','limitar_jugadores','validar_pago','cobrar_mensualidad');
SELECT table_name FROM information_schema.views WHERE table_schema='public';

-- Prueba una restricción CHECK
-- Captura el error esperado
DO $$
BEGIN
  BEGIN
    INSERT INTO usuarios(nombre,cedula,email,telefono,password_hash)
    VALUES('Prueba inválida','0000000000','invalida@arena.test','0990000000',repeat('x',64));
    RAISE EXCEPTION 'Fallo: la BD aceptó una cédula inválida.';
  EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'Correcto: PostgreSQL rechazó la cédula inválida.';
  END;
END; $$;
