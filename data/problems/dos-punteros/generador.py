import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 32452843)

if semilla == 1:
    n, limite, pesos = 1, 10, [10]
elif semilla == 2:
    n, limite = 4, 100
    pesos = [50, 50, 50, 50]
elif semilla == 3:
    n, limite = 300000, 10 ** 9
    pesos = [10 ** 9] * n
elif semilla <= 7:
    n = rng.randint(2, 20)
    limite = rng.randint(10, 200)
    pesos = [rng.randint(1, limite) for _ in range(n)]
else:
    n = rng.randint(100000, 300000)
    limite = rng.randint(10 ** 6, 10 ** 9)
    pesos = [rng.randint(1, limite) for _ in range(n)]

print(n, limite)
print(" ".join(map(str, pesos)))
