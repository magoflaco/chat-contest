# Anti-trampa

El objetivo no es cazar gente. Es **que hacer trampa no sirva de nada** y que el
sistema sea imposible de romper por accidente o a propósito.

Son cuatro capas independientes. Ninguna alcanza sola, y cada una está pensada
suponiendo que las otras van a fallar.

---

## Capa 1 — Análisis estático

`core/contest/antifraud.py`

Antes de ejecutar nada, se parsea la entrega con `ast` y se rechaza si intenta:

- importar módulos de red (`socket`, `urllib`, `requests`, …)
- importar módulos de proceso o filesystem (`subprocess`, `os` peligroso, `shutil`,
  `pathlib`, `io`, …)
- llamar a `open`, `eval`, `exec`, `compile`, `__import__`, `getattr`
- tocar `__subclasses__`, `__globals__`, `__builtins__`, `__mro__` y demás vías
  clásicas de escape

El veredicto en ese caso es `SEC` y queda registrado en la tabla `auditoria`.

**Esta capa es la más débil de las cuatro**, porque una lista negra siempre se puede
esquivar. Está para dar un mensaje claro y educativo ("las soluciones leen de la
entrada estándar y escriben en la salida estándar") y para frenar lo obvio, no para
ser la defensa real.

Tiene un requisito tan importante como atrapar cosas: **no puede molestar a nadie que
escriba código normal**. `sys`, `math`, `collections`, `heapq`, `itertools`, `bisect`
y `functools` se usan todo el tiempo en olimpiadas y pasan sin problema. Hay tests
específicos para eso en `core/tests/test_antifraud.py`, con diez soluciones legítimas
que no pueden dar falso positivo. Un anti-trampa que molesta hace que los chicos dejen
de participar, que es peor que la trampa.

Si el código no parsea, **no se marca nada**: eso lo detecta el juez como `CE`. No
vamos a acusar de trampa a alguien que se olvidó dos puntos.

---

## Capa 2 — El sandbox

`core/contest/judge.py` y `judge/Dockerfile`

Esta es la defensa que de verdad cuenta. Cada entrega corre en un contenedor efímero:

| Medida | Para qué |
|---|---|
| `--network none` | No puede filtrar los tests ni descargarse una solución |
| `--read-only` | No puede modificar nada |
| `--tmpfs /tmp:size=16m,noexec` | Único lugar escribible, chico y sin ejecutar |
| `--user 10001:10001` | Sin privilegios |
| `--cap-drop ALL` | Sin capabilities de Linux |
| `--security-opt no-new-privileges` | No puede escalar |
| `--memory` + `--memory-swap` iguales | Sin swap: no puede esquivar el límite de RAM |
| `--pids-limit 64` | Una bomba de forks no llega a nada |
| `--cpus 1.0` | No puede acaparar el VPS |
| `--ulimit nofile=64` | No puede agotar los descriptores |
| `RLIMIT_AS`, `RLIMIT_CPU`, `RLIMIT_FSIZE`, `RLIMIT_NPROC` | Límites por proceso, dentro del contenedor |
| Timeout de reloj de pared | Corta lo que se cuelga, incluso al contenedor entero |

La imagen **no contiene el código del bot, ni la base, ni las claves**. Aunque alguien
lograra ejecutar lo que quisiera ahí adentro, se encontraría con un contenedor vacío
y sin salida.

### Por qué el juez no ve las respuestas

Esta es la decisión de diseño más importante del sistema, y salió de encontrar una
vulnerabilidad real.

La primera versión copiaba al contenedor los `.in` **y los `.ans`**, y comparaba
adentro. El análisis estático frenaba `open('/work/casos/001.ans')`, pero no
`io.open(...)`. Se podía leer la respuesta y ganar puntos sin resolver nada.

Se podría haber agregado `io` a la lista negra. Pero después aparecería
`codecs.open`, y después `os.fdopen`, y después otra. **Una lista negra nunca está
completa.**

El arreglo fue estructural: al contenedor ahora **solo entran las entradas**. Las
respuestas se quedan del lado del host y la comparación la hace
`core/contest/comparador.py` con las salidas ya devueltas. No hay ningún archivo de
respuestas dentro del sandbox, así que no hay nada que blindar.

La lección general: cuando puedas elegir entre *impedir que alguien acceda a algo* y
*que ese algo no esté ahí*, elegí siempre lo segundo.

### Verificarlo

```bash
python scripts/verificar_sandbox.py
```

Corre 16 entregas maliciosas de verdad (leer los tests, salir a internet, bomba de
forks, agotar la memoria, escapar por `__subclasses__`, inundar la salida, …) y
verifica que ninguna consiga lo que busca.

**Corré esto antes de desplegar y cada vez que toques `judge/` o `antifraud.py`.**

---

## Capa 3 — Detección de copias

Cuando entra una entrega se calcula su huella y se compara contra las de los demás
participantes en el mismo problema.

El método es **winnowing** (Schleimer, Wilkerson & Aiken, 2003), el mismo principio
detrás de MOSS:

1. El código se tokeniza y se **normaliza**: los nombres de variables se reemplazan
   por un símbolo genérico, los números por `0`, los strings por `S`, y se descartan
   comentarios e indentación. Renombrar variables y agregar comentarios —justo lo que
   hace alguien que copia y disimula— no cambia nada.
2. Se hashean todos los k-gramas de 9 tokens.
3. De cada ventana de 4 hashes se guarda el mínimo. Eso reduce el volumen y garantiza
   que cualquier coincidencia suficientemente larga sea detectada.
4. Se compara con el índice de Jaccard.

Por encima de `SIMILITUD_UMBRAL` (0.82 por defecto), la entrega queda **marcada**.

### Marcada, no anulada

Nunca se sanciona en automático, y es deliberado: **dos soluciones correctas de un
problema fácil se parecen legítimamente**. "Leer N, sumar los pares, imprimir" se
escribe de tres formas y listo. Anular por similitud castigaría a gente honesta.

Lo que hace el sistema es avisarle a un admin:

```
!sospechas          lista lo marcado, con el motivo
!anular <id>        anula una entrega y recalcula el ranking
!suspender <num>    saca a alguien de la tabla
```

La decisión la toma una persona, mirando el código y hablando con los chicos.

Tampoco se compara a alguien consigo mismo: reenviar una versión corregida de tu
propio código es lo normal.

---

## Capa 4 — Límites de ritmo

| Límite | Valor | Por qué |
|---|---|---|
| `COOLDOWN_ENTREGA_SEG` | 45 s | No se puede tantear la respuesta a fuerza de reenviar |
| `MAX_INTENTOS` | 12 por problema | Idem, y evita saturar el juez |
| Reenvío idéntico | rechazado | Si no, se podría reenviar lo mismo hasta que un TLE al límite pase por suerte |
| `JUDGE_MAX_SOURCE_BYTES` | 64 KB | Nadie necesita más para un problema de olimpiada |

El reenvío idéntico se detecta por el hash del código **normalizado**, así que cambiar
nombres de variables no lo esquiva. Además tiene un efecto amable: si alguien manda
dos veces sin querer, no se le gasta un intento.

---

## Auditoría

Todo lo relevante queda en la tabla `auditoria`, con fecha, usuario y detalle:

| Evento | Cuándo |
|---|---|
| `entrega_bloqueada` | El análisis estático frenó algo |
| `similitud_alta` | Una entrega se pareció demasiado a otra |
| `entrega_anulada` | Un admin anuló algo, con su motivo |
| `usuario_suspendido` | Un admin suspendió a alguien |
| `juez_error` | El juez falló (no es culpa del participante) |
| `comando_error` | Se rompió un comando |

Nada se borra. Cualquier decisión se puede reconstruir después, que es lo que hace que
sea justa.

---

## Lo que NO hacemos, y por qué

**No aceptamos entregas por foto.** Se evaluó usar un modelo de visión para leer el
código de una imagen. Se descartó: el OCR corrige errores de sintaxis sin querer, y
eso significa que la misma entrega puntúa distinto según cómo la mandaste. Un `.py` o
texto pegado, nada más.

**No intentamos detectar código generado por IA.** No se puede hacer con precisión
aceptable, y acusar en falso a un chico es mucho peor que dejar pasar una trampa. Lo
que sí hacemos es que `!revisar` y `!pista` sean tan útiles que usar la IA *dentro*
del sistema —donde tiene prohibido dar la solución— sea más cómodo que ir a buscarla
afuera.

**No penalizamos entregar tarde más allá del piso de 0.65.** Alguien que resuelve un
problema difícil el último día aprendió lo mismo que quien lo resolvió el primero.
El decay premia la velocidad; no está para castigar a quien tuvo una semana ocupada.
