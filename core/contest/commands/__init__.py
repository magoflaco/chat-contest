"""Registro de comandos del bot.

Agregar un comando es esto y nada mas:

    from . import comando, Contexto

    @comando("saludo", "hola", uso="!saludo", ayuda="Te saluda.")
    def cmd_saludo(ctx: Contexto) -> str:
        return f"hola {ctx.nombre}"

Despues se importa el modulo en `cargar_todos()`, al final de este archivo.

Convenciones para el texto que devuelven los comandos:

- **Nada de emojis**, en ningun lado. Usamos texto y separadores.
- WhatsApp entiende `*negrita*`, `_cursiva_` y ```monoespaciado```.
- Que quepa en una pantalla de celular: si es largo, resumir y ofrecer un comando
  mas especifico para ver el detalle.
"""

from __future__ import annotations

import shlex
import traceback
from dataclasses import dataclass, field
from typing import Callable

from .. import db

#: prefijo de los comandos
PREFIJO = "!"


@dataclass
class Adjunto:
    """Un archivo que acompana la respuesta (por ejemplo el .py de una entrega)."""
    nombre: str
    ruta: str
    mimetype: str = "text/x-python"


@dataclass
class Contexto:
    """Todo lo que un comando necesita saber de quien lo mando."""
    numero: str
    nombre: str
    jid: str
    es_grupo: bool
    es_admin: bool
    texto: str                       # el mensaje completo, con el ! adelante
    args: str                        # lo que sigue al comando, en crudo
    adjunto_texto: str = ""          # contenido de un .py adjunto, si vino
    adjunto_nombre: str = ""

    @property
    def argv(self) -> list[str]:
        """Los argumentos partidos respetando comillas."""
        try:
            return shlex.split(self.args)
        except ValueError:
            return self.args.split()

    def arg(self, i: int, defecto: str = "") -> str:
        v = self.argv
        return v[i] if i < len(v) else defecto


@dataclass
class Respuesta:
    """Lo que un comando devuelve. Los comandos pueden devolver un str pelado."""
    texto: str
    adjuntos: list[Adjunto] = field(default_factory=list)
    #: mensajes extra a otros destinos (ej: avisar al grupo que alguien resolvio algo)
    difundir: list[tuple[str, str]] = field(default_factory=list)


Manejador = Callable[[Contexto], "str | Respuesta"]


@dataclass
class Comando:
    nombres: tuple[str, ...]
    manejador: Manejador
    uso: str
    ayuda: str
    categoria: str
    solo_admin: bool
    solo_privado: bool
    oculto: bool

    @property
    def nombre(self) -> str:
        return self.nombres[0]


REGISTRO: dict[str, Comando] = {}
COMANDOS: list[Comando] = []


def comando(*nombres: str, uso: str = "", ayuda: str = "", categoria: str = "General",
            solo_admin: bool = False, solo_privado: bool = False, oculto: bool = False):
    """Decorador que registra un comando con todos sus alias."""
    if not nombres:
        raise ValueError("un comando necesita al menos un nombre")

    def envolver(fn: Manejador) -> Manejador:
        cmd = Comando(
            nombres=tuple(n.lower() for n in nombres),
            manejador=fn,
            uso=uso or f"{PREFIJO}{nombres[0]}",
            ayuda=ayuda,
            categoria=categoria,
            solo_admin=solo_admin,
            solo_privado=solo_privado,
            oculto=oculto,
        )
        for n in cmd.nombres:
            if n in REGISTRO:
                raise ValueError(f"el comando '{n}' ya estaba registrado")
            REGISTRO[n] = cmd
        COMANDOS.append(cmd)
        return fn

    return envolver


def parsear(texto: str) -> tuple[str, str] | None:
    """Parte '!entrega R1-A codigo...' en ('entrega', 'R1-A codigo...').

    Devuelve None si el mensaje no empieza con el prefijo.
    """
    texto = (texto or "").lstrip()
    if not texto.startswith(PREFIJO):
        return None
    cuerpo = texto[len(PREFIJO):]
    if not cuerpo or cuerpo[0].isspace():
        return None
    nombre, _, resto = cuerpo.partition(" ")
    # los comandos con salto de linea inmediato son comunes al pegar codigo
    if "\n" in nombre:
        nombre, _, resto_nl = nombre.partition("\n")
        resto = f"{resto_nl}\n{resto}" if resto else resto_nl
    return nombre.strip().lower(), resto.strip("\n").strip() if resto.strip() else resto.strip()


def sugerir(nombre: str) -> str | None:
    """El comando conocido mas parecido, para cuando alguien escribe mal."""
    import difflib
    coincidencias = difflib.get_close_matches(nombre, list(REGISTRO), n=1, cutoff=0.6)
    return coincidencias[0] if coincidencias else None


def despachar(ctx: Contexto) -> Respuesta | None:
    """Ejecuta el comando que corresponda. None significa 'esto no era un comando'."""
    parseado = parsear(ctx.texto)
    if not parseado:
        return None
    nombre, args = parseado

    cmd = REGISTRO.get(nombre)
    if cmd is None:
        # en grupos ignoramos los ! desconocidos: puede ser un comando de otro bot
        if ctx.es_grupo:
            return None
        parecido = sugerir(nombre)
        texto = f"no conozco el comando {PREFIJO}{nombre}."
        if parecido:
            texto += f" quisiste decir {PREFIJO}{parecido}?"
        return Respuesta(f"{texto}\nescribi {PREFIJO}help para ver la lista.")

    if cmd.solo_admin and not ctx.es_admin:
        return Respuesta("ese comando es solo para admins.")

    if cmd.solo_privado and ctx.es_grupo:
        return Respuesta(
            f"{PREFIJO}{cmd.nombre} va por privado, no en el grupo.\n"
            "escribime directo y lo resolvemos ahi."
        )

    ctx.args = args
    try:
        salida = cmd.manejador(ctx)
    except Exception as e:  # noqa: BLE001 - un comando roto no puede tumbar el bot
        db.auditar("comando_error", usuario=ctx.numero,
                   detalle=f"{nombre}: {type(e).__name__}: {e}\n{traceback.format_exc()[:1500]}")
        return Respuesta(
            f"se rompio algo procesando {PREFIJO}{nombre}. ya quedo registrado para que lo miremos.\n"
            f"detalle: {type(e).__name__}: {e}"
        )

    if salida is None:
        return None
    return salida if isinstance(salida, Respuesta) else Respuesta(str(salida))


def cargar_todos() -> None:
    """Importa los modulos de comandos para que se registren.

    Si agregas un archivo nuevo en `commands/`, sumalo a esta lista.
    """
    from . import ayuda, admin, entrega, problemas, rank, revisar  # noqa: F401
