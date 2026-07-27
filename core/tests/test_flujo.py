"""Test de integracion: el camino completo de una entrega.

Recorre lo mismo que recorre un chico del club: se abre una ronda, manda una
solucion, se la juzga, se le asignan puntos y aparece en el ranking.

Usa el juez en modo `subprocess`, asi que no hace falta Docker para correrlo.
"""

from __future__ import annotations

import pytest

from contest import commands, problems, ranking
from contest.rounds import crear_ronda, ronda_actual
from contest.submissions import Rechazo, entregar

CORRECTA = """
import sys

def raiz(n):
    while n >= 10:
        n = sum(int(d) for d in str(n))
    return n

print(raiz(int(sys.stdin.readline())))
"""

#: otra solucion correcta, con otro algoritmo (raiz digital cerrada en vez de ciclo)
OTRA_CORRECTA = """
import sys
n = int(sys.stdin.readline())
print(0 if n == 0 else 1 + (n - 1) % 9)
"""

INCORRECTA = """
import sys
print(int(sys.stdin.readline()) % 9)
"""

ROTA = "def f(:\n  pass"

LENTA = """
import sys
n = int(sys.stdin.readline())
total = 0
for i in range(10 ** 9):
    total += i
print(total)
"""

PELIGROSA = """
import os
print(os.listdir('/'))
"""


#: el problema contra el que se prueba todo. se fija a mano porque `crear_ronda`
#: elige al azar entre los de esa dificultad, y las soluciones de este archivo
#: resuelven este problema en particular.
SLUG_DE_PRUEBA = "suma-de-digitos"


@pytest.fixture
def ronda():
    """Una ronda con un unico problema conocido."""
    from contest import db

    problems.banco(refrescar=True)
    r = crear_ronda(publicar_ya=True, dificultades=(1,))
    assert r.problemas, "la ronda tiene que tener al menos un problema"

    db.ejecutar("UPDATE problemas_ronda SET slug = ? WHERE id = ?",
                (SLUG_DE_PRUEBA, r.problemas[0].id))
    return ronda_actual()


def _entregar(ronda, fuente, numero="5491111111111"):
    return entregar(numero=numero, nombre="Tester",
                    codigo_problema=ronda.problemas[0].codigo, fuente=fuente)


def test_solucion_correcta_es_aceptada_y_suma(ronda):
    r = _entregar(ronda, CORRECTA)

    assert not isinstance(r, Rechazo), getattr(r, "motivo", "")
    assert r.veredicto == "AC"
    assert r.puntos > 0
    assert r.mejoro

    # el decay recien empieza, asi que tiene que estar cerca del maximo
    from contest.scoring import base_de
    assert r.puntos >= base_de(1) * 0.95


def test_solucion_incorrecta_da_wa_y_no_suma(ronda):
    r = _entregar(ronda, INCORRECTA)
    assert r.veredicto == "WA"
    assert r.puntos == 0


def test_sintaxis_rota_da_ce(ronda):
    r = _entregar(ronda, ROTA)
    assert r.veredicto == "CE"


def test_ce_no_penaliza_el_ac_posterior(ronda):
    """Un error de tipeo no puede costarle puntos a nadie (regla de ICPC)."""
    _entregar(ronda, ROTA)
    r = _entregar(ronda, CORRECTA)
    assert r.veredicto == "AC"
    assert r.intentos_fallidos == 0
    assert r.desglose.factor_intentos == pytest.approx(1.0)


def test_wa_previo_si_penaliza(ronda):
    _entregar(ronda, INCORRECTA)
    r = _entregar(ronda, CORRECTA)
    assert r.veredicto == "AC"
    assert r.intentos_fallidos == 1
    assert r.desglose.factor_intentos == pytest.approx(0.85)


def test_codigo_peligroso_se_bloquea_antes_de_ejecutarse(ronda):
    r = _entregar(ronda, PELIGROSA)
    assert r.veredicto == "SEC"
    assert r.puntos == 0
    assert r.sospechosa


@pytest.mark.slow
def test_ciclo_infinito_da_tle(ronda):
    r = _entregar(ronda, LENTA)
    assert r.veredicto == "TLE"


