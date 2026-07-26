"""Comandos de administracion. Solo para los numeros listados en ADMINS."""

from __future__ import annotations

from .. import db, format as fmt, judge, problems
from ..config import config
from ..rounds import cerrar_vencidas, crear_ronda, ronda_actual
from . import PREFIJO, Contexto, comando


@comando("nuevaronda", uso="!nuevaronda [dificultades]",
         ayuda="Publica una ronda nueva ahora mismo.", categoria="Admin", solo_admin=True)
def cmd_nuevaronda(ctx: Contexto) -> str:
    dificultades = None
    if ctx.args.strip():
        try:
            dificultades = tuple(int(x) for x in ctx.args.replace(",", " ").split())
        except ValueError:
            return "las dificultades son numeros del 1 al 5, por ejemplo: !nuevaronda 1 3 5"

    try:
        ronda = crear_ronda(publicar_ya=True, dificultades=dificultades)
    except RuntimeError as e:
        return f"no se pudo crear la ronda: {e}"

    from ..scheduler import anunciar_ronda
    anunciar_ronda(ronda)

    return (f"ronda {ronda.numero} publicada con {len(ronda.problemas)} problemas: "
            + ", ".join(p.codigo for p in ronda.problemas))


@comando("cerrarronda", uso="!cerrarronda",
         ayuda="Cierra la ronda abierta antes de tiempo.", categoria="Admin", solo_admin=True)
def cmd_cerrarronda(ctx: Contexto) -> str:
    ronda = ronda_actual()
    if not ronda:
        return "no hay ninguna ronda abierta."
    db.ejecutar("UPDATE rondas SET estado = 'cerrada' WHERE id = ?", (ronda.id,))
    db.auditar("ronda_cerrada_manual", usuario=ctx.numero, detalle=f"ronda {ronda.numero}")
    return f"ronda {ronda.numero} cerrada."


@comando("sospechas", "revisiones", uso="!sospechas",
         ayuda="Entregas marcadas para revision manual.", categoria="Admin", solo_admin=True)
def cmd_sospechas(ctx: Contexto) -> str:
    filas = db.consultar(
        "SELECT e.id, e.usuario, e.motivo_sospecha, e.veredicto, e.anulada, p.codigo "
        "FROM entregas e JOIN problemas_ronda p ON p.id = e.problema_ronda_id "
        "WHERE e.sospechosa = 1 ORDER BY e.id DESC LIMIT 20"
    )
    if not filas:
        return "no hay nada marcado."

    lineas = [fmt.titulo("para revisar")]
    for f in filas:
        estado = " [ANULADA]" if f["anulada"] else ""
        lineas.append(f"#{f['id']} {f['codigo']} {f['veredicto']} - ...{f['usuario'][-4:]}{estado}")
        lineas.append(f"   {f['motivo_sospecha'] or 'sin motivo'}")

    lineas += ["", f"para anular una: {PREFIJO}anular <id> <motivo>"]
    return "\n".join(lineas)


@comando("anular", uso="!anular <id> <motivo>",
         ayuda="Anula una entrega y recalcula el ranking.", categoria="Admin", solo_admin=True)
def cmd_anular(ctx: Contexto) -> str:
    if not ctx.arg(0).lstrip("#").isdigit():
        return f"uso: {PREFIJO}anular <id de entrega> <motivo>"

    entrega_id = int(ctx.arg(0).lstrip("#"))
    motivo = ctx.args.partition(" ")[2].strip() or "sin motivo registrado"

    fila = db.uno("SELECT usuario, problema_ronda_id FROM entregas WHERE id = ?", (entrega_id,))
    if not fila:
        return f"no existe la entrega #{entrega_id}."

    db.ejecutar("UPDATE entregas SET anulada = 1, motivo_sospecha = ? WHERE id = ?",
                (f"anulada por admin: {motivo}", entrega_id))
    db.auditar("entrega_anulada", usuario=ctx.numero, detalle=f"#{entrega_id}: {motivo}")

    recalcular_resultados(fila["usuario"], fila["problema_ronda_id"])
    return f"entrega #{entrega_id} anulada y ranking recalculado."


@comando("suspender", uso="!suspender <numero> <motivo>",
         ayuda="Suspende a un participante.", categoria="Admin", solo_admin=True)
def cmd_suspender(ctx: Contexto) -> str:
    numero = "".join(c for c in ctx.arg(0) if c.isdigit())
    if not numero:
        return f"uso: {PREFIJO}suspender <numero> <motivo>"

    motivo = ctx.args.partition(" ")[2].strip() or "sin motivo"
    cur = db.ejecutar("UPDATE usuarios SET bloqueado = 1, nota_admin = ? WHERE numero = ?",
                      (motivo, numero))
    if cur.rowcount == 0:
        return f"no encuentro al usuario {numero}."

    db.auditar("usuario_suspendido", usuario=ctx.numero, detalle=f"{numero}: {motivo}")
    return f"{numero} suspendido. sale del ranking hasta que lo reactives con {PREFIJO}reactivar."


@comando("reactivar", uso="!reactivar <numero>",
         ayuda="Levanta la suspension de un participante.", categoria="Admin", solo_admin=True)
