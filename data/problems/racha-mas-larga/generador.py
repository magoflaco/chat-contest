import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 104729)
letras = "VED"

if semilla == 1:
    s = "V"
elif semilla == 2:
    s = "VVVDDDEEE"
elif semilla == 3:
    s = "D" * 500000
elif semilla <= 7:
    s = "".join(rng.choice(letras) for _ in range(rng.randint(2, 30)))
elif semilla <= 11:
    # muchas rachas medianas, para castigar soluciones cuadraticas
    trozos = []
    while sum(len(t) for t in trozos) < 200000:
        trozos.append(rng.choice(letras) * rng.randint(1, 50))
    s = "".join(trozos)[:200000]
else:
    s = "".join(rng.choice(letras) for _ in range(rng.randint(100000, 500000)))

print(len(s))
print(s)
