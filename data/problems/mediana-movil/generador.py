import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 30011)

if semilla == 1:
    n, k, a = 1, 1, [5]
elif semilla == 2:
    n, k = 5, 5
    a = [3, 1, 4, 1, 5]                       # una sola ventana
elif semilla == 3:
    n, k = 200000, 1                          # cada elemento es su propia mediana
    a = [rng.randint(-10 ** 9, 10 ** 9) for _ in range(n)]
elif semilla == 4:
    n, k = 200000, 200000                     # una unica ventana gigante
    a = [rng.randint(-10 ** 9, 10 ** 9) for _ in range(n)]
elif semilla == 5:
    n, k = 200000, 2                          # K par: la mediana es el menor de los dos
    a = [rng.randint(-100, 100) for _ in range(n)]
elif semilla == 6:
    n, k = 100000, 777
    a = [7] * n                               # todos iguales
elif semilla <= 10:
    n = rng.randint(1, 20)
    k = rng.randint(1, n)
    a = [rng.randint(-30, 30) for _ in range(n)]
else:
    n = rng.randint(50000, 200000)
    k = rng.randint(1, n)
    if rng.random() < 0.5:
        a = [rng.randint(-10 ** 9, 10 ** 9) for _ in range(n)]
    else:
        a = [rng.randint(-50, 50) for _ in range(n)]   # muchos repetidos

print(n, k)
print(" ".join(map(str, a)))
