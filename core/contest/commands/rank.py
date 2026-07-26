"""Ranking y perfil: !rank, !lb, !perfil, !misentregas."""

from __future__ import annotations

from .. import format as fmt, ranking
from ..rounds import ronda_actual
from ..submissions import asegurar_usuario, historial_usuario
from . import PREFIJO, Contexto, comando


@comando("rank", "lb", "leaderboard", "ranking", "tabla", uso="!rank [ronda|global]",
         ayuda="Tabla de posiciones.", categoria="Ranking")
def cmd_rank(ctx: Contexto) -> str:
    arg = ctx.arg(0).lower()

    if arg in ("global", "total", "gral"):
        filas = ranking.global_()
        encabezado = "ranking global"
    elif arg.isdigit():
        numero = int(arg)
        filas = ranking.por_ronda(numero)
        encabezado = f"ronda {numero}"
        if not filas:
            return f"no hay resultados para la ronda {numero}."
    elif arg in ("ronda", "actual"):
        ronda = ronda_actual()
        if not ronda:
            return f"no hay ninguna ronda abierta. proba {PREFIJO}rank global."
        filas = ranking.por_ronda(ronda.numero)
        encabezado = f"ronda {ronda.numero}"
    else:
        filas = ranking.global_()
        encabezado = "ranking global"

    return "\n".join([
        fmt.titulo(encabezado),
        fmt.tabla_ranking(filas, resaltar=ctx.numero),
        "",
        f"_puntos / resueltos_ - detalle con {PREFIJO}perfil",
    ])


@comando("perfil", "yo", "mistats", uso="!perfil [numero]",
         ayuda="Tus estadisticas y tu detalle por problema.", categoria="Ranking")
def cmd_perfil(ctx: Contexto) -> str:
    objetivo = ctx.numero
    if ctx.arg(0) and ctx.es_admin:
        objetivo = "".join(c for c in ctx.arg(0) if c.isdigit())

    asegurar_usuario(ctx.numero, ctx.nombre)
    p = ranking.perfil(objetivo)
    if not p or p.intentos == 0:
        return ("todavia no tenes ninguna entrega.\n"
                f"mira los problemas de la ronda con {PREFIJO}problemas "
                f"y manda tu solucion con {PREFIJO}entrega.")

    lineas = [
        fmt.titulo(p.nombre or "tu perfil"),
        f"puesto:    {p.puesto}o" if p.puesto else "puesto:    -",
        f"puntos:    {p.puntos}",
        f"resueltos: {p.resueltos} de {len(p.detalle)} intentados",
        f"precision: {p.precision:.0%}",
    ]

    if p.por_dificultad:
        lineas += ["", "*por dificultad*"]
        lineas += [f"  {nombre:<11} {n}" for nombre, n in sorted(p.por_dificultad.items())]

    recientes = p.detalle[:8]
    if recientes:
        lineas += ["", "*ultimos problemas*"]
        for d in recientes:
            estado = f"{d['puntos']} pts" if d["resuelto"] else f"{d['intentos']} int."
            marca = "ok " if d["resuelto"] else "   "
            lineas.append(f"  {marca}{d['codigo']:<7} {estado}")

    return "\n".join(lineas)


@comando("misentregas", "entregas", "historial", uso="!misentregas",
         ayuda="Tus ultimas entregas con su veredicto.", categoria="Ranking",
         solo_privado=True)
def cmd_misentregas(ctx: Contexto) -> str:
    entregas = historial_usuario(ctx.numero, limite=12)
    if not entregas:
        return "todavia no mandaste ninguna entrega."

    lineas = [fmt.titulo("tus entregas")]
    for e in entregas:
        puntos = f" +{e['puntos']}" if e["puntos"] else ""
        lineas.append(f"#{e['id']:<5} {e['codigo']:<7} {e['veredicto']:<4}{puntos}")

    lineas += ["", f"para entender un veredicto: {PREFIJO}revisar <codigo>"]
    return "\n".join(lineas)


@comando("alias", "nombre", uso="!alias <como querés que te llamen>",
         ayuda="Define el nombre con el que aparecés en la tabla.", categoria="Ranking")
def cmd_alias(ctx: Contexto) -> str:
    from .. import db

    nuevo = ctx.args.strip()
    if not nuevo:
        actual = db.uno("SELECT alias FROM usuarios WHERE numero = ?", (ctx.numero,))
        vigente = (actual["alias"] if actual else None) or "(ninguno)"
        return f"tu alias es: {vigente}\npara cambiarlo: {PREFIJO}alias TuNombre"

    nuevo = " ".join(nuevo.split())[:20]
    if len(nuevo) < 2:
        return "el alias tiene que tener al menos 2 caracteres."
    if not all(c.isalnum() or c in " _-." for c in nuevo):
        return "el alias solo puede tener letras, numeros, espacios, guiones y puntos."

    asegurar_usuario(ctx.numero, ctx.nombre)
    ocupado = db.uno("SELECT numero FROM usuarios WHERE alias = ? AND numero != ?",
                     (nuevo, ctx.numero))
    if ocupado:
        return f"ya hay alguien usando el alias '{nuevo}'. elegi otro."

    db.ejecutar("UPDATE usuarios SET alias = ? WHERE numero = ?", (nuevo, ctx.numero))
    return f"listo, ahora aparecés como *{nuevo}* en la tabla."
