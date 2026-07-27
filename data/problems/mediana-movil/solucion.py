import heapq
import sys
from collections import Counter


def main() -> None:
    datos = sys.stdin.buffer.read().split()
    n = int(datos[0])
    k = int(datos[1])
    a = [int(x) for x in datos[2:2 + n]]

    bajos: list[int] = []      # max-heap, con los valores negados
    altos: list[int] = []      # min-heap
    por_borrar: Counter = Counter()
    tam_bajos = tam_altos = 0

    def limpiar_bajos() -> None:
        while bajos and por_borrar[-bajos[0]]:
            por_borrar[-bajos[0]] -= 1
            heapq.heappop(bajos)

    def limpiar_altos() -> None:
        while altos and por_borrar[altos[0]]:
            por_borrar[altos[0]] -= 1
            heapq.heappop(altos)

    def rebalancear() -> None:
        nonlocal tam_bajos, tam_altos
        # bajos tiene que quedar con uno mas, o empatado
        while tam_bajos > tam_altos + 1:
            limpiar_bajos()
            heapq.heappush(altos, -heapq.heappop(bajos))
            tam_bajos -= 1
            tam_altos += 1
        while tam_bajos < tam_altos:
            limpiar_altos()
            heapq.heappush(bajos, -heapq.heappop(altos))
            tam_bajos += 1
            tam_altos -= 1

    salida = []
    for i, x in enumerate(a):
        limpiar_bajos()
        if not bajos or x <= -bajos[0]:
            heapq.heappush(bajos, -x)
            tam_bajos += 1
        else:
            heapq.heappush(altos, x)
            tam_altos += 1

        if i >= k:
            viejo = a[i - k]
            limpiar_bajos()
            if bajos and viejo <= -bajos[0]:
                tam_bajos -= 1
            else:
                tam_altos -= 1
            por_borrar[viejo] += 1

        rebalancear()

        if i >= k - 1:
            limpiar_bajos()
            salida.append(-bajos[0])

    sys.stdout.write(" ".join(map(str, salida)) + "\n")


main()
