Un mapa viejo muestra una region del oceano como una grilla de `F` filas por `C`
columnas. Cada celda es agua (`.`) o tierra (`#`).

Dos celdas de tierra pertenecen a la misma isla si estan pegadas horizontal o
verticalmente. Pegadas en diagonal **no** cuenta.

Contar cuantas islas hay en el mapa.

## Entrada

La primera linea tiene dos enteros `F` y `C`.
Las siguientes `F` lineas tienen `C` caracteres cada una, `.` o `#`.

## Salida

Un unico entero: la cantidad de islas.

## Restricciones

- `1 <= F, C <= 1000`
