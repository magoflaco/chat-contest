En el galpon del club hay `N` cajas en fila, y la `i`-esima tiene ancho `ai`.

Queremos armar una torre apilando algunas de esas cajas. Para que la torre se sostenga,
hay que respetar dos condiciones:

1. Las cajas se apilan en el mismo orden en que estan en la fila (se pueden saltear
   cajas, pero no reordenarlas).
2. Cada caja tiene que ser **estrictamente** mas ancha que la que va justo arriba,
   o sea que de abajo hacia arriba los anchos van estrictamente creciendo en el orden
   de la fila.

Averiguar la maxima cantidad de cajas que puede tener la torre.

## Entrada

La primera linea tiene un entero `N`.
La segunda linea tiene `N` enteros `a1 a2 ... aN`.

## Salida

Un unico entero: la maxima cantidad de cajas.

## Restricciones

- `1 <= N <= 300000`
- `1 <= ai <= 10^9`
