"""Medidas anti-trampa.

La filosofia es **quitarle sentido a hacer trampa**, no cazar gente. Cuatro capas:

1. Analisis estatico: se rechaza codigo que intenta salirse del problema (leer los
   archivos de test, abrir red, escribir en disco, meterse con el proceso).
2. Sandbox: aunque el analisis se le escape algo, el contenedor no tiene red ni
   filesystem escribible. Ver `judge.py`. Esta es la defensa que realmente cuenta.
3. Similitud entre entregas: se comparan huellas de codigo normalizado entre
   participantes del mismo problema, y lo muy parecido queda marcado para revision
   humana. **Nunca se sanciona automaticamente**: dos soluciones correctas de un
   problema facil se parecen legitimamente.
4. Limites de ritmo: cooldown entre entregas y tope de intentos, para que no se
   pueda adivinar la respuesta a fuerza de reenviar.

Nada de esto reemplaza el criterio humano. Todo queda en la tabla `auditoria`.
"""

from __future__ import annotations

import ast
import hashlib
import io
import re
import tokenize
from dataclasses import dataclass

from . import db
from .config import config

# --- capa 1: analisis estatico -------------------------------------------------

#: modulos que no tienen ningun uso legitimo resolviendo un problema de olimpiada
MODULOS_PROHIBIDOS = frozenset({
    "io", "socket", "http", "urllib", "urllib2", "urllib3", "requests", "httpx", "ftplib",
    "smtplib", "telnetlib", "asyncio", "selectors", "ssl", "xmlrpc",
    "subprocess", "multiprocessing", "ctypes", "cffi", "mmap", "signal", "pty", "tty",
    "shutil", "tempfile", "pathlib", "glob", "fileinput", "sqlite3", "dbm", "shelve",
    "pickle", "marshal", "importlib", "imp", "runpy", "site", "sysconfig",
    "webbrowser", "platform", "pwd", "grp", "resource", "gc", "inspect",
})

#: nombres que permiten esquivar el analisis o tocar cosas del sistema
LLAMADAS_PROHIBIDAS = frozenset({
    "eval", "exec", "compile", "open", "__import__", "input_file",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "memoryview", "breakpoint", "help",
})

#: atributos cuyo uso casi siempre es un intento de escapar del sandbox
ATRIBUTOS_PROHIBIDOS = frozenset({
    "__subclasses__", "__globals__", "__builtins__", "__bases__", "__mro__",
    "__code__", "__closure__", "__reduce__", "__reduce_ex__", "__getattribute__",
    "__class__",
})

#: `os` se permite parcialmente porque `os.path` y `os.sep` aparecen en codigo normal
ATRIBUTOS_OS_PROHIBIDOS = frozenset({
    "system", "popen", "spawn", "spawnl", "spawnv", "exec", "execl", "execv", "execve",
    "fork", "forkpty", "kill", "remove", "unlink", "rmdir", "removedirs", "rename",
    "mkdir", "makedirs", "chmod", "chown", "environ", "putenv", "setuid", "setgid",
    "listdir", "walk", "scandir", "open", "read", "write", "dup", "dup2", "pipe",
})


@dataclass
class Hallazgo:
    linea: int
    motivo: str


class Inspector(ast.NodeVisitor):
    """Recorre el AST buscando cosas que no deberian estar en una solucion."""

    def __init__(self) -> None:
        self.hallazgos: list[Hallazgo] = []

    def _marcar(self, nodo: ast.AST, motivo: str) -> None:
        self.hallazgos.append(Hallazgo(getattr(nodo, "lineno", 0), motivo))

    def visit_Import(self, nodo: ast.Import) -> None:
        for alias in nodo.names:
            raiz = alias.name.split(".")[0]
            if raiz in MODULOS_PROHIBIDOS:
                self._marcar(nodo, f"importa el modulo '{alias.name}', que no esta permitido")
        self.generic_visit(nodo)

    def visit_ImportFrom(self, nodo: ast.ImportFrom) -> None:
        raiz = (nodo.module or "").split(".")[0]
        if raiz in MODULOS_PROHIBIDOS:
            self._marcar(nodo, f"importa desde '{nodo.module}', que no esta permitido")
        if nodo.level and nodo.level > 0:
            self._marcar(nodo, "usa un import relativo, que no tiene sentido en una entrega")
        self.generic_visit(nodo)

    def visit_Call(self, nodo: ast.Call) -> None:
        f = nodo.func
        if isinstance(f, ast.Name) and f.id in LLAMADAS_PROHIBIDAS:
            self._marcar(nodo, f"llama a '{f.id}()', que no esta permitido")
        if isinstance(f, ast.Attribute):
            if isinstance(f.value, ast.Name) and f.value.id == "os" and f.attr in ATRIBUTOS_OS_PROHIBIDOS:
                self._marcar(nodo, f"llama a 'os.{f.attr}()', que no esta permitido")
            if f.attr in ATRIBUTOS_PROHIBIDOS:
                self._marcar(nodo, f"usa '{f.attr}', que sirve para escaparse del sandbox")
        self.generic_visit(nodo)

    def visit_Attribute(self, nodo: ast.Attribute) -> None:
        if nodo.attr in ATRIBUTOS_PROHIBIDOS:
            self._marcar(nodo, f"usa '{nodo.attr}', que sirve para escaparse del sandbox")
        if isinstance(nodo.value, ast.Name) and nodo.value.id == "os" and nodo.attr in ATRIBUTOS_OS_PROHIBIDOS:
            self._marcar(nodo, f"usa 'os.{nodo.attr}', que no esta permitido")
        self.generic_visit(nodo)


