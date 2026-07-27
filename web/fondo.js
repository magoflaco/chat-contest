// Fondo animado: sprites pixel art flotando con parallax.
//
// La idea es que el fondo tenga profundidad sin robarle atencion al contenido.
// Cada decoracion vive en una "capa" (--z): las de adelante se mueven mucho con
// el mouse, las del fondo casi nada. Eso alcanza para que la pagina se sienta
// tridimensional aunque todo este dibujado con bordes duros.
//
// El movimiento se hace SOLO con `transform` sobre variables CSS, y se actualiza
// dentro de un requestAnimationFrame. Mover cosas con `left`/`top` en cada
// mousemove obliga al navegador a recalcular el layout entero y en un celular
// modesto se nota enseguida.

const HOJA = document.documentElement;

/** indices de las celdas de assets/deco.png (ver scripts/generar_decoraciones.py) */
const DECO = {
    nube: 0, estrella: 1, chispa: 2, rombo: 3,
    burbuja: 4, bit: 5, pluma: 6, corazon: 7,
};

/** Composicion del fondo: que sprite, donde, de que tamanio y a que profundidad.
 *
 * Las posiciones estan en porcentaje de la ventana y elegidas a mano, no al
 * azar: quedan lejos del centro, que es donde va el texto. El tamanio es
 * siempre multiplo de 16 (el lado nativo del sprite) para no romper el pixel art.
 */
const COMPOSICION = [
    // sprite      x%    y%   lado  z     opacidad  dur    giro
    ['nube',        4,    8,   48,  0.9,  0.55,     7.0,  0],
    ['nube',       82,   14,   64,  0.5,  0.45,     9.0,  0],
    ['nube',       68,   72,   48,  0.7,  0.35,     8.0,  0],
    ['nube',       10,   84,   32,  1.2,  0.40,     6.0,  0],
    ['estrella',   90,   34,   32,  1.6,  0.70,     4.5,  12],
    ['estrella',    6,   46,   16,  2.0,  0.60,     3.5, -14],
    ['estrella',   46,    4,   16,  1.1,  0.45,     5.0,  10],
    ['chispa',     18,   26,   32,  1.4,  0.50,     5.5,  0],
    ['chispa',     76,   56,   32,  1.8,  0.45,     6.5,  0],
    ['rombo',      93,   62,   32,  2.2,  0.55,     4.0,  14],
    ['rombo',       3,   64,   16,  1.5,  0.45,     5.0, -10],
    ['burbuja',    88,   88,   32,  1.0,  0.40,     7.5,  0],
    ['burbuja',    30,   92,   16,  1.7,  0.35,     6.0,  0],
    ['pluma',      12,   40,   32,  0.8,  0.35,     8.5,  16],
    ['pluma',      72,   28,   16,  1.3,  0.30,     7.0, -12],
    ['bit',        58,   88,   16,  2.4,  0.35,     4.0,  0],
    ['bit',        26,   58,   16,  0.6,  0.25,     9.0,  0],
];

/** Cuanto se desplaza la capa mas cercana, en pixeles, de borde a borde. */
const RECORRIDO = 16;

