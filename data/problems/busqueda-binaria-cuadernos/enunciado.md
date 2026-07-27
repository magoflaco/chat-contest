En el club hay `N` cuadernos en fila para pasar en limpio, y el `i`-esimo tiene `pi`
paginas.

El trabajo se reparte en `M` dias. Cada dia se toma un tramo de cuadernos
**consecutivos** de la fila (respetando el orden, sin saltear ninguno) y se copian
enteros: un cuaderno no se puede partir entre dos dias.

Queremos que el dia mas cargado sea lo mas liviano posible. Es decir: minimizar la
cantidad de paginas del dia en que mas se copia.

## Entrada

La primera linea tiene dos enteros `N` y `M`.
La segunda linea tiene `N` enteros `p1 p2 ... pN`.

## Salida

Un unico entero: la minima cantidad de paginas posible para el dia mas cargado.

## Restricciones

- `1 <= M <= N <= 200000`
- `1 <= pi <= 10^9`
