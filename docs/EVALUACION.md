# Cómo se evalúa en las competencias reales (y qué copiamos)

Este documento resume cómo puntúan las competencias de programación de verdad y
justifica las decisiones de diseño de Chat Contest. Si vas a tocar `core/contest/scoring.py`,
leé esto primero.

---

## 1. ICPC (International Collegiate Programming Contest)

Es el formato de los contests universitarios, y el que usan **RPC (Rioplatense
Programming Contest)** y los regionales latinoamericanos.

**Cómo se juzga cada problema**

- Pass/fail. No hay puntaje parcial: o pasás *todos* los tests secretos o no pasás.
- Los tests son secretos. Sólo se publican 1-2 casos de ejemplo dentro del enunciado.
- Se valida salida exacta (o con tolerancia numérica, si el problema lo declara).
- Hay límites de tiempo y memoria por caso de prueba.

**Cómo se rankea**

1. Primero por cantidad de problemas resueltos (más es mejor).
2. Empate: por **tiempo total**, que es la suma de los minutos transcurridos hasta
   cada envío aceptado, más **20 minutos de penalización por cada envío incorrecto
   previo a resolver ese problema**.
3. Los envíos incorrectos a problemas que nunca resolviste **no** penalizan.
4. `Compile Error` y `Judge Error` no penalizan.

