"""Automatizacion: abre rondas, las cierra y avisa al grupo.

Corre en un hilo aparte del servidor HTTP. Cada `INTERVALO_SEG` revisa si hay algo
que hacer. El estado real vive en la base, no en memoria, asi que reiniciar el
proceso no pierde nada ni duplica anuncios.
"""

from __future__ import annotations

import threading
import time

from . import db, format as fmt, ranking
from .config import config
from .rounds import Ronda, cerrar_vencidas, crear_ronda, ronda_actual, toca_ronda_nueva
from .scoring import base_de

#: cada cuanto revisa el reloj. un minuto alcanza de sobra para una liga de 3 dias.
INTERVALO_SEG = 60

_detener = threading.Event()


def encolar(destino: str, texto: str, sticker: str = "") -> None:
    """Deja un mensaje para que el gateway de WhatsApp lo despache.

    Se usa una cola en la base en vez de llamar al bot directo para que un corte
    de conexion de WhatsApp no pierda el anuncio de una ronda.
    """
    if not destino:
        return
    db.ejecutar(
        "INSERT INTO salientes (destino, texto, sticker, creado_en) VALUES (?, ?, ?, ?)",
        (destino, texto, sticker, db.iso()),
    )


def pendientes(limite: int = 20) -> list[dict]:
    return [dict(f) for f in db.consultar(
        "SELECT id, destino, texto, sticker FROM salientes "
        "WHERE enviado_en IS NULL AND intentos < 5 ORDER BY id LIMIT ?",
        (limite,),
    )]


def marcar_enviado(mensaje_id: int) -> None:
    db.ejecutar("UPDATE salientes SET enviado_en = ? WHERE id = ?", (db.iso(), mensaje_id))


def marcar_fallo(mensaje_id: int, error: str) -> None:
    db.ejecutar("UPDATE salientes SET intentos = intentos + 1, error = ? WHERE id = ?",
                (str(error)[:500], mensaje_id))


# --- anuncios ------------------------------------------------------------------

def anunciar_ronda(ronda: Ronda) -> None:
    """Publica la ronda nueva en el grupo."""
    lineas = [
        fmt.titulo(f"ronda {ronda.numero}"),
        "",
        f"{len(ronda.problemas)} problemas nuevos.",
        f"tienen hasta el {fmt.fecha_local(ronda.fin)} "
        f"({int(config.rondas.ventana_horas)} horas).",
        "",
    ]

    for pr in ronda.problemas:
        problema = pr.problema
        titulo_p = problema.titulo if problema else pr.slug
        lineas.append(fmt.problema_corto(pr.codigo, titulo_p, pr.dificultad, base_de(pr.dificultad)))
        if problema and problema.tags:
            lineas.append(f"   temas: {', '.join(problema.tags[:3])}")
        lineas.append("")

    lineas += [
        fmt.LINEA,
        "",
        "*como participar*",
        f"  !problema {ronda.problemas[0].codigo}   ver el enunciado",
        "  !probar <codigo> <tu solucion>   correr contra los ejemplos",
        "  !entrega <codigo> <tu solucion>  entregar (por privado)",
        "",
        "resolver temprano vale mas puntos. suerte.",
        "",
        f"enunciados y tabla: {config.web_url}",
    ]

    encolar(config.grupo_jid, "\n".join(lineas), sticker="jump")


def anunciar_cierre(ronda: Ronda) -> None:
    """Resumen al cerrar: quien resolvio que y como quedo la tabla."""
    tabla = ranking.por_ronda(ronda.numero, limite=10)

    lineas = [fmt.titulo(f"cerro la ronda {ronda.numero}"), ""]

    if tabla:
        lineas += [fmt.tabla_ranking(tabla, hasta=10), ""]
    else:
        lineas += ["esta vez no entrego nadie.", ""]

    for pr in ronda.problemas:
        stats = ranking.estadisticas_problema(pr.codigo)
        problema = pr.problema
        titulo_p = problema.titulo if problema else pr.slug
        lineas.append(f"*{pr.codigo}* {titulo_p}: "
                      f"{stats['resolvieron']}/{stats['intentaron']} lo resolvieron")

    lineas += [
        "",
        "ya podes ver las editoriales: !editorial <codigo>",
        "tabla acumulada: !rank global",
        f"historico completo: {config.web_url}",
    ]

    encolar(config.grupo_jid, "\n".join(lineas), sticker="idle")


