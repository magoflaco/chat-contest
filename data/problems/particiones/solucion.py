import sys


def main() -> None:
    datos = sys.stdin.buffer.read().split()
    n = int(datos[0])
    valores = [int(x) for x in datos[1:1 + n]]
    total = sum(valores)

    # cada bit prendido de `alcanzables` es una suma que se puede formar.
    # el desplazamiento hace todo el paso de la DP en una sola operacion.
    alcanzables = 1
    for v in valores:
        alcanzables |= alcanzables << v

    for s in range(total // 2, -1, -1):
        if alcanzables >> s & 1:
            print(total - 2 * s)
            return

    print(total)


main()
