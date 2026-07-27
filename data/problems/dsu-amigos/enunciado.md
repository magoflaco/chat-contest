En el club hay `N` chicos, numerados de `1` a `N`. Al principio ninguno conoce a
ninguno.

Van a pasar `Q` eventos, de dos tipos:

- `A u v` : `u` y `v` se hacen amigos.
- `C u` : hay que informar cuantos chicos hay en el grupo de `u`.

Dos chicos estan en el mismo grupo si son amigos, o si estan conectados por una cadena
de amistades. Cada chico esta siempre en su propio grupo, aunque no tenga amigos.

## Entrada

La primera linea tiene dos enteros `N` y `Q`.
Las siguientes `Q` lineas tienen un evento cada una, con el formato de arriba.

## Salida

Una linea por cada evento de tipo `C`, con el tamanio del grupo.

## Restricciones

- `1 <= N <= 200000`
- `1 <= Q <= 300000`
- `1 <= u, v <= N`
- En los eventos de tipo `A`, puede pasar que `u = v`, o que ya sean amigos.
