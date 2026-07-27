# Cómo aportar

Este repo es del club. Si se te ocurre un problema, un comando o una mejora, mandala.
No hace falta que sepas JavaScript ni Docker: casi todo se hace en Python y YAML.

---

## Antes que nada

```bash
git clone https://github.com/magoflaco/chat-contest
cd chat-contest
cp .env.example .env
cd core && pip install -r requirements.txt
```

Para trabajar en tu máquina sin Docker, poné en el `.env`:

```ini
JUDGE_BACKEND=subprocess
```

Eso corre las entregas directo, sin aislamiento. Está bien para desarrollar. **Nunca
lo uses en el servidor**, porque cualquiera podría hacer lo que quiera con la máquina.

---

## Aportar un problema

Es la forma más útil de aportar, y la más divertida.

### 1. Creá la carpeta

```
data/problems/tu-problema/
    problema.yaml        metadatos
    enunciado.md         el enunciado
    solucion.py          tu solución de referencia
    generador.py         genera los casos de prueba
    tests/sample/01.in   el ejemplo del enunciado
    tests/sample/01.ans
```

El nombre de la carpeta es el `slug`: minúsculas, números y guiones.

### 2. Escribí el enunciado

En `enunciado.md`, con estas tres secciones sí o sí:

```markdown
Una historia breve que plantea el problema.

## Entrada

Qué se lee, línea por línea.

## Salida

Qué hay que imprimir.

## Restricciones

- `1 <= N <= 100000`
- `1 <= ai <= 10^9`
```

**Las restricciones no son opcionales.** Sin ellas nadie sabe si su solución tiene
que ser O(N) o si le alcanza con O(N²), y eso es la mitad del problema.

Consejos que salen de leer muchos enunciados malos:

- Escribí en español rioplatense, directo. Nada de "el usuario deberá ingresar".
- La historia sirve para hacerlo memorable, pero que sea corta. Tres líneas alcanzan.
- Si hay un caso borde raro (N=1, la respuesta puede ser 0, puede no haber solución),
  decilo explícitamente en las restricciones o en la salida.
- Nada de emojis, en ningún campo.

### 3. Escribí `problema.yaml`

```yaml
slug: tu-problema
titulo: El título que se ve en el bot
dificultad: 3              # 1 a 5, ver la tabla de abajo
tags: [dos-punteros, ordenamiento]
autor: Tu Nombre

limites:
  tiempo_ms: 2000
  memoria_mb: 256

validacion:
  tipo: tokens             # tokens | exacta | numerica
  # tolerancia: 1e-6       # solo si tipo es numerica

fuente:
  tipo: original           # original si lo inventaste vos

pistas:
  - "Una pista suave que empuje a pensar, sin resolverlo."
  - "Una pista más fuerte, con el algoritmo pero sin código."

editorial: |
  Cómo se resuelve, por qué funciona y qué complejidad tiene.
  Se publica cuando la ronda cierra. Escribila pensando en alguien que
  intentó el problema y no le salió: contale qué le faltó ver.
```

Cómo elegir la dificultad:

| Nivel | Qué significa |
|---|---|
| 1 | Leer la entrada, un `if` y un ciclo. Para quien recién arranca. |
| 2 | Arreglos, strings, ordenar, contar. Una idea simple pero no obvia. |
| 3 | Dos punteros, búsqueda binaria, greedy, grafos básicos, DP de una dimensión. |
| 4 | DP no trivial, grafos con pesos, Fenwick, DSU, geometría simple. |
| 5 | Nivel nacional: combinar dos técnicas, DP sobre estados no obvios, teoría de números. |

Si dudás entre dos niveles, elegí el más bajo. Un problema etiquetado más fácil de lo
que es frustra; uno etiquetado más difícil solo sorprende para bien.

### 4. Escribí la solución de referencia

`solucion.py`, leyendo de la entrada estándar y escribiendo en la salida estándar.
Tiene que entrar **cómoda** en el límite de tiempo, no justo: si tu solución tarda
1.9 s con un límite de 2 s, la de un chico que hizo lo mismo pero un poco menos
prolijo va a dar TLE sin merecerlo. Apuntá a usar menos de la mitad del límite.

### 5. Escribí el generador

`generador.py` recibe una semilla por `sys.argv[1]` e imprime **un** caso válido.
Usar la semilla como semilla del `random` hace que los casos sean reproducibles: el
mismo generador siempre produce los mismos tests.

