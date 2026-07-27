import sys


def main() -> None:
    datos = sys.stdin.buffer.read().split()
    n = int(datos[0])
    valores = [int(x) for x in datos[1:1 + n]]

    # se inicializa con el primer elemento, no con 0: el tramo no puede ser vacio
    actual = mejor = valores[0]
    for x in valores[1:]:
        actual = x if actual < 0 else actual + x
        if actual > mejor:
            mejor = actual

    print(mejor)


main()
