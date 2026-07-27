#!/usr/bin/env python3
"""Genera los stickers de WhatsApp de Perove a partir de sus sprites.

WhatsApp pide stickers en **WebP de 512x512**, animados o estaticos, con fondo
transparente. Los animados ademas tienen que pesar poco (apuntamos a menos de
100 KB) o el telefono los rechaza.

El detalle que importa: los sprites son pixel art de 40x40. Escalar a 512 seria
un factor de 12.8, o sea no entero, y eso rompe el pixel art aunque se use
nearest neighbor (algunos pixeles saldrian de 12 y otros de 13). Por eso se
escala **12x exacto** a 480x480 y se centra en un lienzo transparente de 512x512.

Los .webp resultantes se commitean al repo, asi el bot no necesita Pillow ni
ffmpeg en produccion: solo lee el archivo y lo manda.

    python scripts/generar_stickers.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
FRAMES = RAIZ / "assets" / "perove" / "frames"
DESTINO = RAIZ / "assets" / "stickers"

LADO = 512
#: 40 x 12 = 480, que entra en 512 con 16 px de margen a cada lado.
#: Tiene que ser entero: es lo que mantiene los pixeles cuadrados y nitidos.
ESCALA = 12
#: milisegundos por frame. 4 frames a 140 ms dan un ciclo de poco mas de medio segundo
DURACION_MS = 140

#: metadatos que WhatsApp muestra al guardar el sticker
PACK = "Chat Contest"
AUTOR = "Club de Programacion"

ANIMACIONES = {
    "wave": "Perove saluda",
    "cast": "Perove hace magia",
    "jump": "Perove salta",
    "idle": "Perove espera",
}


def _cargar_frames(animacion: str) -> list[Image.Image]:
    """Los 4 frames de una animacion, escalados y centrados en el lienzo."""
    salida = []
    for i in range(4):
        ruta = FRAMES / f"{animacion}_{i}.png"
        if not ruta.is_file():
            raise SystemExit(f"falta el frame {ruta}")

        sprite = Image.open(ruta).convert("RGBA")
        ancho, alto = sprite.size
        # NEAREST y factor entero: cualquier otra cosa reintroduce bordes borrosos
        grande = sprite.resize((ancho * ESCALA, alto * ESCALA), Image.NEAREST)

        lienzo = Image.new("RGBA", (LADO, LADO), (0, 0, 0, 0))
        lienzo.paste(grande, ((LADO - grande.width) // 2, (LADO - grande.height) // 2))
        salida.append(lienzo)
    return salida


def _exif_whatsapp() -> bytes:
    """Metadatos del pack, en el formato que espera WhatsApp.

    Es un bloque EXIF con un JSON adentro, en el tag propietario 0x5741 ('WA').
    Sin esto el sticker funciona igual, pero al guardarlo aparece sin nombre.
    """
    import json

    datos = json.dumps({
        "sticker-pack-id": "com.chatcontest.perove",
        "sticker-pack-name": PACK,
        "sticker-pack-publisher": AUTOR,
        "emojis": [],
    }, separators=(",", ":")).encode("utf-8")

    # cabecera EXIF minima con un solo IFD y el tag 0x5741
    cabecera = bytes([
        0x49, 0x49, 0x2A, 0x00, 0x08, 0x00, 0x00, 0x00, 0x01, 0x00,
        0x41, 0x57, 0x07, 0x00,
    ])
    largo = len(datos).to_bytes(4, "little")
    resto = bytes([0x16, 0x00, 0x00, 0x00])
    return cabecera + largo + resto + datos


def generar(animacion: str) -> Path:
    frames = _cargar_frames(animacion)
    destino = DESTINO / f"perove-{animacion}.webp"

    frames[0].save(
        destino,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=DURACION_MS,
        loop=0,                 # en bucle infinito
        lossless=True,          # el pixel art con perdida se ensucia muchisimo
        quality=100,
        method=6,               # la compresion mas lenta y mas chica
        exif=_exif_whatsapp(),
    )
    return destino


def generar_estatico() -> Path:
    """Un sticker estatico con Perove en reposo, para usos sueltos."""
    frame = _cargar_frames("idle")[0]
    destino = DESTINO / "perove.webp"
    frame.save(destino, format="WEBP", lossless=True, quality=100,
               method=6, exif=_exif_whatsapp())
    return destino


def main() -> int:
    if not FRAMES.is_dir():
        print(f"no encuentro los frames en {FRAMES}")
        return 1

    DESTINO.mkdir(parents=True, exist_ok=True)

    print(f"generando stickers de {LADO}x{LADO} (sprite 40x40 a {ESCALA}x = "
          f"{40 * ESCALA}px, centrado)\n")

    problemas = []
    for animacion, descripcion in ANIMACIONES.items():
        ruta = generar(animacion)
        kb = ruta.stat().st_size / 1024
        aviso = ""
        if kb > 500:
            aviso = "  <- DEMASIADO PESADO, WhatsApp lo va a rechazar"
            problemas.append(animacion)
        elif kb > 100:
            aviso = "  <- pesado, puede tardar en enviarse"
        print(f"  {ruta.name:<24} {kb:6.1f} KB   {descripcion}{aviso}")

    ruta = generar_estatico()
    print(f"  {ruta.name:<24} {ruta.stat().st_size / 1024:6.1f} KB   estatico")

    if problemas:
        print(f"\n{len(problemas)} sticker(s) demasiado pesados. Baja ESCALA o "
              f"pone lossless=False.")
        return 1

    print(f"\nlisto, en assets/stickers/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
