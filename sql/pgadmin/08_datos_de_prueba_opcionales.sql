-- OPCIONAL: datos FICTICIOS para sustentar el procedimiento y las vistas.
-- La cédula cumple el algoritmo, pero NO prueba identidad ni Registro Civil.
-- Usuario de prueba: sql.demo@arena.test / PruebaSQL!2026. No usar en producción.
-- Ejecutar una sola vez, después del paso 7. No sobrescribe personas existentes.
BEGIN;
INSERT INTO usuarios(nombre,cedula,email,telefono,password_hash,rol)
VALUES('Representante de Prueba','1700009200','sql.demo@arena.test','0990000000','pbkdf2_sha256$600000$b82cec5df92a2ba6dfb221081dfde5d2$064b8e98360a8745d1526ee749d734325b6b739ee73f45c67e6a57aab0f8061b','CLIENTE');

INSERT INTO ordenes(id,usuario_id,tipo,descripcion,monto)
SELECT '10000000-0000-4000-8000-000000000001',id,'ESCUELA','Alumno ficticio - mensualidad inicial',50
FROM usuarios WHERE email='sql.demo@arena.test';

INSERT INTO inscripciones_chaca(orden_id,alumno,cedula,nacimiento,categoria,horario_id)
SELECT '10000000-0000-4000-8000-000000000001','Alumno de Prueba','1700009218',
       make_date(extract(year FROM current_date)::integer-10,1,1),'Sub-12',id
FROM horarios_chaca WHERE categoria='Sub-12' AND activo ORDER BY id LIMIT 1;

INSERT INTO mensualidades(orden_id,inscripcion_id,periodo)
SELECT '10000000-0000-4000-8000-000000000001',id,date_trunc('month',current_date)::date
FROM inscripciones_chaca WHERE orden_id='10000000-0000-4000-8000-000000000001';

INSERT INTO ordenes(id,usuario_id,tipo,descripcion,monto)
SELECT '10000000-0000-4000-8000-000000000002',u.id,'RESERVA','Reserva ficticia para probar reportes',c.tarifa_hora
FROM usuarios u CROSS JOIN canchas c WHERE u.email='sql.demo@arena.test' ORDER BY c.id LIMIT 1;

INSERT INTO reservas(orden_id,cancha_id,tipo_evento,inicio,fin)
SELECT '10000000-0000-4000-8000-000000000002',id,'HORA',
 (current_date+5+time '10:00') AT TIME ZONE 'America/Guayaquil',
 (current_date+5+time '11:00') AT TIME ZONE 'America/Guayaquil'
FROM canchas ORDER BY id LIMIT 1;
COMMIT;
SELECT nombre,email FROM usuarios WHERE email='sql.demo@arena.test';
SELECT id,tipo,monto,estado FROM ordenes WHERE id IN
 ('10000000-0000-4000-8000-000000000001','10000000-0000-4000-8000-000000000002');
