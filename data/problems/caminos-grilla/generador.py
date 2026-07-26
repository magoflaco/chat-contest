import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 86028121)

if semilla == 1:
    filas = columnas = 1
    grilla = ["."]
elif semilla == 2:
    filas = columnas = 2
    grilla = [".#", "#."]              # bloqueado: respuesta 0
elif semilla == 3:
    filas = columnas = 1500           # todo libre: numero gigante, exige el modulo por paso
    grilla = ["." * columnas] * filas
elif semilla == 4:
    filas = columnas = 3
    grilla = ["#..", "...", "..."]    # partida bloqueada
elif semilla <= 8:
    filas = rng.randint(1, 10)
    columnas = rng.randint(1, 10)
    grilla = ["".join("#" if rng.random() < 0.25 else "." for _ in range(columnas))
              for _ in range(filas)]
else:
    filas = rng.randint(500, 1500)
    columnas = rng.randint(500, 1500)
    densidad = rng.choice([0.05, 0.15, 0.3])
    grilla = ["".join("#" if rng.random() < densidad else "." for _ in range(columnas))
              for _ in range(filas)]

print(filas, columnas)
print("\n".join(grilla))
