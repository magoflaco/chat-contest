En el pizarron quedo escrita una formula larguisima y hay que verificar si los
parentesis estan bien balanceados.

La formula usa tres tipos de simbolos: `()`, `[]` y `{}`. Esta bien balanceada si:

- cada simbolo que abre tiene su correspondiente que cierra, del mismo tipo, y
- los pares no se cruzan entre si.

Por ejemplo `([]{})` esta bien, pero `([)]` no, porque el corchete se cierra despues
de haber abierto un parentesis que todavia sigue abierto.

## Entrada

Una unica linea con una cadena `S` formada solo por los caracteres `(`, `)`, `[`,
`]`, `{` y `}`.

## Salida

`SI` si la formula esta bien balanceada, o `NO` si no lo esta.

## Restricciones

- `1 <= |S| <= 500000`
