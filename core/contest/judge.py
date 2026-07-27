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
from pathlib import Path, PurePosixPath

from . import comparador
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
    # armamos un directorio autocontenido con la solucion y las ENTRADAS.
    #
    # Las respuestas esperadas (.ans) NO se copian: el contenedor nunca las ve.
    # Es la unica forma de garantizar que una entrega no pueda leerlas, porque
    # cualquier lista negra de imports se puede esquivar. La comparacion la hace
    # este proceso, ya con las salidas de vuelta.
    (trabajo / "casos").mkdir()
    shutil.copyfile(fuente, trabajo / "solucion.py")

    for i, caso in enumerate(casos, start=1):
        shutil.copyfile(caso.entrada, trabajo / "casos" / f"{i:03d}.in")

    docker = config.juez.backend == "docker"
    # las rutas del manifiesto son las que ve el contenedor, que siempre es Linux.
    # `Path` en Windows produciria '\work\solucion.py', asi que para el contenedor
    # usamos PurePosixPath y afuera la ruta nativa.
    raiz = PurePosixPath("/work") if docker else trabajo

    manifiesto = {
        "dir_trabajo": "/tmp" if docker else str(trabajo),
        "fuente": str(raiz / "solucion.py"),
        "tiempo_ms": problema.tiempo_ms,
        "memoria_mb": min(problema.memoria_mb, config.juez.memoria_mb),
        "tiene_subtareas": problema.tiene_subtareas and not solo_samples,
        "casos": [{"entrada": str(raiz / "casos" / f"{i:03d}.in")}
                  for i in range(1, len(casos) + 1)],
    }
    (trabajo / "manifiesto.json").write_text(json.dumps(manifiesto), encoding="utf-8")

    # techo global: si un problema tiene 30 casos de 2s, el contenedor entero no
    # puede tardar mas que eso mas un margen de arranque
    techo_seg = (problema.tiempo_ms * len(casos) + config.juez.overhead_ms * 2) / 1000.0

    crudo = _correr_docker(trabajo, techo_seg) if docker else _correr_local(trabajo, techo_seg)
    return _juzgar_salidas(crudo, problema, casos, solo_samples)


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
        # filesystem de solo lectura; solo escribe en un tmpfs chico y sin ejecutar.
        # el tmpfs va en /tmp y NO dentro de /work: Docker no puede crear el punto
        # de montaje adentro de un bind que ya esta montado de solo lectura.
        "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=48m",
        # limites de recursos
        "--memory", f"{config.juez.memoria_mb}m",
        "--memory-swap", f"{config.juez.memoria_mb}m",   # swap 0: no puede esquivar el limite
        "--cpus", "1.0",
        "--pids-limit", "64",
        "--ulimit", "nofile=64:64",
        "--ulimit", "core=0",
        # el trabajo entra montado de solo lectura
        "--mount", f"type=bind,source={trabajo},target=/work,readonly",
        "--workdir", "/tmp",
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


def _juzgar_salidas(crudo: dict, problema: Problema, casos, solo_samples: bool) -> Resultado:
    """Compara las salidas que devolvio el contenedor contra las respuestas reales.

    Esta parte corre en el host y es la unica que toca los archivos `.ans`.
    """
    if "error" in crudo:
        return Resultado("IE", str(crudo["error"]))
    if crudo.get("veredicto") == "TLE":          # el contenedor entero se colgo
        return Resultado("TLE", str(crudo.get("detalle", "")))
    if crudo.get("veredicto") in VEREDICTOS:     # fallo antes de llegar al runner
        return Resultado(str(crudo["veredicto"]), str(crudo.get("detalle", "")))

    if not crudo.get("compila", False):
        return Resultado("CE", str(crudo.get("detalle", "")))

    publicos = {c.nombre for c in problema.samples}
    corridas = crudo.get("casos") or []

    evaluados: list[dict] = []
    tiempo_max = 0
    primer_fallo: dict | None = None

    for corrida in corridas:
        indice = int(corrida.get("numero", 0))
        if not 1 <= indice <= len(casos):
            continue
        caso = casos[indice - 1]
        tiempo_max = max(tiempo_max, int(corrida.get("tiempo_ms") or 0))

        estado = str(corrida.get("estado", "IE"))
        if estado == "OK":
            ok, motivo = comparador.comparar(
                corrida.get("salida", ""), caso.leer_esperado(),
                problema.validacion, problema.tolerancia,
            )
            veredicto = "AC" if ok else (motivo or "WA")
            detalle = "" if ok else comparador.diferencia(
                corrida.get("salida", ""), caso.leer_esperado())
        else:
            veredicto = estado if estado in VEREDICTOS else "IE"
            detalle = str(corrida.get("detalle", ""))

        registro = {
            "numero": indice,
            "nombre": caso.nombre,
            "subtarea": caso.subtarea,
            "veredicto": veredicto,
            "detalle": detalle,
            "tiempo_ms": int(corrida.get("tiempo_ms") or 0),
            "publico": caso.nombre in publicos,
        }
        evaluados.append(registro)

        if veredicto != "AC" and primer_fallo is None:
            primer_fallo = registro

    if not evaluados:
        return Resultado("IE", "el juez no devolvio ningun caso")

    subtareas_ok = _subtareas_completas(evaluados)

    if primer_fallo is None:
        # solo es AC si efectivamente se corrieron todos los casos
        if len(evaluados) < len(casos):
            return Resultado("IE", "el juez no corrio todos los casos")
        return Resultado("AC", "", None, tiempo_max, subtareas_ok, evaluados)

    detalle = primer_fallo["detalle"]
    # el detalle de un caso secreto revela contenido del test: se oculta salvo que
    # el fallo haya sido en un caso publico, donde ayuda y no filtra nada
    if primer_fallo["veredicto"] in ("WA", "PE") and not primer_fallo["publico"]:
        detalle = ""

    return Resultado(primer_fallo["veredicto"], detalle, primer_fallo["numero"],
                     tiempo_max, subtareas_ok, evaluados)


def _subtareas_completas(evaluados: list[dict]) -> list[str]:
    """Ids de subtarea donde TODOS los casos dieron AC (regla del minimo, estilo IOI)."""
    por_subtarea: dict[str, bool] = {}
    for r in evaluados:
        sid = r.get("subtarea")
        if not sid:
            continue
        por_subtarea[sid] = por_subtarea.get(sid, True) and (r["veredicto"] == "AC")
    return sorted(s for s, ok in por_subtarea.items() if ok)


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
