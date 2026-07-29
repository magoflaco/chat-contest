"""Tests del anti-trampa.

Dos propiedades importan igual de fuerte: que atrape lo que tiene que atrapar, y
que **no** moleste a quien escribe codigo normal. Un anti-trampa con falsos
positivos hace que los chicos dejen de participar, que es peor que la trampa.
"""

from __future__ import annotations

import pytest

from contest import antifraud


# --- analisis estatico ---------------------------------------------------------

@pytest.mark.parametrize("codigo", [
    "import os\nos.system('ls')",
    "import subprocess\nsubprocess.run(['cat', '/etc/passwd'])",
    "import socket\ns = socket.socket()",
    "open('/work/casos/001.ans').read()",
    "eval(input())",
    "exec('print(1)')",
    "__import__('os').listdir('.')",
    "print(().__class__.__bases__[0].__subclasses__())",
    "import urllib.request",
    "from pathlib import Path",
])
def test_rechaza_codigo_que_se_sale_del_problema(codigo):
    assert antifraud.revisar_codigo(codigo), f"deberia haber marcado: {codigo}"


@pytest.mark.parametrize("codigo", [
    # soluciones normales de olimpiada, ninguna puede dar falso positivo
    "n = int(input())\nprint(n * 2)",
    "import sys\ndatos = sys.stdin.read().split()\nprint(len(datos))",
    "import math\nprint(math.gcd(12, 18))",
    "from collections import Counter, deque, defaultdict\nprint(Counter('aab'))",
    "import heapq\nh = []\nheapq.heappush(h, 3)\nprint(heapq.heappop(h))",
    "import bisect\nprint(bisect.bisect_left([1, 2, 3], 2))",
    "from itertools import permutations\nprint(len(list(permutations([1, 2, 3]))))",
    "from functools import lru_cache\n@lru_cache(None)\ndef f(n): return n\nprint(f(5))",
    "import sys\nsys.setrecursionlimit(300000)\nprint(1)",
    "class Nodo:\n    def __init__(self, v):\n        self.v = v\nprint(Nodo(1).v)",
])
def test_no_molesta_al_codigo_legitimo(codigo):
    hallazgos = antifraud.revisar_codigo(codigo)
    assert not hallazgos, f"falso positivo en:\n{codigo}\n-> {[h.motivo for h in hallazgos]}"


def test_codigo_con_sintaxis_rota_no_se_acusa_de_trampa():
    """Un error de tipeo lo tiene que detectar el juez como CE, no el anti-trampa."""
    assert antifraud.revisar_codigo("def f(:\n  pass") == []


def test_os_path_se_permite():
    """os.path aparece en codigo legitimo; solo bloqueamos lo peligroso de os."""
    assert antifraud.revisar_codigo("import math\nprint(math.floor(2.5))") == []


# --- similitud -----------------------------------------------------------------

ORIGINAL = """
import sys

def resolver(numeros):
    total = 0
    for x in numeros:
        if x % 2 == 0:
            total += x
    return total

datos = sys.stdin.read().split()
print(resolver([int(v) for v in datos[1:]]))
"""

COPIA_DISIMULADA = """
import sys

# solucion propia
def calcular(lista):
    acumulado = 0
    for elemento in lista:
        if elemento % 2 == 0:
            acumulado += elemento
    return acumulado

entrada = sys.stdin.read().split()
print(calcular([int(v) for v in entrada[1:]]))
"""

DISTINTA = """
import sys
from collections import Counter

datos = sys.stdin.read().split()
conteo = Counter(datos[1:])
mejor = max(conteo.values())
print(mejor)
"""


def test_detecta_copia_con_variables_renombradas():
    a = antifraud.huellas(ORIGINAL)
    b = antifraud.huellas(COPIA_DISIMULADA)
    assert antifraud.similitud(a, b) >= 0.8


def test_no_marca_soluciones_realmente_distintas():
    a = antifraud.huellas(ORIGINAL)
    b = antifraud.huellas(DISTINTA)
    assert antifraud.similitud(a, b) < 0.4


def test_similitud_de_algo_consigo_mismo_es_uno():
    h = antifraud.huellas(ORIGINAL)
    assert antifraud.similitud(h, h) == pytest.approx(1.0)


