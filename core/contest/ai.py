"""Cliente de IA sobre build.nvidia.com (API compatible con OpenAI).

Se usa para dos cosas:

- `explicar_entrega`: el comando !revisar. Explica **por que** fallo una entrega,
  sin regalar la solucion y sin ver nunca los casos de prueba secretos.
- `redactar_problema`: genera problemas nuevos para el banco. Lo que sale de aca
  **no entra directo**: pasa por validacion automatica (la solucion de referencia
  tiene que pasar todos los tests) y por revision humana via pull request.

Se usa `urllib` de la stdlib a proposito, para no sumar dependencias por una sola
llamada HTTP. Si la IA no esta configurada, todo degrada a un mensaje claro en vez
de romper.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import config
from .problems import Problema


class ErrorIA(Exception):
    pass


@dataclass
class Respuesta:
    texto: str
    modelo: str


def disponible() -> bool:
    return config.ia.habilitada


def _chat(mensajes: list[dict], *, temperatura: float = 0.3, max_tokens: int = 1200,
          timeout_seg: int | None = None) -> Respuesta:
    """Una llamada al endpoint /chat/completions. Lanza `ErrorIA` si algo falla.

    `timeout_seg` sobreescribe el de la config: generar un problema entero tarda
    bastante mas que explicar un veredicto.
    """
    if not config.ia.habilitada:
        raise ErrorIA("la IA no esta configurada (falta NVIDIA_API_KEY en el .env)")

    cuerpo = json.dumps({
        "model": config.ia.modelo,
        "messages": mensajes,
        "temperature": temperatura,
        "max_tokens": max_tokens,
        "stream": False,
    }).encode("utf-8")

    pedido = urllib.request.Request(
        f"{config.ia.base_url.rstrip('/')}/chat/completions",
        data=cuerpo,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {config.ia.api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(pedido, timeout=timeout_seg or config.ia.timeout_seg) as r:
            datos = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", errors="replace")[:300]
        raise ErrorIA(f"el modelo respondio {e.code}: {detalle}") from e
    except urllib.error.URLError as e:
        raise ErrorIA(f"no se pudo conectar con el modelo: {e.reason}") from e
    except (TimeoutError, json.JSONDecodeError) as e:
        raise ErrorIA(f"respuesta invalida del modelo: {e}") from e

    try:
        texto = datos["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise ErrorIA("el modelo devolvio una respuesta con un formato inesperado") from e

    if not texto:
        raise ErrorIA("el modelo devolvio una respuesta vacia")
    return Respuesta(texto=texto, modelo=config.ia.modelo)


# --- !revisar ------------------------------------------------------------------

_SISTEMA_TUTOR = """\
Sos un entrenador de olimpiadas de programacion que ayuda a chicos de secundaria \
en un club de Python. Tu trabajo es explicar POR QUE fallo una entrega.

Reglas que no podes romper:
- NUNCA escribas la solucion completa ni el bloque de codigo que la arregla.
- Podes senalar la linea o la idea que esta mal, y sugerir que concepto estudiar.
- Se concreto: nada de "revisa tu logica". Deci que caso rompe el codigo y por que.
- Escribi en espanol rioplatense, directo y amable, sin condescendencia.
- Maximo 8 lineas. Sin emojis. Sin titulos ni markdown de encabezado.
- Si el veredicto es TLE, hablá de complejidad: que orden tiene su solucion y que \
orden necesitaria.
- Si el veredicto es RE, identifica que excepcion probablemente se lanza y con que entrada.
"""


def explicar_entrega(*, problema: Problema, fuente: str, veredicto: str,
                     detalle: str = "", caso_fallido: int | None = None) -> Respuesta:
    """Explica un veredicto. Nunca recibe los casos secretos, solo los publicos."""
    samples = problema.samples[:2]
    ejemplos = "\n\n".join(
        f"Entrada:\n{c.leer_entrada().strip()[:400]}\nSalida esperada:\n{c.leer_esperado().strip()[:400]}"
        for c in samples
    )

    contexto = [
        f"PROBLEMA: {problema.titulo} (dificultad {problema.dificultad}/5)",
        f"LIMITES: {problema.tiempo_ms} ms, {problema.memoria_mb} MB",
        "",
        "ENUNCIADO:",
        problema.enunciado[:3000],
        "",
        "CASOS DE EJEMPLO (publicos):",
        ejemplos,
        "",
        f"VEREDICTO QUE RECIBIO: {veredicto}",
    ]
    if detalle:
        contexto.append(f"DETALLE DEL JUEZ: {detalle}")
    if caso_fallido:
        contexto.append(f"Fallo en el caso de prueba numero {caso_fallido}.")
    contexto += ["", "CODIGO QUE ENTREGO:", "```python", fuente[:6000], "```"]

    return _chat(
        [
            {"role": "system", "content": _SISTEMA_TUTOR},
            {"role": "user", "content": "\n".join(contexto)},
        ],
        temperatura=0.2,
        max_tokens=600,
    )


def dar_pista(*, problema: Problema, nivel: int = 1) -> Respuesta:
    """Pista progresiva sobre como encarar un problema, sin resolverlo.

    Si el problema trae pistas escritas a mano en su YAML, se usan esas: siempre son
    mejores que las generadas, porque las escribio quien diseno el problema.
    """
    if problema.pistas:
        indice = min(max(1, nivel), len(problema.pistas)) - 1
        return Respuesta(texto=problema.pistas[indice], modelo="banco")

    escalones = {
        1: "una pista muy suave: solo que tipo de problema es y que estructura de datos conviene mirar",
        2: "una pista media: el enfoque general, sin detalles de implementacion",
        3: "una pista fuerte: el algoritmo concreto y su complejidad, pero sin escribir codigo",
    }
    pedido = escalones.get(nivel, escalones[1])

    return _chat(
        [
            {"role": "system", "content":
                "Sos entrenador de olimpiadas de programacion. Das pistas que hacen pensar, "
                "nunca soluciones. Espanol rioplatense, maximo 4 lineas, sin codigo, sin emojis."},
            {"role": "user", "content":
                f"Dame {pedido} para este problema:\n\n{problema.titulo}\n\n{problema.enunciado[:2500]}"},
        ],
        temperatura=0.4,
        max_tokens=300,
    )


# --- generacion de problemas ---------------------------------------------------

_SISTEMA_AUTOR = """\
Sos autor de problemas para olimpiadas de programacion (estilo OIA e ICPC).

