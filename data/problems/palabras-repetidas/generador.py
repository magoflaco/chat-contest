import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 3571)
letras = "abcdefghijklmnopqrstuvwxyz"

if semilla == 1:
    palabras, k = ["hola"], 1
elif semilla == 2:
    # todas con la misma frecuencia: el desempate alfabetico decide todo
    palabras, k = ["zeta", "alfa", "beta", "gama"], 4
elif semilla == 3:
    palabras, k = ["a"] * 200000, 100          # una sola distinta, K mucho mayor
elif semilla == 4:
    # 200000 palabras todas distintas: todas con frecuencia 1
    palabras = [f"{i:05d}".translate(str.maketrans("0123456789", "abcdefghij"))
                for i in range(100000)]
    k = 100
elif semilla <= 8:
    vocabulario = ["".join(rng.choice(letras[:4]) for _ in range(rng.randint(1, 3)))
                   for _ in range(rng.randint(2, 6))]
    palabras = [rng.choice(vocabulario) for _ in range(rng.randint(1, 30))]
    k = rng.randint(1, 5)
else:
    tam = rng.randint(20, 300)
    vocabulario = ["".join(rng.choice(letras) for _ in range(rng.randint(1, 15)))
                   for _ in range(tam)]
    palabras = [rng.choice(vocabulario) for _ in range(rng.randint(50000, 200000))]
    k = rng.randint(1, 100)

print(len(palabras), k)
print(" ".join(palabras))
