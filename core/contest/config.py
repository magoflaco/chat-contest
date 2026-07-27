"""Configuracion global, leida de variables de entorno / .env.

Todo lo que se puede tunear vive aca. Si agregas una opcion nueva, sumala tambien
a `.env.example` para que el resto del club sepa que existe.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# raiz del repo: core/contest/config.py -> core/contest -> core -> raiz
RAIZ = Path(__file__).resolve().parents[2]


def _cargar_dotenv() -> None:
    """Lee .env sin depender de python-dotenv.

    Las variables ya presentes en el entorno ganan, asi systemd/docker pueden
    sobrescribir sin tocar el archivo.
    """
    archivo = RAIZ / ".env"
    if not archivo.is_file():
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        os.environ.setdefault(clave, valor)


_cargar_dotenv()


def _txt(clave: str, defecto: str = "") -> str:
    return os.environ.get(clave, defecto).strip()


def _entero(clave: str, defecto: int) -> int:
    try:
        return int(_txt(clave) or defecto)
    except ValueError:
        return defecto


def _decimal(clave: str, defecto: float) -> float:
    try:
        return float(_txt(clave) or defecto)
    except ValueError:
        return defecto


def _lista(clave: str) -> list[str]:
    return [x.strip() for x in _txt(clave).split(",") if x.strip()]


def _zona(nombre: str) -> ZoneInfo:
    try:
        return ZoneInfo(nombre)
    except (ZoneInfoNotFoundError, ValueError):
        # en Windows sin tzdata esto puede fallar; UTC es un fallback seguro
        return ZoneInfo("UTC")


@dataclass(frozen=True)
class ConfigJuez:
    backend: str = field(default_factory=lambda: _txt("JUDGE_BACKEND", "docker"))
    imagen: str = field(default_factory=lambda: _txt("JUDGE_IMAGE", "chat-contest-judge:latest"))
    timeout_ms: int = field(default_factory=lambda: _entero("JUDGE_TIMEOUT_MS", 5000))
    memoria_mb: int = field(default_factory=lambda: _entero("JUDGE_MEMORY_MB", 256))
    max_fuente_bytes: int = field(default_factory=lambda: _entero("JUDGE_MAX_SOURCE_BYTES", 65536))
    #: multiplica el limite de tiempo de TODOS los problemas.
    #:
    #: Los limites de cada problema se calibran en la maquina de quien lo escribe,
    #: que casi siempre es mas rapida que el servidor. Sin esto, una solucion
    #: correcta puede recibir TLE en produccion y el chico no entiende por que.
    #: Se mide con `python -m contest.cli calibrar` y se pone en el .env.
    factor_tiempo: float = field(default_factory=lambda: _decimal("JUDGE_TIME_FACTOR", 1.0))
    # margen que le damos al contenedor por encima del limite del problema,
    # para que el overhead de arranque de python no se cuente como TLE del alumno
    overhead_ms: int = 3000


@dataclass(frozen=True)
class ConfigRondas:
    cada_dias: int = field(default_factory=lambda: _entero("RONDA_CADA_DIAS", 3))
    hora: int = field(default_factory=lambda: _entero("RONDA_HORA", 18))
    tz_nombre: str = field(default_factory=lambda: _txt("RONDA_TZ", "America/Argentina/Buenos_Aires"))
    dificultades: tuple[int, ...] = field(
        default_factory=lambda: tuple(int(x) for x in (_lista("RONDA_DIFICULTADES") or ["1", "3", "5"]))
    )

    @property
    def tz(self) -> ZoneInfo:
        return _zona(self.tz_nombre)

    @property
    def ventana_horas(self) -> int:
        """La ronda queda abierta hasta que arranca la siguiente."""
        return self.cada_dias * 24


@dataclass(frozen=True)
class ConfigAntiTrampa:
    cooldown_seg: int = field(default_factory=lambda: _entero("COOLDOWN_ENTREGA_SEG", 45))
    max_intentos: int = field(default_factory=lambda: _entero("MAX_INTENTOS", 12))
    similitud_umbral: float = field(default_factory=lambda: _decimal("SIMILITUD_UMBRAL", 0.82))


@dataclass(frozen=True)
class ConfigIA:
    api_key: str = field(default_factory=lambda: _txt("NVIDIA_API_KEY"))
    base_url: str = field(default_factory=lambda: _txt("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"))
    modelo: str = field(default_factory=lambda: _txt("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct"))
    timeout_seg: int = 120

    @property
    def habilitada(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class Config:
    bot_name: str = field(default_factory=lambda: _txt("BOT_NAME", "Chat Contest"))
    #: URL publica del leaderboard, se cita en los mensajes del bot
    web_url: str = field(default_factory=lambda: _txt("WEB_URL", "https://contest.itb.lat"))
    grupo_jid: str = field(default_factory=lambda: _txt("GRUPO_JID"))
    admins: tuple[str, ...] = field(default_factory=lambda: tuple(_lista("ADMINS")))

    host: str = field(default_factory=lambda: _txt("CORE_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _entero("CORE_PORT", 8000))
    token: str = field(default_factory=lambda: _txt("CORE_TOKEN"))

    juez: ConfigJuez = field(default_factory=ConfigJuez)
    rondas: ConfigRondas = field(default_factory=ConfigRondas)
    antitrampa: ConfigAntiTrampa = field(default_factory=ConfigAntiTrampa)
    ia: ConfigIA = field(default_factory=ConfigIA)

    @property
    def db_path(self) -> Path:
        bruto = _txt("DB_PATH", "var/contest.db")
        p = Path(bruto)
        return p if p.is_absolute() else RAIZ / p

    @property
    def dir_problemas(self) -> Path:
        return RAIZ / "data" / "problems"

    @property
    def dir_entregas(self) -> Path:
        return RAIZ / "submissions"

    def es_admin(self, numero: str) -> bool:
        return numero in self.admins


config = Config()
