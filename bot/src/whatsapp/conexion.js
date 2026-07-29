// Conexion a WhatsApp con reconexion automatica.
//
// Basado en el patron del bot anterior del club, con dos agregados importantes:
// backoff exponencial (reconectar en bucle sin esperar hace que WhatsApp te
// limite) y distinguir el cierre por sesion invalida, donde reconectar no sirve
// y hay que escanear el QR de nuevo.

const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, Browsers,
        fetchLatestWaWebVersion } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');

const config = require('../config');
const handler = require('./handler');
const { iniciarPublicador, detenerPublicador } = require('./publicador');

const RECONEXION_BASE_MS = 2000;
const RECONEXION_MAX_MS = 60000;
const TIMEOUT_VERSION_MS = 10000;

let intentos = 0;
let cerrandoAdrede = false;

// De donde sale la version del protocolo de WhatsApp Web.
//
// Baileys trae una version fija adentro, y `fetchLatestBaileysVersion()` la
// compara contra un JSON que vive en el repo de la propia libreria. Cuando ese
// JSON queda atrasado -- y queda -- la funcion devuelve igual `isLatest: true`
// mientras WhatsApp rechaza el handshake con 405. El bot muere antes de generar
// el QR y el diagnostico apunta a cualquier lado menos a la version.
//
// `fetchLatestWaWebVersion()` le pregunta a los servidores de WhatsApp (saca el
// client_revision de web.whatsapp.com/sw.js), que es la unica fuente que manda.
// Nunca lanza: si falla devuelve la version vieja con `isLatest: false`, y ahi
// hay que avisar fuerte porque el 405 vuelve.
//
// Se consulta en cada reconexion, no una sola vez. Si cacheamos la version y
// WhatsApp sube la suya, el backoff reintentaria para siempre con una version
// que ya no sirve; una peticion HTTP al lado de una espera de hasta 60 s no se
// nota.
async function versionDeWhatsApp() {
    const { version, isLatest, error } =
        await fetchLatestWaWebVersion({ signal: AbortSignal.timeout(TIMEOUT_VERSION_MS) });

    if (!isLatest) {
        console.error('[whatsapp] no se pudo consultar la version a WhatsApp ' +
                      `(${error?.message || 'sin detalle'}). Se usa la que trae Baileys, ` +
                      `${version.join('.')}. Si el handshake falla con 405, es por esto.`);
    } else {
        console.log(`[whatsapp] protocolo ${version.join('.')}`);
    }
    return version;
}

async function iniciar() {
    const { state, saveCreds } = await useMultiFileAuthState(config.authDir);
    const version = await versionDeWhatsApp();

    const sock = makeWASocket({
        version,
        auth: state,
        printQRInTerminal: false,
        browser: Browsers.ubuntu(config.botName),
        // no marcamos en linea todo el tiempo: el bot solo responde cuando le hablan
        markOnlineOnConnect: false,
        // Nota: se probo `shouldSyncHistoryMessage: () => false` para ahorrar
        // memoria, pero Baileys avisa que eso le impide acceder al mapeo inicial
        // de LIDs y termina causando errores de sesion. Para un bot que tiene que
        // quedarse conectado, esa estabilidad vale mas que los MB que ahorraba;
        // el techo de memoria lo pone systemd con MemoryMax.
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

            // 405 en el handshake es WhatsApp rechazando la version del cliente.
            // Reintentar sirve solo si la version que pedimos cambio, asi que lo
            // decimos en vez de dejar al proximo mirando reintentos mudos.
            if (codigo === 405) {
                console.error('[whatsapp] 405: WhatsApp rechazo la version del cliente. ' +
                              'Si se repite, actualiza Baileys (npm update @whiskeysockets/baileys).');
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
