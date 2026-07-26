import heapq
import sys


def main() -> None:
    datos = sys.stdin.buffer.read().split()
    n = int(datos[0])
    m = int(datos[1])

    grafo: list[list[tuple[int, int]]] = [[] for _ in range(n + 1)]
    pos = 2
    for _ in range(m):
        u = int(datos[pos])
        v = int(datos[pos + 1])
        w = int(datos[pos + 2])
        pos += 3
        grafo[u].append((v, w))
        grafo[v].append((u, w))

    INF = float("inf")
    dist = [INF] * (n + 1)
    dist[1] = 0
    heap = [(0, 1)]

    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        if u == n:
            break
        for v, peso in grafo[u]:
            nd = d + peso
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))

    print(-1 if dist[n] == INF else dist[n])


main()
