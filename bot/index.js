// Punto de entrada del gateway de WhatsApp.
//
// Antes de conectarse comprueba que el core este arriba: sin el, el bot no puede
// responder nada util, y es mejor avisarlo con un mensaje claro que dejar que
// falle mensaje por mensaje.

const config = require('./src/config');
const core = require('./src/core/client');
const conexion = require('./src/whatsapp/conexion');

async function main() {
    console.log(`${config.botName} - gateway de WhatsApp`);
    console.log(`core: ${config.core.url}`);

    if (!config.core.token) {
        console.error('\nCORE_TOKEN esta vacio en el .env. El core va a rechazar todo.');
        process.exit(1);
    }

    if (!(await core.disponible())) {
        console.error(
            `\nno puedo hablar con el core en ${config.core.url}.\n` +
            'levantalo primero, en otra terminal:\n' +
            '  cd core && python -m contest.cli servir\n'
        );
        process.exit(1);
    }
    console.log('core: ok\n');

    await conexion.iniciar();
}

for (const senial of ['SIGINT', 'SIGTERM']) {
    process.on(senial, () => {
        console.log('\ncerrando...');
        conexion.cerrar();
        process.exit(0);
    });
}

// una promesa rechazada sin atrapar no puede tumbar el bot en produccion
process.on('unhandledRejection', (razon) => {
    console.error('[bot] promesa rechazada sin atrapar:', razon);
});

main().catch((error) => {
    console.error('no se pudo arrancar:', error);
    process.exit(1);
});
