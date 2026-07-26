import sys

MOD = 1000000007


def main() -> None:
    datos = sys.stdin.read().split()
    filas = int(datos[0])
    columnas = int(datos[1])
    grilla = datos[2:2 + filas]

    if grilla[0][0] == "#":
        print(0)
        return

    fila = [0] * columnas
    fila[0] = 1
    for c in range(1, columnas):
        fila[c] = fila[c - 1] if grilla[0][c] == "." else 0

    for f in range(1, filas):
        actual = grilla[f]
        if actual[0] == "#":
            fila[0] = 0
        for c in range(1, columnas):
            if actual[c] == "#":
                fila[c] = 0
            else:
                fila[c] = (fila[c] + fila[c - 1]) % MOD

    print(fila[columnas - 1] % MOD)


main()