function quiereQuieto() {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** Crea los nodos del fondo. Devuelve el contenedor, o null si no corresponde. */
function construir() {
    if (quiereQuieto()) return null;

    const fondo = document.createElement('div');
    fondo.id = 'fondo';
    fondo.setAttribute('aria-hidden', 'true');

    const aura = document.createElement('div');
    aura.className = 'aura';
    fondo.appendChild(aura);

    // en pantallas chicas se dibuja menos: son mas angostas y el telefono
    // agradece pintar la mitad de capas
    const angosta = window.matchMedia('(max-width: 700px)').matches;
    const piezas = angosta ? COMPOSICION.filter((_, i) => i % 2 === 0) : COMPOSICION;

    for (const [nombre, x, y, lado, z, opacidad, dur, giro] of piezas) {
        const el = document.createElement('div');
        el.className = 'deco';
        el.style.cssText = [
            `--n:${DECO[nombre]}`,
            `--x:${x}%`,
            `--y:${y}%`,
            `--lado:${angosta ? Math.max(16, lado / 2) : lado}px`,
            `--z:${z}`,
            `--opacidad:${opacidad}`,
            `--dur:${dur}s`,
            // el retraso desfasa los flotes para que no suban todos a la vez
            `--retraso:${(-dur * Math.random()).toFixed(2)}s`,
            `--giro:${giro}deg`,
        ].join(';');
        fondo.appendChild(el);
    }

    document.body.appendChild(fondo);
    return { fondo, aura };
}

/** Engancha el parallax al mouse (y al giroscopio, si el aparato lo ofrece). */
function seguirPuntero({ fondo, aura }) {
    let destinoX = 0;
    let destinoY = 0;
    let auraX = window.innerWidth / 2;
    let auraY = window.innerHeight / 3;
    let pendiente = false;

    const pintar = () => {
        pendiente = false;
        fondo.style.setProperty('--mx', `${destinoX.toFixed(1)}px`);
        fondo.style.setProperty('--my', `${destinoY.toFixed(1)}px`);
        aura.style.setProperty('--ax', `${auraX.toFixed(0)}px`);
        aura.style.setProperty('--ay', `${auraY.toFixed(0)}px`);
    };

    const pedirPintado = () => {
        if (pendiente) return;
        pendiente = true;
        requestAnimationFrame(pintar);
    };

    // el desplazamiento es al reves que el mouse: al mover el cursor a la
    // derecha el fondo se corre a la izquierda, como al asomarse por una ventana
    const mover = (x, y) => {
        destinoX = -((x / window.innerWidth) - 0.5) * 2 * RECORRIDO;
        destinoY = -((y / window.innerHeight) - 0.5) * 2 * RECORRIDO;
        auraX = x;
        auraY = y;
        pedirPintado();
    };

    window.addEventListener('pointermove', (e) => mover(e.clientX, e.clientY),
                            { passive: true });

    // en el celular no hay mouse: el fondo responde a inclinar el aparato.
    // en iOS hace falta permiso explicito, asi que si no llega el evento
    // simplemente no pasa nada y quedan los flotes.
    window.addEventListener('deviceorientation', (e) => {
        if (e.gamma == null || e.beta == null) return;
        const x = (Math.max(-30, Math.min(30, e.gamma)) / 30 + 1) / 2 * window.innerWidth;
        const y = (Math.max(-30, Math.min(30, e.beta - 40)) / 30 + 1) / 2 * window.innerHeight;
        mover(x, y);
    }, { passive: true });

    pintar();
}

/** Arranca el fondo. Es seguro llamarlo mas de una vez. */
export function iniciarFondo() {
    if (document.getElementById('fondo')) return;
    const partes = construir();
    if (partes) seguirPuntero(partes);
}

/** Lanza un puñado de chispas desde un elemento, para celebrar algo. */
export function chispear(elemento, cantidad = 6) {
    if (quiereQuieto() || !elemento) return;

    const caja = elemento.getBoundingClientRect();
    const capa = document.getElementById('fondo');
    if (!capa) return;

    for (let i = 0; i < cantidad; i++) {
        const chispa = document.createElement('div');
        chispa.className = 'deco chispa-suelta';
        const angulo = (Math.PI * 2 * i) / cantidad;
        chispa.style.cssText = [
            `--n:${DECO.estrella}`,
            `--lado:16px`,
            `--z:0`,
            `--opacidad:1`,
            `left:${caja.left + caja.width / 2}px`,
            `top:${caja.top + caja.height / 2}px`,
            `--dx:${Math.cos(angulo) * 60}px`,
            `--dy:${Math.sin(angulo) * 60}px`,
        ].join(';');
        capa.appendChild(chispa);
        chispa.addEventListener('animationend', () => chispa.remove(), { once: true });
    }
}

// El estilo de las chispas sueltas vive aca y no en la hoja: solo existen si
// este modulo corre, y asi no queda una regla huerfana en estilos.css.
const REGLAS = `
.chispa-suelta {
    position: fixed;
    transform: none;
    transition: none;
    animation: chispa-vuela 520ms steps(6) forwards;
}
.chispa-suelta::before { animation: none; }
@keyframes chispa-vuela {
    from { transform: translate(0, 0) scale(0.4); opacity: 1; }
    to   { transform: translate(var(--dx), var(--dy)) scale(1.1); opacity: 0; }
}`;

const hoja = document.createElement('style');
hoja.textContent = REGLAS;
HOJA.querySelector('head').appendChild(hoja);
