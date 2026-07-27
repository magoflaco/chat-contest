// Leaderboard de Chat Contest.
//
// Sin framework ni build: es un sitio estatico que consume la API publica del
// core. Eso lo hace desplegable en Cloudflare Pages arrastrando la carpeta, y
// facil de entender para alguien del club que recien arranca con JavaScript.

import { icono } from './iconos.js';
import { esc, panelEnunciado } from './enunciados.js';
import { iniciarFondo, chispear } from './fondo.js';
import * as perove from './perove.js';

const API = (window.CONTEST_API || '').replace(/\/$/, '');
const REFRESCO_MS = Number(window.CONTEST_REFRESCO_MS) || 0;

const $ = (sel) => document.querySelector(sel);

const QUIETO = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

async function traer(ruta) {
    const respuesta = await fetch(`${API}${ruta}`, { headers: { Accept: 'application/json' } });
    if (!respuesta.ok) throw new Error(`la API respondio ${respuesta.status}`);
    return respuesta.json();
}

function mostrarError(mensaje) {
    const caja = $('#aviso-error');
    caja.hidden = false;
    caja.innerHTML =
        `<span class="icono-caja">${icono('terminal', 32)}</span>` +
        `<span><strong>No se pudo cargar la informacion.</strong><br>` +
        `<span class="chico">${esc(mensaje)}</span><br>` +
        `<span class="chico tenue">Revisa que el core este levantado en ${esc(API)}.</span></span>`;
    perove.dice('Se me cayo la conexion con el servidor.', 8000);
    perove.descansa();
}

function limpiarError() {
    $('#aviso-error').hidden = true;
}

/** El semaforo de la cabecera: verde cuando la API contesta. */
function marcarPulso(vivo, detalle) {
    const caja = $('#pulso');
    caja.innerHTML =
        `<span class="punto${vivo ? '' : ' frio'}"></span><span>${esc(detalle)}</span>`;
}

// --- formato ------------------------------------------------------------------

function duracion(horas) {
    if (horas <= 0) return 'cerrada';

    // se redondea a minutos PRIMERO y despues se descompone: redondear cada unidad
    // por separado produce cosas como "2 d 24 h"
    const minutos = Math.round(horas * 60);
    if (minutos < 60) return `${minutos} min`;

    const h = Math.floor(minutos / 60);
    if (h < 24) {
        const m = minutos % 60;
        return m ? `${h} h ${m} min` : `${h} h`;
    }

    const dias = Math.floor(h / 24);
    const restoHoras = h % 24;
    return restoHoras ? `${dias} d ${restoHoras} h` : `${dias} d`;
}

