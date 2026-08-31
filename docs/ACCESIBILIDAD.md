# Diseño y accesibilidad

La idea es que la página se entienda y pueda usarse desde un celular, con mouse o con teclado. El diseño mantiene los mismos menús y botones en las distintas secciones.

## Decisiones del diseño

El fondo es negro y gris. El texto es claro y los botones principales usan un tono plateado. La letra es Arial, que ya viene instalada en la mayoría de equipos. Las fotos tienen una descripción y los datos de los flyers también se pueden leer como texto.

Los campos tienen etiquetas, ejemplos y mensajes de error. Un error no se indica solo con un color: también se explica qué hay que corregir. Los datos del titular se recuperan de su cuenta para no pedirlos varias veces.

## Principios de diseño universal

| Principio | Cómo se aplica |
|---|---|
| Uso equitativo | La información de la cancha puede leerse sin crear una cuenta. |
| Flexibilidad en el uso | Se puede navegar con teclado o mouse e imprimir el comprobante. |
| Uso simple e intuitivo | Las reservas e inscripciones siguen los pasos de información, pago y confirmación. |
| Información perceptible | Los textos tienen contraste y los avisos explican su estado con palabras. |
| Tolerancia al error | Se revisan cédulas, fechas, categorías y horarios antes de guardar. |
| Bajo esfuerzo físico | Los botones son amplios y se reutilizan los datos de la cuenta. |
| Tamaño y espacio | El contenido se acomoda al ancho de pantalla y los controles tienen separación. |

## Elementos del código

- `lang="es"` indica el idioma. Cada página tiene un título principal y un contenido `<main>`.
- `<header>`, `<nav>` y `<footer>` separan las partes de la página.
- `label` relaciona cada nombre de campo con su entrada.
- `focus-visible` marca el elemento seleccionado al usar Tab.
- `aria-label` da nombre a controles que lo necesitan; `aria-hidden` evita repetir iconos decorativos.
- El menú móvil usa `aria-expanded` y puede cerrarse con Escape.
- Las tablas pueden desplazarse en pantallas pequeñas.
- `prefers-reduced-motion` reduce los movimientos cuando el dispositivo lo solicita.

## Qué revisar antes de presentar

1. Recorrer la página usando Tab, Shift+Tab y Enter.
2. Comprobar que el menú móvil abre y cierra sin mouse.
3. Probar la vista de celular y aumentar el zoom del navegador.
4. Enviar un formulario con datos incorrectos y leer el mensaje.
5. Revisar los campos y avisos con un lector de pantalla.
6. Imprimir un comprobante y comprobar que se lea bien.

Se comprobaron combinaciones de colores y la estructura del HTML. Todavía falta una revisión completa con lector de pantalla y en diferentes dispositivos. Las pautas de referencia son [WCAG 2.2](https://www.w3.org/TR/WCAG22/) y el material de Diseño Universal.
