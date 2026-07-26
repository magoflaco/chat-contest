import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 217645199)
letras = "abcdefghijklmnopqrstuvwxyz"

if semilla == 1:
    palabras = ["a"]
elif semilla == 2:
    palabras = ["roma", "amor", "mora", "ramo", "casa"]
elif semilla == 3:
    # 100000 palabras todas anagramas entre si
    base = "abcdefghij"
    palabras = []
    for _ in range(100000):
        p = list(base)
        rng.shuffle(p)
        palabras.append("".join(p))
elif semilla == 4:
    # todas distintas: la respuesta es 1
    palabras = [f"{i:06d}".translate(str.maketrans("0123456789", "abcdefghij"))
                for i in range(100000)]
elif semilla <= 8:
    palabras = ["".join(rng.choice(letras[:5]) for _ in range(rng.randint(1, 4)))
                for _ in range(rng.randint(1, 30))]
else:
    n = rng.randint(30000, 100000)
    alfabeto = letras[:rng.randint(3, 26)]
    largo = rng.randint(1, 20)
    palabras = ["".join(rng.choice(alfabeto) for _ in range(largo)) for _ in range(n)]

print(len(palabras))
print("\n".join(palabras))
