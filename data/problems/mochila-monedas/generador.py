import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 15485863)

if semilla == 1:
    m, monedas = 6, [1, 3, 4]
elif semilla == 2:
    m, monedas = 7, [4, 5]          # imposible: respuesta -1
elif semilla == 3:
    m, monedas = 100000, [1]
elif semilla <= 6:
    # subtarea s1: chicos
    m = rng.randint(1, 100)
    monedas = rng.sample(range(1, min(m, 50) + 1), rng.randint(1, min(5, m)))
elif semilla <= 10:
    m = rng.randint(1000, 20000)
    monedas = rng.sample(range(1, m + 1), rng.randint(2, 20))
else:
    m = rng.randint(50000, 100000)
    monedas = rng.sample(range(1, m + 1), rng.randint(50, 100))

print(m, len(monedas))
print(" ".join(map(str, monedas)))
