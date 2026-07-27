# Sprite hamster alado — pixel art nativo

Redibujado **pixel a pixel** con `build_sprite.py` (no es un filtro sobre el JPEG).
Cada pixel tiene alfa 0 o 255: **sin fondo, sin halos, sin bordes semitransparentes**.

## Archivos

| Archivo | Uso |
|---|---|
| `sprite_sheet.png` | 160×160, 16 frames de **40×40**. Resolución nativa — usar esta en el juego/bot. |
| `sprite_sheet@4x.png`, `@8x.png` | Mismo sheet escalado con *nearest neighbor* (para previews / stickers). |
| `frames/*.png` | Cada frame suelto, 40×40 y @8x. |
| `idle.gif` `wave.gif` `jump.gif` `cast.gif` `all.gif` | Animaciones a 6x con fondo transparente. |

## Layout del sheet (4 columnas × 4 filas, 40 px por celda)

| Fila | Animación | Frames | Notas |
|---|---|---|---|
| 0 | `idle` | 0–3 | rebote + parpadeo + aleteo |
| 1 | `wave` | 4–7 | saludo con la patita alzada |
| 2 | `jump` | 8–11 | agachada, impulso, cima, caída |
| 3 | `cast` | 12–15 | magia con chispas |

Índice del frame *n*: `x = (n % 4) * 40`, `y = (n // 4) * 40`.

## Paleta (10 colores + contorno)

```
contorno #2A2A4E   azul #4292D2   azul osc #286CAB   azul prof #20568A
azul luz #69B3E8   crema #F6E4C3  crema som #E2C7AC  rosa #C68A8E
rubor  #E9A3A3     ala #FCFAF0    ala som  #CCC2A8   ojo #1A1A2E
```

## Reglas de uso

- **Escalar solo en múltiplos enteros y con nearest neighbor.** Cualquier interpolación
  (bilinear/lanczos) rompe el pixel art y reintroduce bordes borrosos.
  - CSS: `image-rendering: pixelated;`
  - Pillow: `im.resize((w*k, h*k), Image.NEAREST)`
  - Unity: Filter Mode = Point, Compression = None, Pixels Per Unit = 40.
- No hace falta recortar fondo ni aplicar chroma key: ya viene con alfa real.

## Regenerar / modificar

```bash
python build_sprite.py
```

Todo el dibujo vive en `build_sprite.py`: la silueta está en las tablas `BODY`,
`BELLY`, `EAR`, `WING_BASE` como `(fila, x_inicial, x_final)` en una rejilla de
diseño 32×32, y la función `draw()` recibe la pose (`bob`, `eyes`, `mouth`,
`wing`, `arm_l`, `arm_r`, `feet`, `sq`, `sparks`). Para añadir un frame nuevo
basta con agregar una línea en `frames()`. El contorno se calcula solo.
