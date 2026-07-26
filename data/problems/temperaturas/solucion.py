import sys


def main() -> None:
    datos = sys.stdin.read().split()
    n = int(datos[0])
    t = [int(x) for x in datos[1:1 + n]]

    subidas = bajadas = 0
    for i in range(1, n):
        if t[i] > t[i - 1]:
            subidas += 1
        elif t[i] < t[i - 1]:
            bajadas += 1

    print(subidas, bajadas)


main()
