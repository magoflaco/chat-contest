import bisect
import sys


def main() -> None:
    datos = sys.stdin.buffer.read().split()
    n = int(datos[0])
    anchos = [int(x) for x in datos[1:1 + n]]

    colas: list[int] = []
    for x in anchos:
        i = bisect.bisect_left(colas, x)
        if i == len(colas):
            colas.append(x)
        else:
            colas[i] = x

    print(len(colas))


main()
