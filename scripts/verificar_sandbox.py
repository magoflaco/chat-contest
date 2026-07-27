#!/usr/bin/env python3
"""Bateria de intentos de escape contra el juez.

Corre entregas maliciosas de verdad y verifica que ninguna consiga lo que busca.
Es el test que hay que correr **antes de poner esto en el VPS**, y cada vez que se
toque `judge/` o `antifraud.py`.

    python scripts/verificar_sandbox.py

Importante: se ejecuta con el backend configurado en el .env. Para que valga como
verificacion de produccion tiene que ser `docker`; con `subprocess` casi todo va a
fallar, y esta bien que asi sea, porque ese backend no aisla nada.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "core"))

from contest import antifraud, judge, problems  # noqa: E402
from contest.config import config  # noqa: E402


@dataclass
class Ataque:
    nombre: str
    codigo: str
    #: veredictos que consideramos una defensa exitosa
    esperados: tuple[str, ...]
    explicacion: str


ATAQUES = [
    Ataque(
        "leer los casos de prueba secretos",
        "print(open('/work/casos/001.ans').read())",
        ("SEC",),
        "si pudiera leer los .ans, resolveria cualquier problema copiando la respuesta",
    ),
    Ataque(
        "leer los casos evitando el analisis estatico",
        "import io\nf = io.open('/work/casos/001.ans')\nprint(f.read())",
        ("SEC", "RE"),
        "io.open es un alias de open; si el AST no lo ve, el sandbox tiene que frenarlo",
    ),
    Ataque(
        "listar el filesystem",
        "import os\nprint(os.listdir('/'))",
        ("SEC",),
        "explorar el disco es el primer paso de cualquier escape",
    ),
    Ataque(
        "ejecutar un comando del sistema",
        "import subprocess\nprint(subprocess.check_output(['id']))",
        ("SEC",),
        "ejecutar binarios arbitrarios seria control total del contenedor",
    ),
    Ataque(
        "salir a internet",
        "import urllib.request\nprint(urllib.request.urlopen('http://example.com').status)",
        ("SEC",),
        "sin red no puede filtrar los tests ni descargarse una solucion",
    ),
    Ataque(
        "abrir un socket crudo",
        "import socket\ns = socket.socket()\ns.connect(('1.1.1.1', 53))",
        ("SEC",),
        "lo mismo que arriba, por la via de mas bajo nivel",
    ),
    Ataque(
        "escribir en el filesystem",
        "open('/work/marca.txt', 'w').write('estuve aca')",
        ("SEC",),
        "el filesystem esta montado de solo lectura, ademas del analisis estatico",
    ),
    Ataque(
        "escapar por __subclasses__",
        "print([c for c in ().__class__.__base__.__subclasses__() if 'Popen' in str(c)])",
        ("SEC",),
        "el truco clasico para alcanzar Popen sin importar subprocess",
    ),
    Ataque(
        "evaluar codigo construido en runtime",
        "eval(chr(112)+chr(114)+chr(105)+chr(110)+chr(116)+'(1)')",
        ("SEC",),
        "armar el codigo como string es la forma tipica de esquivar un analisis de AST",
    ),
    Ataque(
        "leer variables de entorno",
        "import os\nprint(os.environ)",
        ("SEC",),
        "si hubiera secretos en el entorno del contenedor, quedarian expuestos",
    ),
    Ataque(
        "bomba de forks",
        "import os\nwhile True:\n    os.fork()",
        ("SEC",),
        "sin --pids-limit una bomba de forks voltea el VPS entero",
    ),
    Ataque(
        "agotar la memoria",
        "x = []\nwhile True:\n    x.append('a' * 10_000_000)",
        ("MLE", "TLE", "RE"),
        "el limite de memoria del cgroup tiene que cortarlo antes de tocar el host",
    ),
    Ataque(
        "ciclo infinito",
        "while True:\n    pass",
        ("TLE",),
        "el limite de tiempo de pared tiene que matarlo",
    ),
    Ataque(
        "recursion infinita",
        "import sys\nsys.setrecursionlimit(10**9)\ndef f(n):\n    return f(n + 1)\nf(0)",
        ("RE", "MLE", "TLE"),
        "reventar la pila no puede tumbar al juez, solo a la entrega",
    ),
    Ataque(
        "escribir un archivo gigante",
        "with open('salida.bin', 'wb') as f:\n    f.write(b'0' * (10 ** 10))",
        ("SEC", "RE", "MLE", "TLE"),
        "sin RLIMIT_FSIZE una entrega podria llenar el disco del VPS",
    ),
    Ataque(
        "inundar la salida estandar",
        "while True:\n    print('a' * 1000)",
        ("TLE", "RE", "WA"),
        "el que tiene que morir es el proceso hijo, no el juez: la salida va a un "
        "archivo del tmpfs y no a un pipe en memoria del runner",
    ),
]


def main() -> int:
    banco = problems.banco(refrescar=True)
    problema = banco.get("suma-de-digitos") or next(iter(banco.values()), None)
    if problema is None:
        print("no hay problemas en el banco, no puedo correr la verificacion")
        return 1

    print(f"backend del juez: {config.juez.backend}")
    if config.juez.backend != "docker":
        print("\nATENCION: el backend no es docker. Esta corrida NO valida el aislamiento.\n"
              "          poné JUDGE_BACKEND=docker en el .env para verificar de verdad.\n")
    elif not judge.imagen_disponible():
        print(f"la imagen {config.juez.imagen} no esta construida.\n"
              f"corré: docker build -t {config.juez.imagen} judge/")
        return 1

    print(f"problema de prueba: {problema.slug}\n")
    print(f"{'ataque':<42} {'estatico':<9} {'veredicto':<10} resultado")
    print("-" * 88)

    fallos = 0
    detalles_ie: list[str] = []
    tmp = RAIZ / "var" / "verificacion"
    tmp.mkdir(parents=True, exist_ok=True)

    for ataque in ATAQUES:
        hallazgos = antifraud.revisar_codigo(ataque.codigo)
        marca_estatica = "bloquea" if hallazgos else "-"

        if hallazgos:
            # el analisis estatico ya lo freno: es exactamente lo que hace submissions.py
            veredicto = "SEC"
        else:
            fuente = tmp / "ataque.py"
            fuente.write_text(ataque.codigo, encoding="utf-8")
            try:
                resultado = judge.juzgar(fuente, problema)
                veredicto = resultado.veredicto
                # un IE es un fallo NUESTRO, no una defensa: hay que poder ver por que
                if veredicto == "IE":
                    detalles_ie.append(f"{ataque.nombre}: {resultado.detalle}")
            except judge.ErrorJuez as e:
                veredicto = "ERR"
                detalles_ie.append(f"{ataque.nombre}: {e}")

        ok = veredicto in ataque.esperados
        if not ok:
            fallos += 1
        print(f"{ataque.nombre:<42} {marca_estatica:<9} {veredicto:<10} "
              f"{'ok' if ok else 'FALLO -> ' + ataque.explicacion}")

    print("-" * 88)

    if detalles_ie:
        print("\nEl juez devolvio IE, que es un error NUESTRO y no una defensa:")
        for d in detalles_ie:
            print(f"  - {d}")
        print("\nSi todos los IE son de permisos, el contenedor no puede leer el")
        print("directorio de trabajo. Ver _abrir_permisos() en core/contest/judge.py.")

    if fallos:
        print(f"\n{fallos} de {len(ATAQUES)} ataques NO fueron contenidos. "
              "NO desplegar hasta resolverlo.")
        return 1

    print(f"\nlos {len(ATAQUES)} ataques fueron contenidos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