```python
import random
import sys

semilla = int(sys.argv[1])
rng = random.Random(semilla * 104729)

if semilla == 1:
    n, a = 1, [1]                       # el caso mínimo
elif semilla == 2:
    n = 200000; a = [10**9] * n         # el caso máximo
elif semilla <= 6:
    n = rng.randint(2, 20)              # chiquitos, fáciles de depurar a mano
    a = [rng.randint(1, 100) for _ in range(n)]
else:
    n = rng.randint(50000, 200000)      # grandes, para castigar lo cuadrático
    a = [rng.randint(1, 10**9) for _ in range(n)]

print(n)
print(" ".join(map(str, a)))
```

Los casos que más valen son los que rompen soluciones *casi* correctas: el mínimo, el
máximo, todo igual, ya ordenado, ordenado al revés, la respuesta es 0, no hay solución.
Dedicale a eso las primeras semillas.

### 6. Generá los tests y probá

```bash
python scripts/generar_tests.py tu-problema --casos 15
cd core && python -m contest.cli probar-todo --slug tu-problema
```

El primer comando corre tu generador 15 veces y calcula cada respuesta con tu
solución. El segundo verifica que tu solución pase los 15 casos.

Si querés subtareas estilo IOI, agregá al YAML:

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

### 7. Mandá el pull request

Contá en la descripción de dónde salió la idea y qué técnica entrena.

---

## Traer problemas de COCI

COCI (Croatian Open Competition in Informatics) es **la mejor fuente que
encontramos**, y vale la pena entender por qué.

Casi todos los jueces online (Kattis, Codeforces, AtCoder) publican solo los casos de
ejemplo. Los tests ocultos no son públicos, y sin ellos no se puede juzgar nada: las
herramientas tipo `kattis-cli` bajan samples, que no nos alcanzan.

