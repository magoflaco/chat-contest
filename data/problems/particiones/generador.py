import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 51001)

if semilla == 1:
    v = [7]
elif semilla == 2:
    v = [1, 1]                                  # perfecto: diferencia 0
elif semilla == 3:
    v = [500] * 200                             # el maximo, todos iguales
elif semilla == 4:
    v = [500] * 199 + [1]                       # imposible de empatar
elif semilla <= 8:
    # subtarea s1: N chico
    n = rng.randint(1, 20)
    v = [rng.randint(1, 500) for _ in range(n)]
else:
    n = rng.randint(100, 200)
    modo = rng.random()
    if modo < 0.4:
        v = [rng.randint(1, 500) for _ in range(n)]
    elif modo < 0.7:
        v = [rng.choice([1, 2, 3]) for _ in range(n)]      # valores chicos
    else:
        v = [rng.choice([497, 499, 500]) for _ in range(n)]  # casi iguales

# la suma no puede pasar de 100000
while sum(v) > 100000:
    v.pop()

print(len(v))
print(" ".join(map(str, v)))
