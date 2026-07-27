import sys
from collections import Counter


def main() -> None:
    datos = sys.stdin.read().split()
    n = int(datos[0])
    k = int(datos[1])
    palabras = datos[2:2 + n]

    conteo = Counter(palabras)
    # frecuencia descendente, y a igual frecuencia alfabetico ascendente
    ordenadas = sorted(conteo.items(), key=lambda par: (-par[1], par[0]))

    salida = [f"{palabra} {cantidad}" for palabra, cantidad in ordenadas[:k]]
    print("\n".join(salida))


main()
