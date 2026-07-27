#!/usr/bin/env python3
"""Genera un problema nuevo con IA y lo valida antes de dejarlo en el banco.

Lo que sale de un modelo **no se acepta a ciegas**. El pipeline es:

    modelo -> escribe archivos -> corre la solucion contra los samples
           -> genera casos con el generador -> corre la solucion contra todos
           -> valida el formato del banco -> queda en data/problems/_borradores/

Nunca escribe directo en `data/problems/`: los problemas generados quedan en
`_borradores/` (que el cargador ignora, porque empieza con guion bajo) hasta que
una persona los lea, ajuste el enunciado y los mueva. Un problema mal planteado o
ambiguo arruina una ronda entera, y eso una validacion automatica no lo detecta.

Uso:

    python scripts/generar_problema.py --dificultad 2
    python scripts/generar_problema.py --dificultad 4 --tema "grafos" --intentos 3
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "core"))

from contest import ai  # noqa: E402

BORRADORES = RAIZ / "data" / "problems" / "_borradores"
TIMEOUT = 30

#: cuantos casos secretos se generan para validar el problema
CASOS = 10


def _correr(script: Path, *, args: list[str] | None = None, entrada: str = "") -> str:
    proceso = subprocess.run(
        [sys.executable, str(script), *(args or [])],
        input=entrada, capture_output=True, text=True,
        timeout=TIMEOUT, cwd=str(script.parent), encoding="utf-8",
    )
    if proceso.returncode != 0:
        raise RuntimeError(proceso.stderr.strip()[:500] or f"salio con codigo {proceso.returncode}")
    return proceso.stdout


def _escribir(datos: dict, dificultad: int, destino: Path) -> None:
    (destino / "tests" / "sample").mkdir(parents=True, exist_ok=True)
    (destino / "tests" / "secret").mkdir(parents=True, exist_ok=True)

    meta = {
        "slug": destino.name,
        "titulo": datos["titulo"],
        "dificultad": dificultad,
        "tags": list(datos.get("tags") or []),
        "autor": "generado con IA, revisar antes de usar",
        "limites": {"tiempo_ms": 2000, "memoria_mb": 256},
        "validacion": {"tipo": "tokens"},
        "fuente": {"tipo": "generado", "nombre": f"generado con {ai.config.ia.modelo}"},
        "editorial": datos.get("editorial", ""),
    }
    (destino / "problema.yaml").write_text(
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\n")

    (destino / "enunciado.md").write_text(datos["enunciado"].strip() + "\n",
                                          encoding="utf-8", newline="\n")
    (destino / "solucion.py").write_text(datos["solucion"].strip() + "\n",
                                         encoding="utf-8", newline="\n")
    (destino / "generador.py").write_text(datos["generador"].strip() + "\n",
                                          encoding="utf-8", newline="\n")

    for i, muestra in enumerate(datos.get("samples") or [], start=1):
        entrada = str(muestra.get("entrada", "")).rstrip() + "\n"
        salida = str(muestra.get("salida", "")).rstrip() + "\n"
        (destino / "tests" / "sample" / f"{i:02d}.in").write_text(entrada, encoding="utf-8", newline="\n")
        (destino / "tests" / "sample" / f"{i:02d}.ans").write_text(salida, encoding="utf-8", newline="\n")


def _validar(destino: Path) -> list[str]:
    """Corre todas las verificaciones. Lista vacia = el problema es usable."""
    errores: list[str] = []
    solucion = destino / "solucion.py"
    generador = destino / "generador.py"

    # 1. la solucion tiene que reproducir los samples que el propio modelo escribio.
    #    aca cae la mayoria de los problemas generados: el modelo inventa una salida
    #    que su propia solucion no produce.
    muestras = sorted((destino / "tests" / "sample").glob("*.in"))
    if not muestras:
        errores.append("no genero ningun sample")

    for entrada in muestras:
        try:
            obtenido = _correr(solucion, entrada=entrada.read_text(encoding="utf-8"))
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            errores.append(f"la solucion fallo con {entrada.name}: {e}")
            continue
        esperado = entrada.with_suffix(".ans").read_text(encoding="utf-8")
        if obtenido.split() != esperado.split():
            errores.append(
                f"{entrada.name}: la solucion imprime {obtenido.split()[:6]} "
                f"pero el sample dice {esperado.split()[:6]}")

    if errores:
        return errores

    # 2. el generador tiene que producir entradas que la solucion pueda resolver
    destino_secret = destino / "tests" / "secret"
    generados = 0
    for semilla in range(1, CASOS + 1):
        try:
            entrada = _correr(generador, args=[str(semilla)])
            salida = _correr(solucion, entrada=entrada)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            errores.append(f"semilla {semilla}: {e}")
            continue
        if not entrada.strip():
            errores.append(f"semilla {semilla}: genero una entrada vacia")
            continue
        (destino_secret / f"{semilla:03d}.in").write_text(entrada, encoding="utf-8", newline="\n")
        (destino_secret / f"{semilla:03d}.ans").write_text(salida, encoding="utf-8", newline="\n")
        generados += 1

    if generados < 3:
        errores.append(f"solo se pudieron generar {generados} casos secretos, hacen falta 3")

    # 3. el formato tiene que cumplir lo que exige el banco
    from contest.problems import ProblemaInvalido, cargar
    try:
        cargar(destino)
    except ProblemaInvalido as e:
        errores.append(str(e))

    return errores


def generar_uno(dificultad: int, tema: str) -> tuple[Path, list[str]] | None:
    datos = ai.redactar_problema(dificultad, tema)

    faltantes = [c for c in ("slug", "titulo", "enunciado", "solucion", "generador")
                 if not str(datos.get(c, "")).strip()]
    if faltantes:
        print(f"  el modelo no devolvio: {', '.join(faltantes)}")
        return None

    slug = "".join(c if c.isalnum() or c == "-" else "-" for c in str(datos["slug"]).lower())
    slug = "-".join(x for x in slug.split("-") if x)[:60]
    if not slug:
        print("  el slug generado no es valido")
        return None

    destino = BORRADORES / slug
    if destino.exists():
        shutil.rmtree(destino)

    _escribir(datos, dificultad, destino)
    return destino, _validar(destino)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dificultad", type=int, required=True, choices=range(1, 6))
    p.add_argument("--tema", default="", help="por ejemplo: grafos, strings, geometria")
    p.add_argument("--intentos", type=int, default=3,
                   help="cuantas veces reintentar si el problema no valida")
    args = p.parse_args()

    if not ai.disponible():
        print("la IA no esta configurada: falta NVIDIA_API_KEY en el .env")
        return 1

    BORRADORES.mkdir(parents=True, exist_ok=True)

    for intento in range(1, args.intentos + 1):
        print(f"\nintento {intento}/{args.intentos}...")
        try:
            resultado = generar_uno(args.dificultad, args.tema)
        except ai.ErrorIA as e:
            print(f"  el modelo fallo: {e}")
            continue

        if resultado is None:
            continue
        destino, errores = resultado

        if errores:
            print(f"  '{destino.name}' no valida:")
            for e in errores[:5]:
                print(f"    - {e}")
            shutil.rmtree(destino, ignore_errors=True)
            continue

        print(f"\nlisto: data/problems/_borradores/{destino.name}")
        print("\nesto NO esta en el banco todavia. Antes de moverlo a data/problems/:")
        print("  1. lee el enunciado: que no sea ambiguo y que declare las restricciones")
        print("  2. verifica que la dificultad declarada sea la real")
        print("  3. revisa que el generador cubra los casos borde (minimo, maximo, vacio)")
        print("  4. escribi las pistas y mejora la editorial")
        print(f"  5. python scripts/generar_tests.py {destino.name} --casos 15")
        return 0

    print(f"\nno se logro generar un problema valido en {args.intentos} intentos.")
    print("probá con otra dificultad o dando un tema mas concreto con --tema.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
