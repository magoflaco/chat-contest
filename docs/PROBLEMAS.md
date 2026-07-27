# El formato de un problema, campo por campo

Referencia completa de `problema.yaml`. Para la guía paso a paso de cómo escribir uno,
mirá [CONTRIBUTING.md](../CONTRIBUTING.md).

El formato está inspirado en el
[problem package format de Kattis/ICPC](https://www.kattis.com/problem-package-format/),
que es el que usan las competencias de verdad. Lo simplificamos donde no nos aportaba
nada y le agregamos lo que sí necesitamos (dificultad, pistas, editorial en el mismo
archivo).

---

## Estructura de la carpeta

```
data/problems/<slug>/
    problema.yaml         metadatos               obligatorio
    enunciado.md          el enunciado            obligatorio
    solucion.py           solución de referencia  obligatorio en la práctica
    generador.py          genera los casos        recomendado
    tests/
        sample/           casos PÚBLICOS          al menos 1
            01.in
            01.ans
        secret/           casos OCULTOS           al menos 3
            001.in
            001.ans
            s1/           (si hay subtareas, una carpeta por subtarea)
                001.in
                001.ans
```

El nombre de la carpeta **es** el `slug` y tiene que coincidir con el campo del YAML.
Minúsculas, números y guiones, de 2 a 60 caracteres.

---

## Campos

### Obligatorios

```yaml
slug: dos-punteros          # igual al nombre de la carpeta
titulo: Las mesas del comedor
dificultad: 3               # entero de 1 a 5
```

La dificultad determina el puntaje base: 100, 200, 350, 550 y 800.

### Borrador

```yaml
borrador: true
```

Un problema marcado así **queda fuera del banco**: no lo carga `banco()` y por lo tanto
no puede salir sorteado en una ronda. Sirve para los problemas a medio terminar,
típicamente los recién importados de COCI, que todavía no tienen enunciado propio ni
solución de referencia.

`python -m contest.cli validar` los lista aparte, para que se sepa qué hay pendiente.

Cuando el problema esté completo, sacá el campo.

### Límites

```yaml
limites:
  tiempo_ms: 3000           # de 200 a 15000. por defecto 2000
  memoria_mb: 256           # de 32 a 1024. por defecto 256
```

El límite de tiempo es **por caso de prueba**, no total.

Regla práctica: poné el triple de lo que tarda tu solución de referencia. Python es
lento y desparejo, y un límite ajustado castiga a quien tuvo la idea correcta pero la
escribió un poco menos optimizada.

El juez además acota la memoria al mínimo entre lo que pide el problema y
`JUDGE_MEMORY_MB` del `.env`, así ningún problema puede pedir más de lo que el
servidor tolera.

### Validación

```yaml
validacion:
  tipo: tokens              # tokens | exacta | numerica
  tolerancia: 1e-6          # solo se usa con numerica
```

| Tipo | Cómo compara | Cuándo usarlo |
|---|---|---|
| `tokens` | Ignora todo el espaciado | **El que va casi siempre.** Justo con chicos que están aprendiendo a formatear |
| `exacta` | Byte a byte (salvo el `\n` final) | Cuando el formato de salida es parte del problema. Si la única diferencia es espaciado, devuelve `PE` |
| `numerica` | Como tokens, con tolerancia | Cuando la respuesta es un número real |

### Tags y autoría

```yaml
tags: [dos-punteros, ordenamiento, greedy]
autor: Nombre de quien lo escribió
```

Los tags se muestran en el bot y en la web. Usá kebab-case y sé consistente con los
que ya existen en el banco.

### Fuente

```yaml
fuente:
  tipo: original            # original | icpc | rpc | oia | ioi | kattis | generado | otro
  nombre: Rioplatense Programming Contest 2024, Problema C
  url: https://...
  anio: 2024
  licencia: "consultar con los organizadores"
```

Si `tipo` no es `original`, el campo `nombre` es **obligatorio** y el bot muestra la
atribución al pie del enunciado automáticamente.

Para COCI hay un importador dedicado: ver la sección correspondiente en
[CONTRIBUTING.md](../CONTRIBUTING.md#traer-problemas-de-coci).

Antes de importar un problema de otra competencia, leé la advertencia sobre
redistribución en [CONTRIBUTING.md](../CONTRIBUTING.md#aportar-un-problema-de-otra-competencia).

### Subtareas (opcional, estilo IOI)

```yaml
subtareas:
  - id: s1
    peso: 40
    descripcion: "N <= 2000 (alcanza una solución cuadrática)"
    semillas: "1-6"
  - id: s2
    peso: 60
    descripcion: "sin restricciones adicionales"
    semillas: "7-15"
```

Con subtareas, el problema puntúa parcial: si resolvés solo el caso chico, te llevás
el 40% de la base en vez de irte con cero. Es lo que hace que un chico que recién
arranca pueda sumar en un problema de dificultad 5.

Reglas:

- Una subtarea otorga su peso **solo si todos sus casos pasan** (la regla del mínimo
  de IOI).
- Los casos de cada subtarea van en `tests/secret/<id>/`.
- `semillas` le dice a `scripts/generar_tests.py` qué semillas mandar a cada carpeta.
- Los pesos deberían sumar 100, aunque el cálculo los normaliza igual.

### Pistas y editorial

```yaml
pistas:
  - "Una pista suave, que solo indique qué tipo de problema es."
  - "Una pista media, con el enfoque pero sin implementación."
  - "Una pista fuerte: el algoritmo y su complejidad, sin código."

editorial: |
  Cómo se resuelve, por qué funciona, y qué complejidad tiene.
  Contá también cuál es el error típico: eso es lo que más se agradece
  cuando intentaste el problema y no te salió.
```

Las pistas escritas a mano siempre le ganan a las generadas: si el problema tiene
`pistas`, `!pista` usa esas y ni llama al modelo. La editorial se publica con
`!editorial` cuando la ronda cierra.

---

## Casos de prueba

### Samples

Van en `tests/sample/`. Son **públicos**: aparecen en el enunciado que muestra el bot,
y cuando una entrega falla en un sample se le muestra la diferencia exacta.

Hace falta al menos uno. Dos es mejor: el primero para ilustrar el formato, el segundo
para mostrar un caso borde.

### Secretos

Van en `tests/secret/`. Con estos se juzga de verdad. **Nunca se muestran**, ni
siquiera cuando una entrega falla en uno: solo se dice en qué número de caso falló.

Hacen falta al menos 3. Con el generador es fácil tener 15.

Los que más valen son los que rompen soluciones *casi* correctas:

- el mínimo posible (`N=1`, arreglo vacío)
- el máximo posible (para que las soluciones lentas den TLE)
- todos los elementos iguales
- ya ordenado, y ordenado al revés
- la respuesta es 0, o no existe solución
- estructuras degeneradas (un grafo que es un camino, una grilla toda llena)

Dedicá las primeras semillas del generador a estos casos, explícitamente, y las
últimas a datos al azar.

---

## Qué valida el sistema

Al cargar el banco, `core/contest/problems.py` rechaza un problema si:

- falta `problema.yaml`, o el YAML está mal formado
- el `slug` no coincide con el nombre de la carpeta, o tiene caracteres raros
- falta `titulo`
- `dificultad` no es un entero de 1 a 5
- falta el enunciado
- `tiempo_ms` o `memoria_mb` están fuera de rango
- `validacion.tipo` no es uno de los tres válidos
- una subtarea no declara `id` y `peso`
- una subtarea declarada no tiene casos en `tests/secret/<id>/`
- `fuente.tipo` no es válido, o un problema importado no declara `fuente.nombre`
- hay menos de 1 sample o menos de 3 casos secretos

Un problema inválido **no tumba el banco**: se saltea, se avisa por consola y el resto
sigue funcionando. Para ver todos los errores de una:

```bash
cd core && python -m contest.cli validar
```

Y para verificar que las soluciones de referencia efectivamente pasen:

```bash
python -m contest.cli probar-todo
```

Las dos cosas las corre la CI en cada pull request.
