import sys


def main() -> None:
    datos = sys.stdin.read().split()
    s = datos[1]

    mejor_largo = 1
    mejor_letra = s[0]
    actual = 1

    for i in range(1, len(s)):
        actual = actual + 1 if s[i] == s[i - 1] else 1
        if actual > mejor_largo:
            mejor_largo = actual
            mejor_letra = s[i]

    print(mejor_letra, mejor_largo)


main()
