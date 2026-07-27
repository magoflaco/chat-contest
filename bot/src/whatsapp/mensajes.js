// Extraccion de contenido de un mensaje de Baileys.
//
// La estructura de `mensaje.message` cambia segun el tipo, y ademas viene
// envuelta cuando el mensaje es efimero o "view once". Aca normalizamos todo eso
// a una forma unica antes de mandarselo al core.

const { downloadMediaMessage } = require('@whiskeysockets/baileys');
const config = require('../config');

// extensiones que aceptamos como entrega. solo Python: es una liga de Python.
const EXTENSIONES_VALIDAS = ['.py', '.txt'];

/** Desenvuelve los mensajes efimeros / view-once para llegar al contenido real. */
function desenvolver(contenido) {
    let actual = contenido;
    for (let i = 0; i < 5 && actual; i++) {
        const interno =
            actual.ephemeralMessage?.message ||
            actual.viewOnceMessage?.message ||
            actual.viewOnceMessageV2?.message ||
            actual.viewOnceMessageV2Extension?.message ||
            actual.documentWithCaptionMessage?.message;
        if (!interno) break;
        actual = interno;
    }
    return actual;
}

/**
 * Normaliza un mensaje de Baileys.
 * @returns {{tipo: string, texto: string, documento?: object}|null}
 */
function extraer(mensaje) {
    const contenido = desenvolver(mensaje.message);
    if (!contenido) return null;

    if (contenido.conversation) {
        return { tipo: 'texto', texto: contenido.conversation };
    }
    if (contenido.extendedTextMessage?.text) {
        return { tipo: 'texto', texto: contenido.extendedTextMessage.text };
    }
    if (contenido.documentMessage) {
        const doc = contenido.documentMessage;
        return {
            tipo: 'documento',
            texto: doc.caption || '',
            documento: {
                nombre: doc.fileName || 'entrega.py',
                mimetype: doc.mimetype || '',
                bytes: Number(doc.fileLength || 0),
            },
        };
    }
    // imagen y audio se reconocen para poder contestar con un mensaje util,
    // no para procesarlos: las entregas por foto no se aceptan (ver README)
    if (contenido.imageMessage) {
        return { tipo: 'imagen', texto: contenido.imageMessage.caption || '' };
    }
    if (contenido.audioMessage) {
        return { tipo: 'audio', texto: '' };
    }
    return null;
}

/** True si el nombre del archivo parece una entrega de codigo. */
function esArchivoDeCodigo(nombre) {
    const minuscula = (nombre || '').toLowerCase();
    return EXTENSIONES_VALIDAS.some((ext) => minuscula.endsWith(ext));
}

/**
 * Descarga un documento adjunto y lo devuelve como texto.
 * Lanza si es demasiado grande o si no es texto decodificable.
 */
async function descargarComoTexto(mensaje, sock) {
    const buffer = await downloadMediaMessage(
        mensaje,
        'buffer',
        {},
        { reuploadRequest: sock.updateMediaMessage }
    );

    if (buffer.length > config.maxAdjuntoBytes) {
        throw new Error(
            `el archivo pesa ${Math.round(buffer.length / 1024)} KB y el maximo es ` +
            `${Math.round(config.maxAdjuntoBytes / 1024)} KB`
        );
    }

    // un .py con bytes nulos es un binario disfrazado, no codigo
    if (buffer.includes(0)) {
        throw new Error('eso no parece un archivo de texto');
    }

    return buffer.toString('utf8');
}

/** Numero pelado de un JID, sin sufijo de dispositivo ni dominio. */
function numeroDe(jid) {
    return (jid || '').split('@')[0].split(':')[0];
}

/** True si el JID es un LID (el identificador opaco nuevo de WhatsApp). */
function esLid(jid) {
    return String(jid || '').includes('@lid');
}

/**
 * Quien mando el mensaje, en todas las formas con las que llego.
 *
 * WhatsApp esta migrando de numeros de telefono a LIDs. Segun el chat, Baileys
 * entrega `remoteJid`/`participant` como uno u otro, y pone la forma alternativa
 * en `remoteJidAlt`/`participantAlt`.
 *
 * Devolvemos las dos y marcamos cual preferimos: el telefono, porque es lo que
 * se configura en ADMINS y lo que una persona reconoce. El core se queda con esa
 * como identidad canonica y recuerda el mapeo, asi nadie termina contado dos
 * veces en el ranking.
 *
 * @returns {{principal: string, alternos: string[]}}
 */
function remitenteDe(mensaje) {
    const clave = mensaje.key || {};
    const enGrupo = String(clave.remoteJid || '').endsWith('@g.us');

    const primario = enGrupo ? clave.participant : clave.remoteJid;
    const alterno = enGrupo ? clave.participantAlt : clave.remoteJidAlt;

    const candidatos = [primario, alterno].filter(Boolean);
    // el telefono primero; si solo hay LID, se usa el LID
    const telefono = candidatos.find((j) => !esLid(j));
    const principal = numeroDe(telefono || candidatos[0]);

    const alternos = candidatos
        .map(numeroDe)
        .filter((n) => n && n !== principal);

    return { principal, alternos };
}

module.exports = {
    extraer,
    esArchivoDeCodigo,
    descargarComoTexto,
    numeroDe,
    remitenteDe,
};
