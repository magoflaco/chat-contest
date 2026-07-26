"""Leaderboard: global, por ronda y perfil individual.

El ranking sale siempre de la tabla `resultados`, que guarda el mejor resultado de
cada usuario por problema. Nunca se edita a mano: se deriva de `entregas`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import db
from .scoring import NOMBRE_DIFICULTAD, clave_de_ranking


@dataclass
class Fila:
    puesto: int
    numero: str
    nombre: str
    puntos: int
    resueltos: int
    intentos: int
    precision: float           # AC / intentos, 0..1
    tiempo_total_seg: float
    ultimo_ac: str | None

    def anonimo(self) -> dict:
        """Version para la web publica: sin el numero de telefono completo."""
        return {
            "puesto": self.puesto,
            "nombre": self.nombre or f"...{self.numero[-4:]}",
            "id": self.numero[-4:],
            "puntos": self.puntos,
            "resueltos": self.resueltos,
            "intentos": self.intentos,
            "precision": round(self.precision, 3),
            "ultimo_ac": self.ultimo_ac,
        }


_BASE = """
SELECT
    u.numero                                    AS numero,
    COALESCE(NULLIF(u.alias, ''), u.nombre, '') AS nombre,
    COALESCE(SUM(r.puntos), 0)                  AS puntos,
    COALESCE(SUM(r.resuelto), 0)                AS resueltos,
    COALESCE(SUM(r.intentos), 0)                AS intentos,
    COALESCE(SUM(r.segundos_hasta_ac), 0)       AS tiempo_total_seg,
    MAX(r.primer_ac_en)                         AS ultimo_ac
FROM usuarios u
JOIN resultados r ON r.usuario = u.numero
JOIN problemas_ronda p ON p.id = r.problema_ronda_id
WHERE u.bloqueado = 0
{filtro}
GROUP BY u.numero
HAVING intentos > 0
"""


def _construir(filas) -> list[Fila]:
    datos = [dict(f) for f in filas]
    datos.sort(key=clave_de_ranking)

    resultado: list[Fila] = []
    puesto_previo = 0
    clave_previa: tuple | None = None

    for i, d in enumerate(datos, start=1):
        clave = (d["puntos"], d["resueltos"])
        # empate exacto en puntos y resueltos comparte puesto, como en cualquier tabla
        puesto = puesto_previo if clave == clave_previa else i
        puesto_previo, clave_previa = puesto, clave

        intentos = int(d["intentos"]) or 1
        resultado.append(Fila(
            puesto=puesto,
            numero=d["numero"],
            nombre=d["nombre"] or "",
            puntos=int(d["puntos"]),
            resueltos=int(d["resueltos"]),
            intentos=int(d["intentos"]),
            precision=int(d["resueltos"]) / intentos,
            tiempo_total_seg=float(d["tiempo_total_seg"] or 0),
            ultimo_ac=d["ultimo_ac"],
        ))
    return resultado


def global_(limite: int | None = None) -> list[Fila]:
    """Ranking acumulado de todas las rondas."""
    filas = _construir(db.consultar(_BASE.format(filtro="")))
    return filas[:limite] if limite else filas


def por_ronda(numero_ronda: int, limite: int | None = None) -> list[Fila]:
    ronda = db.uno("SELECT id FROM rondas WHERE numero = ?", (numero_ronda,))
    if not ronda:
        return []
    filas = _construir(db.consultar(_BASE.format(filtro="AND p.ronda_id = ?"), (ronda["id"],)))
    return filas[:limite] if limite else filas


def posicion_de(numero: str) -> Fila | None:
    """La fila de un participante en el ranking global, con su puesto real."""
    for fila in global_():
        if fila.numero == numero:
            return fila
    return None


@dataclass
class Perfil:
    numero: str
    nombre: str
    puesto: int | None
    puntos: int
    resueltos: int
    intentos: int
    precision: float
    por_dificultad: dict[str, int] = field(default_factory=dict)
    detalle: list[dict] = field(default_factory=list)


def perfil(numero: str) -> Perfil | None:
    usuario = db.uno("SELECT * FROM usuarios WHERE numero = ?", (numero,))
    if not usuario:
        return None

    fila = posicion_de(numero)
    detalle = [dict(f) for f in db.consultar(
        "SELECT p.codigo, p.slug, p.dificultad, r.puntos, r.resuelto, r.intentos, "
        "r.intentos_fallidos, r.primer_ac_en, ro.numero AS ronda "
        "FROM resultados r "
        "JOIN problemas_ronda p ON p.id = r.problema_ronda_id "
        "JOIN rondas ro ON ro.id = p.ronda_id "
        "WHERE r.usuario = ? ORDER BY ro.numero DESC, p.orden",
        (numero,),
    )]

    por_dif: dict[str, int] = {}
    for d in detalle:
        if d["resuelto"]:
            nombre_dif = NOMBRE_DIFICULTAD.get(d["dificultad"], "?")
            por_dif[nombre_dif] = por_dif.get(nombre_dif, 0) + 1

    return Perfil(
        numero=numero,
        nombre=usuario["alias"] or usuario["nombre"] or "",
        puesto=fila.puesto if fila else None,
        puntos=fila.puntos if fila else 0,
        resueltos=fila.resueltos if fila else 0,
        intentos=fila.intentos if fila else 0,
        precision=fila.precision if fila else 0.0,
        por_dificultad=por_dif,
        detalle=detalle,
    )


def estadisticas_problema(codigo: str) -> dict:
    """Cuanta gente lo intento y cuanta lo resolvio. Se muestra en !problema."""
    fila = db.uno(
        "SELECT COUNT(*) AS intentaron, COALESCE(SUM(r.resuelto), 0) AS resolvieron "
        "FROM resultados r JOIN problemas_ronda p ON p.id = r.problema_ronda_id "
        "WHERE p.codigo = ?",
        (codigo.strip().upper(),),
    )
    intentaron = int(fila["intentaron"]) if fila else 0
    resolvieron = int(fila["resolvieron"]) if fila else 0
    return {
        "intentaron": intentaron,
        "resolvieron": resolvieron,
        "tasa": (resolvieron / intentaron) if intentaron else 0.0,
    }


def resumen() -> dict:
    """Numeros generales para la portada de la web."""
    def escalar(sql: str) -> int:
        f = db.uno(sql)
        return int(list(f)[0]) if f else 0

    return {
        "participantes": escalar("SELECT COUNT(*) FROM usuarios WHERE bloqueado = 0"),
        "entregas": escalar("SELECT COUNT(*) FROM entregas"),
        "aceptadas": escalar("SELECT COUNT(*) FROM entregas WHERE veredicto = 'AC'"),
        "rondas": escalar("SELECT COUNT(*) FROM rondas"),
        "problemas": escalar("SELECT COUNT(DISTINCT slug) FROM problemas_ronda"),
    }
