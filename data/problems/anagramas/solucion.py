import sys
from collections import Counter


def main() -> None:
    datos = sys.stdin.read().split()
    n = int(datos[0])
    palabras = datos[1:1 + n]

    grupos = Counter("".join(sorted(p)) for p in palabras)
    print(max(grupos.values()))


main()
