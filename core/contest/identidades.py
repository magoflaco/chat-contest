"""Resolucion de identidad de un participante.

WhatsApp esta migrando de numeros de telefono a **LIDs** (identificadores opacos
del estilo `59735076253926@lid`). Segun el chat y la version del cliente del otro,
Baileys entrega uno u otro, y a veces los dos.

Eso trae dos problemas concretos, y los dos aparecieron en produccion:

1. Un admin configurado por su telefono no era reconocido cuando su mensaje
   llegaba identificado por LID.
2. La misma persona podia terminar con dos filas en el ranking, una por cada
   forma de identificarse.

La solucion es tener una identidad **canonica** por persona (el telefono cuando
se conoce) y una tabla que mapea cualquier alias a esa canonica.
"""

from __future__ import annotations

from . import db

#: los LID son numeros largos sin codigo de pais reconocible. Un telefono real
#: tiene entre 8 y 15 digitos; los LID que emite WhatsApp son de 15 o mas y no
#: corresponden a ningun plan de numeracion.
LARGO_TIPICO_LID = 15


def parece_lid(identificador: str) -> bool:
    """Heuristica para distinguir un LID de un telefono.

    No es exacta ni pretende serlo: solo se usa para *preferir* el telefono
    cuando tenemos los dos. La fuente de verdad es el dominio del JID
    (`@lid` vs `@s.whatsapp.net`), que el gateway ya nos manda resuelto.
    """
    return identificador.isdigit() and len(identificador) >= LARGO_TIPICO_LID


def canonica(principal: str, alternos: list[str] | None = None) -> str:
    """Identidad canonica de quien manda un mensaje, registrando el mapeo.

    `principal` es lo que el gateway considera la mejor identificacion (prefiere
    el telefono). `alternos` son las otras formas con las que llego el mismo
    mensaje.
    """
    candidatos = [x for x in [principal, *(alternos or [])] if x]
    if not candidatos:
        return principal

    # si alguno de los identificadores ya esta mapeado, esa es la canonica:
    # respetar lo que ya decidimos evita partir el historial de alguien
    for c in candidatos:
        fila = db.uno("SELECT usuario FROM identidades WHERE alias = ?", (c,))
        if fila:
            elegida = fila["usuario"]
            break
    else:
        # sin mapeo previo: preferimos algo que parezca un telefono de verdad
        telefonos = [c for c in candidatos if not parece_lid(c)]
        elegida = telefonos[0] if telefonos else candidatos[0]

    ahora = db.iso()
    for c in candidatos:
        db.ejecutar(
            "INSERT INTO identidades (alias, usuario, visto_en) VALUES (?, ?, ?) "
            "ON CONFLICT(alias) DO UPDATE SET visto_en = excluded.visto_en",
            (c, elegida, ahora),
        )

    return elegida


def alias_de(usuario: str) -> list[str]:
    """Todas las formas con las que se identifico a esta persona."""
    return [f["alias"] for f in db.consultar(
        "SELECT alias FROM identidades WHERE usuario = ?", (usuario,))]


def fusionar(desde: str, hacia: str) -> int:
    """Reasigna todo lo de `desde` a `hacia`. Para arreglar duplicados a mano.

    Devuelve cuantas filas se movieron. Lo usa el comando !fusionar de admin.
    """
    movidas = 0
    for tabla, columna in (("entregas", "usuario"), ("resultados", "usuario"),
                           ("huellas", "usuario")):
        cur = db.ejecutar(f"UPDATE OR IGNORE {tabla} SET {columna} = ? WHERE {columna} = ?",
                          (hacia, desde))
        movidas += cur.rowcount

    db.ejecutar("UPDATE identidades SET usuario = ? WHERE usuario = ?", (hacia, desde))
    db.ejecutar(
        "INSERT INTO identidades (alias, usuario, visto_en) VALUES (?, ?, ?) "
        "ON CONFLICT(alias) DO UPDATE SET usuario = excluded.usuario",
        (desde, hacia, db.iso()))
    db.ejecutar("DELETE FROM usuarios WHERE numero = ?", (desde,))
    db.auditar("identidades_fusionadas", usuario=hacia, detalle=f"{desde} -> {hacia}")
    return movidas
