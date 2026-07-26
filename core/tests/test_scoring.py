"""Tests de la formula de puntaje.

`scoring.py` es puro, asi que se testea sin base de datos ni juez. Si alguien del
club quiere proponer un cambio en la formula, estos tests son el lugar donde se
discute que propiedades tiene que conservar.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from contest import scoring

INICIO = datetime(2026, 7, 1, 18, 0, tzinfo=timezone.utc)
FIN = INICIO + timedelta(hours=72)


def test_base_por_dificultad_es_creciente():
    bases = [scoring.base_de(d) for d in range(1, 6)]
    assert bases == sorted(bases)
    assert len(set(bases)) == 5


def test_dificultad_fuera_de_rango_se_acota():
    assert scoring.base_de(0) == scoring.base_de(1)
    assert scoring.base_de(99) == scoring.base_de(5)


def test_factor_tiempo_va_de_uno_al_piso():
    assert scoring.factor_tiempo(INICIO, FIN, INICIO) == pytest.approx(1.0)
    assert scoring.factor_tiempo(INICIO, FIN, FIN) == pytest.approx(scoring.PISO_TIEMPO)


def test_factor_tiempo_nunca_baja_del_piso():
    """Entregar despues del cierre no puede valer menos que el piso."""
    tarde = FIN + timedelta(days=30)
    assert scoring.factor_tiempo(INICIO, FIN, tarde) == pytest.approx(scoring.PISO_TIEMPO)


def test_factor_tiempo_es_monotono():
    momentos = [INICIO + timedelta(hours=h) for h in range(0, 73, 6)]
    factores = [scoring.factor_tiempo(INICIO, FIN, m) for m in momentos]
    assert factores == sorted(factores, reverse=True)


def test_factor_intentos_castiga_quince_por_ciento():
    assert scoring.factor_intentos(0) == pytest.approx(1.0)
    assert scoring.factor_intentos(1) == pytest.approx(0.85)
    assert scoring.factor_intentos(2) == pytest.approx(0.70)


def test_factor_intentos_tiene_piso():
    """Insistir siempre tiene que convenir mas que abandonar."""
    assert scoring.factor_intentos(100) == scoring.PISO_INTENTOS
    assert scoring.factor_intentos(100) > 0


def test_resolver_temprano_vale_mas_que_tarde():
    temprano = scoring.calcular(dificultad=3, inicio_ronda=INICIO, fin_ronda=FIN,
                                momento_aceptado=INICIO + timedelta(hours=4))
    tarde = scoring.calcular(dificultad=3, inicio_ronda=INICIO, fin_ronda=FIN,
                             momento_aceptado=INICIO + timedelta(hours=40))
    assert temprano.puntos > tarde.puntos


def test_un_problema_dificil_tarde_supera_a_uno_facil_temprano():
    """El decay premia velocidad pero no puede invertir el orden de dificultad."""
    dificil_tarde = scoring.calcular(dificultad=5, inicio_ronda=INICIO, fin_ronda=FIN,
                                     momento_aceptado=FIN)
    facil_temprano = scoring.calcular(dificultad=3, inicio_ronda=INICIO, fin_ronda=FIN,
                                      momento_aceptado=INICIO)
    assert dificil_tarde.puntos > facil_temprano.puntos


def test_ce_no_penaliza():
    assert not scoring.cuenta_como_fallo("CE")
    assert not scoring.cuenta_como_fallo("AC")
    assert not scoring.cuenta_como_fallo("IE")
    assert scoring.cuenta_como_fallo("WA")
    assert scoring.cuenta_como_fallo("TLE")


def test_ejemplo_documentado_en_evaluacion_md():
    """Los numeros de la tabla de docs/EVALUACION.md tienen que dar esto."""
    ana = scoring.calcular(dificultad=3, inicio_ronda=INICIO, fin_ronda=FIN,
                           momento_aceptado=INICIO + timedelta(hours=4))
    beto = scoring.calcular(dificultad=3, inicio_ronda=INICIO, fin_ronda=FIN,
                            momento_aceptado=INICIO + timedelta(hours=40))
    cami = scoring.calcular(dificultad=3, inicio_ronda=INICIO, fin_ronda=FIN,
                            momento_aceptado=INICIO + timedelta(hours=4), intentos_fallidos=2)

    assert (ana.puntos, beto.puntos, cami.puntos) == (343, 282, 240)
    assert ana.puntos > beto.puntos > cami.puntos


def test_subtareas_suman_su_peso():
    subtareas = [{"id": "s1", "peso": 30}, {"id": "s2", "peso": 70}]
    assert scoring.fraccion_de_subtareas(subtareas, set()) == pytest.approx(0.0)
    assert scoring.fraccion_de_subtareas(subtareas, {"s1"}) == pytest.approx(0.3)
    assert scoring.fraccion_de_subtareas(subtareas, {"s1", "s2"}) == pytest.approx(1.0)


def test_sin_subtareas_la_fraccion_es_uno():
    assert scoring.fraccion_de_subtareas([], set()) == 1.0


def test_ranking_ordena_por_puntos_luego_resueltos_luego_tiempo():
    filas = [
        {"puntos": 300, "resueltos": 2, "tiempo_total_seg": 9000, "ultimo_ac": "b"},
        {"puntos": 300, "resueltos": 2, "tiempo_total_seg": 100, "ultimo_ac": "a"},
        {"puntos": 500, "resueltos": 1, "tiempo_total_seg": 50, "ultimo_ac": "c"},
    ]
    ordenadas = sorted(filas, key=scoring.clave_de_ranking)
    assert ordenadas[0]["puntos"] == 500
    assert ordenadas[1]["tiempo_total_seg"] == 100    # empate en puntos, gana el mas rapido


def test_datetime_naive_se_asume_utc():
    """Las fechas de la base vienen sin tzinfo; no pueden hacer explotar el calculo."""
    naive_inicio = INICIO.replace(tzinfo=None)
    naive_fin = FIN.replace(tzinfo=None)
    assert scoring.factor_tiempo(naive_inicio, naive_fin, naive_inicio) == pytest.approx(1.0)
