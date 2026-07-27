import sys


def alcanza(paginas: list[int], limite: int, dias: int) -> bool:
    """True si se puede terminar en `dias` dias sin pasar de `limite` por dia."""
    usados = 1
    actual = 0
    for p in paginas:
        if actual + p <= limite:
            actual += p
        else:
            usados += 1
            actual = p
            if usados > dias:
                return False
    return True


def main() -> None:
    datos = sys.stdin.buffer.read().split()
    n = int(datos[0])
    m = int(datos[1])
    paginas = [int(x) for x in datos[2:2 + n]]

    # un cuaderno no se parte: el limite nunca puede ser menor que el mas grande
    bajo = max(paginas)
    alto = sum(paginas)

    while bajo < alto:
        medio = (bajo + alto) // 2
        if alcanza(paginas, medio, m):
            alto = medio
        else:
            bajo = medio + 1

    print(bajo)


main()
