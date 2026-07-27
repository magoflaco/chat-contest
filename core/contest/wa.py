"""Formato de texto para WhatsApp.

WhatsApp **no entiende markdown**. Entiende un formato propio y muy chico:

    *negrita*        un solo asterisco, no dos
    _cursiva_
    ~tachado~
    ```bloque```     triple backtick. El backtick simple NO hace nada.

Todo lo demas sale literal: los `##`, los `**`, los backticks sueltos y los
guiones de lista se ven como basura en la pantalla del celular.

Los enunciados del banco estan escritos en markdown, porque asi se ven bien en la
web y en GitHub. Este modulo los traduce al formato de WhatsApp antes de mandarlos.

Ademas resuelve un problema molesto: WhatsApp convierte cualquier tirada larga de
digitos en un link para llamar por telefono. Una restriccion como `1 <= N <= 1000000`
aparecia como un numero clickeable.
"""

from __future__ import annotations

import re

#: WhatsApp detecta como telefono las tiradas de 7 digitos o mas.
#: Le metemos un WORD JOINER (U+2060) adentro: es de ancho cero, no se ve, y
#: alcanza para que deje de reconocerlo como numero.
MINIMO_PARA_ENLAZAR = 7
JUNTADOR = "⁠"


def proteger_numeros(texto: str) -> str:
    """Evita que WhatsApp convierta numeros largos en links de telefono."""
    def partir(m: re.Match) -> str:
        digitos = m.group(0)
        # se corta despues del primer digito: invisible y suficiente
        return digitos[0] + JUNTADOR + digitos[1:]

    return re.sub(rf"\d{{{MINIMO_PARA_ENLAZAR},}}", partir, texto)


def desde_markdown(texto: str) -> str:
    """Convierte el markdown de un enunciado al formato de WhatsApp."""
    # los bloques de codigo se apartan primero: adentro no se toca nada
    bloques: list[str] = []

    def guardar(m: re.Match) -> str:
        bloques.append(m.group(1).strip("\n"))
        return f"\x00{len(bloques) - 1}\x00"

    t = re.sub(r"```[a-zA-Z]*\n?(.*?)```", guardar, texto, flags=re.DOTALL)

    # encabezados -> una linea en negrita y mayusculas
    t = re.sub(r"^#{1,6}\s+(.+)$", lambda m: f"*{m.group(1).strip().upper()}*",
               t, flags=re.MULTILINE)

    # negrita de markdown (**x**) -> negrita de WhatsApp (*x*)
    t = re.sub(r"\*\*(.+?)\*\*", r"*\1*", t, flags=re.DOTALL)

    # el backtick simple no hace nada en WhatsApp: se saca y se deja el texto
    t = re.sub(r"`([^`\n]+)`", r"\1", t)

    # listas -> vinetas de verdad
    t = re.sub(r"^\s*[-*+]\s+(.+)$", r"  • \1", t, flags=re.MULTILINE)
    t = re.sub(r"^\s*(\d+)\.\s+(.+)$", r"  \1) \2", t, flags=re.MULTILINE)

    # citas
    t = re.sub(r"^>\s?(.*)$", r"  \1", t, flags=re.MULTILINE)

    # los links de markdown pierden el corchete: WhatsApp autodetecta la URL sola
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1: \2", t)

    # no dejar mas de una linea en blanco seguida
    t = re.sub(r"\n{3,}", "\n\n", t).strip()

    t = proteger_numeros(t)

    # se reponen los bloques ya convertidos al monoespaciado de WhatsApp
    def reponer(m: re.Match) -> str:
        return "```" + bloques[int(m.group(1))] + "```"

    return re.sub(r"\x00(\d+)\x00", reponer, t)


def bloque(texto: str) -> str:
    """Envuelve texto en monoespaciado de WhatsApp."""
    return "```" + texto.strip("\n") + "```"


def negrita(texto: str) -> str:
    return f"*{texto}*"


def cursiva(texto: str) -> str:
    return f"_{texto}_"
