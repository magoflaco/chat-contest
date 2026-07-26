// Conexion a WhatsApp con reconexion automatica.
//
// Basado en el patron del bot anterior del club, con dos agregados importantes:
// backoff exponencial (reconectar en bucle sin esperar hace que WhatsApp te
// limite) y distinguir el cierre por sesion invalida, donde reconectar no sirve
// y hay que escanear el QR de nuevo.

const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, Browsers } =
    require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');

const config = require('../config');
const handler = require('./handler');
const { iniciarPublicador, detenerPublicador } = require('./publicador');

const RECONEXION_BASE_MS = 2000;
const RECONEXION_MAX_MS = 60000;

let intentos = 0;
let cerrandoAdrede = false;

async function iniciar() {
    const { state, saveCreds } = await useMultiFileAuthState(config.authDir);

    const sock = makeWASocket({
        auth: state,
        printQRInTerminal: false,
        browser: Browsers.ubuntu(config.botName),
        // no marcamos en linea todo el tiempo: el bot solo responde cuando le hablan
        markOnlineOnConnect: false,
        // sin esto Baileys guarda todos los mensajes del grupo en memoria
        shouldSyncHistoryMessage: () => false,
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, qr, lastDisconnect } = update;

        if (qr) {
            console.log('\nescanea este codigo desde WhatsApp > Dispositivos vinculados:\n');
            qrcode.generate(qr, { small: true });
        }

        if (connection === 'open') {
            intentos = 0;
            console.log(`[whatsapp] ${config.botName} conectada como ${sock.user?.id}`);
            if (!config.grupoJid) {
                console.log('[whatsapp] GRUPO_JID esta vacio: manda !jid en el grupo del club ' +
                            'y copia el resultado al .env, si no las rondas no se van a publicar.');
            }
            iniciarPublicador(sock);
            return;
        }

        if (connection === 'close') {
            detenerPublicador();
            if (cerrandoAdrede) return;

            const codigo = lastDisconnect?.error?.output?.statusCode;

            if (codigo === DisconnectReason.loggedOut) {
                console.error('[whatsapp] la sesion se cerro desde el telefono. ' +
                              `borra ${config.authDir} y volve a escanear el QR.`);
                process.exit(1);
            }

            intentos += 1;
            const espera = Math.min(RECONEXION_BASE_MS * 2 ** (intentos - 1), RECONEXION_MAX_MS);
            console.log(`[whatsapp] desconectado (${codigo || 'sin codigo'}), ` +
                        `reintento ${intentos} en ${Math.round(espera / 1000)}s`);
            setTimeout(() => iniciar().catch((e) => console.error('[whatsapp]', e.message)), espera);
        }
    });

    handler.registrar(sock);
    return sock;
}

function cerrar() {
    cerrandoAdrede = true;
    detenerPublicador();
}

module.exports = { iniciar, cerrar };
