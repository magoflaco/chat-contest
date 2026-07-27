// Perove, la mascota, como companiero de la pagina.
//
// No es decoracion nada mas: reacciona a lo que pasa (cambiar de pestania,
// cargar datos, un error) y suelta tips sobre como se juega. La idea es que
// alguien que entra por primera vez descubra los comandos sin leer las reglas.
//
// El sprite tiene cuatro animaciones (idle, wave, jump, cast) y todas viven en
// una sola imagen; el CSS las corre con steps(). Aca solo se cambia la clase.

const ANIMACIONES = ['idle', 'wave', 'jump', 'cast'];

/** Tips que Perove va soltando. Se muestran en orden, no al azar: asi el que
 *  hace clic varias veces va viendo cosas nuevas y no repetidas. */
const TIPS = [
    'Las entregas van por privado al bot, nunca al grupo.',
    'Probá tu código con !probar antes de entregar: no gasta intentos.',
    'Resolver temprano vale más. El puntaje baja de a poco hasta 0.65.',
    'Si te trabás, pedí !pista. Te orienta sin darte la solución.',
    'Cada entrega rechazada descuenta 15%, con piso en 0.40.',
    'Los errores de sintaxis no penalizan, igual que en ICPC.',
    'Con !revisar te explico por qué falló tu código.',
    'Tocá un problema para leer el enunciado completo acá mismo.',
];

let nodo = null;
let sprite = null;
let globo = null;
let tip = 0;
let reloj = null;
let relojGlobo = null;

const quieto = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Deja a Perove haciendo una animacion; si se le pasa `ms`, vuelve a idle. */
export function anima(nombre, ms = 0) {
    if (!sprite || !ANIMACIONES.includes(nombre)) return;

    clearTimeout(reloj);
    sprite.className = `perove perove-${nombre}`;

    if (ms > 0) {
        reloj = setTimeout(() => { sprite.className = 'perove perove-idle'; }, ms);
    }
}

/** Muestra el globo de dialogo. Se esconde solo. */
export function dice(texto, ms = 5000) {
    if (!globo) return;

    clearTimeout(relojGlobo);
    globo.textContent = texto;
    globo.hidden = false;

    if (ms > 0) {
        relojGlobo = setTimeout(() => { globo.hidden = true; }, ms);
    }
}

/** El proximo tip de la lista. */
function siguienteTip() {
    dice(TIPS[tip % TIPS.length]);
    tip += 1;
    anima('wave', 1400);
}

/** Crea el companiero flotante y lo engancha a la pagina. */
export function iniciarCompaniero() {
    if (nodo || quieto()) return;

    nodo = document.createElement('button');
    nodo.id = 'companiero';
    nodo.type = 'button';
    // el boton existe para el mouse; para un lector de pantalla la informacion
    // util ya esta en la pagina, asi que se anuncia como lo que es y nada mas
    nodo.setAttribute('aria-label', 'Perove: un consejo para competir');

    globo = document.createElement('span');
    globo.className = 'globo';
    globo.hidden = true;

    sprite = document.createElement('span');
    sprite.className = 'perove perove-idle';

    nodo.append(globo, sprite);
    document.body.appendChild(nodo);

    nodo.addEventListener('click', siguienteTip);
    nodo.addEventListener('pointerenter', () => anima('wave', 1200));

    // saludo de bienvenida, despues del tiempo que tarda en entrar
    setTimeout(() => {
        anima('wave', 1600);
        dice('Hola. Soy Perove. Tocame si querés un consejo.', 6000);
    }, 1500);
}

/** Perove festeja: salta y tira chispas. */
export function festeja() {
    anima('jump', 1500);
}

/** Perove esta esperando datos. */
export function trabaja() {
    anima('cast');
}

/** Perove vuelve a la calma. */
export function descansa() {
    anima('idle');
}

/** El nodo del sprite, para quien quiera lanzarle chispas encima. */
export const elemento = () => sprite;
