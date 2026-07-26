import sys


def main() -> None:
    datos = sys.stdin.buffer.read().split()
    n = int(datos[0])
    limite = int(datos[1])
    pesos = sorted(int(x) for x in datos[2:2 + n])

    i, j = 0, n - 1
    mesas = 0
    while i <= j:
        if pesos[i] + pesos[j] <= limite:
            i += 1
        j -= 1
        mesas += 1

    print(mesas)


main()
