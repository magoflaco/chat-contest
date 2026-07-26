import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 7919)

if semilla == 1:
    n, t = 1, [0]
elif semilla == 2:
    n, t = 5, [3, 3, 3, 3, 3]
elif semilla == 3:
    n = 200000
    t = [(-100 + (i % 201)) for i in range(n)]
elif semilla <= 7:
    n = rng.randint(2, 20)
    t = [rng.randint(-100, 100) for _ in range(n)]
else:
    n = rng.randint(50000, 200000)
    t = [rng.randint(-100, 100) for _ in range(n)]

print(n)
print(" ".join(map(str, t)))