function fecha(iso) {
    if (!iso) return '-';
    return new Date(iso).toLocaleString('es-AR',
        { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

/** Que porcentaje de la ronda queda por delante, de 0 a 100.
 *
 *  Se calcula con las fechas y no con `horas_restantes` sola, porque las rondas
 *  no siempre duran lo mismo: una de 72 h y una de 24 h con 12 h restantes no
 *  estan en el mismo punto. */
function porcentajeRestante(ronda) {
    const inicio = Date.parse(ronda.inicio);
    const fin = Date.parse(ronda.fin);
    if (!Number.isFinite(inicio) || !Number.isFinite(fin) || fin <= inicio) return 0;

    const fraccion = (fin - Date.now()) / (fin - inicio);
    return Math.round(Math.max(0, Math.min(1, fraccion)) * 100);
}

function barraDificultad(nivel) {
    const bloques = Array.from({ length: 5 }, (_, i) =>
        `<span class="bloque-dif${i < nivel ? ' lleno' : ''}"></span>`).join('');
    return `<span class="dificultad dif-${nivel}" title="Dificultad ${nivel} de 5">${bloques}</span>`;
}

/** Cuenta desde cero hasta el valor final. Es un detalle chico pero hace que la
 *  pagina se sienta viva al entrar en vez de aparecer ya resuelta. */
function contarHasta(elemento, valor) {
    const destino = Number(valor);
    if (QUIETO || !Number.isFinite(destino) || destino === 0) {
        elemento.textContent = valor;
        return;
    }

    const DURACION = 650;
    const arranque = performance.now();

    const paso = (ahora) => {
        const t = Math.min(1, (ahora - arranque) / DURACION);
        // desacelera al final: sube rapido y se acomoda
        const suave = 1 - (1 - t) * (1 - t);
        elemento.textContent = String(Math.round(destino * suave));
        if (t < 1) requestAnimationFrame(paso);
    };

    elemento.textContent = '0';
    requestAnimationFrame(paso);
}

// --- fichas de resumen --------------------------------------------------------

function pintarFichas(totales) {
    const fichas = [
        ['persona',   totales.participantes, 'participantes'],
        ['tilde',     totales.aceptadas,     'resueltos'],
        ['pergamino', totales.entregas,      'entregas'],
        ['barras',    totales.rondas,        'rondas'],
    ];

    $('#fichas').innerHTML = fichas.map(([ico, valor, nombre], i) => `
        <div class="ficha entra" style="--i:${i}">
            <span class="icono-caja">${icono(ico, 32)}</span>
            <span>
                <span class="ficha-valor" data-valor="${esc(valor)}">0</span>
                <span class="rotulo">${esc(nombre)}</span>
            </span>
        </div>`).join('');

    for (const valor of $('#fichas').querySelectorAll('.ficha-valor')) {
        contarHasta(valor, valor.dataset.valor);
    }
}

// --- podio --------------------------------------------------------------------

/** Los tres primeros, fuera de la tabla. Es lo primero que mira cualquiera. */
function pintarPodio(filas) {
    const caja = $('#podio');
    const top = filas.slice(0, 3);

    // con menos de tres no hay podio que valga: queda mejor solo la tabla
    if (top.length < 3) {
        caja.hidden = true;
        caja.innerHTML = '';
        return;
    }

    caja.hidden = false;
    caja.innerHTML = top.map((f, i) => `
        <div class="escalon escalon-${i + 1} entra" style="--i:${i}"
             tabindex="0" role="button" data-id="${esc(f.id)}"
             aria-label="Puesto ${i + 1}: ${esc(f.nombre)}, ${esc(f.puntos)} puntos">
            <span class="escalon-puesto">${i + 1}</span>
            <span class="perove perove-${i === 0 ? 'jump' : 'idle'}"></span>
            <span class="escalon-nombre" title="${esc(f.nombre)}">${esc(f.nombre)}</span>
            <span class="escalon-puntos">${esc(f.puntos)}</span>
            <span class="rotulo">${esc(f.resueltos)} resueltos</span>
        </div>`).join('');

    for (const escalon of caja.querySelectorAll('.escalon')) {
        const abrir = () => abrirDetalle(escalon.dataset.id);
        escalon.addEventListener('click', abrir);
        escalon.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); abrir(); }
        });
    }

    // el primero festeja con chispas cuando le pasan por encima
    const campeon = caja.querySelector('.escalon-1');
    campeon?.addEventListener('pointerenter', () => chispear(campeon, 8));
}

// --- tabla de posiciones ------------------------------------------------------

