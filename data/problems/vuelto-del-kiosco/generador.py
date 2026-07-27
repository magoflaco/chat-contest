import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 7907)

if semilla == 1:
    v = 0
elif semilla == 2:
    v = 1
elif semilla == 3:
    v = 1000000
elif semilla == 4:
    v = 999
elif semilla <= 8:
    v = rng.randint(1, 200)
else:
    v = rng.randint(1000, 1000000)

print(v)