def revisar_codigo(fuente: str) -> list[Hallazgo]:
    """Analiza la entrega. Lista vacia = no se encontro nada raro.

    Si el codigo no parsea devolvemos vacio: eso lo detecta el juez como CE, y no
    queremos acusar de trampa a alguien que simplemente se olvido dos puntos.
    """
    try:
        arbol = ast.parse(fuente)
    except (SyntaxError, ValueError):
        return []

    inspector = Inspector()
    inspector.visit(arbol)
    return inspector.hallazgos


# --- capa 3: similitud entre entregas -----------------------------------------

#: tamanio de los k-gramas de tokens. 9 es el valor tipico en la literatura de MOSS.
K_GRAMA = 9
#: ventana del winnowing: garantiza detectar coincidencias de >= K+W-1 tokens
VENTANA = 4


def normalizar_tokens(fuente: str) -> list[str]:
    """Convierte el codigo a una secuencia de tokens sin nombres ni formato.

    Renombrar variables, cambiar la indentacion o agregar comentarios no cambia el
    resultado: eso es justamente lo que hace alguien que copia y disimula.
    """
    salida: list[str] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(fuente).readline):
            if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                            tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING,
                            tokenize.ENDMARKER):
                continue
            if tok.type == tokenize.NAME:
                # las palabras reservadas y los builtins se conservan porque definen
                # la estructura; el resto son nombres del autor y se anonimizan
                salida.append(tok.string if _es_estructural(tok.string) else "N")
            elif tok.type == tokenize.NUMBER:
                salida.append("0")
            elif tok.type == tokenize.STRING:
                salida.append("S")
            else:
                salida.append(tok.string)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # codigo roto: caemos a un tokenizado grosero para no perder la senal
        return re.findall(r"[A-Za-z_]+|\d+|\S", fuente)
    return salida


_PALABRAS_ESTRUCTURALES = frozenset({
    "if", "else", "elif", "for", "while", "def", "class", "return", "yield", "import",
    "from", "in", "not", "and", "or", "is", "None", "True", "False", "try", "except",
    "finally", "raise", "with", "as", "lambda", "pass", "break", "continue", "global",
    "nonlocal", "assert", "del", "await", "async",
    "print", "input", "range", "len", "int", "str", "float", "list", "dict", "set",
    "tuple", "sum", "min", "max", "sorted", "abs", "map", "filter", "zip", "enumerate",
})


def _es_estructural(nombre: str) -> bool:
    return nombre in _PALABRAS_ESTRUCTURALES


def huellas(fuente: str) -> set[int]:
    """Fingerprints por winnowing: un subconjunto estable de hashes de k-gramas.

    Winnowing (Schleimer, Wilkerson & Aiken, 2003): de cada ventana de hashes se
    guarda el minimo. Eso reduce el volumen a comparar y ademas garantiza que
    cualquier coincidencia suficientemente larga sea detectada.
    """
    tokens = normalizar_tokens(fuente)
    if len(tokens) < K_GRAMA:
        return set()

    hashes = [
        int.from_bytes(hashlib.blake2b(" ".join(tokens[i:i + K_GRAMA]).encode(),
                                       digest_size=8).digest(), "big")
        for i in range(len(tokens) - K_GRAMA + 1)
    ]
    if len(hashes) < VENTANA:
        return set(hashes)

    elegidos: set[int] = set()
    for i in range(len(hashes) - VENTANA + 1):
        elegidos.add(min(hashes[i:i + VENTANA]))
    return elegidos


