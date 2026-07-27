#!/usr/bin/env python3
"""Dibuja las decoraciones pixel art del fondo de la web.

Mismo metodo que `animacion/build_sprite.py`: cada dibujo es una rejilla de
16x16 escrita a mano, un caracter por pixel, con la paleta de Perove. Nada de
filtros ni de escalar imagenes grandes: el pixel art se dibuja pixel a pixel o
no es pixel art.

Salida: `web/assets/deco.png`, una tira de 8 celdas de 16x16 (128x16). La web la
usa como sprite sheet, corriendo `background-position` de a una celda.

Para agregar una decoracion nueva: sumá una entrada a DIBUJOS con sus 16 filas
de 16 caracteres y actualizá la lista DECO de `web/fondo.js`.

    python scripts/generar_decoraciones.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "web" / "assets" / "deco.png"

LADO = 16

#: la paleta es la misma del sprite de Perove (ver sprites/README.md), para que
#: el fondo y la mascota se vean dibujados por la misma mano.
PALETA = {
    ".": (0, 0, 0, 0),          # transparente
    "o": (42, 42, 78, 255),     # contorno
    "b": (66, 146, 210, 255),   # azul
    "d": (40, 108, 171, 255),   # azul oscuro
    "l": (105, 179, 232, 255),  # azul luz
    "w": (252, 250, 240, 255),  # ala (blanco calido)
    "c": (246, 228, 195, 255),  # crema
    "m": (150, 226, 255, 255),  # magia
    "M": (226, 248, 255, 255),  # magia clara
    "p": (233, 163, 163, 255),  # rubor
    "P": (198, 138, 142, 255),  # rosa
}

#: orden de las celdas en la tira. `fondo.js` referencia por indice.
ORDEN = ["nube", "estrella", "chispa", "rombo", "burbuja", "bit", "pluma", "corazon"]

DIBUJOS: dict[str, list[str]] = {
    # una nube redonda con la base en sombra
    "nube": [
        "................",
        "................",
        "................",
        "......oooo......",
        ".....owwwwo.....",
        "...oowwwwwwoo...",
        "..owwwwwwwwwwo..",
        ".owwwwwwwwwwwwo.",
        ".owwwwwwwwwwwwo.",
        ".ollllllllllllo.",
        "..oooooooooooo..",
        "................",
        "................",
        "................",
        "................",
        "................",
    ],
    # estrella de cuatro puntas, la chispa grande del hechizo de Perove
    "estrella": [
        "................",
        ".......oo.......",
        "......oMMo......",
        "......oMMo......",
        ".....oomMoo.....",
        "..oooommMmoooo..",
        ".oMMMMMMMMMMMMo.",
        ".oMMMMMMMMMMMMo.",
        "..oooommMmoooo..",
        ".....oomMoo.....",
        "......oMMo......",
        "......oMMo......",
        ".......oo.......",
        "................",
        "................",
        "................",
    ],
    # tres chispitas sueltas, para rellenar sin pesar
    "chispa": [
        "................",
        "................",
        "....o...........",
        "...oMo..........",
        "..oMMMo.........",
        "...oMo....oo....",
        "....o....oMMo...",
        ".........oMMo...",
        "..........oo....",
        "................",
        "....oo..........",
        "...oMMo.........",
        "...oMMo.........",
        "....oo..........",
        "................",
        "................",
    ],
    # gema: el azul de Perove con brillo arriba y sombra abajo
    "rombo": [
        "................",
        "................",
        "................",
        ".......oo.......",
        "......olbo......",
        ".....ollbbo.....",
        "....ollbbbbo....",
        "...ollbbbbbbo...",
        "...odbbbbbbdo...",
        "....odbbbbdo....",
        ".....oddbdo.....",
        "......oddo......",
        ".......oo.......",
        "................",
        "................",
        "................",
    ],
    # burbuja hueca, la mas liviana de todas
    "burbuja": [
        "................",
        "................",
        "................",
        "......oooo......",
        ".....ollllo.....",
        "....olo..olo....",
        "....ol....lo....",
        "....ol....lo....",
        "....olo..olo....",
        ".....ollllo.....",
        "......oooo......",
        "................",
        "................",
        "................",
        "................",
        "................",
    ],
    # bloque suelto: un pixel grande, guiño a la grilla
    "bit": [
        "................",
        "................",
        "................",
        "................",
        "................",
        ".....oooooo.....",
        ".....owwwco.....",
        ".....owccco.....",
        ".....occcco.....",
        ".....oooooo.....",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
    ],
    # pluma del ala de Perove
    "pluma": [
        "................",
        "................",
        "..........oo....",
        ".........owwo...",
        "........owwwo...",
        ".......owwwwo...",
        "......owwwwco...",
        ".....owwwwco....",
        "....owwwwco.....",
        "...owwwco.......",
        "...owcco........",
        "...occo.........",
        "...oo...........",
        "................",
        "................",
        "................",
    ],
    # corazon: aparece solo cuando alguien resuelve algo
    "corazon": [
        "................",
        "................",
        "................",
        "....ooo..ooo....",
        "...opppoopppo...",
        "..owwpppppppPo..",
        "..opppppppppPo..",
        "...oppppppppo...",
        "....oppppppo....",
        ".....oPPPPo.....",
        "......oPPo......",
        ".......oo.......",
        "................",
        "................",
        "................",
        "................",
    ],
}


def celda(nombre: str) -> Image.Image:
    """Convierte la rejilla de caracteres en una imagen RGBA de 16x16."""
    filas = DIBUJOS[nombre]
    if len(filas) != LADO:
        raise SystemExit(f"{nombre}: son {len(filas)} filas, tienen que ser {LADO}")

    im = Image.new("RGBA", (LADO, LADO), (0, 0, 0, 0))
    pix = im.load()
    for y, fila in enumerate(filas):
        if len(fila) != LADO:
            raise SystemExit(f"{nombre}, fila {y}: mide {len(fila)}, tiene que medir {LADO}")
        for x, ch in enumerate(fila):
            color = PALETA.get(ch)
            if color is None:
                raise SystemExit(f"{nombre}, fila {y}: '{ch}' no esta en la paleta")
            pix[x, y] = color
    return im


def main() -> int:
    tira = Image.new("RGBA", (LADO * len(ORDEN), LADO), (0, 0, 0, 0))
    for i, nombre in enumerate(ORDEN):
        tira.paste(celda(nombre), (i * LADO, 0))

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    tira.save(DESTINO)

    print(f"{DESTINO.relative_to(RAIZ)}  {tira.width}x{tira.height}")
    for i, nombre in enumerate(ORDEN):
        print(f"  {i}  {nombre}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
