-- Actualiza sin borrar datos
-- Conserva la fecha fija
BEGIN;

-- Carga Pasochoa Cup
-- Agrega la nueva edición
INSERT INTO torneos(nombre,descripcion,fecha_inicio,costo,cupos,max_jugadores,visible,abierto)
VALUES ('Pasochoa Cup · Sexta edición',
        'Torneo de fútbol infantojuvenil. Sexta edición: 16 equipos y hasta 20 jugadores por equipo.',
        DATE '2026-09-30',30.00,16,20,true,true)
ON CONFLICT (nombre) DO NOTHING;

COMMIT;

SELECT id,nombre,fecha_inicio,costo,cupos,max_jugadores,abierto
FROM torneos
WHERE nombre = 'Pasochoa Cup · Sexta edición';
