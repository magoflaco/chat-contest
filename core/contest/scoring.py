"""Calculo de puntajes.

La formula y su justificacion estan en `docs/EVALUACION.md`. Resumen:

    puntos = base(dificultad) x factor_tiempo x factor_intentos x fraccion_subtareas

- base: cuanto vale el problema segun su dificultad (1 a 5)
- factor_tiempo: decae de 1.00 a 0.65 a lo largo de la ventana de la ronda (Codeforces)
- factor_intentos: -15% por envio rechazado previo, con piso en 0.40 (ICPC)
- fraccion_subtareas: 1.0 para problemas pass/fail; en problemas con subtareas es la
  fraccion del peso total que lograste (IOI)

Este modulo es puro: no toca base de datos ni red. Eso lo hace facil de testear y
es el mejor lugar para que alguien del club experimente con la formula.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

# --- constantes de la formula (tocar con cuidado: cambian el ranking historico) ---

BASE_POR_DIFICULTAD: dict[int, int] = {
    1: 100,   # iniciacion
    2: 200,   # facil
    3: 350,   # media
    4: 550,   # dificil
    5: 800,   # olimpica
}

NOMBRE_DIFICULTAD: dict[int, str] = {
    1: "Iniciacion",
    2: "Facil",
    3: "Media",
    4: "Dificil",
    5: "Olimpica",
}

#: piso del factor tiempo. resolver sobre la bocina vale 0.65x, nunca menos.
PISO_TIEMPO = 0.65
#: cuanto castiga cada envio rechazado previo al aceptado
CASTIGO_POR_INTENTO = 0.15
#: piso del factor intentos. insistir siempre conviene mas que abandonar.
PISO_INTENTOS = 0.40

#: veredictos que NO cuentan como intento fallido (igual que en ICPC)
VEREDICTOS_SIN_PENALIZACION = frozenset({"AC", "CE", "IE"})


@dataclass(frozen=True)
class Desglose:
    """El detalle de como se llego al puntaje, para poder mostrarselo al participante."""

    base: int
    factor_tiempo: float
    factor_intentos: float
    fraccion_subtareas: float
    puntos: int
    horas_transcurridas: float
    intentos_fallidos: int

    def explicar(self) -> str:
        """Texto listo para mandar por WhatsApp."""
        lineas = [
            f"base (dificultad): {self.base}",
            f"tiempo: x{self.factor_tiempo:.3f}  ({self.horas_transcurridas:.1f}h desde la publicacion)",
        ]
        if self.intentos_fallidos:
            lineas.append(f"intentos: x{self.factor_intentos:.2f}  ({self.intentos_fallidos} rechazados antes)")
        if self.fraccion_subtareas < 1.0:
            lineas.append(f"subtareas: x{self.fraccion_subtareas:.2f}")
        lineas.append(f"= {self.puntos} puntos")
        return "\n".join(lineas)


def base_de(dificultad: int) -> int:
    """Puntaje base de una dificultad. Fuera de rango se acota a 1..5."""
    d = max(1, min(5, int(dificultad)))
    return BASE_POR_DIFICULTAD[d]


def cuenta_como_fallo(veredicto: str) -> bool:
    """True si este veredicto debe restar puntos."""
    return veredicto.upper() not in VEREDICTOS_SIN_PENALIZACION


def factor_tiempo(inicio: datetime, fin: datetime, momento: datetime) -> float:
    """Decay lineal de 1.00 (al abrir) a PISO_TIEMPO (al cerrar).

    Entregar despues del cierre no da menos que PISO_TIEMPO: la ronda ya cerro, y si
    igual se acepta la entrega (por ejemplo en modo practica) no tiene sentido
    castigarla mas alla del piso.
    """
    inicio, fin, momento = _utc(inicio), _utc(fin), _utc(momento)

    ventana = (fin - inicio).total_seconds()
    if ventana <= 0:
        return 1.0

    restante = (fin - momento).total_seconds()
    frac = max(0.0, min(1.0, restante / ventana))
    return PISO_TIEMPO + (1.0 - PISO_TIEMPO) * frac


def factor_intentos(intentos_fallidos: int) -> float:
    """-15% por cada rechazo previo, con piso en 0.40."""
    n = max(0, int(intentos_fallidos))
    return max(PISO_INTENTOS, 1.0 - CASTIGO_POR_INTENTO * n)


def calcular(
    *,
    dificultad: int,
    inicio_ronda: datetime,
    fin_ronda: datetime,
    momento_aceptado: datetime,
    intentos_fallidos: int = 0,
    fraccion_subtareas: float = 1.0,
) -> Desglose:
    """Puntaje de una entrega aceptada, con su desglose.

    `fraccion_subtareas` es 1.0 en problemas pass/fail. En problemas con subtareas es
    la fraccion del peso total conseguida (ver `fraccion_de_subtareas`).
    """
    base = base_de(dificultad)
    ft = factor_tiempo(inicio_ronda, fin_ronda, momento_aceptado)
    fi = factor_intentos(intentos_fallidos)
    fs = max(0.0, min(1.0, float(fraccion_subtareas)))

    puntos = round(base * ft * fi * fs)
    horas = (_utc(momento_aceptado) - _utc(inicio_ronda)).total_seconds() / 3600.0

    return Desglose(
        base=base,
        factor_tiempo=ft,
        factor_intentos=fi,
        fraccion_subtareas=fs,
        puntos=puntos,
        horas_transcurridas=max(0.0, horas),
        intentos_fallidos=max(0, int(intentos_fallidos)),
    )


def fraccion_de_subtareas(subtareas: list[dict], pasadas: set[str]) -> float:
    """Fraccion del puntaje logrado en un problema con subtareas (estilo IOI).

    Cada subtarea es `{"id": "s1", "peso": 30}`. Una subtarea aporta su peso solo si
    *todos* sus casos pasaron: quien decide eso es el juez, aca solo recibimos el
    conjunto de ids que se dieron por buenas.
    """
    if not subtareas:
        return 1.0

    total = sum(float(s.get("peso", 0)) for s in subtareas)
    if total <= 0:
        return 1.0

    logrado = sum(float(s.get("peso", 0)) for s in subtareas if str(s.get("id")) in pasadas)
    return max(0.0, min(1.0, logrado / total))


def clave_de_ranking(fila: dict) -> tuple:
    """Clave de orden para el leaderboard. Menor es mejor, asi que negamos lo que suma.

    Criterios, en orden (ver docs/EVALUACION.md seccion "Desempate"):
      1. mas puntos
      2. mas problemas resueltos
      3. menor tiempo total hasta los aceptados (criterio ICPC)
      4. quien llego primero a ese puntaje
    """
    return (
        -int(fila.get("puntos", 0)),
        -int(fila.get("resueltos", 0)),
        float(fila.get("tiempo_total_seg", 0.0)),
        str(fila.get("ultimo_ac", "9999")),
    )


def _utc(dt: datetime) -> datetime:
    """Normaliza a UTC. Un datetime naive se asume UTC (asi los guardamos en la db)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
