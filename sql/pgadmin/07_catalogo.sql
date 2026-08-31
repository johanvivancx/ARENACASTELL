-- Cancha, tarifas, Copa Castell, Pasochoa Cup y horarios de la escuela.
BEGIN;

-- Tarifas de Arena Castell: hora $27, evento $30, cumpleaños $25 por hora en paquete de 3 horas.
-- El cupo de Copa Castell sigue pendiente de confirmar; Pasochoa Cup sí tiene 16 equipos.
INSERT INTO canchas(nombre,tarifa_hora,tarifa_evento,tarifa_cumpleanos)
VALUES ('Cancha principal · Fútbol 7',27.00,30.00,25.00)
ON CONFLICT (nombre) DO UPDATE SET
  tarifa_hora=EXCLUDED.tarifa_hora,
  tarifa_evento=EXCLUDED.tarifa_evento,
  tarifa_cumpleanos=EXCLUDED.tarifa_cumpleanos;
-- Copa Castell en juego; inscripciones cerradas.
INSERT INTO torneos(nombre,descripcion,fecha_inicio,costo,cupos,max_jugadores,abierto)
VALUES ('Copa Castell · Mundial de Campeones',
        'Fútbol 7. Máximo 15 jugadores por equipo. Premio al campeón: $300 + trofeo. Torneo en juego.',
        DATE '2026-08-28',25.00,16,15,false)
ON CONFLICT DO NOTHING;
-- Pasochoa Cup: sexta edición, 16 equipos y $30 por inscripción.
INSERT INTO torneos(nombre,descripcion,fecha_inicio,costo,cupos,max_jugadores,visible,abierto)
VALUES ('Pasochoa Cup · Sexta edición',
        'Torneo de fútbol infantojuvenil. Sexta edición: 16 equipos y hasta 20 jugadores por equipo.',
        DATE '2026-09-30',30.00,16,20,true,true)
ON CONFLICT (nombre) DO NOTHING;

-- Se elige una jornada preferida; la escuela confirma el grupo y horario definitivo.
-- Los días de la jornada matutina están por confirmar.
INSERT INTO horarios_chaca(categoria,dias,inicio,fin)
SELECT categoria,dias,inicio::time,fin::time FROM
  (VALUES ('Sub-6'),('Sub-8'),('Sub-10'),('Sub-12'),('Sub-14'),('Sub-16'),('Sub-18')) c(categoria)
  CROSS JOIN (VALUES ('Matutina · días por confirmar','08:30','09:45'),
                     ('Lunes a viernes · jornada vespertina','15:00','18:30')) h(dias,inicio,fin)
ON CONFLICT DO NOTHING;

COMMIT;
