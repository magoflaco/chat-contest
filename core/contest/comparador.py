"""Comparacion de la salida del alumno contra la esperada.

Vive del lado del **host**, no dentro del contenedor, y eso es a proposito: si las
respuestas esperadas entraran al sandbox, una entrega que consiga leer un archivo
las tendria servidas. Al contenedor solo le damos las entradas; las respuestas
nunca cruzan esa frontera.

Ver `docs/ANTITRAMPA.md`, seccion "por que el juez no ve las respuestas".
"""

from __future__ import annotations


def _tokens(texto: str) -> list[str]:
    return texto.split()


def _casi_igual(a: str, b: str, tolerancia: float) -> bool:
    """Compara dos tokens como numeros, con tolerancia absoluta o relativa."""
    if a == b:
        return True
    try:
        x, y = float(a), float(b)
    except ValueError:
        return False
    if x != x or y != y:                       # NaN nunca coincide
        return False
    if x in (float("inf"), float("-inf")) or y in (float("inf"), float("-inf")):
        return x == y
    diferencia = abs(x - y)
    return diferencia <= tolerancia or diferencia <= tolerancia * max(abs(x), abs(y))


def comparar(salida: str, esperado: str, tipo: str = "tokens",
             tolerancia: float = 1e-6) -> tuple[bool, str]:
    """Devuelve `(paso, veredicto)`. El veredicto es '' si paso.

    Tres modos:

    - `exacta`: byte a byte, ignorando solo el salto de linea final y los \\r.
      Si la unica diferencia es el espaciado, devuelve PE en vez de WA.
    - `tokens`: ignora todo el espaciado. Es el modo por defecto y el mas justo
      para chicos que estan aprendiendo a formatear la salida.
    - `numerica`: como tokens, pero comparando numeros con tolerancia.
    """
    if tipo == "exacta":
        a = salida.replace("\r\n", "\n").rstrip("\n")
        b = esperado.replace("\r\n", "\n").rstrip("\n")
        if a == b:
            return True, ""
        if _tokens(a) == _tokens(b):
            return False, "PE"
        return False, "WA"

    ta, tb = _tokens(salida), _tokens(esperado)
    if len(ta) != len(tb):
        return False, "WA"

    if tipo == "numerica":
        for x, y in zip(ta, tb):
            if not _casi_igual(x, y, tolerancia):
                return False, "WA"
        return True, ""

    return (ta == tb, "" if ta == tb else "WA")


def diferencia(salida: str, esperado: str) -> str:
    """Mensaje corto de en que difieren.

    Solo se le muestra al participante cuando el caso que fallo es publico: en un
    caso secreto revelaria contenido del test.
    """
    a = salida.strip().splitlines()
    b = esperado.strip().splitlines()

    if len(a) != len(b):
        return f"esperaba {len(b)} linea(s) y recibi {len(a)}"

    for i, (x, y) in enumerate(zip(a, b), start=1):
        if x.strip() != y.strip():
            return f"linea {i}: esperaba '{y.strip()[:60]}' y recibi '{x.strip()[:60]}'"

    return "la salida no coincide"
