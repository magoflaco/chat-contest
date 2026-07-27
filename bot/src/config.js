// Configuracion del gateway. Lee el .env de la raiz del repo, el mismo que usa
// el core en Python, para que no haya dos fuentes de verdad que se desincronicen.

const path = require('path');
const fs = require('fs');

const RAIZ = path.resolve(__dirname, '..', '..');

// carga manual del .env: es media docena de lineas y nos ahorra una dependencia
function cargarEnv() {
    const archivo = path.join(RAIZ, '.env');
    if (!fs.existsSync(archivo)) return;

    for (const linea of fs.readFileSync(archivo, 'utf8').split('\n')) {
        const limpia = linea.trim();
        if (!limpia || limpia.startsWith('#') || !limpia.includes('=')) continue;

        const corte = limpia.indexOf('=');
        const clave = limpia.slice(0, corte).trim();
        const valor = limpia.slice(corte + 1).trim().replace(/^["']|["']$/g, '');
        // lo que ya venga del entorno gana, asi systemd puede sobrescribir
        if (process.env[clave] === undefined) process.env[clave] = valor;
    }
}

cargarEnv();

function num(clave, porDefecto) {
    const n = Number(process.env[clave]);
    return Number.isFinite(n) ? n : porDefecto;
}

module.exports = {
    raiz: RAIZ,
    botName: process.env.BOT_NAME || 'Chat Contest',
    grupoJid: process.env.GRUPO_JID || '',

    core: {
        url: `http://${process.env.CORE_HOST || '127.0.0.1'}:${num('CORE_PORT', 8000)}`,
        token: process.env.CORE_TOKEN || '',
        timeoutMs: num('CORE_TIMEOUT_MS', 120000),
    },

    // la sesion de WhatsApp vive fuera del repo (esta en .gitignore):
    // son credenciales de la cuenta, no codigo
    authDir: path.join(RAIZ, 'bot', 'auth_info_baileys'),

    // cada cuanto le preguntamos al core si tiene anuncios para publicar
    pollSalientesMs: num('POLL_SALIENTES_MS', 15000),

    // tamano maximo de un .py adjunto que aceptamos descargar
    maxAdjuntoBytes: num('JUDGE_MAX_SOURCE_BYTES', 65536),

    // stickers de Perove, generados por scripts/generar_stickers.py
    stickersDir: path.join(RAIZ, 'assets', 'stickers'),
};
