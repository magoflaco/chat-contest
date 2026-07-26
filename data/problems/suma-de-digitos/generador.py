import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla)

if semilla == 1:
    n = 1
elif semilla == 2:
    n = 9
elif semilla == 3:
    n = 10 ** 18
elif semilla <= 6:
    n = rng.randint(1, 100)
elif semilla <= 10:
    n = rng.randint(10 ** 9, 10 ** 12)
else:
    n = rng.randint(10 ** 15, 10 ** 18)

print(n)
