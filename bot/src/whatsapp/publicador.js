// Publicador de anuncios.
//
// El scheduler del core deja en la base los mensajes que hay que publicar (una
// ronda nueva, el aviso de cierre, el resumen final). Este modulo los busca cada
// tanto y los manda.
//
// Se hace asi, con cola en la base, y no llamando al bot directo desde Python,
// porque si WhatsApp esta caido justo cuando toca abrir una ronda el anuncio
// tiene que salir igual apenas vuelva la conexion.

const core = require('../core/client');
const config = require('../config');
const { responder } = require('./handler');

let reloj = null;
let corriendo = false;

async function despachar(sock) {
    // sin reentrada: si una tanda tarda mas que el intervalo, no arrancamos otra
    if (corriendo) return;
    corriendo = true;

    try {
        const pendientes = await core.salientesPendientes();

        for (const mensaje of pendientes) {
            if (!mensaje.destino) {
                await core.fallarSaliente(mensaje.id, 'sin destino configurado').catch(() => {});
                continue;
            }

            try {
                await responder(sock, mensaje.destino, mensaje.texto, null);
                await core.confirmarSaliente(mensaje.id);
                console.log(`[publicador] enviado #${mensaje.id} a ${mensaje.destino}`);
            } catch (error) {
                console.error(`[publicador] fallo #${mensaje.id}:`, error.message);
                await core.fallarSaliente(mensaje.id, error.message).catch(() => {});
            }
        }
    } catch (error) {
        // el core caido no es noticia: puede estar reiniciando. lo reintentamos solo.
        if (!String(error.message).includes('fetch failed')) {
            console.error('[publicador]', error.message);
        }
    } finally {
        corriendo = false;
    }
}

function iniciarPublicador(sock) {
    detenerPublicador();
    reloj = setInterval(() => despachar(sock), config.pollSalientesMs);
    // una pasada inmediata, para no esperar el primer intervalo despues de conectar
    despachar(sock);
}

function detenerPublicador() {
    if (reloj) {
        clearInterval(reloj);
        reloj = null;
    }
}

module.exports = { iniciarPublicador, detenerPublicador };
