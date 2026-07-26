import sys


def main() -> None:
    datos = sys.stdin.read().split()
    m = int(datos[0])
    k = int(datos[1])
    monedas = sorted(set(int(x) for x in datos[2:2 + k]))

    INF = float("inf")
    dp = [0] + [INF] * m

    for v in monedas:
        for x in range(v, m + 1):
            anterior = dp[x - v]
            if anterior + 1 < dp[x]:
                dp[x] = anterior + 1

    print(-1 if dp[m] == INF else dp[m])


main()
