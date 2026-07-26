import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 122949829)


def emitir(n, aristas):
    print(n, len(aristas))
    salida = []
    for u, v, w in aristas:
        salida.append(f"{u} {v} {w}")
    print("\n".join(salida))


if semilla == 1:
    emitir(2, [(1, 2, 5)])
elif semilla == 2:
    emitir(3, [])                                   # disconexo: respuesta -1
elif semilla == 3:
    # camino largo: obliga a recorrer todo
    n = 100000
    emitir(n, [(i, i + 1, 1000) for i in range(1, n)])
elif semilla == 4:
    # aristas repetidas entre el mismo par, la barata al final
    emitir(2, [(1, 2, 1000), (1, 2, 7), (1, 2, 999)])
elif semilla <= 8:
    n = rng.randint(2, 12)
    m = rng.randint(0, 20)
    aristas = []
    for _ in range(m):
        u = rng.randint(1, n)
        v = rng.randint(1, n)
        while v == u:
            v = rng.randint(1, n)
        aristas.append((u, v, rng.randint(1, 100)))
    emitir(n, aristas)
else:
    n = rng.randint(50000, 100000)
    aristas = []
    # primero un arbol de expansion, para que sea conexo
    for i in range(2, n + 1):
        aristas.append((rng.randint(1, i - 1), i, rng.randint(1, 10 ** 9)))
    # despues aristas extra al azar
    extra = min(300000 - len(aristas), rng.randint(50000, 200000))
    for _ in range(max(0, extra)):
        u = rng.randint(1, n)
        v = rng.randint(1, n)
        while v == u:
            v = rng.randint(1, n)
        aristas.append((u, v, rng.randint(1, 10 ** 9)))
    emitir(n, aristas)
