"""Linea de comandos del core.

    python -m contest.cli servir       levanta la API (lo que usa el bot)
    python -m contest.cli validar      revisa el banco de problemas
    python -m contest.cli probar-todo  corre cada solucion de referencia contra sus tests
    python -m contest.cli ronda        crea y publica una ronda ahora
    python -m contest.cli tabla        imprime el ranking en la terminal
    python -m contest.cli chequeo      diagnostico de la instalacion
"""

from __future__ import annotations

import argparse
import sys

from . import commands, db, judge, problems, ranking
from .config import config


def _servir(_args) -> int:
    import uvicorn
    print(f"core escuchando en http://{config.host}:{config.port}")
    uvicorn.run("contest.api:app", host=config.host, port=config.port, log_level="info")
    return 0


def _validar(_args) -> int:
    errores = problems.validar_todos()
    banco = problems.banco(refrescar=True)

    if errores:
        print(f"{len(errores)} problema(s) con errores:\n")
        for e in errores:
            print(f"  - {e}")
    print(f"\n{len(banco)} problemas validos.")

    por_dificultad: dict[int, int] = {}
    for p in banco.values():
        por_dificultad[p.dificultad] = por_dificultad.get(p.dificultad, 0) + 1
    for d in sorted(por_dificultad):
        print(f"  dificultad {d}: {por_dificultad[d]}")

    return 1 if errores else 0


def _probar_todo(args) -> int:
    """Corre la solucion de referencia de cada problema contra todos sus tests.

    Es la red de seguridad del banco: si un problema tiene un test mal, se ve aca
    y no cuando un chico entrega una solucion correcta y le da WA.
    """
    banco = problems.banco(refrescar=True)
    if args.slug:
        banco = {k: v for k, v in banco.items() if k == args.slug}
        if not banco:
            print(f"no existe el problema '{args.slug}'")
            return 1

    fallos = 0
    for slug, p in sorted(banco.items()):
        referencia = p.solucion_referencia()
        if not referencia:
            print(f"  SIN SOLUCION  {slug}")
            fallos += 1
            continue

        try:
            resultado = judge.juzgar(referencia, p)
        except judge.ErrorJuez as e:
            print(f"  ERROR         {slug}: {e}")
            fallos += 1
            continue

        if resultado.aceptado:
            print(f"  ok            {slug}  ({resultado.tiempo_ms} ms, "
                  f"{len(p.samples) + len(p.secretos)} casos)")
        else:
            print(f"  {resultado.veredicto:<13} {slug}: caso {resultado.caso_fallido} - "
                  f"{resultado.detalle}")
            fallos += 1

    print(f"\n{len(banco) - fallos}/{len(banco)} problemas correctos.")
    return 1 if fallos else 0


def _ronda(args) -> int:
    from .rounds import crear_ronda
    from .scheduler import anunciar_ronda

    dificultades = tuple(int(x) for x in args.dificultades.split(",")) if args.dificultades else None
    try:
        ronda = crear_ronda(publicar_ya=True, dificultades=dificultades)
    except RuntimeError as e:
        print(f"error: {e}")
        return 1

    anunciar_ronda(ronda)
    print(f"ronda {ronda.numero} creada y encolada para publicar:")
    for pr in ronda.problemas:
        p = pr.problema
        print(f"  {pr.codigo}  d{pr.dificultad}  {p.titulo if p else pr.slug}")
    return 0


def _tabla(_args) -> int:
    filas = ranking.global_()
    if not filas:
        print("todavia no hay resultados.")
        return 0
    print(f"{'#':>3}  {'participante':<18} {'pts':>6} {'ok':>4} {'int':>4}")
    print("-" * 42)
    for f in filas:
        nombre = f.nombre or f"...{f.numero[-4:]}"
        print(f"{f.puesto:>3}  {nombre:<18} {f.puntos:>6} {f.resueltos:>4} {f.intentos:>4}")
    return 0


def _chequeo(_args) -> int:
    """Diagnostico: dice que falta configurar antes de arrancar de verdad."""
    problemas_encontrados: list[str] = []

    print("--- configuracion ---")
    print(f"  base de datos: {config.db_path}")
    print(f"  zona horaria:  {config.rondas.tz_nombre}")
    print(f"  ronda cada:    {config.rondas.cada_dias} dias, dificultades "
          f"{config.rondas.dificultades}")

    if not config.token or config.token.startswith("dev-"):
        problemas_encontrados.append("CORE_TOKEN sigue en el valor de ejemplo. "
                                     "generá uno con: openssl rand -hex 32")
    if not config.grupo_jid:
        problemas_encontrados.append("GRUPO_JID vacio: el bot no va a poder publicar las rondas. "
                                     "mandá !jid en el grupo para obtenerlo.")
    if not config.admins:
        problemas_encontrados.append("ADMINS vacio: nadie va a poder usar los comandos de admin.")

    print("\n--- IA ---")
    from . import ai
    print(f"  configurada: {'si' if ai.disponible() else 'no'}  ({config.ia.modelo})")
    if not ai.disponible():
        problemas_encontrados.append("NVIDIA_API_KEY vacia: !revisar y !pista no van a funcionar.")

    print("\n--- juez ---")
    print(f"  backend: {config.juez.backend}")
    if config.juez.backend == "docker":
        if judge.imagen_disponible():
            print(f"  imagen {config.juez.imagen}: lista")
        else:
            problemas_encontrados.append(
                f"la imagen del juez no esta construida. corré: "
                f"docker build -t {config.juez.imagen} judge/")
    else:
        problemas_encontrados.append(
            "JUDGE_BACKEND=subprocess NO AISLA NADA. usalo solo en tu maquina, "
            "nunca en el VPS.")

    print("\n--- problemas ---")
    banco = problems.banco(refrescar=True)
    errores = problems.validar_todos()
    print(f"  {len(banco)} validos, {len(errores)} con errores")
    if not banco:
        problemas_encontrados.append("el banco de problemas esta vacio.")

    print("\n--- comandos ---")
    commands.cargar_todos()
    print(f"  {len(commands.COMANDOS)} comandos registrados")

    if problemas_encontrados:
        print(f"\n{len(problemas_encontrados)} cosa(s) para revisar:")
        for p in problemas_encontrados:
            print(f"  - {p}")
        return 1

    print("\ntodo en orden.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="contest", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("servir", help="levanta la API").set_defaults(fn=_servir)
    sub.add_parser("validar", help="valida el banco de problemas").set_defaults(fn=_validar)
    sub.add_parser("tabla", help="imprime el ranking").set_defaults(fn=_tabla)
    sub.add_parser("chequeo", help="diagnostico de la instalacion").set_defaults(fn=_chequeo)

    p_probar = sub.add_parser("probar-todo", help="corre las soluciones de referencia")
    p_probar.add_argument("--slug", default="", help="probar solo este problema")
    p_probar.set_defaults(fn=_probar_todo)

    p_ronda = sub.add_parser("ronda", help="crea y publica una ronda")
    p_ronda.add_argument("--dificultades", default="", help="por ejemplo: 1,3,5")
    p_ronda.set_defaults(fn=_ronda)

    args = parser.parse_args(argv)
    db.inicializar()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
