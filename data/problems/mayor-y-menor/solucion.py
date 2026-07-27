import sys


def main() -> None:
    datos = sys.stdin.read().split()
    n = int(datos[0])
    valores = [int(x) for x in datos[1:1 + n]]

    print(max(valores) - min(valores))


main()
