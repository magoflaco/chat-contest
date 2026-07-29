"""Tests del cambio de modelo cuando el principal no esta disponible.

Nada de esto toca la red: se reemplaza `_una_llamada`, que es la unica funcion
del modulo que sale a internet. Lo que se prueba es la decision de cuando
cambiar de modelo y cuando rendirse, que es donde se rompio de verdad: el
comando !revisar quedo inutil durante dias porque el modelo configurado estaba
saturado y el core esperaba mas de lo que el gateway aguanta.
"""

from __future__ import annotations

import time

import pytest

from contest import ai
from contest import config as configuracion
from contest.config import config


def _error(codigo: int | None) -> ai.ErrorIA:
    e = ai.ErrorIA(f"falla {codigo}")
    if codigo is not None:
        e.codigo = codigo
    return e


# --- a que modelos se le pregunta ---------------------------------------------


def test_el_principal_va_primero_y_los_suplentes_despues():
    assert config.ia.modelos[0] == config.ia.modelo
    assert len(config.ia.modelos) > 1, "sin suplentes, un modelo saturado deja el comando muerto"


def test_no_se_le_pregunta_dos_veces_al_mismo_modelo():
    assert len(config.ia.modelos) == len(set(config.ia.modelos))


def test_ninguno_devuelve_solo_razonamiento():
    # medidos con scripts/probar_modelos.py: dejan content en null y escriben en
    # reasoning_content, asi que ponerlos solo gasta el tiempo de la espera
    assert not set(config.ia.modelos) & set(configuracion.MODELOS_SIN_CONTENIDO)


def test_ninguno_escribe_markdown_de_dos_asteriscos():
    # WhatsApp marca negrita con un asterisco solo: los dobles llegan literales
    assert not set(config.ia.modelos) & set(configuracion.MODELOS_CON_MARKDOWN)


def test_los_suplentes_son_de_proveedores_distintos():
    """Una cadena de tres modelos del mismo proveedor se cae entera junta.

    La capacidad en build.nvidia.com se agota por pool, y los pools van por
    proveedor: si los tres son meta/, el 503 del primero anticipa los otros dos.
    """
    proveedores = [m.split("/")[0] for m in config.ia.modelos]
    assert len(set(proveedores)) > 1, f"todos del mismo proveedor: {proveedores}"


# --- cuando conviene cambiar de modelo ----------------------------------------


@pytest.mark.parametrize("codigo", [429, 503, 500, 502, 504, 404, 410])
def test_saturado_o_caido_pasa_al_siguiente(codigo):
    assert ai._hay_que_probar_otro_modelo(_error(codigo))


def test_timeout_sin_codigo_pasa_al_siguiente():
    assert ai._hay_que_probar_otro_modelo(_error(None))


@pytest.mark.parametrize("codigo", [400, 401, 403])
def test_problema_nuestro_no_se_reintenta(codigo):
    # la key mal o el pedido mal se repiten identicos en los cinco modelos:
    # insistir solo gasta el tiempo que alguien esta esperando en WhatsApp
    assert not ai._hay_que_probar_otro_modelo(_error(codigo))


# --- el recorrido completo -----------------------------------------------------


def test_si_el_principal_falla_contesta_el_suplente(monkeypatch):
    consultados = []

    def falso(modelo, mensajes, **kw):
        consultados.append(modelo)
        if modelo == config.ia.modelos[0]:
            raise _error(503)
        return ai.Respuesta(texto="listo", modelo=modelo)

    monkeypatch.setattr(ai, "_una_llamada", falso)
    respuesta = ai._chat([{"role": "user", "content": "hola"}])

    assert respuesta.texto == "listo"
    assert respuesta.modelo == config.ia.modelos[1]
    assert consultados == list(config.ia.modelos[:2])


def test_una_key_invalida_corta_en_el_primero(monkeypatch):
    consultados = []

    def falso(modelo, mensajes, **kw):
        consultados.append(modelo)
        raise _error(401)

    monkeypatch.setattr(ai, "_una_llamada", falso)
    with pytest.raises(ai.ErrorIA):
        ai._chat([{"role": "user", "content": "hola"}])

    assert consultados == [config.ia.modelos[0]]


def test_si_fallan_todos_se_propaga_el_ultimo_error(monkeypatch):
    def falso(modelo, mensajes, **kw):
        raise _error(503)

    monkeypatch.setattr(ai, "_una_llamada", falso)
    with pytest.raises(ai.ErrorIA, match="503"):
        ai._chat([{"role": "user", "content": "hola"}])


def test_varios_modelos_colgados_no_suman_mas_que_el_presupuesto(monkeypatch):
    """Lo que se rompio en produccion: esperar de a uno hasta pasarse del limite.

    Con tres modelos colgandose 30 s cada uno serian 90 s, y el gateway corta a
    los 120: el presupuesto tiene que ser total, no por intento.
    """
    plazos = []

    def falso(modelo, mensajes, *, timeout_seg, **kw):
        plazos.append(timeout_seg)
        time.sleep(timeout_seg)          # el modelo se cuelga hasta agotar su plazo
        raise _error(None)

    monkeypatch.setattr(ai, "_una_llamada", falso)
    arranque = time.monotonic()
    with pytest.raises(ai.ErrorIA):
        ai._chat([{"role": "user", "content": "hola"}], timeout_seg=3)

    assert time.monotonic() - arranque < 3 + 1
    assert all(p <= ai.TIMEOUT_INTENTO_SEG for p in plazos)


def test_el_presupuesto_total_no_depende_de_cuantos_suplentes_haya():
    # 3 modelos x 30 s por intento serian 90 s: el limite tiene que venir del
    # presupuesto, no de la cantidad de suplentes
    assert config.ia.timeout_seg < 120, "CORE_TIMEOUT_MS es 120 s: hay que contestar antes"


# --- respuestas raras ----------------------------------------------------------


@pytest.mark.parametrize("cuerpo", [
    {"choices": [{"message": {"content": None}}]},          # modelo de razonamiento
    {"choices": [{"message": {"content": "   "}}]},         # solo espacios
    {"choices": []},                                        # sin respuestas
    {},                                                     # sin choices
])
def test_una_respuesta_sin_texto_no_rompe(cuerpo, monkeypatch):
    """Antes, content=null explotaba con AttributeError y se saltaba los except."""
    class FalsaRespuesta:
        def read(self):
            import json
            return json.dumps(cuerpo).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(ai.urllib.request, "urlopen", lambda *a, **k: FalsaRespuesta())
    with pytest.raises(ai.ErrorIA):
        ai._una_llamada("modelo/x", [{"role": "user", "content": "hola"}],
                        temperatura=0.2, max_tokens=10, timeout_seg=5)
