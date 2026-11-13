-- Permite convocatorias gratuitas sin convertirlas en cobros o ingresos.
ALTER TABLE torneos DROP CONSTRAINT IF EXISTS torneos_costo_check;
ALTER TABLE torneos ADD CONSTRAINT torneos_costo_check CHECK (costo >= 0);
ALTER TABLE ordenes DROP CONSTRAINT IF EXISTS ordenes_monto_check;
ALTER TABLE ordenes ADD CONSTRAINT ordenes_monto_check CHECK (monto >= 0);

-- Añade el Cuadrangular Navideño al formulario público de inscripciones.
INSERT INTO torneos(
  nombre,descripcion,fecha_inicio,costo,cupos,max_jugadores,
  visible,abierto,inscripcion_desde,inscripcion_hasta
)
VALUES (
  'Cuadrangular Navideño 2026',
  'Cuadrangular de fútbol en Arena Castell, con jornadas los sábados 12 y 19 de diciembre de 2026.',
  DATE '2026-12-12',0.00,6,20,true,true,NULL,DATE '2026-12-11'
)
ON CONFLICT (nombre) DO NOTHING;

-- Actualiza solo la convocatoria; las órdenes y pagos históricos no se tocan.
UPDATE torneos
SET descripcion='Cuadrangular de fútbol en Arena Castell, con jornadas los sábados 12 y 19 de diciembre de 2026.',
    fecha_inicio=DATE '2026-12-12',
    costo=0.00,
    cupos=6,
    visible=true,
    abierto=true,
    inscripcion_hasta=DATE '2026-12-11'
WHERE nombre='Cuadrangular Navideño 2026';