function pintarRanking(filas) {
    const caja = $('#tabla-ranking');

    if (!filas.length) {
        caja.innerHTML = `
            <div class="vacio">
                <span class="perove perove-idle"></span>
                <p>Todavia no hay nadie en la tabla.</p>
                <p class="chico">Se el primero: mandale <strong>!problemas</strong> al bot.</p>
            </div>`;
        return;
    }

    // los `data-rotulo` son los que se convierten en etiqueta cuando la tabla
    // pasa a tarjetas en el celular (ver el bloque responsive de estilos.css)
    const cuerpo = filas.map((f, i) => `
        <tr tabindex="0" data-id="${esc(f.id)}" class="entra" style="--i:${Math.min(i, 12)}">
            <td><span class="puesto puesto-${f.puesto <= 3 ? f.puesto : 'n'}">${esc(f.puesto)}</span></td>
            <td class="col-nombre">${esc(f.nombre)}</td>
            <td class="num" data-rotulo="puntos"><strong>${esc(f.puntos)}</strong></td>
            <td class="num" data-rotulo="resueltos">${esc(f.resueltos)}</td>
            <td class="col-precision" data-rotulo="precision">
                <span class="barra-precision" style="--relleno:${Math.round(f.precision * 100)}%"
                      title="${Math.round(f.precision * 100)}% de acierto"></span>
            </td>
        </tr>`).join('');

    caja.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Participante</th>
                    <th class="num">Puntos</th>
                    <th class="num">Resueltos</th>
                    <th class="col-precision">Precision</th>
                </tr>
            </thead>
            <tbody>${cuerpo}</tbody>
        </table>`;

    for (const fila of caja.querySelectorAll('tbody tr')) {
        fila.addEventListener('click', () => abrirDetalle(fila.dataset.id));
        fila.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                abrirDetalle(fila.dataset.id);
            }
        });
    }
}

// --- detalle de participante --------------------------------------------------

async function abrirDetalle(id) {
    const panel = $('#detalle');
    panel.hidden = false;
    panel.innerHTML = '<p class="cargando">cargando</p>';
    panel.scrollIntoView({ behavior: QUIETO ? 'auto' : 'smooth', block: 'nearest' });

    let p;
    try {
        p = await traer(`/api/participante/${encodeURIComponent(id)}`);
    } catch (error) {
        panel.innerHTML = `<p>No se pudo cargar el perfil: ${esc(error.message)}</p>`;
        return;
    }

    const porDificultad = Object.entries(p.por_dificultad || {})
        .map(([nombre, n]) => `<span class="pastilla">${esc(nombre)}: ${esc(n)}</span>`).join('');

    const problemas = (p.problemas || []).map((pr) => `
        <span class="pastilla${pr.resuelto ? ' ok' : ''}"
              title="${pr.resuelto ? `${pr.puntos} puntos` : `${pr.intentos} intento(s)`}">
            ${pr.resuelto ? icono('tilde', 16) : ''}${esc(pr.codigo)}
        </span>`).join('');

    panel.innerHTML = `
        <div class="detalle-cabecera">
            <span class="icono-caja">${icono('persona', 32)}</span>
            <span>
                <h2>${esc(p.nombre)}</h2>
                <span class="chico tenue">puesto ${esc(p.puesto ?? '-')} &middot;
                    ${esc(p.puntos)} puntos &middot; ${Math.round((p.precision || 0) * 100)}% de acierto</span>
            </span>
            <button class="cerrar" type="button" aria-label="Cerrar el detalle">cerrar</button>
        </div>

        ${porDificultad ? `<h3>Resueltos por dificultad</h3><div class="pastillas">${porDificultad}</div>` : ''}
        ${problemas ? `<h3>Problemas</h3><div class="pastillas">${problemas}</div>` : ''}`;

    panel.querySelector('.cerrar').addEventListener('click', () => {
        panel.hidden = true;
    });
}

// --- ronda --------------------------------------------------------------------

function tarjetaProblema(pr, i = 0) {
    const etiquetas = (pr.tags || [])
        .map((t) => `<span class="etiqueta">${esc(t)}</span>`).join('');

    const tasa = pr.intentaron
        ? `${pr.resolvieron} de ${pr.intentaron} lo resolvieron`
        : 'todavia no lo intento nadie';

    return `
        <article class="problema dif-${pr.dificultad} entra" style="--i:${i}"
                 tabindex="0" role="button"
                 aria-label="Ver el enunciado de ${esc(pr.codigo)}">
            <div class="problema-cabecera">
                <span class="codigo-problema">${esc(pr.codigo)}</span>
                ${barraDificultad(pr.dificultad)}
            </div>
            <h3>${esc(pr.titulo)}</h3>
            <p class="chico tenue">${esc(pr.nombre_dificultad)} &middot; ${esc(pr.base)} puntos base</p>
            <p class="chico">${esc(tasa)}</p>
            ${etiquetas ? `<div class="etiquetas">${etiquetas}</div>` : ''}
            <p class="ver-enunciado">${icono('pergamino', 16)} ver el enunciado</p>
        </article>`;
}

/** Abre el panel con el enunciado completo de un problema. */
function abrirEnunciado(pr) {
    const panel = $('#enunciado');
    panel.hidden = false;
    panel.innerHTML = panelEnunciado(pr);
    panel.querySelector('.cerrar').addEventListener('click', () => { panel.hidden = true; });
    panel.scrollIntoView({ behavior: QUIETO ? 'auto' : 'smooth', block: 'start' });
    perove.anima('cast', 1200);
}

/** Hace clickeables las tarjetas de problema que haya dentro de un contenedor. */
function engancharProblemas(caja, problemas) {
    const porCodigo = new Map(problemas.map((p) => [p.codigo, p]));

    for (const tarjeta of caja.querySelectorAll('.problema')) {
        const codigo = tarjeta.querySelector('.codigo-problema')?.textContent?.trim();
        const pr = porCodigo.get(codigo);
        if (!pr) continue;

        const abrir = () => abrirEnunciado(pr);
        tarjeta.addEventListener('click', abrir);
        tarjeta.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                abrir();
            }
        });
    }
}

function pintarRonda(ronda) {
    const caja = $('#ronda-actual');

    if (!ronda) {
        caja.innerHTML = `
            <div class="panel vacio">
                <span class="perove perove-idle"></span>
                <p>No hay ninguna ronda abierta.</p>
                <p class="chico">La proxima sale pronto. Se publican cada 3 dias.</p>
            </div>`;
        return;
    }

    // menos de seis horas ya es "corre": la ficha cambia de color y late
    const urgente = ronda.abierta && ronda.horas_restantes <= 6;

    caja.innerHTML = `
        <div class="regresiva${urgente ? ' urgente' : ''}">
            <span class="icono-caja">${icono(urgente ? 'rayo' : 'reloj', 32)}</span>
            <span>
                <span class="regresiva-valor">${esc(duracion(ronda.horas_restantes))}</span>
                <span class="rotulo">${ronda.abierta ? 'para que cierre' : 'ronda cerrada'}</span>
            </span>
            <span class="barra-ronda" style="--queda:${porcentajeRestante(ronda)}%"
                  role="img" aria-label="Queda ${porcentajeRestante(ronda)}% de la ronda"></span>
        </div>

        <div class="panel">
            <h2>Ronda ${esc(ronda.numero)}</h2>
            <p class="chico tenue">
                abrio el ${esc(fecha(ronda.inicio))} &middot; cierra el ${esc(fecha(ronda.fin))}
            </p>
            <div class="lista-problemas">${ronda.problemas.map(tarjetaProblema).join('')}</div>
        </div>`;

    engancharProblemas(caja, ronda.problemas);
}

// --- historial ----------------------------------------------------------------

function pintarHistorial(rondas) {
    const caja = $('#historial');

    if (!rondas.length) {
        caja.innerHTML = `
            <div class="panel vacio">
                <span class="perove perove-idle"></span>
                <p>Todavia no se publico ninguna ronda.</p>
            </div>`;
        return;
    }

    caja.innerHTML = rondas.map((r, i) => `
        <div class="panel entra" style="--i:${i}">
            <div class="problema-cabecera">
                <h2>Ronda ${esc(r.numero)}</h2>
                <span class="etiqueta">${r.abierta ? 'abierta' : 'cerrada'}</span>
            </div>
            <p class="chico tenue">${esc(fecha(r.inicio))} - ${esc(fecha(r.fin))}</p>
            <div class="lista-problemas">${r.problemas.map(tarjetaProblema).join('')}</div>
        </div>`).join('');

    engancharProblemas(caja, rondas.flatMap((r) => r.problemas));
}

// --- reglas -------------------------------------------------------------------

function pintarDificultades(dificultades) {
    $('#tabla-dificultades').innerHTML = dificultades.map((d) => `
        <tr>
            <td>${barraDificultad(d.nivel)}</td>
            <td>${esc(d.nombre)}</td>
            <td class="num"><strong>${esc(d.base)}</strong></td>
        </tr>`).join('');
}

// --- pestanias ----------------------------------------------------------------

function activarPestanias() {
    const pestanias = [...document.querySelectorAll('.pestania')];

    const seleccionar = (elegida, saltar = true) => {
        for (const p of pestanias) {
            const activa = p === elegida;
            p.setAttribute('aria-selected', String(activa));
            document.getElementById(p.getAttribute('aria-controls')).hidden = !activa;
        }
        location.hash = elegida.id.replace('tab-', '');
        // la pestania elegida se centra sola cuando la barra scrollea en el celular
        elegida.scrollIntoView({ block: 'nearest', inline: 'center',
                                behavior: QUIETO ? 'auto' : 'smooth' });
        if (saltar) perove.festeja();
    };

    for (const p of pestanias) {
        p.addEventListener('click', () => seleccionar(p));
    }

    const desdeHash = () => document.getElementById(`tab-${location.hash.slice(1)}`);

    // cambiar el hash no recarga el documento, asi que sin esto el boton "atras"
    // del navegador cambia la URL pero deja la pestania anterior a la vista
    window.addEventListener('hashchange', () => {
        const objetivo = desdeHash();
        if (objetivo) seleccionar(objetivo);
    });

    // permite compartir un link directo a una seccion
    const inicial = desdeHash();
    if (inicial) seleccionar(inicial, false);
}

// --- arranque -----------------------------------------------------------------

async function cargar() {
    perove.trabaja();

    try {
        const [resumen, ranking, historial] = await Promise.all([
            traer('/api/resumen'),
            traer('/api/ranking'),
            traer('/api/rondas?limite=6'),
        ]);

        limpiarError();
        pintarFichas(resumen.totales);
        pintarDificultades(resumen.dificultades);
        pintarRonda(resumen.ronda_actual);
        pintarPodio(ranking.filas);
        pintarRanking(ranking.filas);
        pintarHistorial(historial.rondas);

        marcarPulso(true, resumen.ronda_actual?.abierta ? 'ronda abierta' : 'en linea');
        perove.descansa();
    } catch (error) {
        mostrarError(error.message);
        marcarPulso(false, 'sin conexion');
        // dejamos las secciones en un estado legible, no en "cargando" para siempre
        pintarPodio([]);
        pintarRanking([]);
        pintarRonda(null);
        pintarHistorial([]);
    }
}

iniciarFondo();
perove.iniciarCompaniero();
activarPestanias();
cargar();

// el Perove de la cabecera saluda cuando le pasan por encima
$('#perove-marca')?.closest('.marca')?.addEventListener('pointerenter', () => {
    const marca = $('#perove-marca');
    marca.className = 'perove perove-wave';
    setTimeout(() => { marca.className = 'perove perove-idle'; }, 1200);
});

if (REFRESCO_MS > 0) {
    setInterval(() => {
        // no refrescamos con la pestania en segundo plano: no tiene sentido gastar
        // pedidos contra el VPS mientras nadie mira
        if (!document.hidden) cargar();
    }, REFRESCO_MS);
}
