"""Mide que modelos de build.nvidia.com sirven para el comando !revisar.

No mide "cual es el modelo mas grande": mide el caso real. Le da a cada uno el
prompt del tutor sobre una entrega que se paso de tiempo, y despues mira lo que
en la practica rompe el mensaje que le llega a un chico por WhatsApp:

- que conteste (la capacidad se agota por modelo y cambia varias veces al dia)
- que no tarde una eternidad, porque del otro lado hay alguien esperando
- que devuelva `content` y no solo `reasoning_content`
- que no escriba **negrita**, que WhatsApp marca con un solo asterisco
- que no regale la solucion, que es justamente lo que el comando no debe hacer

Se corre a mano cuando el catalogo cambia o cuando !revisar empieza a fallar:

    python scripts/probar_modelos.py
    python scripts/probar_modelos.py --todos      # los 100 y pico del catalogo
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "core"))

from contest.config import config  # noqa: E402

# Los que vale la pena mirar primero: chat de proposito general y de buen
# tamano. Se saltean los de embeddings, vision, traduccion y moderacion.
CANDIDATOS = (
    "z-ai/glm-5.2",
    "nvidia/nemotron-3-super-120b-a12b",
    "minimaxai/minimax-m3",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "openai/gpt-oss-120b",
    "deepseek-ai/deepseek-v4-pro",
    "deepseek-ai/deepseek-v4-flash",
    "mistralai/mistral-medium-3.5-128b",
    "google/gemma-4-31b-it",
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.1-8b-instruct",
)

NO_CONVERSACIONALES = ("embed", "retriev", "guard", "safety", "translate", "parse",
                       "reward", "nvclip", "vision", "-vl-", "vila", "deplot", "kosmos")

# Una entrega que se pasa de tiempo por usar dos ciclos anidados: el caso mas
# comun del club y el que mas se le pide a !revisar.
SISTEMA = """\
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
"""

USUARIO = """\
PROBLEMA: Suma de pares (dificultad 2/5)
LIMITES: 1000 ms, 64 MB

ENUNCIADO:
Dado un arreglo de N enteros (1 <= N <= 200000) y un valor K, contar cuantos
pares (i,j) con i<j cumplen a[i]+a[j]==K.

VEREDICTO QUE RECIBIO: TLE
DETALLE DEL JUEZ: se paso del limite de tiempo en el caso 7 (N=200000).

CODIGO QUE ENTREGO:
```python
n, k = map(int, input().split())
a = list(map(int, input().split()))
c = 0
for i in range(n):
    for j in range(i+1, n):
        if a[i]+a[j] == k:
            c += 1
print(c)
```"""


def catalogo() -> list[str]:
    pedido = urllib.request.Request(
        f"{config.ia.base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {config.ia.api_key}"})
    with urllib.request.urlopen(pedido, timeout=30) as r:
        datos = json.loads(r.read().decode())
    return sorted(m["id"] for m in datos.get("data", [])
                  if not any(x in m["id"] for x in NO_CONVERSACIONALES))


def probar(modelo: str, timeout: int) -> dict:
    cuerpo = json.dumps({
        "model": modelo,
        "messages": [{"role": "system", "content": SISTEMA},
                     {"role": "user", "content": USUARIO}],
        "temperature": 0.2, "max_tokens": 600, "stream": False,
    }).encode()
    pedido = urllib.request.Request(
        f"{config.ia.base_url.rstrip('/')}/chat/completions", data=cuerpo,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {config.ia.api_key}"}, method="POST")

    arranque = time.time()
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as r:
            datos = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detalle = e.read().decode(errors="replace")
        motivo = "saturado" if "ResourceExhausted" in detalle else detalle[:60]
        return {"estado": f"HTTP {e.code}", "seg": time.time() - arranque, "nota": motivo}
    except Exception as e:                                   # noqa: BLE001
        return {"estado": "SIN RESPUESTA", "seg": time.time() - arranque, "nota": str(e)[:60]}

    try:
        mensaje = datos["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return {"estado": "RARO", "seg": time.time() - arranque, "nota": "sin choices"}

    texto = (mensaje.get("content") or "").strip()
    if not texto:
        razonamiento = len((mensaje.get("reasoning_content") or ""))
        return {"estado": "VACIO", "seg": time.time() - arranque,
                "nota": f"content null, {razonamiento} chars de razonamiento"}

    reparos = []
    if "```" in texto:
        reparos.append("REGALA CODIGO")
    if "**" in texto:
        reparos.append("markdown **")
    if len([l for l in texto.splitlines() if l.strip()]) > 8:
        reparos.append("mas de 8 lineas")

    return {"estado": "OK", "seg": time.time() - arranque, "texto": texto,
            "nota": " + ".join(reparos) or "limpio"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--todos", action="store_true",
                        help="probar todo el catalogo, no solo los candidatos")
    parser.add_argument("--timeout", type=int, default=70)
    parser.add_argument("--ver", metavar="MODELO", help="mostrar la respuesta completa de uno")
    args = parser.parse_args()

    if not config.ia.habilitada:
        print("falta NVIDIA_API_KEY en el .env", file=sys.stderr)
        return 1

    modelos = [args.ver] if args.ver else (catalogo() if args.todos else list(CANDIDATOS))
    print(f"en uso ahora: {' -> '.join(config.ia.modelos)}\n")

    sirven = []
    for modelo in modelos:
        r = probar(modelo, args.timeout)
        print(f"{r['estado']:13} {r['seg']:6.1f}s  {modelo:42} {r['nota']}", flush=True)
        if args.ver:
            print("\n" + r.get("texto", "") + "\n")
        elif r["estado"] == "OK" and r["nota"] == "limpio":
            sirven.append((r["seg"], modelo))

    if sirven:
        print("\nsirven, del mas rapido al mas lento:")
        for seg, modelo in sorted(sirven):
            print(f"  {seg:6.1f}s  {modelo}")
        print("\nponelos en NVIDIA_MODEL y MODELOS_SUPLENTES (core/contest/config.py).")
        print("elegi de proveedores distintos: la capacidad se agota por pool.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
