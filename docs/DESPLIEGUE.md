# Despliegue

El sistema son tres piezas que se despliegan distinto:

| Pieza | Dónde | Cómo |
|---|---|---|
| `core/` + `judge/` | Tu VPS | systemd + Docker |
| `bot/` | Tu VPS | systemd |
| `web/` | Cloudflare Pages | arrastrar la carpeta, o conectar el repo |

---

## Antes de empezar

Corré esto en el VPS y que **no falle nada**:

```bash
cd chat-contest
python scripts/verificar_sandbox.py
```

Si algún ataque no queda contenido, no sigas. El juez ejecuta código arbitrario de
terceros: es la única parte del sistema donde un error se paga caro.

---

## VPS

### 1. Dependencias

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip docker.io curl git
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 2. Usuario propio

El core no tiene por qué correr como root, y el bot menos:

```bash
sudo useradd --system --create-home --shell /bin/bash contest
# necesita hablar con el socket de Docker para lanzar el juez
sudo usermod -aG docker contest
sudo su - contest
```

### 3. Instalar

```bash
git clone https://github.com/magoflaco/chat-contest
cd chat-contest

python3.12 -m venv .venv
.venv/bin/pip install -r core/requirements.txt

cd bot && npm ci --omit=dev && cd ..

docker build -t chat-contest-judge:latest judge/
```

### 4. Configurar

```bash
cp .env.example .env
chmod 600 .env          # tiene la API key, que no la lea todo el mundo
nano .env
```

Lo que hay que completar sí o sí:

```ini
CORE_TOKEN=<openssl rand -hex 32>
ADMINS=549...
NVIDIA_API_KEY=nvapi-...
JUDGE_BACKEND=docker          # NUNCA subprocess en el servidor
RONDA_TZ=America/Argentina/Buenos_Aires
```

Verificá antes de seguir:

```bash
.venv/bin/python -m core.contest.cli chequeo
```

### 5. Vincular WhatsApp

El QR hay que escanearlo a mano una vez. Levantá el core y el bot en dos terminales:

```bash
.venv/bin/python -m contest.cli servir      # desde core/
node index.js                               # desde bot/
```

Escaneá desde **WhatsApp > Dispositivos vinculados**. La sesión queda en
`bot/auth_info_baileys/`.

Después mandá `!jid` en el grupo del club y pegá el resultado en `GRUPO_JID` del
`.env`. Sin eso, las rondas no se publican.

### 6. Servicios de systemd

`/etc/systemd/system/chat-contest-core.service`:

```ini
[Unit]
Description=Chat Contest - core
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=contest
WorkingDirectory=/home/contest/chat-contest/core
ExecStart=/home/contest/chat-contest/.venv/bin/python -m contest.cli servir
Restart=always
RestartSec=10

# el core no necesita escribir en ningun lado salvo su propio directorio
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/contest/chat-contest/var /home/contest/chat-contest/submissions

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/chat-contest-bot.service`:

```ini
[Unit]
Description=Chat Contest - gateway de WhatsApp
After=network.target chat-contest-core.service
Requires=chat-contest-core.service

[Service]
Type=simple
User=contest
WorkingDirectory=/home/contest/chat-contest/bot
ExecStart=/usr/bin/node index.js
Restart=always
RestartSec=15

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now chat-contest-core chat-contest-bot
sudo journalctl -u chat-contest-core -f
```

### 7. Exponer la API por HTTPS

La web va a estar en Cloudflare Pages (HTTPS), así que la API **también tiene que
estar en HTTPS** o el navegador va a bloquear los pedidos por contenido mixto.

Con Caddy es una línea de configuración. `/etc/caddy/Caddyfile`:

```
contest.tudominio.com {
    # solo la API publica sale a internet
    handle /api/* {
        reverse_proxy 127.0.0.1:8000
    }

    # /bot/* es la interfaz privada del gateway: no tiene por que ser accesible
    # desde afuera, aunque tenga token
    handle {
        respond "Chat Contest" 200
    }
}
```

```bash
sudo apt install -y caddy
sudo systemctl reload caddy
```

Caddy saca el certificado de Let's Encrypt solo.

**Importante**: `CORE_HOST` tiene que quedar en `127.0.0.1`. El core no debe escuchar
en todas las interfaces: quien entra es Caddy, no internet.

---

## Cloudflare Pages

### 1. Apuntar la web a tu API

Editá `web/config.js`:

```js
window.CONTEST_API = 'https://contest.tudominio.com';
window.CONTEST_REFRESCO_MS = 60000;
```

### 2. Publicar

Opción rápida, sin conectar nada:

```bash
npx wrangler pages deploy web --project-name chat-contest
```

Opción recomendada, para que se actualice sola en cada push:

1. En el panel de Cloudflare: **Workers & Pages > Create > Pages > Connect to Git**
2. Elegí `magoflaco/chat-contest`
3. Configuración de build:
   - **Framework preset**: None
   - **Build command**: *(vacío)*
   - **Build output directory**: `web`

No hay build porque no hace falta: la web es HTML, CSS y JS a secas.

### 3. Verificar

Abrí la URL de Pages y mirá la consola del navegador. Si ves un error de CORS o de
contenido mixto, es lo de siempre: la API está en HTTP y la página en HTTPS.

---

## Operación

### Mirar qué pasa

```bash
sudo journalctl -u chat-contest-core -f
sudo journalctl -u chat-contest-bot -f
```

Desde WhatsApp, siendo admin: `!info`, `!banco`, `!juez`, `!sospechas`.

### Backup

Lo único irreemplazable es la base:

```bash
# se puede copiar en caliente, sin frenar el servicio
sqlite3 var/contest.db ".backup /home/contest/backups/contest-$(date +%F).db"
```

Ponelo en el cron:

```
0 4 * * * cd /home/contest/chat-contest && sqlite3 var/contest.db ".backup /home/contest/backups/contest-$(date +\%F).db"
```

Los problemas y el código ya están en GitHub. Las entregas de `submissions/` se pueden
perder sin drama: los veredictos y los puntajes están en la base.

### Actualizar

```bash
cd /home/contest/chat-contest
git pull
.venv/bin/pip install -r core/requirements.txt
cd bot && npm ci --omit=dev && cd ..

# si cambio algo del juez
docker build -t chat-contest-judge:latest judge/
python scripts/verificar_sandbox.py

sudo systemctl restart chat-contest-core chat-contest-bot
```

Reiniciar no pierde nada: el estado vive en SQLite, y los anuncios pendientes están
en una cola en la base.

### Si WhatsApp cierra la sesión

Pasa cada tanto. El bot lo detecta y avisa en el log. Hay que:

```bash
sudo systemctl stop chat-contest-bot
rm -rf /home/contest/chat-contest/bot/auth_info_baileys
cd /home/contest/chat-contest/bot && node index.js    # escaneá el QR
# Ctrl+C y
sudo systemctl start chat-contest-bot
```

---

## Checklist antes de abrir la primera ronda de verdad

- [ ] `python scripts/verificar_sandbox.py` pasa los 16 ataques
- [ ] `JUDGE_BACKEND=docker` en el `.env`
- [ ] `CORE_TOKEN` no es el de ejemplo
- [ ] `chmod 600 .env`
- [ ] `CORE_HOST=127.0.0.1` (el core no escucha en internet)
- [ ] `GRUPO_JID` completo y probado con `!info`
- [ ] `ADMINS` con tu número
- [ ] La API responde por HTTPS y la web la ve
- [ ] El backup de la base está en el cron
- [ ] `python -m contest.cli probar-todo` pasa los 10 problemas
