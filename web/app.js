// Leaderboard de Chat Contest.
//
// Sin framework ni build: es un sitio estatico que consume la API publica del
// core. Eso lo hace desplegable en Cloudflare Pages arrastrando la carpeta, y
// facil de entender para alguien del club que recien arranca con JavaScript.

import { icono } from './iconos.js';

const API = (window.CONTEST_API || '').replace(/\/$/, '');
const REFRESCO_MS = Number(window.CONTEST_REFRESCO_MS) || 0;

const $ = (sel) => document.querySelector(sel);

/** Escapa texto que viene de la API antes de meterlo en innerHTML. */
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]));

async function traer(ruta) {
    const respuesta = await fetch(`${API}${ruta}`, { headers: { Accept: 'application/json' } });
    if (!respuesta.ok) throw new Error(`la API respondio ${respuesta.status}`);
    return respuesta.json();
}

function mostrarError(mensaje) {
    const caja = $('#aviso-error');
    caja.hidden = false;
    caja.innerHTML =
        `<strong>No se pudo cargar la informacion.</strong><br>` +
        `<span class="chico">${esc(mensaje)}</span><br>` +
        `<span class="chico tenue">Revisa que el core este levantado en ${esc(API)}.</span>`;
}

function limpiarError() {
    $('#aviso-error').hidden = true;
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

function barraDificultad(nivel) {
    const bloques = Array.from({ length: 5 }, (_, i) =>
        `<span class="bloque-dif${i < nivel ? ' lleno' : ''}"></span>`).join('');
    return `<span class="dificultad dif-${nivel}" title="Dificultad ${nivel} de 5">${bloques}</span>`;
}

// --- fichas de resumen --------------------------------------------------------

function pintarFichas(totales) {
    const fichas = [
        ['persona',  totales.participantes, 'participantes'],
        ['tilde',    totales.aceptadas,     'resueltos'],
        ['pergamino', totales.entregas,     'entregas'],
        ['barras',   totales.rondas,        'rondas'],
    ];

    $('#fichas').innerHTML = fichas.map(([ico, valor, nombre]) => `
        <div class="ficha">
            <span class="icono-caja">${icono(ico, 20)}</span>
            <span>
                <span class="ficha-valor">${esc(valor)}</span>
                <span class="ficha-nombre">${esc(nombre)}</span>
            </span>
        </div>`).join('');
}

// --- tabla de posiciones ------------------------------------------------------

function pintarRanking(filas) {
    const caja = $('#tabla-ranking');

    if (!filas.length) {
        caja.innerHTML = `
            <div class="vacio">
                <span class="icono-caja">${icono('copa', 48)}</span>
                <p>Todavia no hay nadie en la tabla.</p>
                <p class="chico">Se el primero: mandale <strong>!problemas</strong> al bot.</p>
            </div>`;
        return;
    }

    const cuerpo = filas.map((f) => `
        <tr tabindex="0" data-id="${esc(f.id)}">
            <td><span class="puesto puesto-${f.puesto <= 3 ? f.puesto : 'n'}">${esc(f.puesto)}</span></td>
            <td>${esc(f.nombre)}</td>
            <td class="num"><strong>${esc(f.puntos)}</strong></td>
            <td class="num">${esc(f.resueltos)}</td>
            <td class="col-precision">
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
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

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
            ${pr.resuelto ? icono('tilde', 12) : ''}${esc(pr.codigo)}
        </span>`).join('');

    panel.innerHTML = `
        <div class="detalle-cabecera">
            <span class="icono-caja">${icono('persona', 24)}</span>
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

function tarjetaProblema(pr) {
    const etiquetas = (pr.tags || [])
        .map((t) => `<span class="etiqueta">${esc(t)}</span>`).join('');

    const tasa = pr.intentaron
        ? `${pr.resolvieron} de ${pr.intentaron} lo resolvieron`
        : 'todavia no lo intento nadie';

    return `
        <article class="problema">
            <div class="problema-cabecera">
                <span class="codigo-problema">${esc(pr.codigo)}</span>
                ${barraDificultad(pr.dificultad)}
            </div>
            <h3>${esc(pr.titulo)}</h3>
            <p class="chico tenue">${esc(pr.nombre_dificultad)} &middot; ${esc(pr.base)} puntos base</p>
            <p class="chico">${esc(tasa)}</p>
            ${etiquetas ? `<div class="etiquetas">${etiquetas}</div>` : ''}
        </article>`;
}

function pintarRonda(ronda) {
    const caja = $('#ronda-actual');

    if (!ronda) {
        caja.innerHTML = `
            <div class="panel vacio">
                <span class="icono-caja">${icono('reloj', 48)}</span>
                <p>No hay ninguna ronda abierta.</p>
                <p class="chico">La proxima sale pronto. Se publican cada 3 dias.</p>
            </div>`;
        return;
    }

    caja.innerHTML = `
        <div class="regresiva">
            <span class="icono-caja">${icono('reloj', 24)}</span>
            <span>
                <span class="regresiva-valor">${esc(duracion(ronda.horas_restantes))}</span>
                <span class="ficha-nombre">${ronda.abierta ? 'para que cierre' : 'ronda cerrada'}</span>
            </span>
        </div>

        <div class="panel">
            <h2>Ronda ${esc(ronda.numero)}</h2>
            <p class="chico tenue">
                abrio el ${esc(fecha(ronda.inicio))} &middot; cierra el ${esc(fecha(ronda.fin))}
            </p>
            <div class="lista-problemas">${ronda.problemas.map(tarjetaProblema).join('')}</div>
        </div>`;
}

// --- historial ----------------------------------------------------------------

function pintarHistorial(rondas) {
    const caja = $('#historial');

    if (!rondas.length) {
        caja.innerHTML = `
            <div class="panel vacio">
                <span class="icono-caja">${icono('pergamino', 48)}</span>
                <p>Todavia no se publico ninguna ronda.</p>
            </div>`;
        return;
    }

    caja.innerHTML = rondas.map((r) => `
        <div class="panel">
            <div class="problema-cabecera">
                <h2>Ronda ${esc(r.numero)}</h2>
                <span class="etiqueta">${r.abierta ? 'abierta' : 'cerrada'}</span>
            </div>
            <p class="chico tenue">${esc(fecha(r.inicio))} - ${esc(fecha(r.fin))}</p>
            <div class="lista-problemas">${r.problemas.map(tarjetaProblema).join('')}</div>
        </div>`).join('');
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

    const seleccionar = (elegida) => {
        for (const p of pestanias) {
            const activa = p === elegida;
            p.setAttribute('aria-selected', String(activa));
            document.getElementById(p.getAttribute('aria-controls')).hidden = !activa;
        }
        location.hash = elegida.id.replace('tab-', '');
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
    if (inicial) seleccionar(inicial);
}

// --- arranque -----------------------------------------------------------------

async function cargar() {
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
        pintarRanking(ranking.filas);
        pintarHistorial(historial.rondas);
    } catch (error) {
        mostrarError(error.message);
        // dejamos las secciones en un estado legible, no en "cargando" para siempre
        pintarRanking([]);
        pintarRonda(null);
        pintarHistorial([]);
    }
}

$('#logo').innerHTML = icono('terminal', 28);
activarPestanias();
cargar();

if (REFRESCO_MS > 0) {
    setInterval(() => {
        // no refrescamos con la pestania en segundo plano: no tiene sentido gastar
        // pedidos contra el VPS mientras nadie mira
        if (!document.hidden) cargar();
    }, REFRESCO_MS);
}
