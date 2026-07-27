"""Consulta de enunciados: !problema, !problemas, !pista, !editorial."""

from __future__ import annotations

from .. import ai, format as fmt, ranking, wa
from ..config import config
from ..problems import Problema
from ..rounds import buscar_problema, ronda_actual
from ..scoring import base_de
from . import PREFIJO, Contexto, comando


def _enunciado_completo(codigo: str, problema: Problema, dificultad: int, cerrada: bool) -> str:
    lineas = [
        f"*{codigo}* · {problema.titulo}",
        f"{fmt.dificultad(dificultad)} · {base_de(dificultad)} pts",
        f"⏱️ {problema.tiempo_ms} ms · 💾 {problema.memoria_mb} MB",
    ]
    if problema.tags:
        lineas.append(f"🏷️ {', '.join(problema.tags)}")
    # el enunciado esta en markdown (asi se ve bien en la web y en GitHub);
    # WhatsApp no lo entiende, hay que traducirlo
    lineas += ["", fmt.LINEA, "", fmt.enunciado(problema.enunciado)]

    samples = problema.samples[:2]
    if samples:
        lineas += ["", fmt.LINEA, "", "*EJEMPLOS*"]
        for i, caso in enumerate(samples, start=1):
            entrada = caso.leer_entrada().strip()
            salida = caso.leer_esperado().strip()
            lineas += [f"\n_entrada {i}_", f"```{entrada[:300]}```",
                       f"_salida {i}_", f"```{salida[:300]}```"]

    if problema.tiene_subtareas:
        lineas += ["", "*SUBTAREAS*"]
        for s in problema.subtareas:
            # la descripcion suele traer los limites ("N <= 1000000"), asi que
            # tambien hay que evitar que WhatsApp los tome por telefonos
            descripcion = wa.proteger_numeros(str(s.get("descripcion", "")))
            lineas.append(f"  • *{s['id']}* ({s.get('peso', 0)}%) {descripcion}")
        lineas.append("_cada una suma su parte solo si pasan todos sus casos_")

    atribucion = problema.fuente.atribucion()
    if atribucion:
        lineas += ["", f"_{atribucion}_"]

    if cerrada:
        lineas += ["", "_esta ronda ya cerro: podes practicarlo, pero no suma puntos_"]
    else:
        lineas += [
            "", fmt.LINEA, "",
            f"📤 entregar   {PREFIJO}entrega {codigo}",
            f"🧪 probar     {PREFIJO}probar {codigo}",
            f"💡 pista      {PREFIJO}pista {codigo}",
            "",
            f"_tambien en_ {config.web_url}",
        ]

    return fmt.recortar("\n".join(lineas), 3500)


@comando("problema", "p", "enunciado", uso="!problema <codigo>",
         ayuda="Muestra el enunciado completo de un problema.", categoria="Problemas")
def cmd_problema(ctx: Contexto) -> str:
    codigo = ctx.arg(0).upper()
    if not codigo:
        ronda = ronda_actual()
        if not ronda:
            return f"deci que problema queres ver, por ejemplo: {PREFIJO}problema R1-A"
        disponibles = ", ".join(p.codigo for p in ronda.problemas)
        return f"deci cual: {disponibles}\nasi: {PREFIJO}problema {ronda.problemas[0].codigo}"

    ubicacion = buscar_problema(codigo)
    if not ubicacion:
        return f"no encuentro el problema {codigo}. mira los abiertos con {PREFIJO}problemas."

    ronda, pr = ubicacion
    problema = pr.problema
    if problema is None:
        return "ese problema no se pudo cargar. avisale a un admin."

    return _enunciado_completo(pr.codigo, problema, pr.dificultad, cerrada=not ronda.abierta)


@comando("problemas", "ps", "lista", uso="!problemas [ronda]",
         ayuda="Lista los problemas de la ronda.", categoria="Problemas")
def cmd_problemas(ctx: Contexto) -> str:
    from ..rounds import ronda_por_numero

    arg = ctx.arg(0)
    ronda = ronda_por_numero(int(arg)) if arg.isdigit() else ronda_actual()

    if not ronda:
        return ("no hay ninguna ronda abierta.\n"
                f"mira una anterior con {PREFIJO}problemas <numero de ronda>")

    estado = (f"cierra en {fmt.duracion(ronda.horas_restantes * 3600)}"
              if ronda.abierta else "cerrada")
    lineas = [fmt.titulo(f"ronda {ronda.numero}"), estado, ""]

    for pr in ronda.problemas:
        problema = pr.problema
        titulo_p = problema.titulo if problema else pr.slug
        lineas.append(fmt.problema_corto(pr.codigo, titulo_p, pr.dificultad, base_de(pr.dificultad)))

        stats = ranking.estadisticas_problema(pr.codigo)
        if stats["intentaron"]:
            lineas.append(f"   resuelto por {stats['resolvieron']} de {stats['intentaron']}")
        lineas.append("")

    lineas.append(f"enunciado: {PREFIJO}problema {ronda.problemas[0].codigo}")
    return "\n".join(lineas)


@comando("pista", "hint", uso="!pista <codigo> [1-3]",
         ayuda="Una pista para encarar un problema, sin la solucion.",
         categoria="Problemas", solo_privado=True)
def cmd_pista(ctx: Contexto) -> str:
    codigo = ctx.arg(0).upper()
    if not codigo:
        return f"deci de que problema: {PREFIJO}pista R1-A"

    nivel = int(ctx.arg(1)) if ctx.arg(1).isdigit() else 1
    nivel = max(1, min(3, nivel))

    ubicacion = buscar_problema(codigo)
    if not ubicacion:
        return f"no encuentro el problema {codigo}."
    _, pr = ubicacion

    problema = pr.problema
    if problema is None:
        return "ese problema no se pudo cargar."

    if not problema.pistas and not ai.disponible():
        return "no hay pistas cargadas para este problema y la IA no esta configurada."

    try:
        respuesta = ai.dar_pista(problema=problema, nivel=nivel)
    except ai.ErrorIA as e:
        return f"no pude generar la pista: {e}"

    return "\n".join([
        f"*pista {nivel}/3 - {pr.codigo}*",
        "",
        respuesta.texto,
        "",
        f"_si necesitas mas, pedi {PREFIJO}pista {pr.codigo} {min(3, nivel + 1)}_",
    ])


@comando("editorial", "solucion-oficial", uso="!editorial <codigo>",
         ayuda="La explicacion oficial. Solo cuando la ronda cerro.",
         categoria="Problemas")
def cmd_editorial(ctx: Contexto) -> str:
    codigo = ctx.arg(0).upper()
    if not codigo:
        return f"deci de que problema: {PREFIJO}editorial R1-A"

    ubicacion = buscar_problema(codigo)
    if not ubicacion:
        return f"no encuentro el problema {codigo}."
    ronda, pr = ubicacion

    if ronda.abierta and not ctx.es_admin:
        return (f"la ronda {ronda.numero} sigue abierta, la editorial sale cuando cierre "
                f"(en {fmt.duracion(ronda.horas_restantes * 3600)}).\n"
                f"mientras tanto podes pedir {PREFIJO}pista {pr.codigo}")

    problema = pr.problema
    if problema is None:
        return "ese problema no se pudo cargar."
    if not problema.editorial:
        return f"{pr.codigo} no tiene editorial escrita. si querés escribirla, mandá un PR."

    return fmt.recortar("\n".join([
        f"*editorial de {pr.codigo}*  {problema.titulo}",
        fmt.LINEA,
        "",
        problema.editorial,
    ]), 3000)
