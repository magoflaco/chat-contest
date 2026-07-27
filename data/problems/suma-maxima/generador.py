import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 8191)

if semilla == 1:
    a = [5]
elif semilla == 2:
    a = [-3]                                  # unico dia, y negativo
elif semilla == 3:
    a = [-7, -2, -9, -4]                      # todos negativos: la respuesta es -2
elif semilla == 4:
    a = [10 ** 9] * 300000                    # la suma no entra en 32 bits
elif semilla == 5:
    a = [-10 ** 9] * 300000
elif semilla <= 9:
    a = [rng.randint(-20, 20) for _ in range(rng.randint(1, 25))]
else:
    n = rng.randint(100000, 300000)
    modo = rng.random()
    if modo < 0.35:
        a = [rng.randint(-10 ** 9, 10 ** 9) for _ in range(n)]
    elif modo < 0.7:
        a = [rng.randint(-100, 90) for _ in range(n)]     # sesgado a negativo
    else:
        a = [rng.randint(-10 ** 9, -1) for _ in range(n)]  # todos negativos

print(len(a))
print(" ".join(map(str, a)))
