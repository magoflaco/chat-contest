import sys

PARES = {")": "(", "]": "[", "}": "{"}


def main() -> None:
    s = sys.stdin.readline().strip()

    pila = []
    for c in s:
        if c in "([{":
            pila.append(c)
        else:
            if not pila or pila.pop() != PARES[c]:
                print("NO")
                return

    print("SI" if not pila else "NO")


main()
