#!/usr/bin/env python3
"""Ejecutor de entregas. Corre DENTRO del contenedor del juez.

Recibe un manifiesto JSON con la solucion y las **entradas** de los casos, corre
cada uno con limites de recursos, y devuelve lo que la solucion imprimio.

Dos decisiones de diseno importantes:

1. **Aca no se compara nada.** Las respuestas esperadas nunca entran al
   contenedor. Si entraran, una entrega que logre leer un archivo tendria las
   respuestas servidas, y ninguna lista negra de imports puede garantizar que eso
   no pase. La comparacion la hace el host (`core/contest/comparador.py`).

2. **La salida va a un archivo, no a un pipe.** Un `print` en un ciclo infinito
   llenaria la memoria del propio runner si leyeramos de un pipe. Escribiendo al
   tmpfs, el limite de tamanio del tmpfs actua de techo y despues leemos solo el
   primer trozo.

Se escribio con solo la biblioteca estandar y no importa nada del resto del
proyecto: la imagen del juez no tiene el codigo del bot adentro.

    python runner.py manifiesto.json > resultado.json
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import resource  # solo en POSIX
except ImportError:  # pragma: no cover - Windows
    resource = None  # type: ignore[assignment]

#: cuanto de la salida devolvemos.
#:
#: Tiene que dar lugar a respuestas legitimas grandes: un problema con 200000
#: numeros de salida son mas de 2 MB. Si el techo queda corto, una solucion
#: correcta recibe WA sin que nadie entienda por que. Cuando se supera, NO se
#: trunca en silencio: se devuelve un veredicto explicito.
MAX_SALIDA = 8 << 20        # 8 MiB
MAX_STDERR = 4096
#: techo duro de escritura del proceso hijo (RLIMIT_FSIZE)
MAX_ARCHIVO = 32 << 20      # 32 MiB


def _limitar(memoria_mb: int, cpu_seg: int):
    """preexec_fn que aplica los rlimits al proceso hijo."""
    if resource is None:
        return None

    def aplicar() -> None:
        # nuevo grupo de procesos: nos deja matar a los hijos que haya dejado colgados
        os.setsid()
        bytes_mem = memoria_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (bytes_mem, bytes_mem))
        resource.setrlimit(resource.RLIMIT_DATA, (bytes_mem, bytes_mem))
        # +1s de gracia: preferimos cortar por reloj de pared, que es mas preciso
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


def correr_caso(fuente: Path, entrada: str, tiempo_ms: int, memoria_mb: int, cwd: Path) -> dict:
    """Corre la solucion con una entrada. Devuelve estado, salida y tiempo."""
    limite_seg = tiempo_ms / 1000.0
    cpu_seg = max(1, int(limite_seg) + 1)

    # -I: modo aislado (ignora PYTHONPATH, el entorno y el dir del usuario)
    # -S: no carga site, arranca mas rapido y expone menos superficie
    comando = [sys.executable, "-I", "-S", str(fuente)]

    entorno = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(cwd),
        "TMPDIR": str(cwd),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    archivo_salida = tempfile.NamedTemporaryFile(dir=str(cwd), suffix=".out", delete=False)
    ruta_salida = Path(archivo_salida.name)

    arranque = time.monotonic()
    expiro = False
    try:
        proceso = subprocess.Popen(
            comando,
            stdin=subprocess.PIPE,
            stdout=archivo_salida,
            stderr=subprocess.PIPE,
            cwd=str(cwd),
            env=entorno,
            preexec_fn=_limitar(memoria_mb, cpu_seg),
            close_fds=True,
        )
    except OSError as e:
        archivo_salida.close()
        ruta_salida.unlink(missing_ok=True)
        return {"estado": "IE", "detalle": f"no se pudo lanzar el proceso: {e}",
                "tiempo_ms": 0, "salida": "", "stderr": ""}

    try:
        try:
            _, err_b = proceso.communicate(entrada.encode("utf-8"), timeout=limite_seg)
        except subprocess.TimeoutExpired:
            expiro = True
            _matar(proceso)
            try:
                _, err_b = proceso.communicate(timeout=5)
            except Exception:
                err_b = b""
        except (BrokenPipeError, OSError):
            # el programa cerro stdin antes de que terminemos de escribirle:
            # es valido (por ejemplo si solo lee la primera linea)
            err_b = b""
    finally:
        archivo_salida.close()

    transcurrido = int((time.monotonic() - arranque) * 1000)

    # se lee un byte de mas para poder distinguir "justo entra" de "se paso"
    desbordo = False
    try:
        with ruta_salida.open("rb") as f:
            crudo = f.read(MAX_SALIDA + 1)
        if len(crudo) > MAX_SALIDA:
            desbordo = True
            crudo = crudo[:MAX_SALIDA]
        salida = crudo.decode("utf-8", errors="replace")
    except OSError:
        salida = ""
    finally:
        ruta_salida.unlink(missing_ok=True)

    err = (err_b or b"")[-MAX_STDERR:].decode("utf-8", errors="replace")
    codigo = proceso.returncode

    if expiro:
        return {"estado": "TLE", "detalle": f"supero el limite de {tiempo_ms} ms",
                "tiempo_ms": transcurrido, "salida": salida, "stderr": err}

    # se avisa explicitamente en vez de comparar una salida truncada: si no, una
    # solucion que imprime de mas recibe un WA que no explica nada
    if desbordo:
        return {"estado": "RE",
                "detalle": f"imprimio mas de {MAX_SALIDA // (1 << 20)} MB de salida",
                "tiempo_ms": transcurrido, "salida": "", "stderr": err}

    if codigo != 0:
        if "MemoryError" in err:
            return {"estado": "MLE", "detalle": f"supero los {memoria_mb} MB",
                    "tiempo_ms": transcurrido, "salida": salida, "stderr": err}
        if codigo in (-9, 137):                      # SIGKILL: casi siempre el OOM killer
            return {"estado": "MLE", "detalle": "el proceso fue terminado por consumo de memoria",
                    "tiempo_ms": transcurrido, "salida": salida, "stderr": err}
        if codigo in (-24, 152):                     # SIGXCPU
            return {"estado": "TLE", "detalle": "supero el limite de CPU",
                    "tiempo_ms": transcurrido, "salida": salida, "stderr": err}
        if codigo in (-25, 153):                     # SIGXFSZ: escribio de mas
            return {"estado": "RE", "detalle": "genero demasiada salida",
                    "tiempo_ms": transcurrido, "salida": salida, "stderr": err}
        return {"estado": "RE", "detalle": _resumir_error(err) or f"termino con codigo {codigo}",
                "tiempo_ms": transcurrido, "salida": salida, "stderr": err}

    return {"estado": "OK", "detalle": "", "tiempo_ms": transcurrido,
            "salida": salida, "stderr": err}


def _resumir_error(stderr: str) -> str:
    """Ultima linea util del traceback, que es la que le sirve al participante."""
    lineas = [l.strip() for l in stderr.strip().splitlines() if l.strip()]
    if not lineas:
        return ""
    for linea in reversed(lineas):
        if not linea.startswith(('File "', "Traceback", "  ")):
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


def ejecutar(manifiesto: dict) -> dict:
    """Corre todos los casos y devuelve las salidas crudas, sin juzgarlas."""
    trabajo = Path(manifiesto["dir_trabajo"])
    fuente = Path(manifiesto["fuente"])
    tiempo_ms = int(manifiesto.get("tiempo_ms", 2000))
    memoria_mb = int(manifiesto.get("memoria_mb", 256))
    casos = manifiesto.get("casos", []) or []
    # sin subtareas no tiene sentido seguir despues del primer fallo: es todo o nada
    seguir_tras_fallo = bool(manifiesto.get("tiene_subtareas"))

    error_sintaxis = verificar_sintaxis(fuente)
    if error_sintaxis:
        return {"compila": False, "detalle": error_sintaxis, "casos": []}

    resultados = []
    for indice, caso in enumerate(casos, start=1):
        try:
            entrada = Path(caso["entrada"]).read_text(encoding="utf-8")
        except OSError as e:
            resultados.append({"numero": indice, "estado": "IE",
                               "detalle": f"no se pudo leer la entrada: {e}",
                               "tiempo_ms": 0, "salida": ""})
            break

        corrida = correr_caso(fuente, entrada, tiempo_ms, memoria_mb, trabajo)
        corrida["numero"] = indice
        corrida.pop("stderr", None)          # el host no lo necesita
        resultados.append(corrida)

        if corrida["estado"] != "OK" and not seguir_tras_fallo:
            break

    return {"compila": True, "detalle": "", "casos": resultados}


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "uso: runner.py manifiesto.json"}))
        return 2
    try:
        manifiesto = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        print(json.dumps(ejecutar(manifiesto), ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 - el runner nunca debe salir sin JSON
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
