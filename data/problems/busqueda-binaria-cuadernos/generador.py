import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 15359)

if semilla == 1:
    n, m, p = 1, 1, [7]
elif semilla == 2:
    n = 5; m = 5; p = [3, 1, 4, 1, 5]        # un cuaderno por dia
elif semilla == 3:
    n = 5; m = 1; p = [3, 1, 4, 1, 5]        # todo en un dia
elif semilla == 4:
    n = 200000; m = 1; p = [10 ** 9] * n     # la suma es enorme
elif semilla == 5:
    n = 200000; m = n; p = [10 ** 9] * n
elif semilla <= 9:
    n = rng.randint(1, 15)
    m = rng.randint(1, n)
    p = [rng.randint(1, 50) for _ in range(n)]
else:
    n = rng.randint(80000, 200000)
    m = rng.randint(1, n)
    if rng.random() < 0.5:
        p = [rng.randint(1, 10 ** 9) for _ in range(n)]
    else:
        # muchos chicos y uno gigante: fuerza el limite inferior
        p = [rng.randint(1, 100) for _ in range(n)]
        p[rng.randrange(n)] = 10 ** 9

print(n, m)
print(" ".join(map(str, p)))
