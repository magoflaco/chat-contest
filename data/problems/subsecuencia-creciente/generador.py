import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 67867967)

if semilla == 1:
    a = [5]
elif semilla == 2:
    a = [7, 7, 7, 7, 7]                    # todas iguales: respuesta 1
elif semilla == 3:
    a = list(range(1, 300001))             # ya ordenado: respuesta N
elif semilla == 4:
    a = list(range(300000, 0, -1))         # al reves: respuesta 1
elif semilla <= 8:
    # subtarea s1: chicos, para que la cuadratica pase
    n = rng.randint(1, 2000)
    a = [rng.randint(1, 10 ** 9) for _ in range(n)]
else:
    n = rng.randint(150000, 300000)
    modo = rng.random()
    if modo < 0.4:
        a = [rng.randint(1, 10 ** 9) for _ in range(n)]
    elif modo < 0.7:
        # casi ordenado con ruido: LIS larga
        a = sorted(rng.randint(1, 10 ** 9) for _ in range(n))
        for _ in range(n // 20):
            i, j = rng.randrange(n), rng.randrange(n)
            a[i], a[j] = a[j], a[i]
    else:
        a = [rng.randint(1, 50) for _ in range(n)]   # pocos valores distintos

print(len(a))
print(" ".join(map(str, a)))
