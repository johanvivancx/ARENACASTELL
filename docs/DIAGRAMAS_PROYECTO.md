# Diagramas de Arena Castell

Los tres diagramas se hicieron a partir de la base y de las clases que usa el proyecto. Las imágenes se pueden colocar en el informe o en la presentación. Los archivos `.mmd` quedan como versión editable.

## Modelo entidad-relación

![Modelo entidad-relación de Arena Castell](diagramas/modelo_entidad_relacion.png)

Este modelo muestra las partes principales del negocio y cómo se relacionan. Un usuario puede crear varias órdenes. Cada orden pertenece a una reserva, un equipo, una inscripción de Súper Chaca o una mensualidad, y puede tener un pago.

[Abrir el archivo editable](diagramas/modelo_entidad_relacion.mmd).

## Modelo relacional

![Modelo relacional de Arena Castell](diagramas/modelo_relacional.png)

Aquí aparecen las 15 tablas con sus claves primarias, foráneas y únicas. También se puede ver cómo se conectan usuarios, órdenes, servicios, pagos, sesiones y correos.

Las reglas `CHECK`, los triggers, el procedimiento y las vistas están en `sql/schema.sql` y en los pasos de `sql/pgadmin`.

[Abrir el archivo editable](diagramas/modelo_relacional.mmd).

## Diagrama de clases POO

![Diagrama de clases POO de Arena Castell](diagramas/diagrama_clases_poo.png)

El diagrama representa las clases de `models.py`:

- `Cliente` y `Administrador` heredan de `Usuario`.
- `ReservaCancha`, `InscripcionTorneo` e `InscripcionSuperChaca` heredan de `ServicioArena`.
- `Usuario` mantiene el hash de la contraseña como dato privado.
- Cada servicio implementa `calcular_costo()` con una regla diferente.

Con esto se muestran encapsulamiento, herencia, abstracción y polimorfismo dentro del código que sí utiliza la aplicación.

[Abrir el archivo editable](diagramas/diagrama_clases_poo.mmd).

## Archivos para entregar

- [DIAGRAMAS_PROYECTO.pdf](DIAGRAMAS_PROYECTO.pdf): los tres diagramas en un solo PDF.
- `docs/diagramas/*.png`: imágenes por separado.
- `docs/diagramas/*.mmd`: fuentes editables en Mermaid.

El modelo de datos sale de `sql/schema.sql` y el diagrama de clases sale de `models.py`. Los métodos de pago son una demostración académica y no representan una conexión bancaria real.
