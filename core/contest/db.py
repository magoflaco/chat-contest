"""Capa de base de datos: SQLite con sqlite3 pelado.

Elegimos sqlite3 de la stdlib en vez de un ORM a proposito: cualquiera del club
puede abrir `var/contest.db` con DB Browser y entender que pasa, y no hay que
aprender una libreria nueva para aportar.

Todas las fechas se guardan como texto ISO-8601 en **UTC**. Convertir a hora local
es responsabilidad de la capa que muestra.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import config

ESQUEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- participantes. la identidad es el numero de whatsapp normalizado.
CREATE TABLE IF NOT EXISTS usuarios (
    numero        TEXT PRIMARY KEY,
    nombre        TEXT NOT NULL DEFAULT '',
    alias         TEXT,
    creado_en     TEXT NOT NULL,
    visto_en      TEXT NOT NULL,
    bloqueado     INTEGER NOT NULL DEFAULT 0,
    nota_admin    TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_usuarios_alias ON usuarios(alias) WHERE alias IS NOT NULL;

-- rondas: cada N dias se abre una con varios problemas.
CREATE TABLE IF NOT EXISTS rondas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    numero        INTEGER NOT NULL UNIQUE,
    inicio        TEXT NOT NULL,
    fin           TEXT NOT NULL,
    publicada_en  TEXT,
    estado        TEXT NOT NULL DEFAULT 'programada'  -- programada | abierta | cerrada
);

-- problemas de cada ronda. el enunciado vive en data/problems/<slug>/, aca solo
-- guardamos la asignacion y el codigo publico que usan los chicos (ej: R7-B).
CREATE TABLE IF NOT EXISTS problemas_ronda (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ronda_id      INTEGER NOT NULL REFERENCES rondas(id) ON DELETE CASCADE,
    codigo        TEXT NOT NULL UNIQUE,
    slug          TEXT NOT NULL,
    dificultad    INTEGER NOT NULL,
    orden         INTEGER NOT NULL DEFAULT 0,
    UNIQUE (ronda_id, slug)
);
CREATE INDEX IF NOT EXISTS ix_pr_ronda ON problemas_ronda(ronda_id);

-- cada envio, aceptado o no. es el log inmutable del sistema.
CREATE TABLE IF NOT EXISTS entregas (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario           TEXT NOT NULL REFERENCES usuarios(numero) ON DELETE CASCADE,
    problema_ronda_id INTEGER NOT NULL REFERENCES problemas_ronda(id) ON DELETE CASCADE,
    codigo_hash       TEXT NOT NULL,
    fuente_path       TEXT NOT NULL,
    origen            TEXT NOT NULL,          -- archivo | texto
    bytes             INTEGER NOT NULL,
    enviada_en        TEXT NOT NULL,
    veredicto         TEXT NOT NULL,          -- AC WA TLE MLE RE CE PE SEC IE PENDIENTE
    detalle           TEXT NOT NULL DEFAULT '',
    caso_fallido      INTEGER,
    tiempo_ms         INTEGER,
    memoria_kb        INTEGER,
    subtareas_ok      TEXT NOT NULL DEFAULT '',   -- ids separados por coma
    puntos            INTEGER NOT NULL DEFAULT 0,
    desglose          TEXT NOT NULL DEFAULT '',
    sospechosa        INTEGER NOT NULL DEFAULT 0,
    motivo_sospecha   TEXT NOT NULL DEFAULT '',
    anulada           INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_entregas_usuario  ON entregas(usuario);
CREATE INDEX IF NOT EXISTS ix_entregas_problema ON entregas(problema_ronda_id);
CREATE INDEX IF NOT EXISTS ix_entregas_fecha    ON entregas(enviada_en);

-- el mejor resultado de cada usuario por problema. es lo que alimenta el ranking.
-- se recalcula desde `entregas`, nunca se edita a mano.
CREATE TABLE IF NOT EXISTS resultados (
    usuario           TEXT NOT NULL REFERENCES usuarios(numero) ON DELETE CASCADE,
    problema_ronda_id INTEGER NOT NULL REFERENCES problemas_ronda(id) ON DELETE CASCADE,
    puntos            INTEGER NOT NULL DEFAULT 0,
    resuelto          INTEGER NOT NULL DEFAULT 0,
    intentos          INTEGER NOT NULL DEFAULT 0,
    intentos_fallidos INTEGER NOT NULL DEFAULT 0,
    primer_ac_en      TEXT,
    segundos_hasta_ac REAL,
    entrega_id        INTEGER REFERENCES entregas(id) ON DELETE SET NULL,
    PRIMARY KEY (usuario, problema_ronda_id)
);

-- cola de mensajes salientes que el gateway de whatsapp va a despachar.
CREATE TABLE IF NOT EXISTS salientes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    destino      TEXT NOT NULL,
    texto        TEXT NOT NULL,
    adjunto_path TEXT,
    sticker      TEXT NOT NULL DEFAULT '',
    creado_en    TEXT NOT NULL,
    enviado_en   TEXT,
    intentos     INTEGER NOT NULL DEFAULT 0,
    error        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_salientes_pend ON salientes(enviado_en) WHERE enviado_en IS NULL;

-- auditoria: todo lo relevante queda registrado, sobre todo lo sospechoso.
CREATE TABLE IF NOT EXISTS auditoria (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    momento   TEXT NOT NULL,
    usuario   TEXT,
    evento    TEXT NOT NULL,
    detalle   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_auditoria_evento ON auditoria(evento);
CREATE INDEX IF NOT EXISTS ix_auditoria_momento ON auditoria(momento);

-- WhatsApp esta migrando de numeros de telefono a LIDs, y un mismo usuario puede
-- llegar identificado de las dos formas segun el chat. Sin esta tabla, la misma
-- persona aparecia dos veces en el ranking.
CREATE TABLE IF NOT EXISTS identidades (
    alias     TEXT PRIMARY KEY,       -- LID o numero, como venga
    usuario   TEXT NOT NULL,          -- la identidad canonica (el telefono si se conoce)
    visto_en  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_identidades_usuario ON identidades(usuario);

-- huellas de codigo para detectar copias entre participantes (ver antifraud.py)
CREATE TABLE IF NOT EXISTS huellas (
    entrega_id        INTEGER PRIMARY KEY REFERENCES entregas(id) ON DELETE CASCADE,
    problema_ronda_id INTEGER NOT NULL,
    usuario           TEXT NOT NULL,
    fingerprints      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_huellas_problema ON huellas(problema_ronda_id);
"""

