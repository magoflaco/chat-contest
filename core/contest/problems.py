"""Carga y validacion del banco de problemas de `data/problems/`.

Cada problema es una carpeta, con un formato inspirado en el
`problem package format` de Kattis/ICPC para que importar problemas reales sea
casi directo y para que los chicos aprendan el formato que van a ver en las
competencias de verdad:

    data/problems/<slug>/
        problema.yaml        metadatos, limites, atribucion
        enunciado.md         el enunciado en markdown
        solucion.py          solucion de referencia (la CI verifica que pase todo)
        tests/sample/*.in    casos de ejemplo, PUBLICOS (van en el enunciado)
        tests/sample/*.ans
        tests/secret/*.in    casos ocultos, con estos se juzga de verdad
        tests/secret/*.ans
        generador.py         opcional: genera los casos secretos de forma reproducible
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .config import config
from .scoring import NOMBRE_DIFICULTAD

SLUG_VALIDO = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")

TIPOS_VALIDACION = {"exacta", "tokens", "numerica"}
TIPOS_FUENTE = {"original", "icpc", "rpc", "oia", "ioi", "kattis", "generado", "otro"}


class ProblemaInvalido(Exception):
    """El YAML o los archivos del problema no cumplen el formato."""


@dataclass(frozen=True)
class Caso:
    nombre: str
    entrada: Path
    esperado: Path
    subtarea: str | None = None

    def leer_entrada(self) -> str:
        return self.entrada.read_text(encoding="utf-8")

    def leer_esperado(self) -> str:
        return self.esperado.read_text(encoding="utf-8")


@dataclass(frozen=True)
class Fuente:
    tipo: str = "original"
    nombre: str = ""
    url: str = ""
    licencia: str = ""
    anio: int | None = None

    def atribucion(self) -> str:
        """Linea de credito que se agrega al enunciado publicado."""
        if self.tipo == "original":
            return ""
        partes = [p for p in (self.nombre, str(self.anio) if self.anio else "") if p]
        credito = " ".join(partes) or self.tipo.upper()
        texto = f"Fuente: {credito}"
        if self.url:
            texto += f" - {self.url}"
        if self.licencia:
            texto += f" ({self.licencia})"
        return texto


@dataclass(frozen=True)
class Problema:
    slug: str
    titulo: str
    dificultad: int
    enunciado: str
    directorio: Path
    tags: tuple[str, ...] = ()
    autor: str = ""
    tiempo_ms: int = 2000
    memoria_mb: int = 256
    validacion: str = "tokens"
    tolerancia: float = 1e-6
    subtareas: tuple[dict[str, Any], ...] = ()
    editorial: str = ""
    pistas: tuple[str, ...] = ()
    fuente: Fuente = field(default_factory=Fuente)

    @property
    def nombre_dificultad(self) -> str:
        return NOMBRE_DIFICULTAD.get(self.dificultad, "?")

    @property
    def tiene_subtareas(self) -> bool:
        return bool(self.subtareas)

    def casos(self, grupo: str) -> list[Caso]:
        """Casos de `sample` o de `secret`, ordenados por nombre."""
        base = self.directorio / "tests" / grupo
        if not base.is_dir():
            return []

        encontrados: list[Caso] = []
        # los casos secretos pueden estar sueltos o agrupados por subtarea en subcarpetas
        for entrada in sorted(base.rglob("*.in")):
            esperado = entrada.with_suffix(".ans")
            if not esperado.is_file():
                continue
            rel = entrada.relative_to(base)
            subtarea = rel.parts[0] if len(rel.parts) > 1 else None
            encontrados.append(
                Caso(nombre=str(rel.with_suffix("")).replace("\\", "/"),
                     entrada=entrada, esperado=esperado, subtarea=subtarea)
            )
        return encontrados

    @property
    def samples(self) -> list[Caso]:
        return self.casos("sample")

    @property
    def secretos(self) -> list[Caso]:
        return self.casos("secret")

    def solucion_referencia(self) -> Path | None:
        ruta = self.directorio / "solucion.py"
        return ruta if ruta.is_file() else None


def _exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise ProblemaInvalido(mensaje)


def cargar(directorio: Path) -> Problema:
    """Lee y valida un problema. Lanza `ProblemaInvalido` con un mensaje util."""
    yml = directorio / "problema.yaml"
    _exigir(yml.is_file(), f"{directorio.name}: falta problema.yaml")

    try:
        datos = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ProblemaInvalido(f"{directorio.name}: YAML mal formado: {e}") from e
    _exigir(isinstance(datos, dict), f"{directorio.name}: problema.yaml debe ser un mapa")

    slug = str(datos.get("slug") or directorio.name).strip()
    _exigir(bool(SLUG_VALIDO.match(slug)),
            f"{directorio.name}: slug invalido '{slug}' (minusculas, numeros y guiones)")
    _exigir(slug == directorio.name,
            f"{directorio.name}: el slug '{slug}' no coincide con el nombre de la carpeta")

    titulo = str(datos.get("titulo") or "").strip()
    _exigir(bool(titulo), f"{slug}: falta 'titulo'")

    try:
        dificultad = int(datos.get("dificultad"))
    except (TypeError, ValueError):
        raise ProblemaInvalido(f"{slug}: 'dificultad' debe ser un entero de 1 a 5") from None
    _exigir(1 <= dificultad <= 5, f"{slug}: 'dificultad' debe estar entre 1 y 5, no {dificultad}")

    md = directorio / "enunciado.md"
    enunciado = md.read_text(encoding="utf-8").strip() if md.is_file() else str(datos.get("enunciado", "")).strip()
    _exigir(bool(enunciado), f"{slug}: falta el enunciado (enunciado.md o clave 'enunciado')")

    limites = datos.get("limites") or {}
    _exigir(isinstance(limites, dict), f"{slug}: 'limites' debe ser un mapa")
    tiempo_ms = int(limites.get("tiempo_ms", 2000))
    memoria_mb = int(limites.get("memoria_mb", 256))
    _exigir(200 <= tiempo_ms <= 15000, f"{slug}: tiempo_ms fuera de rango (200..15000)")
    _exigir(32 <= memoria_mb <= 1024, f"{slug}: memoria_mb fuera de rango (32..1024)")

    val = datos.get("validacion") or {}
    _exigir(isinstance(val, dict), f"{slug}: 'validacion' debe ser un mapa")
    tipo_val = str(val.get("tipo", "tokens")).lower()
    _exigir(tipo_val in TIPOS_VALIDACION,
            f"{slug}: validacion.tipo '{tipo_val}' no valido (usa: {', '.join(sorted(TIPOS_VALIDACION))})")

    subtareas = tuple(datos.get("subtareas") or ())
    for s in subtareas:
        _exigir(isinstance(s, dict) and "id" in s and "peso" in s,
                f"{slug}: cada subtarea necesita 'id' y 'peso'")

    fuente_raw = datos.get("fuente") or {}
    _exigir(isinstance(fuente_raw, dict), f"{slug}: 'fuente' debe ser un mapa")
    tipo_fuente = str(fuente_raw.get("tipo", "original")).lower()
    _exigir(tipo_fuente in TIPOS_FUENTE,
            f"{slug}: fuente.tipo '{tipo_fuente}' no valido (usa: {', '.join(sorted(TIPOS_FUENTE))})")
    if tipo_fuente != "original":
        _exigir(bool(str(fuente_raw.get("nombre", "")).strip()),
                f"{slug}: los problemas importados necesitan fuente.nombre para dar credito")

    problema = Problema(
        slug=slug,
        titulo=titulo,
        dificultad=dificultad,
        enunciado=enunciado,
        directorio=directorio,
        tags=tuple(str(t).strip().lower() for t in (datos.get("tags") or ())),
        autor=str(datos.get("autor", "")).strip(),
        tiempo_ms=tiempo_ms,
        memoria_mb=memoria_mb,
        validacion=tipo_val,
        tolerancia=float(val.get("tolerancia", 1e-6)),
        subtareas=subtareas,
        editorial=str(datos.get("editorial", "")).strip(),
        pistas=tuple(str(p) for p in (datos.get("pistas") or ())),
        fuente=Fuente(
            tipo=tipo_fuente,
            nombre=str(fuente_raw.get("nombre", "")).strip(),
            url=str(fuente_raw.get("url", "")).strip(),
            licencia=str(fuente_raw.get("licencia", "")).strip(),
            anio=int(fuente_raw["anio"]) if str(fuente_raw.get("anio", "")).isdigit() else None,
        ),
    )

    _exigir(len(problema.samples) >= 1, f"{slug}: hace falta al menos un caso en tests/sample/")
    _exigir(len(problema.secretos) >= 3,
            f"{slug}: hace falta al menos 3 casos en tests/secret/ (tenes {len(problema.secretos)})")

    if problema.tiene_subtareas:
        declaradas = {str(s["id"]) for s in subtareas}
        usadas = {c.subtarea for c in problema.secretos if c.subtarea}
        faltan = declaradas - usadas
        _exigir(not faltan,
                f"{slug}: las subtareas {sorted(faltan)} no tienen casos en tests/secret/<id>/")

    return problema


@lru_cache(maxsize=1)
def _cache_banco() -> dict[str, Problema]:
    banco: dict[str, Problema] = {}
    raiz = config.dir_problemas
    if not raiz.is_dir():
        return banco
    for d in sorted(raiz.iterdir()):
        if not d.is_dir() or d.name.startswith((".", "_")):
            continue
        try:
            p = cargar(d)
        except ProblemaInvalido as e:
            # un problema roto no puede tumbar todo el banco; se avisa y se saltea
            print(f"[problemas] se ignora {d.name}: {e}")
            continue
        banco[p.slug] = p
    return banco


def banco(refrescar: bool = False) -> dict[str, Problema]:
    """Todos los problemas validos, indexados por slug."""
    if refrescar:
        _cache_banco.cache_clear()
    return _cache_banco()


def obtener(slug: str) -> Problema | None:
    return banco().get(slug)


def por_dificultad(dificultad: int) -> list[Problema]:
    return [p for p in banco().values() if p.dificultad == dificultad]


def validar_todos() -> list[str]:
    """Valida el banco entero y devuelve la lista de errores. Lo usa la CI."""
    errores: list[str] = []
    raiz = config.dir_problemas
    if not raiz.is_dir():
        return [f"no existe el directorio de problemas: {raiz}"]

    vistos: set[str] = set()
    for d in sorted(raiz.iterdir()):
        if not d.is_dir() or d.name.startswith((".", "_")):
            continue
        try:
            p = cargar(d)
        except ProblemaInvalido as e:
            errores.append(str(e))
            continue
        if p.titulo.lower() in vistos:
            errores.append(f"{p.slug}: ya existe otro problema con el titulo '{p.titulo}'")
        vistos.add(p.titulo.lower())
    return errores
