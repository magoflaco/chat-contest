"""Flujo de una entrega, de punta a punta.

    texto o .py  ->  limites  ->  analisis estatico  ->  juez  ->  puntaje  ->  ranking

Cada paso puede cortar el flujo. Todo queda registrado en `entregas` y lo relevante
tambien en `auditoria`, asi una decision siempre se puede reconstruir despues.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import antifraud, db, judge, scoring
from .config import config
from .problems import Problema
from .rounds import ProblemaRonda, Ronda, buscar_problema

#: bloques ```python ... ``` que manda mucha gente al pegar codigo
_CERCA = re.compile(r"^\s*```[a-zA-Z]*\s*\n?(.*?)\n?\s*```\s*$", re.DOTALL)


@dataclass
class Rechazo:
    """La entrega ni siquiera llego al juez."""
    motivo: str


@dataclass
class Veredicto:
    """El resultado de una entrega juzgada."""
    entrega_id: int
    codigo: str
    veredicto: str
    descripcion: str
    detalle: str
    puntos: int
    puntos_previos: int
    mejoro: bool
    tiempo_ms: int
    caso_fallido: int | None
    intentos_fallidos: int
    desglose: scoring.Desglose | None
    sospechosa: bool

    @property
    def aceptado(self) -> bool:
        return self.veredicto == "AC"


#: Caracteres de ancho cero que llegan pegados al copiar de WhatsApp. El
#: primero lo ponemos nosotros: `wa.proteger_numeros` mete un WORD JOINER
#: adentro de los numeros largos para que WhatsApp no los convierta en links de
#: telefono. Es invisible, asi que quien copia `1000000007` del enunciado a su
#: codigo se lleva uno puesto sin verlo y Python le contesta
#: "invalid non-printable character U+2060", que no le dice nada a nadie.
_INVISIBLES = str.maketrans({
    "⁠": None,   # word joiner, el que ponemos nosotros
    "​": None,   # zero width space
    "‌": None,   # zero width non-joiner
    "‍": None,   # zero width joiner
    "﻿": None,   # BOM, tipico de copiar desde un editor de Windows
    " ": " ",    # espacio duro: se ve igual que un espacio y rompe la indentacion
})


def limpiar_fuente(texto: str) -> str:
    """Saca el markdown que WhatsApp o el editor del chico dejan pegado."""
    m = _CERCA.match(texto)
    if m:
        texto = m.group(1)
    texto = texto.translate(_INVISIBLES)
    return texto.replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"


def normalizar_numero(jid: str) -> str:
    """Numero pelado de un JID de WhatsApp, sin sufijo de dispositivo ni dominio."""
    return (jid or "").split("@")[0].split(":")[0]


def asegurar_usuario(numero: str, nombre: str = "") -> None:
    """Alta perezosa: alguien existe la primera vez que interactua con el bot."""
    ahora = db.iso()
    db.ejecutar(
        "INSERT INTO usuarios (numero, nombre, creado_en, visto_en) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(numero) DO UPDATE SET visto_en = excluded.visto_en, "
        "nombre = CASE WHEN excluded.nombre != '' THEN excluded.nombre ELSE usuarios.nombre END",
        (numero, nombre.strip()[:60], ahora, ahora),
    )


def entregar(*, numero: str, nombre: str, codigo_problema: str, fuente: str,
             origen: str = "texto") -> Rechazo | Veredicto:
    """Procesa una entrega completa. Es el unico punto de entrada.

    `origen` es 'archivo' o 'texto', y solo se guarda para estadistica.
    """
    asegurar_usuario(numero, nombre)

    ubicacion = buscar_problema(codigo_problema)
    if not ubicacion:
        return Rechazo(f"no existe ningun problema con codigo {codigo_problema.upper()}.")
    ronda, pr = ubicacion

    if not ronda.abierta:
        return Rechazo(
            f"la ronda {ronda.numero} ya cerro, {pr.codigo} no acepta mas entregas.\n"
            "podes practicarlo igual con !probar, pero no suma puntos."
        )

    problema = pr.problema
    if problema is None:
        db.auditar("problema_faltante", usuario=numero, detalle=pr.slug)
        return Rechazo("ese problema no se pudo cargar. avisale a un admin, es un error nuestro.")

    veto = antifraud.revisar_limites(numero, pr.id)
    if veto:
        return Rechazo(veto.motivo)

    fuente = limpiar_fuente(fuente)
    if not fuente.strip():
        return Rechazo("la entrega vino vacia.")
    if len(fuente.encode("utf-8")) > config.juez.max_fuente_bytes:
        return Rechazo(f"el codigo es demasiado largo (maximo {config.juez.max_fuente_bytes // 1024} KB).")

    codigo_hash = antifraud.hash_codigo(fuente)
    if antifraud.es_reenvio_identico(numero, pr.id, codigo_hash):
        return Rechazo("ya mandaste exactamente este codigo para este problema, no te gasto un intento.")

    ruta = _guardar_fuente(numero, pr.codigo, fuente)

    # --- analisis estatico: se corta antes de ejecutar nada ---
    hallazgos = antifraud.revisar_codigo(fuente)
    if hallazgos:
        detalle = "; ".join(f"linea {h.linea}: {h.motivo}" for h in hallazgos[:3])
        db.auditar("entrega_bloqueada", usuario=numero, detalle=f"{pr.codigo}: {detalle}")
        entrega_id = _registrar(
            numero=numero, pr=pr, codigo_hash=codigo_hash, ruta=ruta, origen=origen,
            fuente=fuente, veredicto="SEC", detalle=detalle,
        )
        return Veredicto(
            entrega_id=entrega_id, codigo=pr.codigo, veredicto="SEC",
            descripcion=judge.DESCRIPCION_VEREDICTO["SEC"],
            detalle=(f"{detalle}\n\nlas soluciones se resuelven leyendo de la entrada estandar y "
                     "escribiendo en la salida estandar. no hace falta abrir archivos ni usar la red."),
            puntos=0, puntos_previos=_puntos_actuales(numero, pr.id), mejoro=False,
            tiempo_ms=0, caso_fallido=None,
            intentos_fallidos=_intentos_fallidos(numero, pr.id),
            desglose=None, sospechosa=True,
        )

    # --- juez ---
    try:
        resultado = judge.juzgar(ruta, problema)
    except judge.ErrorJuez as e:
        db.auditar("juez_error", usuario=numero, detalle=f"{pr.codigo}: {e}")
        return Rechazo(f"el juez no pudo correr tu entrega: {e}\nno te descuenta el intento.")

    # un error interno es culpa nuestra: se registra pero no penaliza
    if resultado.veredicto == "IE":
        db.auditar("juez_error_interno", usuario=numero, detalle=f"{pr.codigo}: {resultado.detalle}")

    intentos_fallidos = _intentos_fallidos(numero, pr.id)

    desglose = None
    puntos = 0
    if resultado.aceptado:
        fraccion = 1.0
        if problema.tiene_subtareas:
            fraccion = scoring.fraccion_de_subtareas(list(problema.subtareas), set(resultado.subtareas_ok))
        desglose = scoring.calcular(
            dificultad=problema.dificultad,
            inicio_ronda=ronda.inicio,
            fin_ronda=ronda.fin,
            momento_aceptado=db.ahora(),
            intentos_fallidos=intentos_fallidos,
            fraccion_subtareas=fraccion,
        )
        puntos = desglose.puntos
    elif problema.tiene_subtareas and resultado.subtareas_ok:
        # puntaje parcial estilo IOI: lo que resolviste vale, aunque no sea todo
        fraccion = scoring.fraccion_de_subtareas(list(problema.subtareas), set(resultado.subtareas_ok))
        if fraccion > 0:
            desglose = scoring.calcular(
                dificultad=problema.dificultad,
                inicio_ronda=ronda.inicio,
                fin_ronda=ronda.fin,
                momento_aceptado=db.ahora(),
                intentos_fallidos=intentos_fallidos,
                fraccion_subtareas=fraccion,
            )
            puntos = desglose.puntos

    # --- similitud con otras entregas ---
    parecidos = antifraud.buscar_parecidos(fuente, pr.id, numero)
    sospechosa = bool(parecidos)
    motivo = ""
    if parecidos:
        otro, sim = parecidos[0]
        motivo = f"similitud {sim:.0%} con la entrega de {otro}"
        db.auditar("similitud_alta", usuario=numero, detalle=f"{pr.codigo}: {motivo}")

    entrega_id = _registrar(
        numero=numero, pr=pr, codigo_hash=codigo_hash, ruta=ruta, origen=origen, fuente=fuente,
        veredicto=resultado.veredicto, detalle=resultado.detalle,
        caso_fallido=resultado.caso_fallido, tiempo_ms=resultado.tiempo_ms,
        subtareas_ok=resultado.subtareas_ok, puntos=puntos,
        desglose=desglose.explicar() if desglose else "",
        sospechosa=sospechosa, motivo_sospecha=motivo,
    )

    previos = _puntos_actuales(numero, pr.id)
    mejoro = _actualizar_resultado(numero, pr, ronda, entrega_id, resultado.veredicto, puntos)

    return Veredicto(
        entrega_id=entrega_id, codigo=pr.codigo, veredicto=resultado.veredicto,
        descripcion=resultado.descripcion, detalle=resultado.detalle,
        puntos=puntos, puntos_previos=previos, mejoro=mejoro,
        tiempo_ms=resultado.tiempo_ms, caso_fallido=resultado.caso_fallido,
        intentos_fallidos=intentos_fallidos, desglose=desglose, sospechosa=sospechosa,
    )


def probar(*, numero: str, nombre: str, codigo_problema: str, fuente: str) -> Rechazo | judge.Resultado:
    """Corre la entrega solo contra los casos publicos. No puntua ni gasta intentos.

    Existe para que nadie pierda un intento por leer mal el formato de entrada.
    """
    asegurar_usuario(numero, nombre)

    ubicacion = buscar_problema(codigo_problema)
    if not ubicacion:
        return Rechazo(f"no existe ningun problema con codigo {codigo_problema.upper()}.")
    _, pr = ubicacion

    problema = pr.problema
    if problema is None:
        return Rechazo("ese problema no se pudo cargar. avisale a un admin.")

    veto = antifraud.revisar_limites(numero, pr.id)
    if veto and veto.espera_seg:
        return Rechazo(veto.motivo)

    fuente = limpiar_fuente(fuente)
    hallazgos = antifraud.revisar_codigo(fuente)
    if hallazgos:
        h = hallazgos[0]
        return Rechazo(f"linea {h.linea}: {h.motivo}")

    ruta = _guardar_fuente(numero, f"{pr.codigo}-prueba", fuente)
    try:
        return judge.juzgar(ruta, problema, solo_samples=True)
    except judge.ErrorJuez as e:
        return Rechazo(f"no se pudo correr: {e}")


# --- persistencia --------------------------------------------------------------

def _guardar_fuente(numero: str, etiqueta: str, fuente: str) -> Path:
    """Guarda el codigo en disco. Queda fuera del repo (`submissions/` esta ignorado)."""
    carpeta = config.dir_entregas / numero
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{etiqueta}-{db.ahora().strftime('%Y%m%d-%H%M%S-%f')}.py"
    ruta.write_text(fuente, encoding="utf-8")
    return ruta


def _registrar(*, numero: str, pr: ProblemaRonda, codigo_hash: str, ruta: Path, origen: str,
               fuente: str, veredicto: str, detalle: str = "", caso_fallido: int | None = None,
               tiempo_ms: int = 0, subtareas_ok: list[str] | None = None, puntos: int = 0,
               desglose: str = "", sospechosa: bool = False, motivo_sospecha: str = "") -> int:
    cur = db.ejecutar(
        "INSERT INTO entregas (usuario, problema_ronda_id, codigo_hash, fuente_path, origen, "
        "bytes, enviada_en, veredicto, detalle, caso_fallido, tiempo_ms, subtareas_ok, puntos, "
        "desglose, sospechosa, motivo_sospecha) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (numero, pr.id, codigo_hash, str(ruta), origen, len(fuente.encode("utf-8")), db.iso(),
         veredicto, detalle[:2000], caso_fallido, tiempo_ms, ",".join(subtareas_ok or []),
         puntos, desglose, int(sospechosa), motivo_sospecha),
    )
    entrega_id = cur.lastrowid
    antifraud.guardar_huellas(entrega_id, pr.id, numero, fuente)
    return entrega_id


def _intentos_fallidos(numero: str, problema_ronda_id: int) -> int:
    """Envios previos que penalizan. CE e IE no cuentan, igual que en ICPC."""
    fila = db.uno(
        "SELECT COUNT(*) AS n FROM entregas "
        "WHERE usuario = ? AND problema_ronda_id = ? AND anulada = 0 "
        "AND veredicto NOT IN ('AC', 'CE', 'IE', 'PENDIENTE')",
        (numero, problema_ronda_id),
    )
    return int(fila["n"]) if fila else 0


def _puntos_actuales(numero: str, problema_ronda_id: int) -> int:
    fila = db.uno("SELECT puntos FROM resultados WHERE usuario = ? AND problema_ronda_id = ?",
                  (numero, problema_ronda_id))
    return int(fila["puntos"]) if fila else 0


def _actualizar_resultado(numero: str, pr: ProblemaRonda, ronda: Ronda, entrega_id: int,
                          veredicto: str, puntos: int) -> bool:
    """Guarda el mejor resultado del usuario en ese problema. Devuelve si mejoro.

    Regla de IOI: reenviar nunca te baja el puntaje, se conserva el maximo.
    """
    fila = db.uno("SELECT * FROM resultados WHERE usuario = ? AND problema_ronda_id = ?",
                  (numero, pr.id))
    ahora = db.ahora()
    aceptado = veredicto == "AC"
    penaliza = scoring.cuenta_como_fallo(veredicto)

    if fila is None:
        db.ejecutar(
            "INSERT INTO resultados (usuario, problema_ronda_id, puntos, resuelto, intentos, "
            "intentos_fallidos, primer_ac_en, segundos_hasta_ac, entrega_id) "
            "VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)",
            (numero, pr.id, puntos, int(aceptado), int(penaliza),
             db.iso(ahora) if aceptado else None,
             (ahora - ronda.inicio).total_seconds() if aceptado else None,
             entrega_id if puntos else None),
        )
        return puntos > 0

    mejora = puntos > int(fila["puntos"])
    db.ejecutar(
        "UPDATE resultados SET "
        "puntos = MAX(puntos, ?), "
        "resuelto = MAX(resuelto, ?), "
        "intentos = intentos + 1, "
        "intentos_fallidos = intentos_fallidos + ?, "
        "primer_ac_en = COALESCE(primer_ac_en, ?), "
        "segundos_hasta_ac = COALESCE(segundos_hasta_ac, ?), "
        "entrega_id = CASE WHEN ? THEN ? ELSE entrega_id END "
        "WHERE usuario = ? AND problema_ronda_id = ?",
        (puntos, int(aceptado), int(penaliza),
         db.iso(ahora) if aceptado else None,
         (ahora - ronda.inicio).total_seconds() if aceptado else None,
         int(mejora), entrega_id, numero, pr.id),
    )
    return mejora


def historial_usuario(numero: str, limite: int = 20) -> list[dict]:
    filas = db.consultar(
        "SELECT e.id, e.veredicto, e.puntos, e.enviada_en, e.tiempo_ms, p.codigo, p.slug "
        "FROM entregas e JOIN problemas_ronda p ON p.id = e.problema_ronda_id "
        "WHERE e.usuario = ? ORDER BY e.id DESC LIMIT ?",
        (numero, limite),
    )
    return [dict(f) for f in filas]


def entrega_por_id(entrega_id: int) -> dict | None:
    fila = db.uno(
        "SELECT e.*, p.codigo, p.slug, p.dificultad "
        "FROM entregas e JOIN problemas_ronda p ON p.id = e.problema_ronda_id WHERE e.id = ?",
        (entrega_id,),
    )
    return dict(fila) if fila else None


def ultima_entrega(numero: str, codigo_problema: str | None = None) -> dict | None:
    """La ultima entrega del usuario, opcionalmente filtrada por problema."""
    if codigo_problema:
        fila = db.uno(
            "SELECT e.*, p.codigo, p.slug, p.dificultad "
            "FROM entregas e JOIN problemas_ronda p ON p.id = e.problema_ronda_id "
            "WHERE e.usuario = ? AND p.codigo = ? ORDER BY e.id DESC LIMIT 1",
            (numero, codigo_problema.strip().upper()),
        )
    else:
        fila = db.uno(
            "SELECT e.*, p.codigo, p.slug, p.dificultad "
            "FROM entregas e JOIN problemas_ronda p ON p.id = e.problema_ronda_id "
            "WHERE e.usuario = ? ORDER BY e.id DESC LIMIT 1",
            (numero,),
        )
    return dict(fila) if fila else None
