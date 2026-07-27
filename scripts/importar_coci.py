#!/usr/bin/env python3
"""Importa problemas del archivo publico de COCI.

COCI (Croatian Open Competition in Informatics) publica en hsin.hr/coci/archive/
los enunciados, **los datos de prueba completos** y las soluciones de todas sus
competencias desde 2006/2007. Es la fuente mas util que encontramos: la mayoria
de los jueces online publica solo los casos de ejemplo, y sin tests ocultos no se
puede juzgar nada.

Formato de sus zips de test data:

    tarea/tarea.dummy.in.1   .out.1     casos de ejemplo (van a sample/)
    tarea/tarea.in.1a  .out.1a          subtarea 1, caso a
    tarea/tarea.in.2a  .out.2a          subtarea 2, caso a

El numero es la subtarea y la letra el caso dentro de ella, que mapea directo a
nuestro formato de subtareas estilo IOI.

Uso:

    # ver que trae, sin escribir nada
    python scripts/importar_coci.py 2020_2021 1 --listar

    # importar una tarea
    python scripts/importar_coci.py 2020_2021 1 --tarea patkice --dificultad 2

    # importar todas las del contest, para revisarlas despues una por una
    python scripts/importar_coci.py 2020_2021 1 --todas --dificultad 3

SOBRE LOS ENUNCIADOS
--------------------
Los enunciados de COCI vienen en un PDF aparte y este script **no los copia**.
Deja en `enunciado.md` un placeholder con el link al PDF oficial para que quien
importa escriba su propio resumen del problema.

Es a proposito: COCI publica su archivo para que la gente practique, pero no da
una licencia explicita de redistribucion. Un resumen propio con atribucion y link
es seguro; copiar el texto completo a un repo publico no lo es.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
import zipfile
from collections import defaultdict
from io import BytesIO
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
DESTINO_BASE = RAIZ / "data" / "problems"
CACHE = RAIZ / "var" / "coci"

BASE_URL = "https://hsin.hr/coci/archive"

#: tarea/tarea.dummy.in.1   ->  (tarea, 'dummy', '1')
#: tarea/tarea.in.2c        ->  (tarea, 'secret', '2c')
_PATRON = re.compile(
    r"^(?P<tarea>[^/]+)/(?P=tarea)\.(?P<dummy>dummy\.)?in\.(?P<caso>[0-9]+[a-z]*)$"
)


def descargar(temporada: str, contest: int) -> bytes:
    """Baja el zip de test data, con cache en var/coci/ para no repetir."""
    nombre = f"contest{contest}_testdata.zip"
    cacheado = CACHE / temporada / nombre

    if cacheado.is_file():
        print(f"usando la copia en cache: {cacheado.relative_to(RAIZ)}")
        return cacheado.read_bytes()

    url = f"{BASE_URL}/{temporada}/{nombre}"
    print(f"descargando {url} ...")
    try:
        with urllib.request.urlopen(url, timeout=600) as r:
            datos = r.read()
    except OSError as e:
        raise SystemExit(f"no se pudo descargar: {e}")

    cacheado.parent.mkdir(parents=True, exist_ok=True)
    cacheado.write_bytes(datos)
    print(f"  {len(datos) // 1024} KB, guardado en cache")
    return datos


def inventario(zf: zipfile.ZipFile) -> dict[str, dict]:
    """Agrupa los archivos del zip por tarea.

    Devuelve `{tarea: {"samples": [caso], "subtareas": {id: [caso]}}}`.
    """
    tareas: dict[str, dict] = defaultdict(
        lambda: {"samples": [], "subtareas": defaultdict(list)})

    for nombre in zf.namelist():
        m = _PATRON.match(nombre.replace("\\", "/"))
        if not m:
            continue

        tarea = m.group("tarea")
        caso = m.group("caso")

        # el .out correspondiente tiene que existir para que el caso sirva
        salida = nombre.replace(".in.", ".out.")
        if salida not in zf.namelist():
            continue

        if m.group("dummy"):
            tareas[tarea]["samples"].append((nombre, salida, caso))
        else:
            # el prefijo numerico es la subtarea
            subtarea = re.match(r"^([0-9]+)", caso).group(1)
            tareas[tarea]["subtareas"][f"s{subtarea}"].append((nombre, salida, caso))

    return tareas


def importar(zf: zipfile.ZipFile, tarea: str, datos: dict, *, temporada: str,
             contest: int, dificultad: int, slug: str) -> tuple[Path, list[str]]:
    """Escribe una tarea al banco. Devuelve (carpeta, advertencias)."""
    destino = DESTINO_BASE / slug
    (destino / "tests" / "sample").mkdir(parents=True, exist_ok=True)

    advertencias: list[str] = []

    # --- samples ---
    for i, (entrada, salida, _) in enumerate(sorted(datos["samples"]), start=1):
        (destino / "tests" / "sample" / f"{i:02d}.in").write_bytes(zf.read(entrada))
        (destino / "tests" / "sample" / f"{i:02d}.ans").write_bytes(zf.read(salida))

    if not datos["samples"]:
        advertencias.append("no trae casos de ejemplo: hay que escribir al menos uno a mano")

    # --- casos secretos, uno por subtarea ---
    subtareas_meta = []
    ordenadas = sorted(datos["subtareas"].items())
    # COCI reparte el puntaje entre subtareas; sin esa info repartimos parejo
    peso = 100 // len(ordenadas) if ordenadas else 0
    sobrante = 100 - peso * len(ordenadas)

    for indice, (sid, casos) in enumerate(ordenadas):
        carpeta = destino / "tests" / "secret" / sid
        carpeta.mkdir(parents=True, exist_ok=True)
        for i, (entrada, salida, _) in enumerate(sorted(casos), start=1):
            (carpeta / f"{i:03d}.in").write_bytes(zf.read(entrada))
            (carpeta / f"{i:03d}.ans").write_bytes(zf.read(salida))

        subtareas_meta.append({
            "id": sid,
            "peso": peso + (sobrante if indice == 0 else 0),
            "descripcion": f"subtarea {sid[1:]} de COCI ({len(casos)} casos)",
        })

    total_secretos = sum(len(c) for c in datos["subtareas"].values())
    if total_secretos < 3:
        advertencias.append(f"solo trae {total_secretos} casos secretos, el banco exige 3")

    # --- metadatos ---
    anio = temporada.split("_")[0]
    url_pdf = f"{BASE_URL}/{temporada}/contest{contest}_tasks.pdf"

    meta = {
        "slug": slug,
        "titulo": tarea.capitalize(),
        "dificultad": dificultad,
        # fuera del banco hasta que alguien escriba el enunciado y la solucion
        "borrador": True,
        "tags": [],
        "autor": "",
        "limites": {"tiempo_ms": 2000, "memoria_mb": 256},
        "validacion": {"tipo": "tokens"},
        "fuente": {
            "tipo": "otro",
            "nombre": f"COCI {temporada.replace('_', '/')}, contest {contest}, tarea {tarea}",
            "url": url_pdf,
            "anio": int(anio),
            "licencia": "archivo publico de hsin.hr, publicado para practica",
        },
        "editorial": "",
    }
    if len(subtareas_meta) > 1:
        meta["subtareas"] = subtareas_meta

    (destino / "problema.yaml").write_text(
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
        encoding="utf-8", newline="\n")

    (destino / "enunciado.md").write_text(
        f"> **Pendiente de redaccion.**\n"
        f">\n"
        f"> Este problema viene de COCI {temporada.replace('_', '/')}, contest {contest},\n"
        f"> tarea `{tarea}`. El enunciado original esta en:\n"
        f">\n"
        f"> {url_pdf}\n"
        f">\n"
        f"> Escribi aca un resumen **propio** del problema, con sus secciones de\n"
        f"> Entrada, Salida y Restricciones. No copies el texto original: COCI\n"
        f"> publica su archivo para practicar, pero no da permiso de redistribucion.\n"
        f">\n"
        f"> Verifica ademas los limites de tiempo y memoria contra el PDF, y ajusta\n"
        f"> la dificultad y los pesos de las subtareas.\n",
        encoding="utf-8", newline="\n")

    advertencias.append("falta escribir enunciado.md (esta el placeholder con el link)")
    advertencias.append("falta solucion.py: sin ella la CI no puede verificar los tests")

    return destino, advertencias


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("temporada", help="por ejemplo 2020_2021")
    p.add_argument("contest", type=int, help="numero de contest, de 1 a 6")
    p.add_argument("--listar", action="store_true", help="solo mostrar que trae")
    p.add_argument("--tarea", default="", help="importar solo esta tarea")
    p.add_argument("--todas", action="store_true", help="importar todas las tareas")
    p.add_argument("--dificultad", type=int, default=3, choices=range(1, 6))
    p.add_argument("--prefijo", default="coci", help="prefijo del slug")
    args = p.parse_args()

    zf = zipfile.ZipFile(BytesIO(descargar(args.temporada, args.contest)))
    tareas = inventario(zf)

    if not tareas:
        print("el zip no tiene el formato esperado de COCI")
        return 1

    if args.listar or (not args.tarea and not args.todas):
        print(f"\nCOCI {args.temporada.replace('_', '/')}, contest {args.contest}:\n")
        for tarea, datos in sorted(tareas.items()):
            subs = len(datos["subtareas"])
            casos = sum(len(c) for c in datos["subtareas"].values())
            print(f"  {tarea:<16} {len(datos['samples'])} ejemplo(s), "
                  f"{casos} caso(s) secreto(s) en {subs} subtarea(s)")
        print(f"\nenunciados: {BASE_URL}/{args.temporada}/contest{args.contest}_tasks.pdf")
        print(f"\npara importar una:  --tarea <nombre> --dificultad <1-5>")
        return 0

    elegidas = sorted(tareas) if args.todas else [args.tarea]
    importadas = []

    for tarea in elegidas:
        if tarea not in tareas:
            print(f"no existe la tarea '{tarea}' en este contest")
            return 1

        anio_corto = args.temporada.split("_")[0][-2:]
        slug = f"{args.prefijo}-{anio_corto}-{args.contest}-{tarea}".lower()
        slug = re.sub(r"[^a-z0-9-]", "-", slug)

        if (DESTINO_BASE / slug).exists():
            print(f"  {slug}: ya existe, se saltea")
            continue

        destino, advertencias = importar(
            zf, tarea, tareas[tarea], temporada=args.temporada, contest=args.contest,
            dificultad=args.dificultad, slug=slug)
        importadas.append((slug, advertencias))
        print(f"  {slug}")

    if not importadas:
        return 0

    print(f"\n{len(importadas)} tarea(s) importada(s) en data/problems/.")
    print("\nNINGUNA es usable todavia. Para cada una hace falta:")
    print("  1. escribir enunciado.md con un resumen propio (hay un placeholder con el link)")
    print("  2. escribir solucion.py, y verificar que pase con:")
    print("       cd core && python -m contest.cli probar-todo --slug <slug>")
    print("  3. ajustar dificultad, limites y pesos de las subtareas segun el PDF")
    print("\nHasta que tengan enunciado y solucion, el cargador las va a rechazar,")
    print("asi que no van a salir sorteadas en ninguna ronda.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
