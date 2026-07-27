"""Armado de los textos que salen por WhatsApp.

Sobre los emojis: la web **no lleva ninguno**, ahi los iconos son SVG pixel art
propios. En WhatsApp es al reves: no hay forma de dibujar un icono, el texto es
todo lo que hay, y un `[###--]` en una pantalla de celular se ve mal. Asi que en
los mensajes del bot se usan unos pocos emojis, elegidos para que signifiquen
algo y no de adorno.

WhatsApp solo entiende `*negrita*` (un asterisco), `_cursiva_`, `~tachado~` y
```bloque```. Nada de markdown. La conversion de los enunciados la hace `wa.py`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import wa
from .config import config
from .judge import DESCRIPCION_VEREDICTO
from .scoring import NOMBRE_DIFICULTAD

LINEA = "─" * 22

#: un color por dificultad, los mismos que usa la web
COLOR_DIFICULTAD = {1: "🟢", 2: "🔵", 3: "🟣", 4: "🟠", 5: "🔴"}

#: el veredicto se lee de un vistazo antes de leer el texto
ICONO_VEREDICTO = {
    "AC": "✅", "WA": "❌", "TLE": "⏱️", "MLE": "💾",
    "RE": "💥", "CE": "✏️", "PE": "📐", "SEC": "🚫", "IE": "⚙️",
}

MEDALLAS = {1: "🥇", 2: "🥈", 3: "🥉"}


def titulo(texto: str) -> str:
    return f"*{texto.upper()}*\n{LINEA}"


def dificultad(nivel: int) -> str:
    """Dificultad como color + nombre. Reemplaza al viejo [###--]."""
    n = max(1, min(5, int(nivel)))
    return f"{COLOR_DIFICULTAD[n]} {NOMBRE_DIFICULTAD.get(n, '?')}"


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
    """Tabla de posiciones.

    Se arma con lineas sueltas y no con un bloque monoespaciado alineado: en un
    celular angosto el monoespaciado se corta o se achica tanto que no se lee.
    """
    if not filas:
        return "Todavia no hay nadie en la tabla. Se el primero."

    visibles = filas[:hasta]
    lineas = []

    for f in visibles:
        marca = MEDALLAS.get(f.puesto, f"{f.puesto}.")
        nombre = (f.nombre or f"...{f.numero[-4:]}").strip()
        if f.numero == resaltar:
            nombre = f"*{nombre}* ←"
        lineas.append(f"{marca} {nombre} — {f.puntos} pts · {f.resueltos} ok")

    # si quien pregunta quedo fuera del corte, se le agrega su fila igual
    if resaltar and not any(f.numero == resaltar for f in visibles):
        mia = next((f for f in filas if f.numero == resaltar), None)
        if mia:
            lineas.append("⋯")
            lineas.append(f"{mia.puesto}. *{mia.nombre or '...' + mia.numero[-4:]}* ← "
                          f"— {mia.puntos} pts · {mia.resueltos} ok")

    cuerpo = "\n".join(lineas)
    if len(filas) > hasta:
        cuerpo += f"\n\n_y {len(filas) - hasta} mas_"
    return wa.proteger_numeros(cuerpo)


def veredicto(v: str) -> str:
    """Linea de veredicto: icono + sigla + que significa."""
    icono = ICONO_VEREDICTO.get(v, "")
    return f"{icono} *{v}* — {DESCRIPCION_VEREDICTO.get(v, v)}"


def problema_corto(codigo: str, titulo_problema: str, nivel: int, base: int) -> str:
    return f"*{codigo}* · {titulo_problema}\n{dificultad(nivel)} · {base} pts"


def enunciado(texto: str) -> str:
    """Convierte el markdown de un enunciado al formato de WhatsApp."""
    return wa.desde_markdown(texto)
