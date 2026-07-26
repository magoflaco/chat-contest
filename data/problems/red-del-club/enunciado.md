El club tiene `N` computadoras numeradas de `1` a `N`, conectadas por `M` cables.
Cada cable une dos computadoras distintas `u` y `v` y tiene una latencia `w`
milisegundos. Los cables son bidireccionales.

Puede haber mas de un cable entre el mismo par de computadoras, y puede haber
computadoras que queden aisladas.

Hay que averiguar la minima latencia total para mandar un mensaje desde la
computadora `1` hasta la computadora `N`, sumando las latencias de los cables que se
recorren.

## Entrada

La primera linea tiene dos enteros `N` y `M`.
Las siguientes `M` lineas tienen tres enteros `u v w` cada una.

## Salida

Un unico entero: la minima latencia total desde `1` hasta `N`.
Si no existe ningun camino, imprimir `-1`.

## Restricciones

- `2 <= N <= 100000`
- `0 <= M <= 300000`
- `1 <= u, v <= N`, `u != v`
- `1 <= w <= 10^9`
