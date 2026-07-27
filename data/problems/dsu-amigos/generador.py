import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 40009)

lineas = []

if semilla == 1:
    n = 1
    lineas = ["C 1"]
elif semilla == 2:
    n = 4
    lineas = ["C 1", "A 1 2", "C 1", "A 2 3", "C 3", "A 1 3", "C 2", "C 4"]
elif semilla == 3:
    # cadena larga: sin union por tamanio, el arbol degenera
    n = 200000
    lineas = [f"A {i} {i + 1}" for i in range(1, n)]
    lineas.append("C 1")
elif semilla == 4:
    n = 200000
    lineas = ["C 1"] * 300000          # solo consultas
elif semilla == 5:
    n = 100
    lineas = ["A 1 1"] * 1000 + ["C 1"]   # unir a alguien consigo mismo
elif semilla <= 9:
    n = rng.randint(1, 12)
    for _ in range(rng.randint(1, 25)):
        if rng.random() < 0.5:
            lineas.append(f"A {rng.randint(1, n)} {rng.randint(1, n)}")
        else:
            lineas.append(f"C {rng.randint(1, n)}")
else:
    n = rng.randint(50000, 200000)
    for _ in range(rng.randint(100000, 300000)):
        if rng.random() < 0.6:
            lineas.append(f"A {rng.randint(1, n)} {rng.randint(1, n)}")
        else:
            lineas.append(f"C {rng.randint(1, n)}")
    if not any(l.startswith("C") for l in lineas):
        lineas.append("C 1")

print(n, len(lineas))
print("\n".join(lineas))
