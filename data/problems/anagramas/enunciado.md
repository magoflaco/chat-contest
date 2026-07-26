En el taller de palabras del club tienen `N` fichas, cada una con una palabra escrita
en minusculas.

Dos palabras son anagramas si una se puede formar reordenando las letras de la otra.
Por ejemplo `roma` y `amor` son anagramas, y `casa` y `saca` tambien.

Las fichas se agrupan poniendo juntas todas las que son anagramas entre si.
Averiguar cuantas fichas tiene el grupo mas numeroso.

## Entrada

La primera linea tiene un entero `N`.
Las siguientes `N` lineas tienen una palabra cada una, en minusculas sin acentos.

## Salida

Un unico entero: la cantidad de fichas del grupo mas grande.

## Restricciones

- `1 <= N <= 100000`
- Cada palabra tiene entre `1` y `20` letras de la `a` a la `z`.
- Puede haber palabras repetidas, y cuentan como fichas distintas.