COCI en cambio publica en [hsin.hr/coci/archive](https://hsin.hr/coci/archive/) los
enunciados, **los datos de prueba completos** y las soluciones de todas sus
competencias desde 2006/2007. Son 6 contests por año, 5 tareas por contest, casi 20
años: unas 500 tareas con tests reales. Y sus casos vienen ya agrupados por subtarea,
que mapea directo a nuestro formato.

```bash
# ver qué trae un contest, sin escribir nada
python scripts/importar_coci.py 2020_2021 1 --listar

# importar una tarea
python scripts/importar_coci.py 2020_2021 1 --tarea patkice --dificultad 3
```

### Lo que el importador NO hace

Trae los tests, la estructura de subtareas y la atribución. **No trae el enunciado ni
la solución**, y marca el problema con `borrador: true`, que lo deja fuera del banco:
no puede salir sorteado en una ronda hasta que alguien lo complete.

Falta hacer dos cosas por problema, y las dos son trabajo humano:

1. **Escribir el enunciado.** El original está en un PDF y hay que redactar un resumen
   **propio** en español. No copies el texto: COCI publica su archivo para que la gente
   practique, pero no da una licencia explícita de redistribución. Un resumen tuyo con
   atribución y link es seguro; una copia textual en un repo público no lo es.
2. **Escribir `solucion.py`.** Los `.ans` vienen de COCI y son correctos, así que la
   solución no hace falta para juzgar; hace falta para que la CI pueda verificar que
   los tests siguen sanos y para que quede una referencia de cómo se resuelve.

Después:

```bash
cd core && python -m contest.cli probar-todo --slug coci-20-1-patkice
```

y sacá el `borrador: true` del YAML.

Un problema importado bien hecho es un aporte grande: te obliga a resolverlo, a
entender por qué las subtareas están donde están, y a escribir un enunciado claro.
Es la mejor forma de aprender a diseñar problemas.

---

## Aportar un problema de otra competencia

Se puede, con dos condiciones: **atribución completa** y **verificar la licencia**.

```yaml
fuente:
  tipo: rpc                # icpc | rpc | oia | ioi | kattis | otro
  nombre: Rioplatense Programming Contest, Problema C
  url: https://...
  anio: 2024
  licencia: "consultar con los organizadores"
```

El bot muestra esa atribución al final del enunciado, automáticamente.

Ojo con esto: muchos jueces online **prohíben redistribuir sus enunciados**. Si no
estás seguro de que se pueda, en vez de copiar el texto poné un resumen tuyo del
problema y el link al original. Nadie se enoja por un link.

---

## Generar un problema con IA

```bash
python scripts/generar_problema.py --dificultad 2 --tema "grafos"
```

El script le pide un problema al modelo y **lo valida antes de aceptarlo**: corre la
solución contra los samples que el propio modelo escribió, genera casos con el
generador, y verifica el formato del banco. Si algo falla, reintenta.

Lo que pasa la validación queda en `data/problems/_borradores/`, que el cargador
ignora y que no se sube al repo. **No está en el banco todavía, y no lo muevas sin
leerlo.**

La validación automática comprueba que el problema sea *consistente*, no que sea
*bueno*. Un ejemplo real de la primera corrida: el modelo generó un problema de contar
frutas cuya solución imprimía los resultados en el orden de un `Counter`. Todo
validaba, porque la solución de referencia y los tests coincidían entre sí. Pero el
enunciado nunca decía en qué orden había que imprimir, así que un chico que ordenara
alfabéticamente —lo más natural— habría recibido WA sin entender nunca por qué.

Cosas así solo las ve una persona. Antes de mover un borrador al banco:

1. Leelo como si fueras a resolverlo. ¿Hay algo ambiguo? ¿El orden de la salida está
   definido? ¿Qué pasa si la respuesta es 0, o si no existe?
2. ¿La dificultad declarada es la real?
3. ¿El generador cubre el mínimo, el máximo y los casos degenerados?
4. Escribí las pistas y mejorá la editorial.
5. `python scripts/generar_tests.py <slug> --casos 15`

---

## Aportar un comando

Los comandos viven en `core/contest/commands/`. Agregar uno es esto:

```python
# core/contest/commands/rank.py

from . import comando, Contexto


@comando("racha", "streak",
         uso="!racha",
         ayuda="Cuántas rondas seguidas venís entregando.",
         categoria="Ranking")
def cmd_racha(ctx: Contexto) -> str:
    return f"llevás {calcular_racha(ctx.numero)} rondas seguidas"
```

Si creás un archivo nuevo, sumalo a `cargar_todos()` al final de
`core/contest/commands/__init__.py`.

Lo que tenés a mano en `ctx`:

| Campo | Qué es |
|---|---|
| `ctx.numero` | Quién lo mandó, normalizado |
| `ctx.nombre` | Su nombre de WhatsApp |
| `ctx.es_grupo` | Si vino del grupo o de un privado |
| `ctx.es_admin` | Si está en `ADMINS` |
| `ctx.args` | Todo lo que sigue al comando, en crudo |
| `ctx.argv` | Eso mismo partido en palabras |
| `ctx.arg(0)` | El primer argumento, o `""` |
| `ctx.adjunto_texto` | El contenido del `.py` adjunto, si vino |

Y en el decorador: `solo_admin=True`, `solo_privado=True`, `oculto=True`.

### Reglas del texto que devuelve un comando

1. **Nada de emojis.** En ningún lado. Es una decisión del proyecto: usamos texto,
   separadores y sangrías. Hay un test que lo verifica.
2. WhatsApp entiende `*negrita*`, `_cursiva_` y ` ```monoespaciado``` `.
3. Que entre en una pantalla de celular. Si es largo, resumí y ofrecé otro comando
   para el detalle.
4. Usá los helpers de `core/contest/format.py`: `titulo()`, `dificultad()`,
   `duracion()`, `tabla_ranking()`.

---

## Antes de mandar el pull request

```bash
cd core
python -m pytest                          # los tests tienen que pasar
python -m contest.cli validar             # el banco tiene que estar sano
cd .. && python scripts/generar_tests.py --verificar
```

Si tocaste algo de `judge/` o de `antifraud.py`, además:

```bash
python scripts/verificar_sandbox.py       # los 16 ataques tienen que quedar contenidos
```

Si tu cambio arregla un bug, sumá un test que falle sin el arreglo. Si agrega una
regla de puntaje, sumá el test a `core/tests/test_scoring.py` explicando qué propiedad
tiene que valer.

---

## Estilo

- **Nombres en español.** Es un club de habla hispana; el código se lee mejor así.
  Las palabras que son de la disciplina (`slug`, `commit`, `AC`, `TLE`) se dejan
  como están.
- **Comentá el porqué, no el qué.** `i += 1  # incrementa i` no le sirve a nadie.
  `# arrancamos en 1 porque el primero no tiene anterior con qué compararse` sí.
- Sin acentos en el código y los comentarios (evita líos de encoding entre Windows
  y Linux). En los archivos `.md` y en los enunciados sí van, escribilos bien.
- Líneas de hasta 110 caracteres.

---

## Ideas si no sabés por dónde empezar

- Escribir un problema de dificultad 2. Es lo que más falta en el banco.
- Escribir la editorial de un problema que ya está pero no la tiene.
- Un comando `!versus <alguien>` que compare tu ranking con el de otro.
- Un comando `!racha` con las rondas seguidas entregando.
- Que la web muestre un gráfico de la evolución de puntos por ronda.
- Traducir un problema de la OIA vieja al formato del banco, con su atribución.