_local = threading.local()


def ahora() -> datetime:
    """Momento actual en UTC, siempre con tzinfo."""
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    """Serializa a ISO-8601 UTC, el formato en que guardamos todas las fechas."""
    d = dt or ahora()
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat(timespec="seconds")


def desde_iso(texto: str | None) -> datetime | None:
    """Parsea una fecha guardada. Devuelve None si el campo estaba vacio."""
    if not texto:
        return None
    try:
        d = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)


def conexion() -> sqlite3.Connection:
    """Conexion por hilo. sqlite3 no permite compartirlas entre hilos."""
    con = getattr(_local, "con", None)
    if con is not None:
        return con

    ruta: Path = config.db_path
    ruta.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(ruta, timeout=15.0, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 15000")
    _local.con = con
    return con


#: columnas agregadas despues de la primera version del esquema.
#: SQLite no tiene "ADD COLUMN IF NOT EXISTS", asi que se consulta el pragma.
MIGRACIONES: list[tuple[str, str, str]] = [
    # (tabla, columna, definicion)
    ("salientes", "sticker", "TEXT NOT NULL DEFAULT ''"),
]


def _migrar() -> None:
    """Agrega las columnas que falten. Idempotente y seguro sobre datos existentes."""
    con = conexion()
    for tabla, columna, definicion in MIGRACIONES:
        existentes = {f["name"] for f in con.execute(f"PRAGMA table_info({tabla})")}
        if not existentes:
            continue                       # la tabla todavia no existe
        if columna not in existentes:
            con.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")


def inicializar() -> None:
    """Crea el esquema si falta. Es idempotente: se puede llamar en cada arranque."""
    conexion().executescript(ESQUEMA)
    _migrar()


@contextmanager
def transaccion() -> Iterator[sqlite3.Connection]:
    """Agrupa varias escrituras: o entran todas o no entra ninguna."""
    con = conexion()
    con.execute("BEGIN IMMEDIATE")
    try:
        yield con
    except Exception:
        con.execute("ROLLBACK")
        raise
    else:
        con.execute("COMMIT")


def consultar(sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
    return conexion().execute(sql, params).fetchall()


def uno(sql: str, params: tuple | dict = ()) -> sqlite3.Row | None:
    return conexion().execute(sql, params).fetchone()


def ejecutar(sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
    return conexion().execute(sql, params)


def auditar(evento: str, *, usuario: str | None = None, detalle: Any = "") -> None:
    """Registra un evento. Nunca lanza: la auditoria no puede tumbar el flujo principal."""
    try:
        ejecutar(
            "INSERT INTO auditoria (momento, usuario, evento, detalle) VALUES (?, ?, ?, ?)",
            (iso(), usuario, evento, str(detalle)[:4000]),
        )
    except sqlite3.Error:
        pass