def aviso_de_cierre(ronda: Ronda) -> None:
    """Recordatorio cuando quedan pocas horas."""
    sin_resolver = db.consultar(
        "SELECT COUNT(DISTINCT r.usuario) AS n FROM resultados r "
        "JOIN problemas_ronda p ON p.id = r.problema_ronda_id WHERE p.ronda_id = ?",
        (ronda.id,),
    )
    participaron = int(sin_resolver[0]["n"]) if sin_resolver else 0

    encolar(config.grupo_jid, "\n".join([
        f"*quedan {int(ronda.horas_restantes)} horas de la ronda {ronda.numero}*",
        "",
        f"participaron {participaron} hasta ahora.",
        "el puntaje baja a medida que pasa el tiempo, pero entregar tarde "
        "sigue sumando bastante mas que no entregar.",
        "",
        "problemas abiertos: " + ", ".join(p.codigo for p in ronda.problemas),
    ]))


# --- ciclo ---------------------------------------------------------------------

def _ya_avisado(clave: str) -> bool:
    """Evita anuncios duplicados usando la propia auditoria como registro."""
    return db.uno("SELECT 1 FROM auditoria WHERE evento = 'aviso' AND detalle = ?",
                  (clave,)) is not None


def _marcar_avisado(clave: str) -> None:
    db.auditar("aviso", detalle=clave)


def tic() -> None:
    """Una pasada del scheduler. Es idempotente: se puede llamar cuantas veces sea."""
    for cerrada in cerrar_vencidas():
        anunciar_cierre(cerrada)

    ronda = ronda_actual()

    # recordatorio a las 12 horas del cierre
    if ronda and 0 < ronda.horas_restantes <= 12:
        clave = f"cierre-{ronda.numero}"
        if not _ya_avisado(clave):
            aviso_de_cierre(ronda)
            _marcar_avisado(clave)

    if ronda is None and toca_ronda_nueva():
        # sin grupo configurado el anuncio no sale, y la ronda quemaria sus 72 horas
        # sin que nadie se entere. Es preferible no abrirla y avisar en la auditoria.
        if not config.grupo_jid:
            if not _ya_avisado("sin-grupo"):
                db.auditar("ronda_postergada",
                           detalle="GRUPO_JID esta vacio: no se abre ninguna ronda hasta "
                                   "configurarlo, si no nadie se enteraria de que existe")
                _marcar_avisado("sin-grupo")
            return

        try:
            nueva = crear_ronda(publicar_ya=True)
        except RuntimeError as e:
            db.auditar("ronda_fallida", detalle=str(e))
            if config.grupo_jid and not _ya_avisado("banco-vacio"):
                encolar(config.grupo_jid,
                        "no pude publicar la ronda: el banco de problemas esta vacio o roto. "
                        "avisenle a un admin.")
                _marcar_avisado("banco-vacio")
            return
        anunciar_ronda(nueva)


def _bucle() -> None:
    while not _detener.wait(INTERVALO_SEG):
        try:
            tic()
        except Exception as e:  # noqa: BLE001 - el scheduler nunca debe morirse
            db.auditar("scheduler_error", detalle=f"{type(e).__name__}: {e}")


def iniciar() -> threading.Thread:
    """Arranca el scheduler en segundo plano."""
    _detener.clear()
    hilo = threading.Thread(target=_bucle, name="scheduler", daemon=True)
    hilo.start()
    return hilo


def detener() -> None:
    _detener.set()
