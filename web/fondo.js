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
 * azar: se concentran en los margenes, que es donde no va el texto, y dejan
 * respirar la franja central. El tamanio es siempre multiplo de 16 (el lado
 * nativo del sprite) para no romper el pixel art.
 */
const COMPOSICION = [
    // sprite      x%    y%   lado  z     opacidad  dur    giro
    // --- nubes: las mas grandes y las mas lentas, bien al fondo -------------
    ['nube',        3,    7,   48,  0.9,  0.55,     7.0,  0],
    ['nube',       84,   13,   64,  0.5,  0.45,     9.0,  0],
    ['nube',       68,   71,   48,  0.7,  0.35,     8.0,  0],
    ['nube',        8,   83,   32,  1.2,  0.40,     6.0,  0],
    ['nube',       94,   45,   32,  0.6,  0.30,    10.0,  0],
    ['nube',       38,    2,   32,  0.8,  0.28,     8.5,  0],
    ['nube',       52,   95,   48,  0.9,  0.30,     9.5,  0],
    // --- estrellas: el brillo del hechizo de Perove -------------------------
    ['estrella',   91,   33,   32,  1.6,  0.70,     4.5,  12],
    ['estrella',    5,   45,   16,  2.0,  0.60,     3.5, -14],
    ['estrella',   46,    5,   16,  1.1,  0.45,     5.0,  10],
    ['estrella',   79,   84,   32,  1.9,  0.55,     4.0, -10],
    ['estrella',   16,   67,   16,  2.3,  0.50,     3.0,  16],
    ['estrella',   63,   17,   16,  1.4,  0.40,     5.5, -8],
    ['estrella',   97,   72,   16,  2.1,  0.45,     4.2,  12],
    // --- chispas: relleno liviano -------------------------------------------
    ['chispa',     17,   25,   32,  1.4,  0.50,     5.5,  0],
    ['chispa',     76,   55,   32,  1.8,  0.45,     6.5,  0],
    ['chispa',     34,   77,   32,  1.6,  0.40,     6.0,  0],
    ['chispa',     89,    6,   16,  2.0,  0.35,     4.8,  0],
    ['chispa',      2,   30,   16,  1.2,  0.35,     7.0,  0],
    // --- gemas: el azul fuerte, poquitas y bien repartidas ------------------
    ['rombo',      93,   61,   32,  2.2,  0.55,     4.0,  14],
    ['rombo',       3,   63,   16,  1.5,  0.45,     5.0, -10],
    ['rombo',      70,   38,   16,  2.5,  0.40,     3.6,  18],
    ['rombo',      24,   11,   16,  1.9,  0.35,     4.4, -16],
    // --- burbujas y plumas: lo mas tenue ------------------------------------
    ['burbuja',    88,   90,   32,  1.0,  0.40,     7.5,  0],
    ['burbuja',    29,   92,   16,  1.7,  0.35,     6.0,  0],
    ['burbuja',    58,   64,   16,  1.3,  0.28,     8.0,  0],
    ['burbuja',    11,   16,   16,  1.1,  0.28,     7.2,  0],
    ['pluma',      11,   39,   32,  0.8,  0.35,     8.5,  16],
    ['pluma',      73,   27,   16,  1.3,  0.30,     7.0, -12],
    ['pluma',      44,   88,   16,  1.0,  0.26,     9.0,  14],
    ['pluma',      96,   19,   16,  0.9,  0.26,     8.2, -18],
    // --- bits: guiño a la grilla, casi invisibles ---------------------------
    ['bit',        57,   87,   16,  2.4,  0.35,     4.0,  0],
    ['bit',        26,   57,   16,  0.6,  0.25,     9.0,  0],
    ['bit',        82,   47,   16,  2.6,  0.30,     3.8,  0],
    ['bit',         6,   95,   16,  1.5,  0.25,     6.6,  0],
    ['corazon',    36,   40,   16,  2.2,  0.22,     5.4,  0],
];

/** Cuanto se desplaza la capa mas cercana, en pixeles, de borde a borde. */
const RECORRIDO = 16;

/** Radio en pixeles dentro del cual el puntero espanta a las decoraciones. */
const RADIO_ESPANTO = 150;

/** Cuanto se aparta, como maximo, la que tiene el puntero justo encima. */
const EMPUJE = 46;

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
    const composicion = angosta ? COMPOSICION.filter((_, i) => i % 2 === 0) : COMPOSICION;
    const piezas = [];

    for (const [nombre, x, y, lado, z, opacidad, dur, giro] of composicion) {
        const el = document.createElement('div');
        el.className = 'deco';
        const tamanio = angosta ? Math.max(16, lado / 2) : lado;
        el.style.cssText = [
            `--n:${DECO[nombre]}`,
            `--x:${x}%`,
            `--y:${y}%`,
            `--lado:${tamanio}px`,
            `--z:${z}`,
            `--opacidad:${opacidad}`,
            `--dur:${dur}s`,
            // el retraso desfasa los flotes para que no suban todos a la vez
            `--retraso:${(-dur * Math.random()).toFixed(2)}s`,
            `--giro:${giro}deg`,
        ].join(';');
        fondo.appendChild(el);
        piezas.push({ el, x, y, z, tamanio, cx: 0, cy: 0 });
    }

    document.body.appendChild(fondo);
    return { fondo, aura, piezas };
}