def test_los_comentarios_no_cambian_la_huella():
    con_comentarios = "# hola\nn = int(input())  # leo\nprint(n)  # imprimo"
    sin_comentarios = "n = int(input())\nprint(n)"
    assert (antifraud.normalizar_tokens(con_comentarios)
            == antifraud.normalizar_tokens(sin_comentarios))


# --- el hash de identidad ------------------------------------------------------
#
# Es el que decide si mostrar "ya mandaste exactamente este codigo". Tiene que
# responder a "es el mismo texto?" y nada mas. Antes usaba la normalizacion
# antiplagio, que borra comentarios y reemplaza todo numero por 0, y eso dejaba
# a alguien sin poder corregir una constante mal escrita: el sistema le decia
# que era el mismo codigo y le rechazaba el arreglo.


def test_hash_distingue_una_constante_corregida():
    """El caso real que rompio: R1-B, modulo con un cero de menos."""
    malo = "print(n % 100000007)"
    bueno = "print(n % 1000000007)"
    assert antifraud.hash_codigo(malo) != antifraud.hash_codigo(bueno)


def test_hash_distingue_un_comentario_agregado():
    a = "print(n)"
    assert antifraud.hash_codigo(a) != antifraud.hash_codigo("# intento 2\n" + a)


def test_hash_distingue_nombres_distintos():
    a = "def f(x):\n    return x + 1"
    b = "def sumar_uno(valor):\n    return valor + 1"
    assert antifraud.hash_codigo(a) != antifraud.hash_codigo(b)


def test_hash_distingue_logica_distinta():
    assert antifraud.hash_codigo("print(1 + 2)") != antifraud.hash_codigo("print(1 * 2)")


def test_hash_ignora_lo_que_pone_el_chat_y_no_la_persona():
    a = "n = int(input())\nprint(n)"
    assert antifraud.hash_codigo(a) == antifraud.hash_codigo("n = int(input())  \nprint(n)   ")
    assert antifraud.hash_codigo(a) == antifraud.hash_codigo(a.replace("\n", "\r\n"))


def test_el_mismo_reenvio_sigue_dando_igual():
    """Lo que el hash si tiene que atajar: mandar dos veces lo mismo."""
    a = "n = int(input())\nprint(n * 2)\n"
    assert antifraud.hash_codigo(a) == antifraud.hash_codigo(a)


def test_la_deteccion_de_copias_sigue_ignorando_nombres_y_numeros():
    """El hash cambio; la huella antiplagio NO tiene que cambiar.

    Ahi si queremos que renombrar variables o tocar una constante no alcance
    para disimular un plagio.
    """
    a = "def f(x):\n    return x + 1"
    b = "def sumar_uno(valor):\n        return valor + 7"
    assert antifraud.normalizar_tokens(a) == antifraud.normalizar_tokens(b)


def test_codigo_muy_corto_no_genera_huellas():
    """Sin esto, 'print(1)' se parece a 'print(2)' y marcaria a medio club."""
    assert antifraud.huellas("print(1)") == set()


# --- lo que llega pegado desde WhatsApp ----------------------------------------


def test_el_word_joiner_del_enunciado_no_rompe_la_entrega():
    """Los numeros largos del enunciado llevan un U+2060 para que WhatsApp no los
    convierta en links de telefono. Es invisible: quien copia `1000000007` se lo
    lleva puesto y Python le contesta "invalid non-printable character U+2060".
    """
    from contest.submissions import limpiar_fuente

    pegado = "n = int(input())\nprint(n % 1\u2060000000007)"
    with pytest.raises(SyntaxError):
        compile(pegado, "<entrega>", "exec")

    compile(limpiar_fuente(pegado), "<entrega>", "exec")


@pytest.mark.parametrize("invisible", ["\u2060", "\u200b", "\u200c", "\u200d", "\ufeff"])
def test_se_sacan_los_caracteres_de_ancho_cero(invisible):
    from contest.submissions import limpiar_fuente

    assert invisible not in limpiar_fuente(f"print({invisible}1)")


def test_el_espacio_duro_no_rompe_la_indentacion():
    """Se ve igual que un espacio comun y da IndentationError."""
    from contest.submissions import limpiar_fuente

    pegado = "if True:\n\u00a0\u00a0\u00a0\u00a0print(1)"
    compile(limpiar_fuente(pegado), "<entrega>", "exec")