Fuentes: [reglas oficiales en Kattis/ICPC](https://submit.icpc.global/help/rules),
[ECNA – Rules & Info](https://ec.na.icpc.global/rules-info/),
[OI Wiki: formato ICPC/CCPC](https://en.oi-wiki.org/contest/icpc/).

**Qué tomamos de acá:** el modelo pass/fail contra tests secretos, la penalización
por envío incorrecto, y la idea de que el tiempo importa.

---

## 2. IOI (International Olympiad in Informatics)

Es el formato de las olimpiadas de secundaria, y el que sigue la **OIA (Olimpíada
Informática Argentina)**.

**Cómo se juzga cada problema**

- Desde IOI 2010 las tareas se dividen en **subtareas** de dificultad creciente.
- Una subtarea otorga puntos sólo si **todos** sus tests pasan dentro de los límites.
  Formalmente: el puntaje de una subtarea es el **mínimo** de los puntajes de sus casos.
- El puntaje final de una subtarea es el **máximo** logrado entre todos tus envíos:
  reenviar nunca te baja el puntaje.
- Existen problemas de optimización (NP-hard) donde el puntaje es proporcional a qué
  tan buena es tu solución respecto de la mejor conocida.

**Cómo se rankea**

Suma simple de puntajes. No hay penalización por tiempo dentro de la competencia.

Fuentes: [IOI 2026 Contest Rules](https://ioi2026.uz/contest-rules),
[IOI 2022 Competition Rules](https://ioi2022.id/competition-rules/),
[Wikipedia: IOI](https://en.wikipedia.org/wiki/International_Olympiad_in_Informatics).

**Qué tomamos de acá:** la estructura de subtareas en el schema de problemas (para
que los chicos se acostumbren al formato real y podamos importar problemas de OIA),
y la regla de que reenviar no destruye tu mejor resultado.

---

## 3. OIA (Olimpíada Informática Argentina)

- En el certamen nacional se resuelven **entre 3 y 6 problemas de dificultad variada
  en 4 horas**. ([OIA – Programación](https://www.oia.unsam.edu.ar/oia-programacion/))
- Formato de evaluación tipo IOI, con subtareas.
- El comité acepta problemas propuestos por la comunidad
  ([solicitud de problemas](https://www.oia.unsam.edu.ar/solicitud-de-problemas/)).

**Qué tomamos de acá:** publicar **3 problemas de dificultad escalonada por ronda**.
Es el mismo rango que enfrentan en el nacional, así que entrenan la habilidad real de
repartir el tiempo entre un problema fácil, uno medio y uno duro.

---

## 4. Codeforces (para la parte de velocidad)

Codeforces usa *decay*: el valor de un problema baja de forma continua a medida que
pasa el tiempo del contest, y cada envío incorrecto resta un fijo. Esto premia
resolver rápido y bien **sin necesidad de desempates artificiales**: los puntajes
casi nunca empatan.

**Qué tomamos de acá:** la fórmula de puntaje. Ver sección 5.

---

## 5. El sistema de Chat Contest

Somos una liga asincrónica: los chicos resuelven en su casa, en días distintos, con
ventanas de 72 horas. Eso hace que ICPC puro (tiempo total acumulado) sea injusto
—alguien que vio el problema recién a las 20h no puede competir contra quien lo vio
a los 5 minutos— y que IOI puro no premie la velocidad en absoluto.

Así que combinamos: **pass/fail estilo ICPC + decay estilo Codeforces**, con el
tiempo medido *desde que la ronda se publicó*.

### Fórmula

```
puntos = base(dificultad) × factor_tiempo × factor_intentos
```

**`base(dificultad)`** — la dificultad va de 1 a 5:

| Dificultad | Nombre       | Base |
|-----------:|--------------|-----:|
| 1          | Iniciación   |  100 |
| 2          | Fácil        |  200 |
| 3          | Media        |  350 |
| 4          | Difícil      |  550 |
| 5          | Olímpica     |  800 |

**`factor_tiempo`** — decae linealmente durante la ventana de la ronda:

```
frac_restante = (fin_ronda - momento_del_envio_aceptado) / (fin_ronda - inicio_ronda)
factor_tiempo = 0.65 + 0.35 × frac_restante
```

Resolver en el instante cero vale 1.00× y resolver justo sobre la bocina vale 0.65×.
Nunca baja de 0.65: llegar tarde cuesta, pero resolver un problema difícil tarde
sigue valiendo mucho más que no resolverlo.

**`factor_intentos`** — 15% menos por cada envío rechazado previo al aceptado:

```
factor_intentos = max(0.40, 1 - 0.15 × intentos_fallidos)
```

Con piso en 0.40 para que insistir siempre sea mejor que abandonar. Igual que en
ICPC, **los `Compile Error` no cuentan como intento fallido** (son un error de tipeo,
no un error de razonamiento) y los problemas que nunca resolvés no penalizan nada.

### Ejemplo

Problema de dificultad 3 (base 350), ventana de 72 h:

| Quién | Resolvió a las | Intentos fallidos | Cuenta                        | Puntos |
|-------|---------------:|------------------:|-------------------------------|-------:|
| Ana   |             4 h |                 0 | 350 × (0.65+0.35×0.944) × 1.00 |    342 |
| Beto  |            40 h |                 0 | 350 × (0.65+0.35×0.444) × 1.00 |    282 |
| Cami  |             4 h |                 2 | 350 × 0.978 × 0.70             |    240 |

### Desempate

Con decay los empates son raros, pero si pasan, el orden es:

1. Más puntos.
2. Más problemas resueltos.
3. Menor tiempo total hasta los envíos aceptados (criterio ICPC).
4. Quien llegó a ese puntaje primero.

### Puntaje parcial (opcional, por problema)

Los problemas que declaran `subtareas:` en su YAML puntúan estilo IOI: cada subtarea
aporta su fracción de la base, y se aplica el mismo `factor_tiempo`. Sirve para que
un chico que recién arranca se lleve algo por resolver el caso chico, en vez de
irse con cero. Se activa por problema, no globalmente.

---

## 6. Veredictos

Usamos la nomenclatura estándar de los jueces online, para que cuando los chicos
entren a Codeforces o Kattis ya la conozcan:

| Sigla | Significado                | ¿Penaliza? |
|-------|----------------------------|------------|
| `AC`  | Accepted                   | —          |
| `WA`  | Wrong Answer               | sí         |
| `TLE` | Time Limit Exceeded        | sí         |
| `MLE` | Memory Limit Exceeded      | sí         |
| `RE`  | Runtime Error              | sí         |
| `CE`  | Compile Error (sintaxis)   | **no**     |
| `PE`  | Presentation Error         | sí         |
| `SEC` | Violación de seguridad     | **sí, y queda auditado** |
| `IE`  | Internal Error (culpa nuestra) | **no**  |

---

## 7. Anti-trampa

El objetivo no es atrapar gente sino **quitarle sentido a hacer trampa**. Ver
`docs/ANTITRAMPA.md` para el detalle de las medidas implementadas.
