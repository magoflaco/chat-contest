#!/usr/bin/env python3
"""Genera los favicons de Perove.

Dos cosas que hay que cuidar para que no se vea chico ni sucio:

1. **Recortar el marco vacio.** El frame del sprite es de 40x40 pero el dibujo
   ocupa 32x33: el resto es transparente. Si se usa el frame entero, Perove
   queda con ~20% de aire alrededor y en una pestania se ve diminuto.

2. **Fondo transparente y escala entera.** Nada de pintar un color atras, y
   nada de escalar por un factor fraccionario, que rompe el pixel art.

El lienzo queda cuadrado del alto del dibujo escalado, asi que el aire que
sobra es de medio pixel por lado.

    python scripts/generar_favicon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
ORIGEN = RAIZ / "assets" / "perove" / "frames" / "idle_0.png"
DESTINO = RAIZ / "web"

#: (factor de escala, nombre). El factor SIEMPRE entero.
TAMANIOS = [
    (1, "assets/favicon-32.png"),
    (2, "assets/favicon-64.png"),
    (4, "assets/favicon-128.png"),
    (6, "assets/apple-touch-icon.png"),
]


def recortado() -> Image.Image:
    """El sprite sin el marco transparente que trae el frame."""
    frame = Image.open(ORIGEN).convert("RGBA")
    caja = frame.getbbox()
    if caja is None:
        raise SystemExit(f"{ORIGEN} esta completamente transparente")
    return frame.crop(caja)


def cuadrado(sprite: Image.Image, escala: int) -> Image.Image:
    """Escala con nearest y centra en un lienzo cuadrado transparente."""
    grande = sprite.resize((sprite.width * escala, sprite.height * escala), Image.NEAREST)
    lado = max(grande.width, grande.height)
    lienzo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    lienzo.paste(grande, ((lado - grande.width) // 2, (lado - grande.height) // 2), grande)
    return lienzo


def main() -> int:
    sprite = recortado()
    print(f"sprite recortado: {sprite.width}x{sprite.height} "
          f"(el frame original es 40x40, el resto era aire)\n")

    for escala, nombre in TAMANIOS:
        icono = cuadrado(sprite, escala)
        destino = DESTINO / nombre
        destino.parent.mkdir(parents=True, exist_ok=True)
        icono.save(destino)
        print(f"  {nombre:<32} {icono.width}x{icono.height}")

    # el .ico lo piden algunos navegadores viejos y las barras de favoritos.
    # se baja con NEAREST para no emborronar el pixel art mas de lo necesario.
    base = cuadrado(sprite, 4)
    capas = [base.resize((n, n), Image.NEAREST) for n in (16, 32, 48)]
    capas[0].save(DESTINO / "favicon.ico", format="ICO",
                  sizes=[(16, 16), (32, 32), (48, 48)],
                  append_images=capas[1:])
    print(f"  {'favicon.ico':<32} 16/32/48")

    print("\nfondo transparente, sin color atras.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
