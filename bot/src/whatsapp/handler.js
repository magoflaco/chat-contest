// Handler de mensajes entrantes.
//
// Es deliberadamente delgado: reconoce si el mensaje es un comando, resuelve el
// adjunto si lo hay, y le pasa todo al core. No decide nada de la competencia.

const core = require('../core/client');
const stickers = require('./stickers');
const { extraer, esArchivoDeCodigo, descargarComoTexto, remitenteDe } = require('./mensajes');

const PREFIJO = '!';

// una entrega larga puede tardar (el juez corre 17 casos en un contenedor).
// mientras tanto no procesamos otro mensaje del mismo chat, para que las
// respuestas no lleguen desordenadas ni se dupliquen entregas.
const enProceso = new Set();

function esComando(texto) {
    const limpio = (texto || '').trimStart();
    return limpio.startsWith(PREFIJO) && limpio.length > 1 && !/\s/.test(limpio[1]);
}

async function responder(sock, jid, texto, citado) {
    if (!texto) return;
    // WhatsApp corta los mensajes muy largos; partimos en trozos por linea
    for (const trozo of partir(texto, 3800)) {
        await sock.sendMessage(jid, { text: trozo }, citado ? { quoted: citado } : undefined);
    }
}

function partir(texto, maximo) {
    if (texto.length <= maximo) return [texto];

    const trozos = [];
    let actual = '';
    for (const linea of texto.split('\n')) {
        if (actual.length + linea.length + 1 > maximo) {
            if (actual) trozos.push(actual);
            actual = linea;
        } else {
            actual = actual ? `${actual}\n${linea}` : linea;
        }
    }
    if (actual) trozos.push(actual);
    return trozos;
}

function registrar(sock) {
    sock.ev.on('messages.upsert', async (evento) => {
        if (evento.type !== 'notify') return;

        for (const mensaje of evento.messages) {
            try {
                await manejar(sock, mensaje);
            } catch (error) {
                console.error('[handler] error no atrapado:', error.message);
            }
        }
    });
}

async function manejar(sock, mensaje) {
    if (!mensaje.message || mensaje.key.fromMe) return;

    const jid = mensaje.key.remoteJid;
    if (!jid || jid === 'status@broadcast') return;

    const item = extraer(mensaje);
    if (!item) return;

    const esGrupo = jid.endsWith('@g.us');
    const { principal: numero, alternos } = remitenteDe(mensaje);
    const nombre = mensaje.pushName || '';

    // fotos y audios: contestamos una sola vez y por privado, para no ensuciar el grupo
    if (item.tipo === 'imagen' || item.tipo === 'audio') {
        if (!esGrupo) {
            const que = item.tipo === 'imagen' ? 'fotos' : 'audios';
            await responder(sock, jid,
                `no acepto entregas por ${que}.\n\n` +
                'mandame el codigo como texto o como archivo .py:\n' +
                '```!entrega R1-A\nn = int(input())\nprint(n)```', mensaje);
        }
        return;
    }

    let texto = item.texto || '';
    let adjunto = null;

    // documento adjunto: si es .py lo bajamos y lo mandamos como adjunto del comando
    if (item.tipo === 'documento') {
        if (!esArchivoDeCodigo(item.documento.nombre)) {
            if (!esGrupo) {
                await responder(sock, jid,
                    `solo acepto archivos .py, y me mandaste "${item.documento.nombre}".`, mensaje);
            }
            return;
        }

        // sin epigrafe no sabemos a que problema responde: asumimos !entrega y
        // dejamos que el core explique como se indica el codigo del problema
        if (!esComando(texto)) {
            texto = `${PREFIJO}entrega ${texto}`.trim();
        }

        try {
            const contenido = await descargarComoTexto(mensaje, sock);
            adjunto = { nombre: item.documento.nombre, contenido };
        } catch (error) {
            await responder(sock, jid, `no pude leer el archivo: ${error.message}`, mensaje);
            return;
        }
    }

    if (!esComando(texto)) {
        // en el grupo damos de alta a quien participa aunque no use comandos,
        // asi aparece en el ranking apenas entregue algo
        if (esGrupo && numero) {
            core.registrarVisto({ jid, numero, nombre, texto: '', es_grupo: true, alternos })
                .catch(() => {});
        }
        return;
    }

    const llave = `${jid}:${numero}`;
    if (enProceso.has(llave)) {
        await responder(sock, jid, 'esperá que todavía estoy con lo anterior.', mensaje);
        return;
    }
    enProceso.add(llave);

    sock.readMessages([mensaje.key]).catch(() => {});
    // el juez tarda unos segundos: mostrar "escribiendo" evita que parezca colgado
    sock.sendPresenceUpdate('composing', jid).catch(() => {});

    try {
        const respuestas = await core.procesarMensaje({
            jid,
            numero,
            alternos,
            nombre,
            texto,
            es_grupo: esGrupo,
            adjunto,
        });

        for (const r of respuestas) {
            await responder(sock, r.destino || jid, r.texto, r.destino === jid ? mensaje : null);
            // el sticker va despues del texto: primero la informacion, despues Perove
            await stickers.enviar(sock, r.destino || jid, r.sticker);
        }
    } catch (error) {
        console.error('[handler] el core fallo:', error.message);
        await responder(sock, jid,
            'no pude procesar eso, el sistema no esta respondiendo. probá de nuevo en un rato.',
            mensaje);
    } finally {
        enProceso.delete(llave);
        sock.sendPresenceUpdate('paused', jid).catch(() => {});
    }
}

module.exports = { registrar, responder };
