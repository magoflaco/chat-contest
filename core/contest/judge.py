"""Lado host del juez: prepara el trabajo y lo lanza aislado.

Dos backends:

- `docker` (produccion): un contenedor efimero por entrega, sin red, con el
  filesystem de solo lectura, sin privilegios, con limites de CPU/memoria/procesos
  y matado por reloj de pared si se cuelga. Es el unico backend seguro.
- `subprocess` (solo desarrollo): corre el runner directo en la maquina. NO aisla
  nada. Sirve para probar el flujo en Windows sin levantar Docker.

En ambos casos el trabajo pesado lo hace `judge/runner.py`, asi hay un solo camino
de codigo para ejecutar y comparar.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .config import RAIZ, config
from .problems import Problema

RUNNER = RAIZ / "judge" / "runner.py"

#: veredictos que el juez puede devolver (ver docs/EVALUACION.md)
VEREDICTOS = ("AC", "WA", "TLE", "MLE", "RE", "CE", "PE", "SEC", "IE")

DESCRIPCION_VEREDICTO = {
    "AC": "Aceptado",
    "WA": "Respuesta incorrecta",
    "TLE": "Se paso del tiempo limite",
    "MLE": "Se paso de memoria",
    "RE": "Error en ejecucion",
    "CE": "Error de sintaxis",
    "PE": "Error de presentacion (el formato de salida no es el pedido)",
    "SEC": "La entrega intento hacer algo que no esta permitido",
    "IE": "Error interno del juez (no es culpa tuya, avisale a un admin)",
}


@dataclass
class Resultado:
    veredicto: str
    detalle: str = ""
    caso_fallido: int | None = None
    tiempo_ms: int = 0
    subtareas_ok: list[str] = field(default_factory=list)
    casos: list[dict] = field(default_factory=list)

    @property
    def aceptado(self) -> bool:
        return self.veredicto == "AC"

    @property
    def descripcion(self) -> str:
        return DESCRIPCION_VEREDICTO.get(self.veredicto, self.veredicto)


class ErrorJuez(Exception):
    pass


def juzgar(fuente: Path, problema: Problema, *, solo_samples: bool = False) -> Resultado:
    """Corre `fuente` contra los casos de `problema` y devuelve el veredicto.

    Con `solo_samples=True` corre unicamente los casos publicos: es lo que usa el
    comando !probar, que no puntua y sirve para que el chico se de cuenta si esta
    leyendo mal el formato de entrada antes de gastar un intento.
    """
    if not fuente.is_file():
        raise ErrorJuez(f"no existe el archivo de la entrega: {fuente}")

    tamanio = fuente.stat().st_size
    if tamanio == 0:
        return Resultado("CE", "el archivo esta vacio")
    if tamanio > config.juez.max_fuente_bytes:
        return Resultado("CE", f"el archivo pesa {tamanio} bytes, el maximo es {config.juez.max_fuente_bytes}")

    casos = problema.samples if solo_samples else (problema.samples + problema.secretos)
    if not casos:
        raise ErrorJuez(f"el problema {problema.slug} no tiene casos de prueba")

    trabajo = Path(tempfile.mkdtemp(prefix="cc-juez-"))
    try:
        return _ejecutar(fuente, problema, casos, trabajo, solo_samples)
    finally:
        shutil.rmtree(trabajo, ignore_errors=True)


def _ejecutar(fuente: Path, problema: Problema, casos, trabajo: Path, solo_samples: bool) -> Resultado:
    # armamos un directorio autocontenido: la solucion y una copia de los casos.
    # copiar los casos (en vez de montar data/problems) evita exponerle al contenedor
    # el banco entero de problemas con sus soluciones de referencia.
    (trabajo / "casos").mkdir()
    shutil.copyfile(fuente, trabajo / "solucion.py")

    publicos = {c.nombre for c in problema.samples}
    entradas = []
    for i, caso in enumerate(casos, start=1):
        destino_in = trabajo / "casos" / f"{i:03d}.in"
        destino_ans = trabajo / "casos" / f"{i:03d}.ans"
        shutil.copyfile(caso.entrada, destino_in)
        shutil.copyfile(caso.esperado, destino_ans)
        entradas.append({
            "nombre": caso.nombre,
            "subtarea": caso.subtarea,
            "publico": caso.nombre in publicos,
            "_in": destino_in.name,
            "_ans": destino_ans.name,
        })

    docker = config.juez.backend == "docker"
    raiz = Path("/work") if docker else trabajo

    manifiesto = {
        "dir_trabajo": str(raiz / "tmp") if docker else str(trabajo),
        "fuente": str(raiz / "solucion.py"),
        "tiempo_ms": problema.tiempo_ms,
        "memoria_mb": min(problema.memoria_mb, config.juez.memoria_mb),
        "validacion": {"tipo": problema.validacion, "tolerancia": problema.tolerancia},
        "tiene_subtareas": problema.tiene_subtareas and not solo_samples,
        "casos": [
            {**{k: v for k, v in e.items() if not k.startswith("_")},
             "entrada": str(raiz / "casos" / e["_in"]),
             "esperado": str(raiz / "casos" / e["_ans"])}
            for e in entradas
        ],
    }
    (trabajo / "manifiesto.json").write_text(json.dumps(manifiesto), encoding="utf-8")

    # techo global: si un problema tiene 30 casos de 2s, el contenedor entero no
    # puede tardar mas que eso mas un margen de arranque
    techo_seg = (problema.tiempo_ms * len(casos) + config.juez.overhead_ms * 2) / 1000.0

    crudo = _correr_docker(trabajo, techo_seg) if docker else _correr_local(trabajo, techo_seg)
    return _interpretar(crudo, solo_samples)


def _correr_docker(trabajo: Path, techo_seg: float) -> dict:
    comando = [
        "docker", "run", "--rm", "-i",
        "--name", f"cc-juez-{uuid.uuid4().hex[:12]}",
        # sin red: no puede filtrar la solucion ni descargarse una
        "--network", "none",
        # sin privilegios ni forma de escalarlos
        "--user", "10001:10001",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        # filesystem de solo lectura; solo escribe en un tmpfs chico y sin ejecutar
        "--read-only",
        "--tmpfs", "/work/tmp:rw,noexec,nosuid,size=16m",
        # limites de recursos
        "--memory", f"{config.juez.memoria_mb}m",
        "--memory-swap", f"{config.juez.memoria_mb}m",   # swap 0: no puede esquivar el limite
        "--cpus", "1.0",
        "--pids-limit", "64",
        "--ulimit", "nofile=64:64",
        "--ulimit", "core=0",
        # el trabajo entra montado de solo lectura
        "--mount", f"type=bind,source={trabajo},target=/work,readonly",
        "--workdir", "/work/tmp",
        config.juez.imagen,
        "/work/manifiesto.json",
    ]
    return _invocar(comando, techo_seg)


def _correr_local(trabajo: Path, techo_seg: float) -> dict:
    import sys
    return _invocar([sys.executable, str(RUNNER), str(trabajo / "manifiesto.json")], techo_seg)


def _invocar(comando: list[str], techo_seg: float) -> dict:
    try:
        proceso = subprocess.run(
            comando,
            capture_output=True,
            timeout=max(15.0, techo_seg + 20.0),
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {"veredicto": "TLE", "detalle": "la entrega se colgo y hubo que cortar la ejecucion entera"}
    except FileNotFoundError as e:
        return {"veredicto": "IE", "detalle": f"no se encontro el ejecutable del juez: {e}"}
    except OSError as e:
        return {"veredicto": "IE", "detalle": f"no se pudo lanzar el juez: {e}"}

    salida = (proceso.stdout or "").strip()
    if not salida:
        err = (proceso.stderr or "").strip()[-500:]
        # 137 = el contenedor entero fue matado por OOM
        if proceso.returncode == 137:
            return {"veredicto": "MLE", "detalle": "el proceso consumio toda la memoria disponible"}
        return {"veredicto": "IE", "detalle": f"el juez no devolvio nada (codigo {proceso.returncode}): {err}"}

    # el runner imprime una sola linea de JSON; si algo mas ensucio stdout, tomamos la ultima
    try:
        return json.loads(salida.splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"veredicto": "IE", "detalle": f"respuesta ilegible del juez: {salida[:300]}"}


def _interpretar(crudo: dict, solo_samples: bool) -> Resultado:
    veredicto = str(crudo.get("veredicto", "IE")).upper()
    if veredicto not in VEREDICTOS:
        veredicto = "IE"

    detalle = str(crudo.get("detalle", ""))
    # el detalle de un caso secreto revela informacion del test: se oculta salvo
    # que el fallo haya sido en un caso publico (ahi ayuda y no filtra nada)
    if veredicto in ("WA", "PE") and not solo_samples and not crudo.get("fallo_publico"):
        detalle = ""

    return Resultado(
        veredicto=veredicto,
        detalle=detalle,
        caso_fallido=crudo.get("caso_fallido"),
        tiempo_ms=int(crudo.get("tiempo_max_ms") or 0),
        subtareas_ok=list(crudo.get("subtareas_ok") or []),
        casos=list(crudo.get("casos") or []),
    )


def imagen_disponible() -> bool:
    """True si la imagen del juez ya esta construida. Lo usa el chequeo de arranque."""
    if config.juez.backend != "docker":
        return True
    try:
        r = subprocess.run(["docker", "image", "inspect", config.juez.imagen],
                           capture_output=True, timeout=20)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def construir_imagen() -> tuple[bool, str]:
    """Construye la imagen del juez. Devuelve (ok, salida)."""
    try:
        r = subprocess.run(
            ["docker", "build", "-t", config.juez.imagen, str(RAIZ / "judge")],
            capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace",
        )
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
