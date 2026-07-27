import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 22571)

if semilla == 1:
    n = 1
elif semilla == 2:
    n = 3
elif semilla == 3:
    n = 1000000
elif semilla == 4:
    n = 999999
elif semilla <= 8:
    n = rng.randint(1, 20)
else:
    n = rng.randint(500000, 1000000)

print(n)
