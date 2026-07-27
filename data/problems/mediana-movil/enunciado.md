El invernadero del club tiene un sensor que toma una medicion por minuto. Como el
sensor es ruidoso, en vez de mirar las mediciones sueltas se mira la **mediana** de
las ultimas `K` mediciones.

Dadas las `N` mediciones, informar la mediana de cada ventana de `K` mediciones
consecutivas.

Con `K` impar, la mediana es el elemento del medio al ordenar la ventana. Con `K` par,
es el **menor** de los dos del medio.

## Entrada

La primera linea tiene dos enteros `N` y `K`.
La segunda linea tiene `N` enteros `a1 a2 ... aN`.

## Salida

Una unica linea con `N - K + 1` enteros separados por espacios: las medianas de las
ventanas, de izquierda a derecha.

## Restricciones

- `1 <= K <= N <= 200000`
- `-10^9 <= ai <= 10^9`
