#!/usr/bin/env python3
"""Ejecutor de entregas. Corre DENTRO del contenedor del juez.

Recibe un manifiesto JSON con la solucion y los casos de prueba, corre cada caso
con limites de recursos, compara la salida y escribe un JSON con el veredicto.

Se escribio con solo la biblioteca estandar y a proposito **no importa nada del
resto del proyecto**: la imagen del juez no tiene el codigo del bot adentro, asi
que aunque alguien lograra escaparse del proceso hijo no encontraria nada util.

El mismo archivo se usa como fallback fuera de Docker para desarrollo local
(en Windows no hay `resource`, asi que ahi solo aplica el limite de tiempo de
pared; por eso el backend `subprocess` NO debe usarse en produccion).

Uso:
    python runner.py manifiesto.json > resultado.json
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import resource  # solo en POSIX
except ImportError:  # pragma: no cover - Windows
    resource = None  # type: ignore[assignment]

# cuanto texto de stdout/stderr guardamos como mucho, para que nadie llene el disco
MAX_SALIDA = 1 << 20        # 1 MiB
MAX_STDERR = 4096
# el proceso se mata si escribe mas que esto (RLIMIT_FSIZE + corte de lectura)
MAX_ARCHIVO = 32 << 20      # 32 MiB


def _limitar(memoria_mb: int, cpu_seg: int):
    """Devuelve el preexec_fn que aplica los rlimits al proceso hijo."""
    if resource is None:
        return None

    def aplicar() -> None:
        # nuevo grupo de procesos: nos deja matar a los hijos que haya dejado colgados
        os.setsid()
        bytes_mem = memoria_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (bytes_mem, bytes_mem))
        resource.setrlimit(resource.RLIMIT_DATA, (bytes_mem, bytes_mem))
        # +1s de gracia: preferimos cortar por tiempo de pared, que es mas preciso
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seg, cpu_seg + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_ARCHIVO, MAX_ARCHIVO))
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    return aplicar


def _matar(proceso) -> None:
    """Mata al proceso y a todo su grupo, para que no queden hijos huerfanos."""
    try:
        if resource is not None:
            os.killpg(os.getpgid(proceso.pid), 9)
        else:
            proceso.kill()
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proceso.kill()
        except OSError:
            pass


def _normalizar_tokens(texto: str) -> list[str]:
    return texto.split()


def _casi_igual(a: str, b: str, tolerancia: float) -> bool:
    """Compara dos tokens como numeros con tolerancia absoluta o relativa."""
    if a == b:
        return True
    try:
        x, y = float(a), float(b)
    except ValueError:
        return False
    if x != x or y != y:          # NaN
        return False
    if x in (float("inf"), float("-inf")) or y in (float("inf"), float("-inf")):
        return x == y
    diferencia = abs(x - y)
    return diferencia <= tolerancia or diferencia <= tolerancia * max(abs(x), abs(y))


def comparar(salida: str, esperado: str, tipo: str, tolerancia: float) -> tuple[bool, str]:
    """Compara la salida del alumno con la esperada. Devuelve (ok, motivo)."""
    if tipo == "exacta":
        # ignoramos solo el salto de linea final y los \r de Windows
        a = salida.replace("\r\n", "\n").rstrip("\n")
        b = esperado.replace("\r\n", "\n").rstrip("\n")
        if a == b:
            return True, ""
        # si difieren solo en espaciado es un error de presentacion, no de logica
        if _normalizar_tokens(a) == _normalizar_tokens(b):
            return False, "PE"
        return False, "WA"

    ta, tb = _normalizar_tokens(salida), _normalizar_tokens(esperado)
    if len(ta) != len(tb):
        return False, "WA"

    if tipo == "numerica":
        for x, y in zip(ta, tb):
            if not _casi_igual(x, y, tolerancia):
                return False, "WA"
        return True, ""

    return (ta == tb), ("" if ta == tb else "WA")


def correr_caso(fuente: Path, entrada: str, tiempo_ms: int, memoria_mb: int, cwd: Path) -> dict:
    """Corre la solucion con una entrada. Devuelve un dict con lo que paso."""
    limite_seg = tiempo_ms / 1000.0
    cpu_seg = max(1, int(limite_seg) + 1)

    # -I: modo aislado (ignora PYTHONPATH, variables de entorno y el dir del usuario)
    # -S: no carga site, arranca mas rapido y expone menos superficie
    comando = [sys.executable, "-I", "-S", str(fuente)]

    entorno = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(cwd),
        "TMPDIR": str(cwd),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONHASHSEED": "0",       # reproducible
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    arranque = time.monotonic()
    try:
        proceso = subprocess.Popen(
            comando,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(cwd),
            env=entorno,
            preexec_fn=_limitar(memoria_mb, cpu_seg),
            close_fds=True,
        )
    except OSError as e:
        return {"veredicto": "IE", "detalle": f"no se pudo lanzar el proceso: {e}",
                "tiempo_ms": 0, "salida": "", "stderr": ""}

    expiro = False
    try:
        salida_b, err_b = proceso.communicate(entrada.encode("utf-8"), timeout=limite_seg)
    except subprocess.TimeoutExpired:
        expiro = True
        _matar(proceso)
        try:
            salida_b, err_b = proceso.communicate(timeout=5)
        except Exception:
            salida_b, err_b = b"", b""
    except (BrokenPipeError, OSError):
        # el programa cerro stdin antes de que termine de escribirle: no es su culpa
        salida_b, err_b = b"", b""

    transcurrido = int((time.monotonic() - arranque) * 1000)
    salida = salida_b[:MAX_SALIDA].decode("utf-8", errors="replace")
    err = err_b[-MAX_STDERR:].decode("utf-8", errors="replace")
    codigo = proceso.returncode

    if expiro:
        return {"veredicto": "TLE", "detalle": f"supero el limite de {tiempo_ms} ms",
                "tiempo_ms": transcurrido, "salida": salida, "stderr": err}

    if codigo != 0:
        # el propio interprete avisa cuando se queda sin memoria
        if "MemoryError" in err:
            return {"veredicto": "MLE", "detalle": f"supero los {memoria_mb} MB",
                    "tiempo_ms": transcurrido, "salida": salida, "stderr": err}
        # SIGKILL suele ser el OOM killer del cgroup
        if codigo in (-9, 137):
            return {"veredicto": "MLE", "detalle": "el proceso fue terminado por consumo de memoria",
                    "tiempo_ms": transcurrido, "salida": salida, "stderr": err}
        if codigo in (-24, 152):    # SIGXCPU
            return {"veredicto": "TLE", "detalle": "supero el limite de CPU",
                    "tiempo_ms": transcurrido, "salida": salida, "stderr": err}
        return {"veredicto": "RE", "detalle": _resumir_error(err) or f"termino con codigo {codigo}",
                "tiempo_ms": transcurrido, "salida": salida, "stderr": err}

    return {"veredicto": "OK", "detalle": "", "tiempo_ms": transcurrido,
            "salida": salida, "stderr": err}


def _resumir_error(stderr: str) -> str:
    """Ultima linea util del traceback, que es la que le sirve al participante."""
    lineas = [l.strip() for l in stderr.strip().splitlines() if l.strip()]
    if not lineas:
        return ""
    for linea in reversed(lineas):
        if not linea.startswith(("File \"", "Traceback", "  ")):
            return linea[:300]
    return lineas[-1][:300]


def verificar_sintaxis(fuente: Path) -> str:
    """Compila sin ejecutar. Devuelve el mensaje de error, o '' si compila bien."""
    try:
        codigo = fuente.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"no se pudo leer el archivo: {e}"
    try:
        compile(codigo, "solucion.py", "exec")
    except SyntaxError as e:
        return f"linea {e.lineno}: {e.msg}"
    except ValueError as e:
        return str(e)
    return ""


def juzgar(manifiesto: dict) -> dict:
    """Corre todos los casos y arma el veredicto global."""
    trabajo = Path(manifiesto["dir_trabajo"])
    fuente = Path(manifiesto["fuente"])
    tiempo_ms = int(manifiesto.get("tiempo_ms", 2000))
    memoria_mb = int(manifiesto.get("memoria_mb", 256))
    validacion = manifiesto.get("validacion", {}) or {}
    tipo_val = str(validacion.get("tipo", "tokens"))
    tolerancia = float(validacion.get("tolerancia", 1e-6))
    casos = manifiesto.get("casos", []) or []

    error_sintaxis = verificar_sintaxis(fuente)
    if error_sintaxis:
        return {"veredicto": "CE", "detalle": error_sintaxis, "casos": [],
                "tiempo_max_ms": 0, "subtareas_ok": [], "caso_fallido": None}

    resultados: list[dict] = []
    tiempo_max = 0
    primer_fallo: dict | None = None

    for indice, caso in enumerate(casos, start=1):
        entrada = Path(caso["entrada"]).read_text(encoding="utf-8")
        esperado = Path(caso["esperado"]).read_text(encoding="utf-8")

        corrida = correr_caso(fuente, entrada, tiempo_ms, memoria_mb, trabajo)
        tiempo_max = max(tiempo_max, corrida["tiempo_ms"])

        if corrida["veredicto"] == "OK":
            ok, motivo = comparar(corrida["salida"], esperado, tipo_val, tolerancia)
            veredicto = "AC" if ok else (motivo or "WA")
            detalle = "" if ok else _diferencia(corrida["salida"], esperado)
        else:
            veredicto = corrida["veredicto"]
            detalle = corrida["detalle"]

        registro = {
            "numero": indice,
            "nombre": caso.get("nombre", str(indice)),
            "subtarea": caso.get("subtarea"),
            "veredicto": veredicto,
            "detalle": detalle,
            "tiempo_ms": corrida["tiempo_ms"],
            "publico": bool(caso.get("publico")),
        }
        resultados.append(registro)

        if veredicto != "AC" and primer_fallo is None:
            primer_fallo = registro
            # sin subtareas no tiene sentido seguir: es todo o nada
            if not manifiesto.get("tiene_subtareas"):
                break

    subtareas_ok = _subtareas_completas(resultados)

    if primer_fallo is None:
        return {"veredicto": "AC", "detalle": "", "casos": resultados,
                "tiempo_max_ms": tiempo_max, "subtareas_ok": subtareas_ok, "caso_fallido": None}

    return {
        "veredicto": primer_fallo["veredicto"],
        "detalle": primer_fallo["detalle"],
        "casos": resultados,
        "tiempo_max_ms": tiempo_max,
        "subtareas_ok": subtareas_ok,
        "caso_fallido": primer_fallo["numero"],
        "fallo_publico": primer_fallo["publico"],
    }


def _subtareas_completas(resultados: list[dict]) -> list[str]:
    """Ids de subtarea donde TODOS los casos dieron AC (regla del minimo, estilo IOI)."""
    por_subtarea: dict[str, bool] = {}
    for r in resultados:
        sid = r.get("subtarea")
        if not sid:
            continue
        por_subtarea[sid] = por_subtarea.get(sid, True) and (r["veredicto"] == "AC")
    return sorted(s for s, ok in por_subtarea.items() if ok)


def _diferencia(salida: str, esperado: str) -> str:
    """Mensaje corto de en que se diferencian. Solo se muestra en casos publicos."""
    a = salida.strip().splitlines()
    b = esperado.strip().splitlines()
    if len(a) != len(b):
        return f"esperaba {len(b)} linea(s) y recibi {len(a)}"
    for i, (x, y) in enumerate(zip(a, b), start=1):
        if x.strip() != y.strip():
            return f"linea {i}: esperaba '{y.strip()[:60]}' y recibi '{x.strip()[:60]}'"
    return "la salida no coincide"


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"veredicto": "IE", "detalle": "uso: runner.py manifiesto.json"}))
        return 2
    try:
        manifiesto = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        print(json.dumps(juzgar(manifiesto), ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 - el runner nunca debe reventar sin JSON
        print(json.dumps({"veredicto": "IE", "detalle": f"{type(e).__name__}: {e}",
                          "casos": [], "tiempo_max_ms": 0, "subtareas_ok": [], "caso_fallido": None}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
