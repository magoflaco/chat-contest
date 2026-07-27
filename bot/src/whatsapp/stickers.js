// Envio de los stickers de Perove.
//
// Los .webp ya vienen generados y commiteados (scripts/generar_stickers.py), asi
// que en produccion no hace falta Pillow ni ffmpeg: solo leer el archivo.
//
// Se cachean en memoria porque pesan 2 KB cada uno y se mandan seguido; releerlos
// del disco en cada AC no tiene sentido.

const fs = require('fs');
const path = require('path');
const config = require('../config');

const cache = new Map();

/** Nombres validos. Tiene que coincidir con STICKERS en core/contest/commands. */
const DISPONIBLES = new Set(['wave', 'cast', 'jump', 'idle']);

function cargar(nombre) {
    if (cache.has(nombre)) return cache.get(nombre);

    // el nombre viene del core, pero igual se valida contra la lista blanca:
    // nunca construimos una ruta con texto que no controlamos del todo
    if (!DISPONIBLES.has(nombre)) {
        cache.set(nombre, null);
        return null;
    }

    const ruta = path.join(config.stickersDir, `perove-${nombre}.webp`);
    let buffer = null;
    try {
        buffer = fs.readFileSync(ruta);
    } catch (error) {
        console.error(`[stickers] no pude leer ${ruta}: ${error.message}`);
    }
    cache.set(nombre, buffer);
    return buffer;
}

/**
 * Manda un sticker. Nunca lanza: un sticker que falla no puede tumbar la
 * respuesta que de verdad le importa al participante.
 */
async function enviar(sock, jid, nombre) {
    if (!nombre) return;

    const buffer = cargar(nombre);
    if (!buffer) return;

    try {
        await sock.sendMessage(jid, { sticker: buffer });
    } catch (error) {
        console.error(`[stickers] no se pudo enviar '${nombre}': ${error.message}`);
    }
}

module.exports = { enviar, DISPONIBLES };
