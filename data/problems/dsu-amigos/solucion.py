import sys


def main() -> None:
    datos = sys.stdin.buffer.read().split()
    n = int(datos[0])
    q = int(datos[1])

    padre = list(range(n + 1))
    tamanio = [1] * (n + 1)

    def buscar(x: int) -> int:
        # iterativa a proposito: la recursiva revienta la pila con N grande
        raiz = x
        while padre[raiz] != raiz:
            raiz = padre[raiz]
        while padre[x] != raiz:          # compresion de caminos
            padre[x], x = raiz, padre[x]
        return raiz

    salida = []
    pos = 2
    for _ in range(q):
        tipo = datos[pos]
        if tipo == b"A":
            u = buscar(int(datos[pos + 1]))
            v = buscar(int(datos[pos + 2]))
            pos += 3
            if u != v:
                if tamanio[u] < tamanio[v]:   # union por tamanio
                    u, v = v, u
                padre[v] = u
                tamanio[u] += tamanio[v]
        else:
            u = int(datos[pos + 1])
            pos += 2
            salida.append(tamanio[buscar(u)])

    sys.stdout.write("\n".join(map(str, salida)) + "\n")


main()
