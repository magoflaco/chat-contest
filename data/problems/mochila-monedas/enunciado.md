El kiosco del club tiene una caja con monedas de `K` valores distintos, y de cada
valor hay cantidad ilimitada. Hay que pagar exactamente `M` pesos, y como la caja
esta desordenada, conviene usar la menor cantidad posible de monedas.

Cuidado: agarrar siempre la moneda mas grande que entra no siempre da el minimo.

## Entrada

La primera linea tiene dos enteros `M` y `K`.
La segunda linea tiene `K` enteros distintos `v1 v2 ... vK`, los valores de las monedas.

## Salida

Un unico entero: la minima cantidad de monedas necesarias para sumar exactamente `M`.
Si no se puede formar `M` con esas monedas, imprimir `-1`.

## Restricciones

- `1 <= M <= 100000`
- `1 <= K <= 100`
- `1 <= vi <= M`