def cmd_reactivar(ctx: Contexto) -> str:
    numero = "".join(c for c in ctx.arg(0) if c.isdigit())
    if not numero:
        return f"uso: {PREFIJO}reactivar <numero>"

    cur = db.ejecutar("UPDATE usuarios SET bloqueado = 0, nota_admin = '' WHERE numero = ?", (numero,))
    if cur.rowcount == 0:
        return f"no encuentro al usuario {numero}."

    db.auditar("usuario_reactivado", usuario=ctx.numero, detalle=numero)
    return f"{numero} reactivado."


@comando("banco", uso="!banco", ayuda="Estado del banco de problemas.",
         categoria="Admin", solo_admin=True)
def cmd_banco(ctx: Contexto) -> str:
    disponibles = problems.banco(refrescar=True)
    errores = problems.validar_todos()

    por_dificultad: dict[int, int] = {}
    for p in disponibles.values():
        por_dificultad[p.dificultad] = por_dificultad.get(p.dificultad, 0) + 1

    usados = {f["slug"] for f in db.consultar("SELECT DISTINCT slug FROM problemas_ronda")}

    lineas = [fmt.titulo("banco de problemas"),
              f"{len(disponibles)} validos, {len(usados)} ya usados", ""]
    for d in sorted(por_dificultad):
        sin_usar = sum(1 for p in disponibles.values()
                       if p.dificultad == d and p.slug not in usados)
        lineas.append(f"  dificultad {d}: {por_dificultad[d]} ({sin_usar} sin usar)")

    if errores:
        lineas += ["", f"*{len(errores)} con problemas:*"]
        lineas += [f"  {e}" for e in errores[:6]]

    return "\n".join(lineas)


@comando("juez", uso="!juez", ayuda="Estado del sandbox del juez.",
         categoria="Admin", solo_admin=True)
def cmd_juez(ctx: Contexto) -> str:
    backend = config.juez.backend
    lineas = [fmt.titulo("juez"), f"backend: {backend}"]

    if backend == "docker":
        ok = judge.imagen_disponible()
        lineas.append(f"imagen {config.juez.imagen}: {'lista' if ok else 'NO CONSTRUIDA'}")
        if not ok:
            lineas.append(f"\ncorre: docker build -t {config.juez.imagen} judge/")
    else:
        lineas.append("\n*ATENCION*: el backend 'subprocess' no aisla nada.")
        lineas.append("solo sirve para desarrollo local. en el VPS usa docker.")

    lineas += ["", f"tiempo maximo: {config.juez.timeout_ms} ms",
               f"memoria maxima: {config.juez.memoria_mb} MB"]
    return "\n".join(lineas)


@comando("recalcular", uso="!recalcular",
         ayuda="Reconstruye toda la tabla de resultados desde las entregas.",
         categoria="Admin", solo_admin=True)
def cmd_recalcular(ctx: Contexto) -> str:
    n = recalcular_todo()
    db.auditar("recalculo_total", usuario=ctx.numero, detalle=f"{n} filas")
    return f"listo, {n} resultados recalculados."


# --- recalculo -----------------------------------------------------------------

def recalcular_resultados(usuario: str, problema_ronda_id: int) -> None:
    """Reconstruye el resultado de un usuario en un problema, ignorando lo anulado."""
    entregas = db.consultar(
        "SELECT veredicto, puntos, enviada_en, id FROM entregas "
        "WHERE usuario = ? AND problema_ronda_id = ? AND anulada = 0 ORDER BY id",
        (usuario, problema_ronda_id),
    )

    if not entregas:
        db.ejecutar("DELETE FROM resultados WHERE usuario = ? AND problema_ronda_id = ?",
                    (usuario, problema_ronda_id))
        return

    from ..scoring import cuenta_como_fallo

    inicio = db.desde_iso((db.uno(
        "SELECT r.inicio FROM rondas r JOIN problemas_ronda p ON p.ronda_id = r.id WHERE p.id = ?",
        (problema_ronda_id,),
    ) or {"inicio": None})["inicio"])

    mejor_puntos = 0
    mejor_id = None
    resuelto = 0
    fallidos = 0
    primer_ac = None

    for e in entregas:
        if e["veredicto"] == "AC" and primer_ac is None:
            primer_ac = db.desde_iso(e["enviada_en"])
            resuelto = 1
        if e["puntos"] > mejor_puntos:
            mejor_puntos, mejor_id = e["puntos"], e["id"]
        if cuenta_como_fallo(e["veredicto"]):
            fallidos += 1

    segundos = (primer_ac - inicio).total_seconds() if primer_ac and inicio else None

    db.ejecutar(
        "INSERT INTO resultados (usuario, problema_ronda_id, puntos, resuelto, intentos, "
        "intentos_fallidos, primer_ac_en, segundos_hasta_ac, entrega_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(usuario, problema_ronda_id) DO UPDATE SET "
        "puntos = excluded.puntos, resuelto = excluded.resuelto, intentos = excluded.intentos, "
        "intentos_fallidos = excluded.intentos_fallidos, primer_ac_en = excluded.primer_ac_en, "
        "segundos_hasta_ac = excluded.segundos_hasta_ac, entrega_id = excluded.entrega_id",
        (usuario, problema_ronda_id, mejor_puntos, resuelto, len(entregas), fallidos,
         db.iso(primer_ac) if primer_ac else None, segundos, mejor_id),
    )


def recalcular_todo() -> int:
    """Rehace la tabla `resultados` entera. Util despues de anular varias entregas."""
    pares = db.consultar("SELECT DISTINCT usuario, problema_ronda_id FROM entregas")
    for p in pares:
        recalcular_resultados(p["usuario"], p["problema_ronda_id"])
    return len(pares)