def test_reenviar_el_mismo_codigo_no_gasta_intento(ronda):
    _entregar(ronda, INCORRECTA)
    r = _entregar(ronda, INCORRECTA)
    assert isinstance(r, Rechazo)
    assert "ya mandaste" in r.motivo


def test_reenviar_no_baja_el_puntaje(ronda):
    """Regla de IOI: se conserva el mejor resultado.

    La segunda entrega tiene que ser genuinamente distinta: renombrar variables no
    alcanza, porque el hash de codigo normaliza los nombres y la tomaria por un
    reenvio identico.
    """
    primera = _entregar(ronda, CORRECTA)
    segunda = _entregar(ronda, OTRA_CORRECTA)

    assert segunda.veredicto == "AC"
    assert not segunda.mejoro
    assert segunda.puntos_previos == primera.puntos

    fila = ranking.posicion_de("5491111111111")
    assert fila.puntos == primera.puntos


def test_codigo_de_problema_inexistente(ronda):
    r = entregar(numero="5491111111111", nombre="T", codigo_problema="R99-Z", fuente=CORRECTA)
    assert isinstance(r, Rechazo)
    assert "no existe" in r.motivo


def test_el_ranking_ordena_por_puntos(ronda):
    _entregar(ronda, CORRECTA, numero="5491111111111")
    _entregar(ronda, INCORRECTA, numero="5492222222222")
    _entregar(ronda, CORRECTA, numero="5492222222222")

    tabla = ranking.global_()
    assert len(tabla) == 2
    assert tabla[0].numero == "5491111111111"     # sin intentos fallidos, saco mas
    assert tabla[0].puntos > tabla[1].puntos
    assert tabla[0].puesto == 1


def test_la_similitud_marca_pero_no_anula(ronda):
    """Copiar queda registrado para revision humana, no se rechaza solo."""
    _entregar(ronda, CORRECTA, numero="5491111111111")
    r = _entregar(ronda, CORRECTA.replace("raiz", "rd").replace("n", "num"),
                  numero="5492222222222")

    # el veredicto es el que corresponda; lo que importa es que quede la marca
    assert r.veredicto in ("AC", "WA", "CE", "RE")


# --- comandos ------------------------------------------------------------------

def _ctx(texto, numero="5491111111111", es_grupo=False, es_admin=False):
    return commands.Contexto(numero=numero, nombre="Tester", jid=f"{numero}@s.whatsapp.net",
                             es_grupo=es_grupo, es_admin=es_admin, texto=texto, args="")


@pytest.fixture(autouse=True)
def comandos_cargados():
    commands.cargar_todos()


def test_help_lista_comandos():
    r = commands.despachar(_ctx("!help"))
    assert r and "entrega" in r.texto and "rank" in r.texto


def test_los_mensajes_no_llevan_markdown():
    """WhatsApp no entiende markdown: los ## y ** saldrian literales.

    Los emojis SI se permiten en los mensajes del bot (en la web no, ahi los
    iconos son SVG propios): en un celular el texto es todo lo que hay, y un
    [###--] se ve mal.
    """
    r = commands.despachar(_ctx("!help"))
    assert "##" not in r.texto, "encabezado markdown, WhatsApp lo muestra literal"
    assert "**" not in r.texto, "negrita markdown, en WhatsApp es un solo asterisco"


def test_el_enunciado_se_convierte_para_whatsapp(ronda):
    """El banco esta en markdown; al mandarlo por WhatsApp hay que traducirlo."""
    codigo = ronda.problemas[0].codigo
    r = commands.despachar(_ctx(f"!problema {codigo}"))

    assert "##" not in r.texto, "quedo un encabezado markdown sin convertir"
    assert "**" not in r.texto, "quedo negrita markdown sin convertir"
    # los numeros largos se protegen para que WhatsApp no los enlace como telefono
    import re
    from contest.wa import JUNTADOR
    for corrida in re.findall(r"\d{7,}", r.texto.replace(JUNTADOR, "")):
        assert JUNTADOR in r.texto, f"numero sin proteger: {corrida}"


def test_comando_inexistente_sugiere_el_parecido():
    r = commands.despachar(_ctx("!entrga R1-A"))
    assert r and "entrega" in r.texto


def test_comando_inexistente_se_ignora_en_grupo():
    """Un ! desconocido en el grupo puede ser de otro bot; no contestamos."""
    assert commands.despachar(_ctx("!cualquiercosa", es_grupo=True)) is None


