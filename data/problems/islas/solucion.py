import sys


def main() -> None:
    datos = sys.stdin.read().split()
    filas = int(datos[0])
    columnas = int(datos[1])
    grilla = datos[2:2 + filas]

    visitado = [bytearray(columnas) for _ in range(filas)]
    islas = 0

    for inicio_f in range(filas):
        fila_actual = grilla[inicio_f]
        for inicio_c in range(columnas):
            if fila_actual[inicio_c] != "#" or visitado[inicio_f][inicio_c]:
                continue

            islas += 1
            pila = [(inicio_f, inicio_c)]
            visitado[inicio_f][inicio_c] = 1

            while pila:
                f, c = pila.pop()
                for df, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nf, nc = f + df, c + dc
                    if 0 <= nf < filas and 0 <= nc < columnas:
                        if not visitado[nf][nc] and grilla[nf][nc] == "#":
                            visitado[nf][nc] = 1
                            pila.append((nf, nc))

    print(islas)


main()
