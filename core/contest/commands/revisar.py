"""!revisar: explica con IA por que una entrega recibio el veredicto que recibio."""

from __future__ import annotations

from pathlib import Path

from .. import ai, db, format as fmt
from ..rounds import buscar_problema
from ..submissions import entrega_por_id, ultima_entrega
from . import PREFIJO, Contexto, comando


@comando("revisar", "review", "porque", "explicar", uso="!revisar <codigo|#id>",
         ayuda="Te explica por que fallo tu entrega, sin darte la solucion.",
         categoria="Competencia", solo_privado=True)
def cmd_revisar(ctx: Contexto) -> str:
    arg = ctx.arg(0).strip()

    # Pegar el codigo aca es lo primero que hace todo el mundo, porque !entrega y
    # !probar funcionan asi. Pero !revisar mira una entrega ya juzgada, no texto
    # suelto: sin este aviso revisa la entrega vieja y contesta algo que no tiene
    # nada que ver con lo que la persona esta mirando en la pantalla.
    if "\n" in ctx.args.strip():
        codigo = arg.upper() if arg else "<codigo>"
        return "\n".join([
            "!revisar mira tu ultima entrega, no el codigo que pegues aca.",
            "",
            f"si querés que revise lo que acabas de escribir, mandalo con "
            f"{PREFIJO}entrega {codigo} y despues {PREFIJO}revisar {codigo}.",
            f"si querés probarlo sin gastar un intento: {PREFIJO}probar {codigo}",
        ])

    if not arg:
        entrega = ultima_entrega(ctx.numero)
        if not entrega:
            return ("todavia no mandaste ninguna entrega.\n"
                    f"proba con {PREFIJO}revisar R1-A cuando tengas una.")
    elif arg.startswith("#") or arg.isdigit():
        entrega = entrega_por_id(int(arg.lstrip("#")))
        if not entrega:
            return f"no existe la entrega {arg}."
        if entrega["usuario"] != ctx.numero and not ctx.es_admin:
            return "esa entrega no es tuya."
    else:
        entrega = ultima_entrega(ctx.numero, arg.upper())
        if not entrega:
            ubicacion = buscar_problema(arg)
            if not ubicacion:
                return f"no encuentro el problema {arg.upper()}."
            return (f"no mandaste ninguna entrega para {arg.upper()} todavia.\n"
                    f"mira el enunciado con {PREFIJO}problema {arg.upper()}")

    ubicacion = buscar_problema(entrega["codigo"])
    if not ubicacion:
        return "no pude ubicar el problema de esa entrega."
    _, pr = ubicacion
    problema = pr.problema
    if problema is None:
        return "ese problema no se pudo cargar."

    if entrega["veredicto"] == "AC":
        return "\n".join([
            f"*{entrega['codigo']}* ya esta aceptada, no hay nada que revisar.",
            "",
            f"```{entrega['desglose'] or 'sin desglose'}```",
            "",
            f"si querés ver como la resolvieron oficialmente: {PREFIJO}editorial {entrega['codigo']}",
        ])

    if entrega["veredicto"] == "SEC":
        return "\n".join([
            f"*{entrega['codigo']}* fue bloqueada antes de ejecutarse.",
            "",
            entrega["detalle"] or "el codigo intentaba hacer algo que no esta permitido.",
            "",
            "las soluciones leen de la entrada estandar con input() y escriben con print().",
            "no hace falta abrir archivos, usar la red ni lanzar procesos.",
        ])

    fuente = _leer_fuente(entrega["fuente_path"])
    if not fuente:
        return "no pude recuperar el codigo de esa entrega."

    if not ai.disponible():
        return "\n".join([
            f"*{entrega['codigo']}*  {fmt.veredicto(entrega['veredicto'])}",
            entrega["detalle"] or "",
            "",
            "_la explicacion con IA no esta configurada (falta NVIDIA_API_KEY)._",
        ])

    try:
        respuesta = ai.explicar_entrega(
            problema=problema,
            fuente=fuente,
            veredicto=entrega["veredicto"],
            detalle=entrega["detalle"],
            caso_fallido=entrega["caso_fallido"],
        )
    except ai.ErrorIA as e:
        db.auditar("ia_error", usuario=ctx.numero, detalle=str(e))
        return (f"no pude generar la explicacion: {e}\n"
                f"tu veredicto fue {entrega['veredicto']}: {entrega['detalle'] or 'sin detalle'}")

    db.auditar("revision", usuario=ctx.numero, detalle=f"entrega {entrega['id']}")

    return "\n".join([
        f"*revision de {entrega['codigo']}*  ({entrega['veredicto']})",
        fmt.LINEA,
        "",
        respuesta.texto,
        "",
        f"_generado por IA, puede equivocarse. entrega #{entrega['id']}_",
    ])


def _leer_fuente(ruta: str) -> str:
    try:
        return Path(ruta).read_text(encoding="utf-8", errors="replace")[:20000]
    except OSError:
        return ""