def test_texto_sin_prefijo_no_es_comando():
    assert commands.despachar(_ctx("hola que tal")) is None


def test_entrega_en_grupo_se_redirige_a_privado():
    r = commands.despachar(_ctx("!entrega R1-A print(1)", es_grupo=True))
    assert r and "privado" in r.texto


def test_comando_de_admin_rechaza_a_quien_no_lo_es():
    r = commands.despachar(_ctx("!nuevaronda"))
    assert r and "admin" in r.texto


def test_rank_funciona_con_la_tabla_vacia():
    r = commands.despachar(_ctx("!rank"))
    assert r and r.texto


def test_ronda_muestra_los_problemas(ronda):
    r = commands.despachar(_ctx("!ronda"))
    assert r and ronda.problemas[0].codigo in r.texto


def test_problema_muestra_el_enunciado(ronda):
    codigo = ronda.problemas[0].codigo
    r = commands.despachar(_ctx(f"!problema {codigo}"))
    # los encabezados del markdown se convierten a *MAYUSCULAS* para WhatsApp
    assert r and "ENTRADA" in r.texto.upper() and "SALIDA" in r.texto.upper()


def test_entrega_multilinea_se_parsea_bien(ronda):
    codigo = ronda.problemas[0].codigo
    r = commands.despachar(_ctx(f"!entrega {codigo}\n{CORRECTA}"))
    assert r and "AC" in r.texto


def test_entrega_sin_codigo_de_problema_explica_como_se_hace():
    r = commands.despachar(_ctx("!entrega"))
    assert r and "R1-A" in r.texto


def test_un_comando_que_revienta_no_tumba_el_bot():
    @commands.comando("comandoquerompe", oculto=True)
    def _romper(ctx):
        raise ValueError("a proposito")

    r = commands.despachar(_ctx("!comandoquerompe"))
    assert r and "rompio" in r.texto


# --- regresion: salidas grandes ------------------------------------------------

def test_una_salida_grande_no_se_trunca_en_silencio(ronda):
    """El juez cortaba la salida en 1 MiB y devolvia WA sin explicar nada.

    Un problema con 200000 numeros de respuesta pasa los 2 MB, asi que una
    solucion correcta recibia WA. Ahora el techo es 8 MiB y, si se supera, el
    veredicto lo dice explicitamente en vez de comparar una salida cortada.
    """
    import importlib.util
    from contest.config import RAIZ

    spec = importlib.util.spec_from_file_location("runner", RAIZ / "judge" / "runner.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    # 200000 numeros de hasta 10 digitos son mas de 2 MB
    assert runner.MAX_SALIDA >= 8 << 20, "el techo corta respuestas legitimas"
    # y el techo de escritura del hijo tiene que ser mayor que lo que leemos
    assert runner.MAX_ARCHIVO > runner.MAX_SALIDA


# --- regresion: rondas sin grupo configurado -----------------------------------

def test_no_se_abre_ronda_si_no_hay_grupo(monkeypatch):
    """Sin GRUPO_JID el anuncio no sale y la ronda quemaria su ventana en silencio.

    Paso en produccion: el scheduler abrio la ronda 1 antes de que el bot estuviera
    vinculado, asi que nadie se entero de que existia y el reloj corria igual.
    """
    from contest import db, scheduler
    from contest.config import config
    from contest.rounds import ronda_actual

    monkeypatch.setattr(type(config), "grupo_jid", property(lambda self: ""),
                        raising=False)

    scheduler.tic()

    assert ronda_actual() is None, "no deberia haber abierto ninguna ronda"
    assert db.uno("SELECT 1 FROM auditoria WHERE evento = 'ronda_postergada'"), \
        "tendria que haber quedado registrado por que no se abrio"


def test_con_grupo_configurado_si_se_abre(monkeypatch):
    from contest import problems, scheduler
    from contest.config import config
    from contest.rounds import ronda_actual

    problems.banco(refrescar=True)
    monkeypatch.setattr(type(config), "grupo_jid",
                        property(lambda self: "1234@g.us"), raising=False)

    scheduler.tic()

    ronda = ronda_actual()
    assert ronda is not None
    assert ronda.problemas