/** Engancha el parallax y el espanto al mouse (o al giroscopio, si lo hay). */
function seguirPuntero({ fondo, aura, piezas }) {
    let destinoX = 0;
    let destinoY = 0;
    let auraX = window.innerWidth / 2;
    let auraY = window.innerHeight / 3;
    let punteroX = -9999;
    let punteroY = -9999;
    let pendiente = false;

    // Los centros se calculan de la composicion y no con getBoundingClientRect:
    // las decoraciones estan posicionadas en porcentaje sobre una capa fija del
    // tamanio de la ventana, asi que la cuenta sale sola y no hay que forzar al
    // navegador a recalcular el layout en cada movimiento del mouse.
    const medir = () => {
        for (const p of piezas) {
            p.cx = (p.x / 100) * window.innerWidth + p.tamanio / 2;
            p.cy = (p.y / 100) * window.innerHeight + p.tamanio / 2;
        }
    };

    /** Aparta del puntero las decoraciones que tenga cerca. */
    const espantar = () => {
        for (const p of piezas) {
            // al centro medido hay que sumarle el parallax, que ya corrio la
            // decoracion de su sitio: sin esto el radio efectivo se achica y
            // varias se espantan tarde o directamente no se espantan
            const dx = p.cx + destinoX * p.z - punteroX;
            const dy = p.cy + destinoY * p.z - punteroY;
            const distancia = Math.hypot(dx, dy);

            if (distancia > RADIO_ESPANTO) {
                // fuera del radio vuelven a su sitio y a su opacidad
                if (p.apartada) {
                    p.el.style.setProperty('--ex', '0px');
                    p.el.style.setProperty('--ey', '0px');
                    p.el.style.setProperty('--claridad', '1');
                    p.apartada = false;
                }
                continue;
            }

            // cuanto mas cerca, mas empuje. el +1 evita dividir por cero cuando
            // el puntero cae justo en el centro del sprite
            const fuerza = 1 - distancia / RADIO_ESPANTO;
            const norma = distancia + 1;
            p.el.style.setProperty('--ex', `${((dx / norma) * EMPUJE * fuerza).toFixed(1)}px`);
            p.el.style.setProperty('--ey', `${((dy / norma) * EMPUJE * fuerza).toFixed(1)}px`);
            // ademas se desvanecen: apartarse y aclararse juntos es lo que hace
            // que se lea como "despejar" y no como que rebotan
            p.el.style.setProperty('--claridad', (1 - fuerza * 0.75).toFixed(2));
            p.apartada = true;
        }
    };

    const pintar = () => {
        pendiente = false;
        fondo.style.setProperty('--mx', `${destinoX.toFixed(1)}px`);
        fondo.style.setProperty('--my', `${destinoY.toFixed(1)}px`);
        aura.style.setProperty('--ax', `${auraX.toFixed(0)}px`);
        aura.style.setProperty('--ay', `${auraY.toFixed(0)}px`);
        espantar();
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
        punteroX = x;
        punteroY = y;
        pedirPintado();
    };

    window.addEventListener('pointermove', (e) => mover(e.clientX, e.clientY),
                            { passive: true });

    // al sacar el mouse de la ventana no queda ninguna apartada para siempre
    document.addEventListener('pointerleave', () => {
        punteroX = punteroY = -9999;
        pedirPintado();
    });

    // en el celular no hay mouse: el fondo responde a inclinar el aparato.
    // en iOS hace falta permiso explicito, asi que si no llega el evento
    // simplemente no pasa nada y quedan los flotes.
    window.addEventListener('deviceorientation', (e) => {
        if (e.gamma == null || e.beta == null) return;
        const x = (Math.max(-30, Math.min(30, e.gamma)) / 30 + 1) / 2 * window.innerWidth;
        const y = (Math.max(-30, Math.min(30, e.beta - 40)) / 30 + 1) / 2 * window.innerHeight;
        // al inclinar no se espanta nada: no hay puntero, solo parallax
        destinoX = -((x / window.innerWidth) - 0.5) * 2 * RECORRIDO;
        destinoY = -((y / window.innerHeight) - 0.5) * 2 * RECORRIDO;
        auraX = x;
        auraY = y;
        pedirPintado();
    }, { passive: true });

    window.addEventListener('resize', () => { medir(); pedirPintado(); }, { passive: true });

    medir();
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