def similitud(a: set[int], b: set[int]) -> float:
    """Indice de Jaccard entre dos conjuntos de huellas. 0 = nada en comun, 1 = identico."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def hash_codigo(fuente: str) -> str:
    """Hash del codigo normalizado. Sirve para detectar reenvios identicos."""
    return hashlib.sha256(" ".join(normalizar_tokens(fuente)).encode()).hexdigest()


def buscar_parecidos(fuente: str, problema_ronda_id: int, usuario: str) -> list[tuple[str, float]]:
    """Compara contra las entregas de otros participantes en el mismo problema.

    Devuelve `[(numero_del_otro, similitud)]` por encima del umbral, mas parecido
    primero. Solo se compara contra **otros** usuarios: reenviarte a vos mismo una
    version corregida de tu propio codigo es lo normal y no es sospechoso.
    """
    mias = huellas(fuente)
    if not mias:
        return []

    filas = db.consultar(
        "SELECT usuario, fingerprints FROM huellas WHERE problema_ronda_id = ? AND usuario != ?",
        (problema_ronda_id, usuario),
    )

    mejor_por_usuario: dict[str, float] = {}
    for fila in filas:
        try:
            otras = {int(x) for x in fila["fingerprints"].split(",") if x}
        except ValueError:
            continue
        s = similitud(mias, otras)
        if s > mejor_por_usuario.get(fila["usuario"], 0.0):
            mejor_por_usuario[fila["usuario"]] = s

    umbral = config.antitrampa.similitud_umbral
    return sorted(((u, s) for u, s in mejor_por_usuario.items() if s >= umbral),
                  key=lambda par: -par[1])


def guardar_huellas(entrega_id: int, problema_ronda_id: int, usuario: str, fuente: str) -> None:
    huella = huellas(fuente)
    if not huella:
        return
    db.ejecutar(
        "INSERT OR REPLACE INTO huellas (entrega_id, problema_ronda_id, usuario, fingerprints) "
        "VALUES (?, ?, ?, ?)",
        (entrega_id, problema_ronda_id, usuario, ",".join(str(h) for h in sorted(huella))),
    )


# --- capa 4: limites de ritmo --------------------------------------------------

@dataclass
class Veto:
    """Motivo por el que una entrega no se acepta. `None` significa que puede pasar."""
    motivo: str
    espera_seg: int = 0


def revisar_limites(usuario: str, problema_ronda_id: int) -> Veto | None:
    """Cooldown entre entregas y tope de intentos por problema."""
    fila = db.uno("SELECT bloqueado FROM usuarios WHERE numero = ?", (usuario,))
    if fila and fila["bloqueado"]:
        return Veto("tu cuenta esta suspendida. hablalo con un admin.")

    ultima = db.uno(
        "SELECT enviada_en FROM entregas WHERE usuario = ? ORDER BY id DESC LIMIT 1",
        (usuario,),
    )
    if ultima:
        momento = db.desde_iso(ultima["enviada_en"])
        if momento:
            pasados = (db.ahora() - momento).total_seconds()
            cooldown = config.antitrampa.cooldown_seg
            if pasados < cooldown:
                falta = int(cooldown - pasados) + 1
                return Veto(f"espera {falta} segundos antes de mandar otra entrega.", falta)

    intentos = db.uno(
        "SELECT COUNT(*) AS n FROM entregas WHERE usuario = ? AND problema_ronda_id = ? AND anulada = 0",
        (usuario, problema_ronda_id),
    )
    maximo = config.antitrampa.max_intentos
    if intentos and intentos["n"] >= maximo:
        return Veto(f"ya usaste tus {maximo} intentos en este problema.")

    return None


def es_reenvio_identico(usuario: str, problema_ronda_id: int, codigo_hash: str) -> bool:
    """True si este usuario ya mando exactamente este codigo para este problema.

    Sin esto, alguien podria reenviar lo mismo hasta que un TLE al limite pase por
    suerte. Ademas evita gastarle un intento a quien manda dos veces sin querer.
    """
    fila = db.uno(
        "SELECT 1 FROM entregas WHERE usuario = ? AND problema_ronda_id = ? AND codigo_hash = ? LIMIT 1",
        (usuario, problema_ronda_id, codigo_hash),
    )
    return fila is not None
