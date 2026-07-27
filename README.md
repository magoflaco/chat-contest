# Chat Contest

Liga de problemas de Python para el club de programación, con vistas a las
olimpiadas. Cada 3 días el bot publica **3 problemas de dificultad escalonada** en el
grupo de WhatsApp, los chicos entregan su solución por privado, un juez automático la
corre contra tests ocultos y el ranking se actualiza solo.

El proyecto es de los chicos: la lógica está en Python y los problemas en YAML, así
que se puede aportar sin tocar una línea de JavaScript. Ver [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Cómo funciona

```
   WhatsApp                  HTTP local                    Docker
  ┌──────────┐   !entrega   ┌──────────────┐   entrega   ┌───────────┐
  │   bot/   │ ───────────► │    core/     │ ──────────► │  judge/   │
  │ Baileys  │ ◄─────────── │   Python     │ ◄────────── │  sin red  │
  └──────────┘   veredicto  └──────┬───────┘   salidas   └───────────┘
                                   │
                            ┌──────┴───────┐
                            │  SQLite +    │        ┌──────────┐
                            │ data/problems│ ─────► │   web/   │
                            └──────────────┘  API   │ ranking  │
                                                    └──────────┘
```

| Carpeta  | Qué hay | Lenguaje |
|----------|---------|----------|
| `core/`  | Toda la lógica: comandos, puntaje, rondas, ranking, IA | Python |
| `judge/` | El sandbox que ejecuta las entregas | Python + Docker |
| `data/`  | El banco de problemas (20 originales) | YAML + Python |
| `bot/`   | Gateway de WhatsApp. Traduce y nada más | JavaScript |
| `web/`   | Leaderboard público | HTML + CSS + JS, sin build |

El bot es a propósito la parte más chica y más aburrida del sistema. Todo lo
interesante pasa en `core/`.

---

## Arrancar en tu máquina

Necesitás **Python 3.11+**, **Node 20+** y **Docker**.

### 1. Configurar

```bash
git clone https://github.com/magoflaco/chat-contest
cd chat-contest
cp .env.example .env
```

Abrí el `.env` y completá al menos:

```ini
CORE_TOKEN=...            # generalo con: openssl rand -hex 32
ADMINS=5491122334455      # tu número, sin + ni espacios
NVIDIA_API_KEY=nvapi-...  # de build.nvidia.com, para !revisar y !pista
```

`GRUPO_JID` lo completás después: cuando el bot esté conectado, mandá `!jid` en el
grupo del club y te devuelve el valor.

### 2. Construir el juez

```bash
docker build -t chat-contest-judge:latest judge/
```

### 3. Levantar el core

```bash
cd core
pip install -r requirements.txt
python -m contest.cli chequeo     # te dice qué falta configurar
python -m contest.cli servir
```

### 4. Levantar el bot (en otra terminal)

```bash
cd bot
npm install
npm start
```

Escaneá el QR desde **WhatsApp > Dispositivos vinculados**. La sesión queda guardada
en `bot/auth_info_baileys/`, que está en `.gitignore` porque son credenciales de la
cuenta.

### 5. Publicar la primera ronda

Desde tu WhatsApp, por privado al bot:

```
!nuevaronda
```

### 6. Ver el leaderboard

```bash
cd web
python -m http.server 8080
```

Y abrí <http://127.0.0.1:8080>.

---

## Comandos

Las entregas van **siempre por privado**. El resto funciona también en el grupo.

### Competencia

| Comando | Qué hace |
|---|---|
| `!entrega <código> <tu código>` | Entrega tu solución. También acepta un `.py` adjunto. |
| `!probar <código> <tu código>` | La corre solo contra los ejemplos. No puntúa ni gasta intentos. |
| `!revisar <código>` | Te explica por qué falló, sin darte la solución. |
| `!ronda` | Qué hay abierto y cuánto falta. |

### Problemas

| Comando | Qué hace |
|---|---|
| `!problemas` | Lista los problemas de la ronda. |
| `!problema <código>` | El enunciado completo. |
| `!pista <código> [1-3]` | Una pista progresiva. |
| `!editorial <código>` | La explicación oficial, cuando la ronda cerró. |

### Ranking

| Comando | Qué hace |
|---|---|
| `!rank`, `!lb`, `!leaderboard` | La tabla de posiciones. |
| `!perfil` | Tus estadísticas. |
| `!misentregas` | Tus últimas entregas con su veredicto. |
| `!alias <nombre>` | Cómo aparecés en la tabla. |

### General

`!help`, `!reglas`, `!info`

### Admin

`!nuevaronda`, `!cerrarronda`, `!sospechas`, `!anular`, `!suspender`, `!reactivar`,
`!banco`, `!juez`, `!recalcular`

---

## Cómo se puntúa

```
puntos = base(dificultad) × factor_tiempo × factor_intentos
```

| Dificultad | Nombre | Base |
|---:|---|---:|
| 1 | Iniciación | 100 |
| 2 | Fácil | 200 |
| 3 | Media | 350 |
| 4 | Difícil | 550 |
| 5 | Olímpica | 800 |

- **Tiempo**: de 1.00 al abrir la ronda a 0.65 al cerrar. Resolver temprano vale
  más, pero entregar tarde sigue sumando mucho más que no entregar.
- **Intentos**: −15% por cada envío rechazado, con piso en 0.40. Los errores de
  sintaxis no penalizan, igual que en ICPC.
- Reenviar nunca te baja el puntaje: se guarda tu mejor resultado.

El diseño está justificado contra las reglas reales de ICPC, IOI y OIA en
[docs/EVALUACION.md](docs/EVALUACION.md).

---

## Por qué el juez es seguro

Los chicos mandan código arbitrario y el sistema lo ejecuta. Eso se toma en serio:

- Cada entrega corre en un **contenedor efímero sin red**, con el filesystem de solo
  lectura, sin privilegios, sin capabilities, y con límites de CPU, memoria y
  cantidad de procesos.
- **Las respuestas esperadas nunca entran al contenedor.** Solo entran las entradas;
  la comparación la hace el host. No hay archivo de respuestas que leer.
- Un análisis estático rechaza antes de ejecutar el código que intenta abrir red,
  tocar el disco o escapar del sandbox.
- Se comparan huellas de código entre participantes para detectar copias, y lo
  sospechoso queda **marcado para revisión humana, nunca sancionado solo**.

Todo esto se verifica corriendo ataques de verdad:

```bash
python scripts/verificar_sandbox.py
```

Corré ese script antes de desplegar y cada vez que toques `judge/`.
Ver [docs/ANTITRAMPA.md](docs/ANTITRAMPA.md).

---

## Desarrollo

```bash
cd core && python -m pytest              # la suite de tests
python -m contest.cli validar            # valida el banco de problemas
python -m contest.cli probar-todo        # corre cada solución de referencia
python -m contest.cli chequeo            # diagnóstico de la instalación
python scripts/verificar_sandbox.py      # ataques contra el juez
```

En Windows, sin Docker, podés poner `JUDGE_BACKEND=subprocess` para probar el flujo.
**Ese backend no aísla nada**: sirve para desarrollar, nunca para el VPS.

---

## Documentación

- [CONTRIBUTING.md](CONTRIBUTING.md) — cómo aportar un problema o un comando
- [docs/EVALUACION.md](docs/EVALUACION.md) — cómo evalúan ICPC, IOI y OIA, y qué copiamos
- [docs/ANTITRAMPA.md](docs/ANTITRAMPA.md) — las capas de defensa
- [docs/PROBLEMAS.md](docs/PROBLEMAS.md) — el formato de un problema, campo por campo
- [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md) — VPS y Cloudflare Pages
- [docs/DISENIO.md](docs/DISENIO.md) — cómo tocar la web sin romperle el estilo

---

## Licencia

MIT, ver [LICENSE](LICENSE). Los problemas importados de otras competencias
conservan su atribución y su licencia original en el campo `fuente` de su YAML.
