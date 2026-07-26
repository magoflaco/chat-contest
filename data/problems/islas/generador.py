import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 49979687)

if semilla == 1:
    filas = columnas = 1
    grilla = ["#"]
elif semilla == 2:
    filas = columnas = 3
    grilla = ["#.#", ".#.", "#.#"]      # 5 islas, ninguna conectada en diagonal
elif semilla == 3:
    filas = columnas = 1000            # una sola isla gigante: castiga el DFS recursivo
    grilla = ["#" * columnas] * filas
elif semilla == 4:
    filas = columnas = 1000            # tablero de ajedrez: muchisimas islas chicas
    grilla = ["".join("#" if (i + j) % 2 == 0 else "." for j in range(columnas))
              for i in range(filas)]
elif semilla <= 8:
    filas = rng.randint(2, 12)
    columnas = rng.randint(2, 12)
    grilla = ["".join(rng.choice("#.") for _ in range(columnas)) for _ in range(filas)]
else:
    filas = rng.randint(300, 1000)
    columnas = rng.randint(300, 1000)
    densidad = rng.choice([0.3, 0.45, 0.6])
    grilla = ["".join("#" if rng.random() < densidad else "." for _ in range(columnas))
              for _ in range(filas)]

print(filas, columnas)
print("\n".join(grilla))
