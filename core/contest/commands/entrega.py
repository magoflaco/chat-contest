"""!entrega y !probar: el camino por el que se manda codigo."""

from __future__ import annotations

from .. import format as fmt
from ..config import config
from ..rounds import ronda_actual
from ..submissions import Rechazo, entregar, probar
from . import PREFIJO, Contexto, Respuesta, comando

#: como identificamos el problema al que responde una entrega
_AYUDA_CODIGO = (
    f"tenes que decir a que problema estas respondiendo.\n\n"
    f"*asi:*\n"
    f"```{PREFIJO}entrega R1-A\n"
    f"n = int(input())\n"
    f"print(n * 2)```\n\n"
    f"o mandando un archivo .py con el codigo del problema en el epigrafe:\n"
    f"```{PREFIJO}entrega R1-A```\n\n"
    f"los codigos de la ronda salen con {PREFIJO}problemas"
)


def _partir(ctx: Contexto) -> tuple[str, str] | str:
    """Separa el codigo del problema del codigo fuente. Devuelve un str si hay error."""
    args = ctx.args

    # caso 1: vino un archivo adjunto. el codigo del problema esta en el epigrafe.
    if ctx.adjunto_texto:
        codigo = args.split()[0].strip().upper() if args.split() else ""
        if not codigo:
            return ("mandaste el archivo pero no dijiste de que problema es.\n"
                    f"poné el codigo en el epigrafe, asi: {PREFIJO}entrega R1-A")
        return codigo, ctx.adjunto_texto

    # caso 2: el codigo viene pegado en el mensaje, despues del codigo del problema
    if not args.strip():
        return _AYUDA_CODIGO

    primera, _, resto = args.partition("\n")
    partes = primera.split(None, 1)
    if not partes:
        return _AYUDA_CODIGO

    codigo = partes[0].strip().upper()
    en_linea = partes[1] if len(partes) > 1 else ""
    fuente = f"{en_linea}\n{resto}" if en_linea and resto else (en_linea or resto)

    if not fuente.strip():
        return ("me diste el codigo del problema pero no el codigo Python.\n\n"
                f"pegalo en el mismo mensaje, despues de {codigo}, o mandame un archivo .py.")

    return codigo, fuente


@comando("entrega", "enviar", "submit", "solucion", "sub",
         uso="!entrega <codigo> <tu codigo python>",
         ayuda="Manda tu solucion a un problema.", categoria="Competencia",
         solo_privado=True)
def cmd_entrega(ctx: Contexto) -> Respuesta | str:
    partido = _partir(ctx)
    if isinstance(partido, str):
        return partido
    codigo_problema, fuente = partido

    resultado = entregar(
        numero=ctx.numero,
        nombre=ctx.nombre,
        codigo_problema=codigo_problema,
        fuente=fuente,
        origen="archivo" if ctx.adjunto_texto else "texto",
    )

    if isinstance(resultado, Rechazo):
        return resultado.motivo

    lineas = [f"*{resultado.codigo}*  {fmt.veredicto(resultado.veredicto)}"]

    if resultado.aceptado:
        lineas.append("")
        if resultado.mejoro:
            lineas.append(f"*+{resultado.puntos} puntos*")
            if resultado.desglose:
                lineas.append(f"```{resultado.desglose.explicar()}```")
        else:
            lineas.append(f"ya lo tenias resuelto con {resultado.puntos_previos} puntos, "
                          "asi que el puntaje no cambia.")

        from .. import ranking
        fila = ranking.posicion_de(ctx.numero)
        if fila:
            lineas.append(f"\nvas {fila.puesto}o con {fila.puntos} puntos.")

    else:
        if resultado.caso_fallido:
            lineas.append(f"fallo en el caso {resultado.caso_fallido}.")
        if resultado.detalle:
            lineas.append(f"```{fmt.recortar(resultado.detalle, 400)}```")
        if resultado.tiempo_ms:
            lineas.append(f"tardo {resultado.tiempo_ms} ms.")

        if resultado.puntos:
            lineas.append(f"\npuntaje parcial por subtareas: *{resultado.puntos} puntos*")

        siguiente = resultado.intentos_fallidos + 1
        factor = max(0.40, 1 - 0.15 * siguiente)
        lineas += [
            "",
            f"llevas {siguiente} intento(s) fallido(s): el proximo AC vale x{factor:.2f}.",
            f"para entender que paso: {PREFIJO}revisar {resultado.codigo}",
        ]

    if resultado.sospechosa:
        lineas += ["", "_esta entrega quedo marcada para revision manual._"]

    return Respuesta("\n".join(lineas))


@comando("probar", "test", "sample", uso="!probar <codigo> <tu codigo python>",
         ayuda="Corre tu codigo solo contra los ejemplos. No suma ni gasta intentos.",
         categoria="Competencia", solo_privado=True)
def cmd_probar(ctx: Contexto) -> str:
    partido = _partir(ctx)
    if isinstance(partido, str):
        return partido.replace(f"{PREFIJO}entrega", f"{PREFIJO}probar")
    codigo_problema, fuente = partido

    resultado = probar(numero=ctx.numero, nombre=ctx.nombre,
                       codigo_problema=codigo_problema, fuente=fuente)

    if isinstance(resultado, Rechazo):
        return resultado.motivo

    lineas = [f"*prueba de {codigo_problema.upper()}* (no cuenta para el puntaje)", ""]

    if resultado.aceptado:
        lineas.append("pasa todos los ejemplos.")
        lineas.append(f"\nsi estas conforme, mandalo con {PREFIJO}entrega {codigo_problema.upper()}")
        lineas.append("_ojo: los casos secretos son mas grandes y mas rebuscados._")
    else:
        lineas.append(fmt.veredicto(resultado.veredicto))
        if resultado.detalle:
            lineas.append(f"```{fmt.recortar(resultado.detalle, 400)}```")
        if resultado.caso_fallido:
            lineas.append(f"fallo en el ejemplo {resultado.caso_fallido}.")

    return "\n".join(lineas)


@comando("ronda", uso="!ronda", ayuda="Que problemas hay abiertos y cuanto falta.",
         categoria="Competencia")
def cmd_ronda(ctx: Contexto) -> str:
    from .. import ranking
    from ..scoring import base_de

    ronda = ronda_actual()
    if not ronda:
        return "no hay ninguna ronda abierta. la proxima sale pronto."

    lineas = [
        fmt.titulo(f"ronda {ronda.numero}"),
        f"cierra en {fmt.duracion(ronda.horas_restantes * 3600)}  ({fmt.fecha_local(ronda.fin)})",
        "",
    ]

    for pr in ronda.problemas:
        problema = pr.problema
        titulo_p = problema.titulo if problema else pr.slug
        stats = ranking.estadisticas_problema(pr.codigo)
        lineas.append(fmt.problema_corto(pr.codigo, titulo_p, pr.dificultad, base_de(pr.dificultad)))
        if stats["intentaron"]:
            lineas.append(f"   {stats['resolvieron']}/{stats['intentaron']} lo resolvieron")
        lineas.append("")

    lineas.append(f"enunciado completo: {PREFIJO}problema <codigo>")
    return "\n".join(lineas)
