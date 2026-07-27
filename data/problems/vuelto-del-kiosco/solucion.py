import sys

VALORES = [1000, 500, 200, 100, 50, 20, 10, 5, 2, 1]


def main() -> None:
    vuelto = int(sys.stdin.readline())

    total = 0
    for valor in VALORES:
        total += vuelto // valor
        vuelto %= valor

    print(total)


main()
