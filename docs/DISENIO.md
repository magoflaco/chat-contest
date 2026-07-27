# Diseño de la web

La web es HTML, CSS y JavaScript a mano: no hay framework, no hay build, no hay
`node_modules`. Se despliega copiando la carpeta `web/` a Cloudflare Pages. Si
sabés algo de CSS ya podés tocarla.

Esta guía es para que los cambios no rompan el aspecto que tiene.

## La idea

Pixel art minimalista sobre pastel claro, con **Perove** como identidad. La
paleta no es inventada: son los colores exactos con los que está dibujado el
sprite de la mascota (ver `sprites/README.md`), así que la interfaz y el bichito
parecen salidos de la misma mano.

## Las cuatro reglas

**1. Bordes duros, nunca difusos.** Nada de `border-radius`, nada de sombras
con blur. Las sombras son bloques sólidos desplazados, en dos capas:

```css
--relieve: 4px 4px 0 var(--tinte), 8px 8px 0 var(--contorno);
```

Primero un tinte de color y después la línea oscura. Esa segunda capa es lo que
saca a la página de la planitud; con una sola queda todo pegado al fondo.

La única excepción es el degradé del cielo en `body::before` y el aura que sigue
al mouse. Funcionan porque son el fondo, no elementos dibujados.

**2. Todo en la grilla de 4 px.** Los espaciados son múltiplos de `--u`. Para
tamaños que dependen del ancho de pantalla se usa `clamp()`, siempre con valores
que caen en la grilla.

**3. Las transiciones usan `steps()`.** Un sprite no interpola: salta de un
frame al siguiente. Un `ease-in-out` de 300 ms al lado de este dibujo se ve
prestado de otra página.

**4. Escala entera o no es pixel art.** Vale para todo:

- Perove: `--escala` siempre entero (1, 2, 3…) y `image-rendering: pixelated`.
- Los iconos SVG: el tamaño se ajusta solo al múltiplo de 16 más cercano
  (`iconos.js`). A 12 o a 20 px cada pixel del dibujo mediría 0.75 o 1.25 px,
  `crispEdges` los redondea de a uno y el icono se ve como un recuadro vacío.
  Si pedís 20, te da 16; no es un bug.
- Las decoraciones del fondo: `--lado` múltiplo de 16.

## Archivos

| Archivo | Qué hace |
|---|---|
| `estilos.css` | Toda la hoja, en secciones con encabezado |
| `app.js` | Pide los datos y pinta la página |
| `iconos.js` | Iconos pixel art propios, dibujados sobre una grilla de 16×16 |
| `enunciados.js` | Convierte el markdown de los enunciados a HTML |
| `fondo.js` | Las decoraciones flotantes, el parallax y el espanto del mouse |
| `perove.js` | El compañero de la esquina: reacciona y tira tips |

## Colores

Cada sección define su propio `--acento` y `--tinte`, y el resto de las reglas
los usan. Así la página es colorida sin repetir una regla por color:

```css
#seccion-ronda { --acento: var(--menta); --tinte: #d6efe4; }
```

Lo mismo hacen las tarjetas de problema con `.dif-1` … `.dif-5`.

Hay modo oscuro. Si agregás un color, agregalo también en el bloque
`@media (prefers-color-scheme: dark)`, o de noche va a quedar encandilando.

## Nada de emojis

En la web los iconos son SVG propios. Para agregar uno: dibujalo en papel
cuadriculado de 16×16, anotá las coordenadas de cada pixel y sumalo al objeto
`PIXELES` de `iconos.js`. `a` es el trazo principal, `b` el relleno de acento.

(En los mensajes de WhatsApp sí se usan emojis: ahí no hay CSS ni SVG, y sin
ellos los mensajes quedan ilegibles.)

## El visor de enunciados

El enunciado completo se abre en un `<dialog>` que cuelga del `<body>`, no en un
panel dentro de una sección. Eso es lo que permite abrirlo desde la ronda actual
y desde el historial con el mismo código, y trae gratis el fondo oscurecido, el
foco atrapado adentro y el cierre con Escape.

Dos detalles del CSS que no son obvios:

- El `<dialog>` ocupa toda la ventana y es **transparente**. Así el click que cae
  fuera de la caja le llega a él (y `app.js` compara `e.target === visor` para
  cerrar) en vez de perderse. El oscurecido real lo pinta `::backdrop`.
- La cabecera es `position: sticky` y lleva el riel de color. En un enunciado
  largo, tener que volver arriba para encontrar el botón de cerrar es una
  molestia gratuita.

Abajo de 620 px la caja pasa a pantalla completa: partir un enunciado en una
ventanita con márgenes desperdicia la mitad del ancho del teléfono.

## El fondo

`fondo.js` hace tres cosas a la vez sobre las mismas decoraciones:

1. **Flotar.** Cada una sube y baja con su propia duración, desfasada al azar
   para que no se muevan todas juntas. Es una animación CSS sobre `::before`.
2. **Parallax.** El contenedor pone `--mx` / `--my` una sola vez y cada
   decoración los multiplica por su profundidad `--z`.
3. **Espantarse.** Cuando el puntero entra en un radio de 150 px, la decoración
   se aparta en la dirección contraria y se desvanece. Apartarse *y* aclararse
   a la vez es lo que se lee como "despejar el camino"; con solo una de las dos
   parece que rebotan.

El punto 2 va en el `transform` del div y el 1 en el del `::before`: si
compartieran propiedad, una pisaría a la otra.

Todo se calcula dentro de un solo `requestAnimationFrame` y los centros salen de
la composición, no de `getBoundingClientRect`, para no forzar al navegador a
recalcular el layout en cada movimiento del mouse.

## Movimiento

Todo lo que se mueve respeta `prefers-reduced-motion`. Cuando está activo el
fondo no se dibuja, el compañero no aparece y Perove se queda en el primer
frame. Si agregás una animación, comprobá que también se apague:

```bash
# con Playwright, reduced_motion="reduce"
```

## Regenerar el arte

Los PNG de `web/assets/` están versionados porque Pages sirve la carpeta tal
cual, pero **se generan con scripts**. No los edites a mano: CI regenera los dos
y falla si el resultado no coincide con lo que hay en el repo.

```bash
python scripts/generar_decoraciones.py   # web/assets/deco.png
python scripts/generar_favicon.py        # favicons de Perove
python scripts/generar_stickers.py       # stickers de WhatsApp
```

Para agregar una decoración nueva al fondo: sumá su rejilla de 16×16 a `DIBUJOS`
en `generar_decoraciones.py`, agregala a `ORDEN`, corré el script y sumá una
línea a `COMPOSICION` en `fondo.js`.

## Probar los cambios

```bash
cd web && python -m http.server 8777
```

Y abrí `http://127.0.0.1:8777`. Editá `config.js` para apuntar a tu core local.

Mirá siempre en celular antes de mandar el PR: la tabla de posiciones cambia
por completo abajo de 620 px (cada fila pasa a ser una tarjeta, con los rótulos
sacados de `data-rotulo`), y el podio abajo de 520 px.
