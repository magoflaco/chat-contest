import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 5443)

if semilla == 1:
    a = [0]
elif semilla == 2:
    a = [-1000, 1000]
elif semilla == 3:
    a = [-7] * 200000            # todos iguales y negativos: la respuesta es 0
elif semilla == 4:
    a = [-1000] * 100 + [-999]   # todos negativos
elif semilla <= 8:
    a = [rng.randint(-1000, 1000) for _ in range(rng.randint(1, 20))]
else:
    a = [rng.randint(-1000, 1000) for _ in range(rng.randint(50000, 200000))]

print(len(a))
print(" ".join(map(str, a)))
