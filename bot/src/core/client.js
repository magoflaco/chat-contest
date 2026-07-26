// Cliente HTTP del core en Python.
//
// El gateway no sabe nada de puntajes, rondas ni problemas: solo traduce entre
// WhatsApp y esta API. Toda la logica vive del lado de Python para que el club
// pueda aportar sin tocar JavaScript.

const config = require('../config');

async function pedir(ruta, opciones = {}) {
    const controlador = new AbortController();
    const reloj = setTimeout(() => controlador.abort(), config.core.timeoutMs);

    try {
        const respuesta = await fetch(`${config.core.url}${ruta}`, {
            ...opciones,
            signal: controlador.signal,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${config.core.token}`,
                ...(opciones.headers || {}),
            },
        });

        if (!respuesta.ok) {
            const cuerpo = await respuesta.text().catch(() => '');
            throw new Error(`core respondio ${respuesta.status}: ${cuerpo.slice(0, 300)}`);
        }

        // los endpoints de confirmacion devuelven cuerpos triviales
        const texto = await respuesta.text();
        return texto ? JSON.parse(texto) : null;
    } catch (error) {
        if (error.name === 'AbortError') {
            throw new Error('el core no respondio a tiempo');
        }
        throw error;
    } finally {
        clearTimeout(reloj);
    }
}

/**
 * Manda un mensaje entrante al core y devuelve los mensajes a responder.
 * @returns {Promise<Array<{texto: string, destino: string}>>}
 */
async function procesarMensaje(mensaje) {
    const datos = await pedir('/bot/mensaje', {
        method: 'POST',
        body: JSON.stringify(mensaje),
    });
    return datos?.mensajes || [];
}

/** Anuncios que el scheduler dejo listos para publicar. */
async function salientesPendientes() {
    return (await pedir('/bot/salientes')) || [];
}

async function confirmarSaliente(id) {
    await pedir(`/bot/salientes/${id}/enviado`, { method: 'POST' });
}

async function fallarSaliente(id, error) {
    const query = encodeURIComponent(String(error).slice(0, 300));
    await pedir(`/bot/salientes/${id}/fallo?error=${query}`, { method: 'POST' });
}

/** Registra a alguien que hablo en el grupo sin usar un comando. */
async function registrarVisto(mensaje) {
    await pedir('/bot/visto', { method: 'POST', body: JSON.stringify(mensaje) });
}

/** True si el core esta levantado. Se usa al arrancar, para avisar temprano. */
async function disponible() {
    try {
        const r = await fetch(`${config.core.url}/api/salud`, {
            signal: AbortSignal.timeout(5000),
        });
        return r.ok;
    } catch {
        return false;
    }
}

module.exports = {
    procesarMensaje,
    salientesPendientes,
    confirmarSaliente,
    fallarSaliente,
    registrarVisto,
    disponible,
};
