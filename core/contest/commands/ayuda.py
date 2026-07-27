"""!help y comandos informativos generales."""

from __future__ import annotations

from .. import db, format as fmt
from ..config import config
from ..rounds import ronda_actual
from ..scoring import BASE_POR_DIFICULTAD, NOMBRE_DIFICULTAD
from . import COMANDOS, PREFIJO, REGISTRO, Contexto, Respuesta, comando


@comando("help", "ayuda", "comandos", uso="!help [comando]",
         ayuda="Muestra los comandos disponibles, o el detalle de uno.",
         categoria="General")
def cmd_help(ctx: Contexto) -> str:
    pedido = ctx.arg(0).lstrip(PREFIJO).lower()

    if pedido:
        cmd = REGISTRO.get(pedido)
        if not cmd:
            return f"no existe el comando {PREFIJO}{pedido}. escribi {PREFIJO}help para ver la lista."
        partes = [fmt.titulo(f"{PREFIJO}{cmd.nombre}"), cmd.ayuda or "sin descripcion.", "",
                  f"*uso:* {cmd.uso}"]
        if len(cmd.nombres) > 1:
            alias = ", ".join(f"{PREFIJO}{n}" for n in cmd.nombres[1:])
            partes.append(f"*alias:* {alias}")
        if cmd.solo_privado:
            partes.append("_solo funciona por privado_")
        if cmd.solo_admin:
            partes.append("_solo para admins_")
        return "\n".join(partes)

    por_categoria: dict[str, list] = {}
    for cmd in COMANDOS:
        if cmd.oculto or (cmd.solo_admin and not ctx.es_admin):
            continue
        por_categoria.setdefault(cmd.categoria, []).append(cmd)

    lineas = [fmt.titulo(config.bot_name)]
    orden = ["Competencia", "Problemas", "Ranking", "General", "Admin"]
    for categoria in orden + [c for c in por_categoria if c not in orden]:
        grupo = por_categoria.get(categoria)
        if not grupo:
            continue
        lineas.append(f"\n*{categoria}*")
        for cmd in grupo:
            lineas.append(f"  {PREFIJO}{cmd.nombre} - {cmd.ayuda}")

    lineas += [
        "",
        LINEA_AYUDA,
        f"detalle de un comando: {PREFIJO}help entrega",
        f"tabla y enunciados: {config.web_url}",
    ]
    # Perove saluda solo con el listado completo, no con la ayuda de un comando suelto
    return Respuesta("\n".join(lineas), sticker="wave")


LINEA_AYUDA = "_las entregas van por privado_"


@comando("reglas", "puntos", "scoring", uso="!reglas",
         ayuda="Como se calculan los puntos y como se rankea.",
         categoria="General")
def cmd_reglas(ctx: Contexto) -> str:
    from ..format import COLOR_DIFICULTAD

    tabla = "\n".join(
        f"{COLOR_DIFICULTAD[n]} {NOMBRE_DIFICULTAD[n]} · {BASE_POR_DIFICULTAD[n]} pts"
        for n in sorted(BASE_POR_DIFICULTAD)
    )
    return "\n".join([
        fmt.titulo("como se puntua"),
        "",
        "*puntos = base × tiempo × intentos*",
        "",
        "*Base segun dificultad*",
        tabla,
        "",
        "*Tiempo* ⏳",
        "de 1.00 al abrir la ronda a 0.65 al cerrar.",
        "resolver temprano vale mas, pero entregar tarde",
        "sigue sumando mucho mas que no entregar.",
        "",
        "*Intentos* 🔁",
        "-15% por cada envio rechazado, con piso en 0.40.",
        "los errores de sintaxis no penalizan.",
        "",
        "reenviar nunca te baja el puntaje:",
        "se guarda tu mejor resultado.",
        "",
        "*Desempate*",
        "mas puntos → mas resueltos → menos tiempo total.",
        "",
        f"_detalle completo en_ {config.web_url}",
    ])


@comando("info", "estado", uso="!info",
         ayuda="Estado de la ronda actual y del sistema.",
         categoria="General")
def cmd_info(ctx: Contexto) -> str:
    ronda = ronda_actual()
    lineas = [fmt.titulo("estado")]

    if ronda:
        lineas += [
            f"📅 ronda *{ronda.numero}* abierta",
            f"⏳ cierra en {fmt.duracion(ronda.horas_restantes * 3600)}"
            f"  ({fmt.fecha_local(ronda.fin)})",
            f"📝 {', '.join(p.codigo for p in ronda.problemas)}",
        ]
    else:
        lineas.append("no hay ninguna ronda abierta ahora mismo.")

    stats = db.uno(
        "SELECT (SELECT COUNT(DISTINCT usuario) FROM entregas) AS gente, "
        "(SELECT COUNT(*) FROM entregas) AS entregas, "
        "(SELECT COUNT(*) FROM entregas WHERE veredicto = 'AC') AS ac"
    )
    if stats:
        lineas += ["", f"👥 {stats['gente']} participantes",
                   f"📤 {stats['entregas']} entregas · ✅ {stats['ac']} aceptadas"]

    lineas += ["", f"🏆 {config.web_url}", f"_escribi_ {PREFIJO}help _para ver que podes hacer_"]
    return "\n".join(lineas)


@comando("jid", uso="!jid", ayuda="Muestra el identificador de este chat.",
         categoria="General", oculto=True)
def cmd_jid(ctx: Contexto) -> str:
    """Sirve para configurar GRUPO_JID en el .env sin tener que adivinarlo."""
    return f"```{ctx.jid}```\ncopialo a GRUPO_JID en el .env si este es el grupo del club."


@comando("miid", "quiensoy", uso="!miid",
         ayuda="Muestra como te identifica WhatsApp (util para configurar admins).",
         categoria="General", oculto=True)
def cmd_miid(ctx: Contexto) -> str:
    """Sirve para configurar ADMINS sin adivinar.

    WhatsApp esta migrando de numeros de telefono a LIDs, y segun el chat una
    persona puede llegar identificada de una forma o de la otra. Si un admin no
    es reconocido, con esto se ve exactamente que poner en el .env.
    """
    from .. import identidades

    alias = identidades.alias_de(ctx.numero)
    lineas = [
        fmt.titulo("tu identidad"),
        f"principal: `{ctx.numero}`",
    ]
    if alias:
        otros = [a for a in alias if a != ctx.numero]
        if otros:
            lineas.append("tambien conocido como: " + ", ".join(f"`{a}`" for a in otros))
    lineas += [
        "",
        f"admin: {'si' if ctx.es_admin else 'no'}",
        "",
        "_para que alguien sea admin, su identidad principal tiene que estar_",
        "_en ADMINS del .env, separada por comas_",
    ]
    return "\n".join(lineas)
