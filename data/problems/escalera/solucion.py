import sys

MOD = 1000000007


def main() -> None:
    n = int(sys.stdin.readline())

    # a, b, c son las formas de llegar a los escalones i-3, i-2 e i-1
    a, b, c = 1, 1, 2
    if n == 1:
        print(1)
        return
    if n == 2:
        print(2)
        return

    for _ in range(3, n + 1):
        a, b, c = b, c, (a + b + c) % MOD

    print(c % MOD)


main()
