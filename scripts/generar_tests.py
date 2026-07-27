#!/usr/bin/env python3
"""Genera los casos de prueba secretos de un problema.

Asi es como se arman los tests en las competencias de verdad: no se escriben a
mano, se generan con un programa y la respuesta la calcula la solucion de
referencia. Eso garantiza que entrada y salida esperada siempre esten en sintonia.

Cada problema trae un `generador.py` que recibe una semilla por `sys.argv[1]` e
imprime UN caso valido en la salida estandar. Este script lo corre N veces, le pasa
cada salida a `solucion.py` y guarda el par `.in` / `.ans`.

    python scripts/generar_tests.py                 todos los problemas
    python scripts/generar_tests.py islas           uno solo
    python scripts/generar_tests.py islas --casos 25

Los archivos generados se commitean: asi el juez no depende de poder ejecutar el
generador, y cualquiera puede revisar en el pull request que los tests tengan sentido.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
PROBLEMAS = RAIZ / "data" / "problems"

#: tiempo maximo que le damos al generador y a la solucion de referencia
TIMEOUT = 60


def _rango(texto: str) -> set[int]:
    """Parsea '1-8' o '3,5,9-12' a un conjunto de semillas."""
    semillas: set[int] = set()
    for trozo in str(texto).replace(" ", "").split(","):
        if not trozo:
            continue
        if "-" in trozo:
            desde, _, hasta = trozo.partition("-")
            semillas.update(range(int(desde), int(hasta) + 1))
        else:
            semillas.add(int(trozo))
    return semillas


def _mapa_subtareas(directorio: Path) -> dict[int, str]:
    """Semilla -> id de subtarea, leido de `subtareas[].semillas` en el YAML.

    Los problemas con subtareas guardan sus casos en `tests/secret/<id>/`, porque
    el juez puntua cada subtarea por separado (regla del minimo, estilo IOI).
    """
    yml = directorio / "problema.yaml"
    if not yml.is_file():
        return {}
    datos = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}

    mapa: dict[int, str] = {}
    for sub in datos.get("subtareas") or []:
        if not isinstance(sub, dict) or "semillas" not in sub:
            continue
        for semilla in _rango(sub["semillas"]):
            mapa[semilla] = str(sub["id"])
    return mapa


def _correr(script: Path, *, args: list[str] | None = None, entrada: str = "") -> str:
    proceso = subprocess.run(
        [sys.executable, str(script), *(args or [])],
        input=entrada,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        cwd=str(script.parent),
        encoding="utf-8",
    )
    if proceso.returncode != 0:
        raise RuntimeError(f"{script.name} fallo:\n{proceso.stderr.strip()[:800]}")
    return proceso.stdout


def generar(directorio: Path, cantidad: int, verbose: bool = True) -> int:
    if es_borrador(directorio):
        # un borrador trae los casos de su fuente original; regenerarlos los borraria
        if verbose:
            print(f"  {directorio.name}: es borrador, se deja como esta")
        return 0

    generador = directorio / "generador.py"
    solucion = directorio / "solucion.py"

    if not solucion.is_file():
        print(f"  {directorio.name}: falta solucion.py, se saltea")
        return 0
    if not generador.is_file():
        print(f"  {directorio.name}: sin generador.py, se dejan los tests que ya estan")
        return 0

    raiz_secret = directorio / "tests" / "secret"
    # se borra y se rehace: si no, quedan casos viejos de una version anterior del
    # generador mezclados con los nuevos, y eso es dificilisimo de depurar despues
    shutil.rmtree(raiz_secret, ignore_errors=True)
    raiz_secret.mkdir(parents=True, exist_ok=True)

    mapa = _mapa_subtareas(directorio)

    escritos = 0
    for semilla in range(1, cantidad + 1):
        try:
            entrada = _correr(generador, args=[str(semilla)])
            esperado = _correr(solucion, entrada=entrada)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f"  {directorio.name}: semilla {semilla} fallo: {e}")
            continue

        if not entrada.strip():
            print(f"  {directorio.name}: semilla {semilla} genero una entrada vacia")
            continue

        destino = raiz_secret / mapa[semilla] if semilla in mapa else raiz_secret
        destino.mkdir(parents=True, exist_ok=True)

        (destino / f"{semilla:03d}.in").write_text(entrada, encoding="utf-8", newline="\n")
        (destino / f"{semilla:03d}.ans").write_text(esperado, encoding="utf-8", newline="\n")
        escritos += 1

    if mapa:
        huerfanas = sorted(set(range(1, cantidad + 1)) - set(mapa))
        if huerfanas:
            print(f"  {directorio.name}: las semillas {huerfanas} no estan asignadas a "
                  f"ninguna subtarea y no van a puntuar")

    if verbose:
        print(f"  {directorio.name}: {escritos} casos secretos")
    return escritos


def es_borrador(directorio: Path) -> bool:
    """True si el problema esta marcado `borrador: true`.

    Los borradores estan a medio terminar (tipicamente recien importados, sin
    enunciado propio ni solucion de referencia). El cargador ya los deja fuera del
    banco, asi que verificarlos aca solo produciria ruido en la CI.
    """
    yml = directorio / "problema.yaml"
    if not yml.is_file():
        return False
    try:
        datos = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return False
    return bool(datos.get("borrador", False))


def verificar_samples(directorio: Path) -> list[str]:
    """Comprueba que la solucion de referencia reproduzca los samples del enunciado.

    Un sample que no coincide con la solucion es el error mas comun al escribir un
    problema, y el mas frustrante para quien lo intenta resolver.
    """
    if es_borrador(directorio):
        return []

    solucion = directorio / "solucion.py"
    if not solucion.is_file():
        return [f"{directorio.name}: falta solucion.py"]

    errores = []
    for entrada in sorted((directorio / "tests" / "sample").glob("*.in")):
        esperado_path = entrada.with_suffix(".ans")
        if not esperado_path.is_file():
            errores.append(f"{directorio.name}/{entrada.name}: falta el .ans")
            continue
        try:
            obtenido = _correr(solucion, entrada=entrada.read_text(encoding="utf-8"))
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            errores.append(f"{directorio.name}/{entrada.name}: {e}")
            continue

        if obtenido.split() != esperado_path.read_text(encoding="utf-8").split():
            errores.append(
                f"{directorio.name}/{entrada.name}: la solucion de referencia no reproduce el sample"
            )
    return errores


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slug", nargs="?", default="", help="generar solo este problema")
    parser.add_argument("--casos", type=int, default=15, help="casos secretos por problema")
    parser.add_argument("--verificar", action="store_true",
                        help="solo verificar los samples, sin generar nada")
    args = parser.parse_args()

    directorios = [d for d in sorted(PROBLEMAS.iterdir())
                   if d.is_dir() and not d.name.startswith((".", "_"))]
    if args.slug:
        directorios = [d for d in directorios if d.name == args.slug]
        if not directorios:
            print(f"no existe el problema '{args.slug}'")
            return 1

    errores: list[str] = []
    for d in directorios:
        errores += verificar_samples(d)
        if not args.verificar:
            generar(d, args.casos)

    if errores:
        print(f"\n{len(errores)} error(es) en los samples:")
        for e in errores:
            print(f"  - {e}")
        return 1

    print(f"\n{len(directorios)} problema(s) procesados, samples correctos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
