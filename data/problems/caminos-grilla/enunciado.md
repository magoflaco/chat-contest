Un robot repartidor tiene que ir desde la esquina superior izquierda de una grilla
de `F` filas por `C` columnas hasta la esquina inferior derecha. En cada paso solo
puede moverse una celda hacia abajo o una celda hacia la derecha.

Algunas celdas estan bloqueadas por cajas y el robot no puede pasar por ellas.

Contar de cuantas formas distintas puede hacer el recorrido. Como el numero puede ser
enorme, informarlo modulo `1000000007`.

## Entrada

La primera linea tiene dos enteros `F` y `C`.
Las siguientes `F` lineas tienen `C` caracteres cada una: `.` para celda libre y
`#` para celda bloqueada.

## Salida

Un unico entero: la cantidad de caminos, modulo `1000000007`.
Si no hay ningun camino posible, imprimir `0`.

## Restricciones

- `1 <= F, C <= 1500`
- La celda de partida y la de llegada pueden estar bloqueadas; en ese caso la
  respuesta es `0`.
