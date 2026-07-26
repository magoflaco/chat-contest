"""Rondas: seleccion de problemas, apertura, cierre y publicacion.

Cada `RONDA_CADA_DIAS` dias se abre una ronda con un problema por cada dificultad
de `RONDA_DIFICULTADES` (por defecto 1, 3 y 5: uno accesible, uno medio y uno duro).
Es el mismo formato que enfrentan en el certamen nacional de la OIA, donde se
resuelven entre 3 y 6 problemas de dificultad variada.

La ronda queda abierta hasta que arranca la siguiente, asi nadie se queda afuera
por no haber mirado el celular el dia que salio.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import db
from .config import config
from .problems import Problema, banco, obtener

#: letras que se le asignan a los problemas dentro de una ronda, como en ICPC
LETRAS = "ABCDEFGHIJ"


@dataclass
class ProblemaRonda:
    id: int
    codigo: str
    slug: str
    dificultad: int
    orden: int

    @property
    def problema(self) -> Problema | None:
        return obtener(self.slug)


@dataclass
class Ronda:
    id: int
    numero: int
    inicio: datetime
    fin: datetime
    estado: str
    problemas: list[ProblemaRonda]

    @property
    def abierta(self) -> bool:
        return self.estado == "abierta" and self.inicio <= db.ahora() < self.fin

    @property
    def horas_restantes(self) -> float:
        return max(0.0, (self.fin - db.ahora()).total_seconds() / 3600.0)

    def buscar(self, codigo: str) -> ProblemaRonda | None:
        codigo = codigo.strip().upper()
        for p in self.problemas:
            if p.codigo == codigo:
                return p
        return None


def _armar(fila) -> Ronda:
    problemas = [
        ProblemaRonda(id=f["id"], codigo=f["codigo"], slug=f["slug"],
                      dificultad=f["dificultad"], orden=f["orden"])
        for f in db.consultar(
            "SELECT * FROM problemas_ronda WHERE ronda_id = ? ORDER BY orden", (fila["id"],)
        )
    ]
    return Ronda(
        id=fila["id"],
        numero=fila["numero"],
        inicio=db.desde_iso(fila["inicio"]),
        fin=db.desde_iso(fila["fin"]),
        estado=fila["estado"],
        problemas=problemas,
    )


def ronda_actual() -> Ronda | None:
    """La ronda abierta, si hay alguna."""
    fila = db.uno("SELECT * FROM rondas WHERE estado = 'abierta' ORDER BY numero DESC LIMIT 1")
    return _armar(fila) if fila else None


def ronda_por_numero(numero: int) -> Ronda | None:
    fila = db.uno("SELECT * FROM rondas WHERE numero = ?", (numero,))
    return _armar(fila) if fila else None


def buscar_problema(codigo: str) -> tuple[Ronda, ProblemaRonda] | None:
    """Ubica un problema por su codigo publico (ej: R3-B), en cualquier ronda."""
    fila = db.uno(
        "SELECT r.* FROM rondas r JOIN problemas_ronda p ON p.ronda_id = r.id "
        "WHERE p.codigo = ?",
        (codigo.strip().upper(),),
    )
    if not fila:
        return None
    ronda = _armar(fila)
    pr = ronda.buscar(codigo)
    return (ronda, pr) if pr else None


def historial(limite: int = 10) -> list[Ronda]:
    return [_armar(f) for f in db.consultar(
        "SELECT * FROM rondas ORDER BY numero DESC LIMIT ?", (limite,))]


# --- seleccion de problemas ----------------------------------------------------

def _ya_usados() -> set[str]:
    return {f["slug"] for f in db.consultar("SELECT DISTINCT slug FROM problemas_ronda")}


def elegir_problemas(dificultades: tuple[int, ...] | None = None) -> list[Problema]:
    """Elige un problema por dificultad, sin repetir ninguno ya usado.

    Si para una dificultad no queda nada sin usar, se busca en la dificultad mas
    cercana antes que dejar la ronda incompleta. La rotacion prefiere los problemas
    que llevan mas tiempo sin salir (aca: eleccion al azar entre los no usados,
    que con un banco grande da el mismo efecto y es mas simple).
    """
    objetivo = dificultades or config.rondas.dificultades
    usados = _ya_usados()
    disponibles = [p for p in banco().values() if p.slug not in usados]

    if not disponibles:
        # se agoto el banco: reciclamos, empezando por los que menos veces salieron
        conteo = {f["slug"]: f["n"] for f in db.consultar(
            "SELECT slug, COUNT(*) AS n FROM problemas_ronda GROUP BY slug")}
        disponibles = sorted(banco().values(), key=lambda p: conteo.get(p.slug, 0))

    elegidos: list[Problema] = []
    tomados: set[str] = set()

    for dificultad in objetivo:
        candidatos = [p for p in disponibles if p.dificultad == dificultad and p.slug not in tomados]
        if not candidatos:
            # nada exacto: agarramos lo mas cercano en dificultad
            candidatos = sorted(
                (p for p in disponibles if p.slug not in tomados),
                key=lambda p: abs(p.dificultad - dificultad),
            )
        if not candidatos:
            continue
        elegido = random.choice(candidatos[:8]) if len(candidatos) > 1 else candidatos[0]
        elegidos.append(elegido)
        tomados.add(elegido.slug)

    return elegidos


# --- ciclo de vida -------------------------------------------------------------

def proximo_inicio(desde: datetime | None = None) -> datetime:
    """Cuando arranca la proxima ronda: a las RONDA_HORA hora local, RONDA_CADA_DIAS despues."""
    tz = config.rondas.tz
    base = (desde or db.ahora()).astimezone(tz)
    objetivo = base.replace(hour=config.rondas.hora, minute=0, second=0, microsecond=0)
    if objetivo <= base:
        objetivo += timedelta(days=1)
    return objetivo.astimezone(timezone.utc)


def crear_ronda(*, publicar_ya: bool = True, dificultades: tuple[int, ...] | None = None) -> Ronda:
    """Crea la ronda siguiente y le asigna problemas.

    Lanza `RuntimeError` si el banco no alcanza: es preferible avisar que publicar
    una ronda a medias.
    """
    problemas = elegir_problemas(dificultades)
    if not problemas:
        raise RuntimeError(
            "no hay problemas validos en data/problems/. "
            "corre 'python -m contest.cli validar' para ver que esta fallando."
        )

    with db.transaccion():
        ultimo = db.uno("SELECT MAX(numero) AS n FROM rondas")
        numero = (ultimo["n"] or 0) + 1

        inicio = db.ahora() if publicar_ya else proximo_inicio()
        fin = inicio + timedelta(hours=config.rondas.ventana_horas)

        # solo puede haber una ronda abierta a la vez
        db.ejecutar("UPDATE rondas SET estado = 'cerrada' WHERE estado = 'abierta'")

        cur = db.ejecutar(
            "INSERT INTO rondas (numero, inicio, fin, publicada_en, estado) VALUES (?, ?, ?, ?, ?)",
            (numero, db.iso(inicio), db.iso(fin),
             db.iso() if publicar_ya else None,
             "abierta" if publicar_ya else "programada"),
        )
        ronda_id = cur.lastrowid

        for i, p in enumerate(sorted(problemas, key=lambda x: x.dificultad)):
            db.ejecutar(
                "INSERT INTO problemas_ronda (ronda_id, codigo, slug, dificultad, orden) "
                "VALUES (?, ?, ?, ?, ?)",
                (ronda_id, f"R{numero}-{LETRAS[i]}", p.slug, p.dificultad, i),
            )

    db.auditar("ronda_creada", detalle=f"ronda {numero} con {len(problemas)} problemas")
    return ronda_por_numero(numero)


def cerrar_vencidas() -> list[Ronda]:
    """Cierra las rondas cuya ventana ya paso. Devuelve las que se cerraron."""
    vencidas = [_armar(f) for f in db.consultar(
        "SELECT * FROM rondas WHERE estado = 'abierta' AND fin <= ?", (db.iso(),))]
    for r in vencidas:
        db.ejecutar("UPDATE rondas SET estado = 'cerrada' WHERE id = ?", (r.id,))
        db.auditar("ronda_cerrada", detalle=f"ronda {r.numero}")
    return vencidas


def toca_ronda_nueva() -> bool:
    """True si ya paso el intervalo desde la ultima ronda."""
    fila = db.uno("SELECT inicio FROM rondas ORDER BY numero DESC LIMIT 1")
    if not fila:
        return True
    ultimo = db.desde_iso(fila["inicio"])
    if not ultimo:
        return True
    return db.ahora() - ultimo >= timedelta(days=config.rondas.cada_dias)
