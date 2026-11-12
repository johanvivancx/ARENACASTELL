-- Añade el Cuadrangular Navideño al formulario público de inscripciones.
-- Es idempotente y no modifica torneos ni inscripciones existentes.
INSERT INTO torneos(
  nombre,descripcion,fecha_inicio,costo,cupos,max_jugadores,
  visible,abierto,inscripcion_desde,inscripcion_hasta
)
VALUES (
  'Cuadrangular Navideño 2026',
  'Cuadrangular de fútbol en Arena Castell. Todo el torneo se juega el sábado 12 de diciembre de 2026.',
  DATE '2026-12-12',5.00,4,20,true,true,NULL,DATE '2026-12-11'
)
ON CONFLICT (nombre) DO NOTHING;
