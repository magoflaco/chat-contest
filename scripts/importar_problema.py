#!/usr/bin/env python3
"""Importa un problema en formato de paquete Kattis/ICPC al banco.

Es el formato que usan ICPC, el RPC y los regionales latinoamericanos, y el que
producen DOMjudge y Kattis:

    paquete/
        problem.yaml
        problem_statement/problem.en.tex   (o .md)
        data/sample/*.in  *.ans
        data/secret/*.in  *.ans
        submissions/accepted/*.py

Uso:

    python scripts/importar_problema.py ~/descargas/rpc2024-C \\
        --slug caminos-del-rio \\
        --dificultad 4 \\
        --fuente-tipo rpc \\
        --fuente-nombre "Rioplatense Programming Contest 2024, Problema C" \\
        --fuente-url https://... \\
        --fuente-anio 2024

Sobre licencias: la mayoria de los jueces online **prohibe redistribuir sus
enunciados**. Este script exige atribucion completa, pero la atribucion no
reemplaza al permiso. Si no estas seguro de poder redistribuir el texto, usa
`--solo-referencia`: importa los tests y los metadatos, y en vez del enunciado
completo deja un resumen tuyo y el link al original.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
DESTINO_BASE = RAIZ / "data" / "problems"

TIPOS_FUENTE = ("icpc", "rpc", "oia", "ioi", "kattis", "otro")


def _texto_del_enunciado(paquete: Path) -> str:
    """Busca el enunciado en las ubicaciones habituales del formato."""
    candidatos = [
        *sorted(paquete.glob("problem_statement/*.md")),
        *sorted(paquete.glob("problem_statement/*.tex")),
        *sorted(paquete.glob("statement/*.md")),
        *sorted(paquete.glob("*.md")),
    ]
    for c in candidatos:
        if c.name.lower() == "readme.md":
            continue
        texto = c.read_text(encoding="utf-8", errors="replace").strip()
        if texto:
            return _limpiar_latex(texto) if c.suffix == ".tex" else texto
    return ""


def _limpiar_latex(tex: str) -> str:
    """Conversion grosera de LaTeX a markdown.

    No pretende ser completa: deja el enunciado legible y despues hay que
    repasarlo a mano. Los enunciados de ICPC vienen en LaTeX con macros propias
    de cada regional, asi que no hay conversion automatica que sirva del todo.
    """
    t = tex
    t = re.sub(r"\\section\*?\{([^}]*)\}", r"\n## \1\n", t)
    t = re.sub(r"\\subsection\*?\{([^}]*)\}", r"\n### \1\n", t)
    t = re.sub(r"\\textbf\{([^}]*)\}", r"**\1**", t)
    t = re.sub(r"\\emph\{([^}]*)\}|\\textit\{([^}]*)\}", r"*\1\2*", t)
    t = re.sub(r"\\texttt\{([^}]*)\}", r"`\1`", t)
    t = re.sub(r"\$([^$]*)\$", r"`\1`", t)
    t = re.sub(r"\\begin\{[^}]*\}|\\end\{[^}]*\}", "", t)
    t = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _limites(paquete: Path) -> tuple[int, int]:
    """Lee los limites del problem.yaml del paquete, con valores por defecto sanos."""
    yml = paquete / "problem.yaml"
    if not yml.is_file():
        return 2000, 256
    try:
        datos = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return 2000, 256

    limites = datos.get("limits") or {}
    # el formato declara el tiempo en segundos
    segundos = limites.get("time_limit") or datos.get("time_limit") or 2
    memoria = limites.get("memory") or 256
    return int(float(segundos) * 1000), int(memoria)


def _copiar_casos(paquete: Path, destino: Path) -> tuple[int, int]:
    """Copia sample y secret. Devuelve (cantidad_samples, cantidad_secretos)."""
    contados = []
    for grupo in ("sample", "secret"):
        origen = paquete / "data" / grupo
        salida = destino / "tests" / grupo
        salida.mkdir(parents=True, exist_ok=True)

        n = 0
        for entrada in sorted(origen.rglob("*.in")) if origen.is_dir() else []:
            esperado = entrada.with_suffix(".ans")
            if not esperado.is_file():
                continue
            # se conserva la estructura de subcarpetas: en el formato Kattis cada
            # subdirectorio de secret/ es un grupo de tests (una subtarea)
            relativo = entrada.relative_to(origen)
            (salida / relativo.parent).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(entrada, salida / relativo)
            shutil.copyfile(esperado, (salida / relativo).with_suffix(".ans"))
            n += 1
        contados.append(n)
    return contados[0], contados[1]


def _copiar_solucion(paquete: Path, destino: Path) -> bool:
    """Copia una solucion aceptada en Python, si el paquete trae alguna."""
    for patron in ("submissions/accepted/*.py", "submissions/*.py", "*.py"):
        for candidata in sorted(paquete.glob(patron)):
            shutil.copyfile(candidata, destino / "solucion.py")
            return True
    return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("paquete", type=Path, help="carpeta del paquete a importar")
    p.add_argument("--slug", required=True, help="nombre de la carpeta destino")
    p.add_argument("--dificultad", type=int, required=True, choices=range(1, 6))
    p.add_argument("--titulo", default="", help="por defecto se toma del problem.yaml")
    p.add_argument("--tags", default="", help="separados por coma")
    p.add_argument("--fuente-tipo", required=True, choices=TIPOS_FUENTE)
    p.add_argument("--fuente-nombre", required=True,
                   help="credito completo, por ejemplo 'RPC 2024, Problema C'")
    p.add_argument("--fuente-url", default="")
    p.add_argument("--fuente-anio", default="")
    p.add_argument("--fuente-licencia", default="consultar con los organizadores")
    p.add_argument("--solo-referencia", action="store_true",
                   help="no copia el enunciado; deja un placeholder y el link al original")
    args = p.parse_args()

    paquete: Path = args.paquete.expanduser().resolve()
    if not paquete.is_dir():
        print(f"no existe la carpeta {paquete}")
        return 1

    if not re.match(r"^[a-z0-9][a-z0-9-]{1,60}$", args.slug):
        print("el slug tiene que ser minusculas, numeros y guiones")
        return 1

    destino = DESTINO_BASE / args.slug
    if destino.exists():
        print(f"ya existe data/problems/{args.slug}, elegi otro slug")
        return 1
    destino.mkdir(parents=True)

    # --- enunciado ---
    if args.solo_referencia:
        enunciado = (
            f"Problema tomado de **{args.fuente_nombre}**.\n\n"
            f"El enunciado original esta en: {args.fuente_url or '(falta el link)'}\n\n"
            "> TODO: reemplazar esto por un resumen propio del problema, con sus\n"
            "> secciones de Entrada, Salida y Restricciones. No copiar el texto\n"
            "> original salvo que este permitido redistribuirlo.\n"
        )
    else:
        enunciado = _texto_del_enunciado(paquete)
        if not enunciado:
            enunciado = ("> TODO: no se encontro el enunciado en el paquete.\n"
                         "> Escribilo a mano en este archivo.\n")

    (destino / "enunciado.md").write_text(enunciado + "\n", encoding="utf-8", newline="\n")

    # --- metadatos ---
    tiempo_ms, memoria_mb = _limites(paquete)
    titulo = args.titulo
    if not titulo:
        yml = paquete / "problem.yaml"
        if yml.is_file():
            datos = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
            nombre = datos.get("name")
            titulo = nombre if isinstance(nombre, str) else args.slug.replace("-", " ").title()
        else:
            titulo = args.slug.replace("-", " ").title()

    meta = {
        "slug": args.slug,
        "titulo": titulo,
        "dificultad": args.dificultad,
        "tags": [t.strip() for t in args.tags.split(",") if t.strip()],
        "limites": {"tiempo_ms": tiempo_ms, "memoria_mb": memoria_mb},
        "validacion": {"tipo": "tokens"},
        "fuente": {
            "tipo": args.fuente_tipo,
            "nombre": args.fuente_nombre,
            "url": args.fuente_url,
            "licencia": args.fuente_licencia,
        },
        "editorial": "",
    }
    if str(args.fuente_anio).isdigit():
        meta["fuente"]["anio"] = int(args.fuente_anio)

    (destino / "problema.yaml").write_text(
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
        encoding="utf-8", newline="\n")

    # --- casos y solucion ---
    samples, secretos = _copiar_casos(paquete, destino)
    tiene_solucion = _copiar_solucion(paquete, destino)

    print(f"importado en data/problems/{args.slug}")
    print(f"  {samples} sample(s), {secretos} caso(s) secreto(s)")
    print(f"  solucion de referencia: {'si' if tiene_solucion else 'NO'}")

    pendientes = []
    if samples == 0:
        pendientes.append("no hay samples: el banco exige al menos 1")
    if secretos < 3:
        pendientes.append(f"solo hay {secretos} casos secretos: el banco exige al menos 3")
    if not tiene_solucion:
        pendientes.append("falta solucion.py (el paquete no traia una en Python)")
    if not args.solo_referencia:
        pendientes.append("repasa enunciado.md a mano: la conversion de LaTeX es aproximada")
    pendientes.append("verifica que se pueda redistribuir el enunciado antes de commitear")

    print("\npara terminar:")
    for i, t in enumerate(pendientes, start=1):
        print(f"  {i}. {t}")
    print(f"\n  python -m contest.cli probar-todo --slug {args.slug}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