Devolves UNICAMENTE un objeto JSON valido, sin texto alrededor y sin ```json.

Estructura exacta:
{
  "slug": "kebab-case-corto",
  "titulo": "Titulo del problema",
  "tags": ["dos", "o", "tres", "temas"],
  "enunciado": "markdown con historia breve, seccion Entrada, seccion Salida y Restricciones explicitas",
  "solucion": "codigo Python 3 completo que lee de stdin y escribe en stdout",
  "generador": "codigo Python 3 que recibe una semilla por sys.argv[1] e imprime un caso de prueba valido en stdout",
  "samples": [{"entrada": "...", "salida": "..."}],
  "editorial": "explicacion del enfoque y su complejidad, 4 a 8 lineas"
}

Reglas:
- El enunciado va en espanol rioplatense y declara SIEMPRE los rangos de las variables.
- La solucion debe ser correcta y entrar comoda en 2 segundos con los limites que declaraste.
- La solucion no importa nada fuera de: sys, math, collections, heapq, itertools, bisect, functools.
- Los samples tienen que ser consistentes con la solucion: si la corres con esa entrada, sale esa salida.
- El generador nunca produce entradas fuera de las restricciones del enunciado.
- Nada de emojis en ningun campo.
"""

DESCRIPCION_DIFICULTAD = {
    1: "muy accesible: lectura de entrada, condicionales y un ciclo. Para alguien que arranca.",
    2: "facil: arreglos, strings, ordenamiento, conteo. Una idea simple pero no obvia.",
    3: "media: dos punteros, busqueda binaria, greedy con demostracion, grafos basicos, DP de una dimension.",
    4: "dificil: DP no trivial, grafos con pesos, estructuras como Fenwick o DSU, geometria simple.",
    5: "nivel olimpiada nacional: combinar dos tecnicas, DP sobre estados no obvios, teoria de numeros, flujo.",
}


def redactar_problema(dificultad: int, tema: str = "") -> dict:
    """Genera un problema nuevo. El resultado hay que validarlo antes de aceptarlo.

    Devuelve el dict crudo del modelo. Quien llama es responsable de correr la
    solucion contra los samples y los tests generados: ver `scripts/generar_problema.py`.
    """
    dificultad = max(1, min(5, int(dificultad)))
    pedido = [
        f"Escribi un problema de dificultad {dificultad} de 5.",
        f"Ese nivel significa: {DESCRIPCION_DIFICULTAD[dificultad]}",
    ]
    if tema:
        pedido.append(f"El tema tiene que ser: {tema}.")
    pedido.append("Incluí al menos 2 samples.")

    respuesta = _chat(
        [
            {"role": "system", "content": _SISTEMA_AUTOR},
            {"role": "user", "content": "\n".join(pedido)},
        ],
        temperatura=0.8,
        max_tokens=4000,
        timeout_seg=420,      # escribir enunciado, solucion y generador lleva su tiempo
    )

    return _extraer_json(respuesta.texto)


def _extraer_json(texto: str) -> dict:
    """Rescata el JSON aunque el modelo lo haya envuelto en markdown o en prosa."""
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.lstrip().lower().startswith("json"):
            texto = texto.lstrip()[4:]

    # strict=False acepta saltos de linea y tabs literales dentro de los strings.
    # Hace falta: el campo "solucion" es codigo Python, y los modelos casi nunca
    # lo escapan, aunque el JSON estricto lo exija.
    for candidato in (texto, _entre_llaves(texto)):
        if not candidato:
            continue
        try:
            return json.loads(candidato, strict=False)
        except json.JSONDecodeError:
            continue

    raise ErrorIA("el modelo no devolvio un JSON que se pueda leer")


def _entre_llaves(texto: str) -> str:
    """El trozo desde la primera llave hasta la ultima, por si vino con prosa alrededor."""
    inicio, fin = texto.find("{"), texto.rfind("}")
    return texto[inicio:fin + 1] if inicio != -1 and fin > inicio else ""
