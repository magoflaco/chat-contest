import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 6961)
ABRE = "([{"
CIERRA = ")]}"


def balanceada(n):
    """Genera una cadena balanceada de exactamente 2n simbolos."""
    salida = []
    pila = []
    restantes = n
    while restantes > 0 or pila:
        if restantes > 0 and (not pila or rng.random() < 0.55):
            i = rng.randrange(3)
            salida.append(ABRE[i])
            pila.append(i)
            restantes -= 1
        else:
            salida.append(CIERRA[pila.pop()])
    return "".join(salida)


if semilla == 1:
    s = "()"
elif semilla == 2:
    s = "([)]"                       # cruzados: NO
elif semilla == 3:
    s = "(" * 250000 + ")" * 250000  # el maximo, balanceado
elif semilla == 4:
    s = "(" * 500000                 # nunca cierra: NO
elif semilla == 5:
    s = ")" * 500000                 # arranca cerrando: NO
elif semilla <= 9:
    s = balanceada(rng.randint(1, 12))
    if rng.random() < 0.5:           # la rompemos cambiando un simbolo
        i = rng.randrange(len(s))
        s = s[:i] + rng.choice(ABRE + CIERRA) + s[i + 1:]
else:
    s = balanceada(rng.randint(50000, 250000))
    if rng.random() < 0.4:
        i = rng.randrange(len(s))
        s = s[:i] + rng.choice(ABRE + CIERRA) + s[i + 1:]

print(s)
