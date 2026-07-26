"""Armado de los textos que salen por WhatsApp.

Regla de oro del proyecto: **nada de emojis**. Para marcar cosas usamos texto,
separadores y sangrias. Se ve mas prolijo en monoespaciado y no depende de que el
celular del otro tenga la fuente.

WhatsApp entiende `*negrita*`, `_cursiva_`, `~tachado~` y ```monoespaciado```.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .config import config
from .judge import DESCRIPCION_VEREDICTO
from .scoring import NOMBRE_DIFICULTAD

LINEA = "-" * 28

#: marca de puesto sin emoji, estilo tabla de competencia
MEDALLAS = {1: "1o", 2: "2o", 3: "3o"}


def titulo(texto: str) -> str:
    return f"*{texto.upper()}*\n{LINEA}"


def dificultad(nivel: int) -> str:
    """Barra de dificultad en texto: [###--] Media."""
    n = max(1, min(5, int(nivel)))
    return f"[{'#' * n}{'-' * (5 - n)}] {NOMBRE_DIFICULTAD.get(n, '?')}"


def duracion(segundos: float) -> str:
    """Duracion legible: 2d 5h, 5h 12m, 12m, 45s."""
    s = max(0, int(segundos))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        horas, resto = divmod(s, 3600)
        minutos = resto // 60
        return f"{horas}h {minutos}m" if minutos else f"{horas}h"
    dias, resto = divmod(s, 86400)
    horas = resto // 3600
    return f"{dias}d {horas}h" if horas else f"{dias}d"


def fecha_local(dt: datetime | None) -> str:
    """Fecha en la zona horaria del club, no en UTC."""
    if dt is None:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(config.rondas.tz).strftime("%d/%m %H:%M")


def recortar(texto: str, maximo: int = 1400) -> str:
    """Corta un texto largo en un limite razonable para un mensaje de WhatsApp."""
    texto = texto.strip()
    if len(texto) <= maximo:
        return texto
    corte = texto.rfind("\n", 0, maximo)
    if corte < maximo // 2:
        corte = maximo
    return texto[:corte].rstrip() + "\n[...]"


def tabla_ranking(filas, *, hasta: int = 15, resaltar: str = "") -> str:
    """Tabla de posiciones en monoespaciado, alineada."""
    if not filas:
        return "todavia no hay nadie en la tabla. se el primero."

    visibles = filas[:hasta]
    ancho_nombre = max((len(_nombre_corto(f)) for f in visibles), default=6)
    ancho_nombre = min(max(ancho_nombre, 6), 14)

    lineas = []
    for f in visibles:
        marca = ">" if f.numero == resaltar else " "
        puesto = MEDALLAS.get(f.puesto, f"{f.puesto}o")
        nombre = _nombre_corto(f).ljust(ancho_nombre)[:ancho_nombre]
        lineas.append(f"{marca}{puesto:>3} {nombre} {f.puntos:>5}  {f.resueltos}ok")

    cuerpo = "```" + "\n".join(lineas) + "```"

    # si quien pregunta no entro en el corte, se le agrega su fila igual
    if resaltar and not any(f.numero == resaltar for f in visibles):
        mia = next((f for f in filas if f.numero == resaltar), None)
        if mia:
            cuerpo += (f"\n```{'>':>1}{str(mia.puesto) + 'o':>3} "
                       f"{_nombre_corto(mia).ljust(ancho_nombre)[:ancho_nombre]} "
                       f"{mia.puntos:>5}  {mia.resueltos}ok```")

    if len(filas) > hasta:
        cuerpo += f"\n_y {len(filas) - hasta} mas_"
    return cuerpo


def _nombre_corto(fila) -> str:
    return (fila.nombre or f"...{fila.numero[-4:]}").strip()


def veredicto(v: str) -> str:
    """Linea de veredicto: sigla + que significa."""
    return f"*{v}* - {DESCRIPCION_VEREDICTO.get(v, v)}"


def problema_corto(codigo: str, titulo_problema: str, nivel: int, base: int) -> str:
    return f"*{codigo}* {titulo_problema}\n   {dificultad(nivel)} - {base} pts"
