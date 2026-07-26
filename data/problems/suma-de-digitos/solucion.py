import sys


def raiz_digital(n: int) -> int:
    while n >= 10:
        s = 0
        while n > 0:
            s += n % 10
            n //= 10
        n = s
    return n


def main() -> None:
    n = int(sys.stdin.readline())
    print(raiz_digital(n))


main()
