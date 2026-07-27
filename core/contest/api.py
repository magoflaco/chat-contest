"""API HTTP del core.

Tiene dos caras:

- `/bot/*`: privada, la usa el gateway de Baileys. Protegida con CORE_TOKEN y
  pensada para escuchar solo en localhost.
- `/api/*`: publica y de solo lectura, la consume el leaderboard web. No expone
  numeros de telefono completos ni nada de los casos de prueba.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import commands, db, identidades, problems, ranking, scheduler
from .config import config
from .rounds import historial, ronda_actual, ronda_por_numero
from .scoring import BASE_POR_DIFICULTAD, NOMBRE_DIFICULTAD
from .submissions import asegurar_usuario, normalizar_numero


@asynccontextmanager
async def _ciclo_vida(app: FastAPI):
    db.inicializar()
    commands.cargar_todos()
    problems.banco(refrescar=True)
    scheduler.iniciar()
    yield
    scheduler.detener()


app = FastAPI(
    title="Chat Contest",
    description="Liga de problemas de Python para el club de programacion",
    version="0.1.0",
    lifespan=_ciclo_vida,
)

# la web es estatica y puede estar en otro dominio (Cloudflare Pages).
# solo se exponen GET publicos, asi que un origen abierto no agrega riesgo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _autorizar(authorization: str = Header(default="")) -> None:
    """Valida el token compartido con el gateway."""
    if not config.token:
        raise HTTPException(500, "CORE_TOKEN no esta configurado en el .env")
    esperado = f"Bearer {config.token}"
    # comparacion en tiempo constante para no filtrar el token por temporizacion
    import hmac
    if not hmac.compare_digest(authorization, esperado):
        raise HTTPException(401, "token invalido")


# --- lado bot ------------------------------------------------------------------

class Adjunto(BaseModel):
    nombre: str = ""
    contenido: str = ""


class MensajeEntrante(BaseModel):
    jid: str
    numero: str
    nombre: str = ""
    texto: str = ""
    es_grupo: bool = False
    adjunto: Adjunto | None = None
    #: otras formas con las que llego identificado el mismo remitente.
    #: WhatsApp esta migrando a LIDs y manda uno u otro segun el chat.
    alternos: list[str] = Field(default_factory=list)


class MensajeSaliente(BaseModel):
    texto: str
    destino: str = ""
    #: nombre de un sticker de Perove, sin ruta ni extension (ej: "cast")
    sticker: str = ""


class RespuestaBot(BaseModel):
    mensajes: list[MensajeSaliente] = Field(default_factory=list)


@app.post("/bot/mensaje", response_model=RespuestaBot, dependencies=[Depends(_autorizar)])
def recibir_mensaje(m: MensajeEntrante) -> RespuestaBot:
    """Punto de entrada de todo lo que llega por WhatsApp."""
    alternos = [normalizar_numero(x) for x in m.alternos]
    numero = identidades.canonica(normalizar_numero(m.numero), alternos)

    # un admin puede estar configurado por telefono y escribir desde un chat que
    # lo identifica por LID (o al reves): vale cualquiera de sus identidades
    es_admin = any(config.es_admin(x) for x in {numero, *alternos})

    ctx = commands.Contexto(
        numero=numero,
        nombre=m.nombre,
        jid=m.jid,
        es_grupo=m.es_grupo,
        es_admin=es_admin,
        texto=m.texto,
        args="",
        adjunto_texto=(m.adjunto.contenido if m.adjunto else ""),
        adjunto_nombre=(m.adjunto.nombre if m.adjunto else ""),
    )

    respuesta = commands.despachar(ctx)
    if respuesta is None:
        return RespuestaBot()

    mensajes = [MensajeSaliente(texto=respuesta.texto, destino=m.jid,
                                sticker=respuesta.sticker)]
    mensajes += [MensajeSaliente(texto=t, destino=d) for d, t in respuesta.difundir]
    return RespuestaBot(mensajes=mensajes)


class Saliente(BaseModel):
    id: int
    destino: str
    texto: str
    sticker: str = ""


@app.get("/bot/salientes", response_model=list[Saliente], dependencies=[Depends(_autorizar)])
def obtener_salientes() -> list[Saliente]:
    """Mensajes que el scheduler dejo listos para publicar."""
    return [Saliente(id=m["id"], destino=m["destino"], texto=m["texto"],
                     sticker=m.get("sticker", ""))
            for m in scheduler.pendientes()]


@app.post("/bot/salientes/{mensaje_id}/enviado", dependencies=[Depends(_autorizar)])
def confirmar_saliente(mensaje_id: int) -> dict:
    scheduler.marcar_enviado(mensaje_id)
    return {"ok": True}


@app.post("/bot/salientes/{mensaje_id}/fallo", dependencies=[Depends(_autorizar)])
def fallar_saliente(mensaje_id: int, error: str = Query(default="")) -> dict:
    scheduler.marcar_fallo(mensaje_id, error)
    return {"ok": True}


@app.post("/bot/visto", dependencies=[Depends(_autorizar)])
def registrar_visto(m: MensajeEntrante) -> dict:
    """Alta perezosa de alguien que hablo en el grupo pero no uso un comando."""
    numero = identidades.canonica(normalizar_numero(m.numero),
                                  [normalizar_numero(x) for x in m.alternos])
    asegurar_usuario(numero, m.nombre)
    return {"ok": True}


# --- lado web (publico, solo lectura) ------------------------------------------

@app.get("/api/salud")
def salud() -> dict:
    return {"ok": True, "bot": config.bot_name}


@app.get("/api/resumen")
def api_resumen() -> dict:
    ronda = ronda_actual()
    return {
        "bot": config.bot_name,
        "totales": ranking.resumen(),
        "ronda_actual": _ronda_publica(ronda) if ronda else None,
        "dificultades": [
            {"nivel": n, "nombre": NOMBRE_DIFICULTAD[n], "base": BASE_POR_DIFICULTAD[n]}
            for n in sorted(BASE_POR_DIFICULTAD)
        ],
    }


@app.get("/api/ranking")
def api_ranking(ronda: int | None = None, limite: int = Query(default=100, ge=1, le=500)) -> dict:
    filas = ranking.por_ronda(ronda) if ronda else ranking.global_()
    return {
        "alcance": f"ronda {ronda}" if ronda else "global",
        "total": len(filas),
        "filas": [f.anonimo() for f in filas[:limite]],
    }


@app.get("/api/rondas")
def api_rondas(limite: int = Query(default=10, ge=1, le=50)) -> dict:
    return {"rondas": [_ronda_publica(r, con_editorial=not r.abierta)
                       for r in historial(limite)]}


@app.get("/api/ronda/{numero}")
def api_ronda(numero: int) -> dict:
    r = ronda_por_numero(numero)
    if not r:
        raise HTTPException(404, "esa ronda no existe")
    return _ronda_publica(r, con_editorial=not r.abierta)


@app.get("/api/participante/{sufijo}")
def api_participante(sufijo: str) -> dict:
    """Perfil publico, buscado por los ultimos 4 digitos que muestra el ranking."""
    fila = next((f for f in ranking.global_() if f.numero.endswith(sufijo)), None)
    if not fila:
        raise HTTPException(404, "no encuentro ese participante")

    p = ranking.perfil(fila.numero)
    if not p:
        raise HTTPException(404, "no encuentro ese participante")

    return {
        "nombre": p.nombre or f"...{sufijo}",
        "id": sufijo,
        "puesto": p.puesto,
        "puntos": p.puntos,
        "resueltos": p.resueltos,
        "intentos": p.intentos,
        "precision": round(p.precision, 3),
        "por_dificultad": p.por_dificultad,
        "problemas": [
            {"codigo": d["codigo"], "ronda": d["ronda"], "dificultad": d["dificultad"],
             "puntos": d["puntos"], "resuelto": bool(d["resuelto"]), "intentos": d["intentos"]}
            for d in p.detalle
        ],
    }


def _ronda_publica(r, con_editorial: bool = False) -> dict:
    """Serializa una ronda para la web.

    El enunciado y los casos de EJEMPLO van siempre: son publicos, igual que en
    cualquier juez online. Lo que nunca sale son los casos secretos.

    La editorial si se reserva hasta que la ronda cierra: es la solucion.
    """
    problemas_out = []
    for pr in r.problemas:
        p = pr.problema
        stats = ranking.estadisticas_problema(pr.codigo)
        item = {
            "codigo": pr.codigo,
            "titulo": p.titulo if p else pr.slug,
            "dificultad": pr.dificultad,
            "nombre_dificultad": NOMBRE_DIFICULTAD.get(pr.dificultad, "?"),
            "base": BASE_POR_DIFICULTAD.get(pr.dificultad, 0),
            "tags": list(p.tags) if p else [],
            "intentaron": stats["intentaron"],
            "resolvieron": stats["resolvieron"],
        }
        if p:
            item["enunciado"] = p.enunciado
            item["fuente"] = p.fuente.atribucion()
            item["tiempo_ms"] = p.tiempo_ms
            item["memoria_mb"] = p.memoria_mb
            item["samples"] = [
                {"entrada": c.leer_entrada().strip()[:2000],
                 "salida": c.leer_esperado().strip()[:2000]}
                for c in p.samples[:2]
            ]
            item["subtareas"] = [
                {"id": str(s.get("id")), "peso": s.get("peso"),
                 "descripcion": s.get("descripcion", "")}
                for s in p.subtareas
            ]
            # la editorial es la solucion: recien cuando la ronda cerro
            if con_editorial:
                item["editorial"] = p.editorial
        problemas_out.append(item)

    return {
        "numero": r.numero,
        "inicio": r.inicio.isoformat() if r.inicio else None,
        "fin": r.fin.isoformat() if r.fin else None,
        "estado": r.estado,
        "abierta": r.abierta,
        "horas_restantes": round(r.horas_restantes, 1),
        "problemas": problemas_out,
    }
