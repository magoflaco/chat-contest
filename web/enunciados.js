// Render de los enunciados en la web.
//
// Los enunciados del banco son markdown. En vez de traer una libreria entera
// para cuatro construcciones, se convierte a mano lo que realmente usamos:
// encabezados, negrita, codigo inline, bloques, listas y citas.
//
// Seguridad: se escapa TODO primero y despues se reintroducen unicamente las
// etiquetas que generamos nosotros. Da igual lo que traiga el enunciado (o de
// donde se haya importado): no puede inyectar HTML.

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ESCAPES[c]);

// marcador para apartar los bloques de codigo mientras se procesa el resto.
// se usa un texto improbable en vez de un caracter de control, que ensucia el archivo.
const MARCA = '␄BLOQUE';

export function markdown(texto) {
    const bloques = [];

    let t = esc(texto).replace(/```([\s\S]*?)```/g, (_, codigo) => {
        bloques.push(codigo.replace(/^\n/, '').replace(/\n$/, ''));
        return `${MARCA}${bloques.length - 1}${MARCA}`;
    });

    t = t
        .replace(/^#{3,} (.+)$/gm, '<h4>$1</h4>')
        .replace(/^## (.+)$/gm, '<h3>$1</h3>')
        .replace(/^# (.+)$/gm, '<h3>$1</h3>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`\n]+)`/g, '<code>$1</code>')
        // el > del markdown ya quedo escapado como &gt; en el paso anterior
        .replace(/^&gt; ?(.*)$/gm, '<blockquote>$1</blockquote>')
        .replace(/^[-*] (.+)$/gm, '<li>$1</li>');

    // envuelve cada corrida de <li> en un solo <ul>
    t = t.replace(/(?:<li>.*<\/li>\n?)+/g, (m) => `<ul>${m.trim()}</ul>`);

    t = t
        .split(/\n{2,}/)
        .map((parrafo) => {
            const limpio = parrafo.trim();
            if (!limpio) return '';
            if (/^<(h3|h4|ul|blockquote)/.test(limpio)) return limpio;
            if (limpio.startsWith(MARCA)) return limpio;
            return `<p>${limpio.replace(/\n/g, '<br>')}</p>`;
        })
        .join('');

    return t.replace(new RegExp(`${MARCA}(\\d+)${MARCA}`, 'g'),
        (_, i) => `<pre class="codigo">${bloques[Number(i)]}</pre>`);
}

/** Devuelve el HTML del panel de enunciado de un problema. */
export function panelEnunciado(pr) {
    const ejemplos = (pr.samples || []).map((s, i) => `
        <div class="ejemplo">
            <div>
                <h4>Entrada ${i + 1}</h4>
                <pre class="codigo">${esc(s.entrada)}</pre>
            </div>
            <div>
                <h4>Salida ${i + 1}</h4>
                <pre class="codigo">${esc(s.salida)}</pre>
            </div>
        </div>`).join('');

    const subtareas = (pr.subtareas || []).length ? `
        <h3>Subtareas</h3>
        <ul>${pr.subtareas.map((s) =>
            `<li><strong>${esc(s.id)}</strong> (${esc(s.peso)}%) ${esc(s.descripcion)}</li>`
        ).join('')}</ul>
        <p class="chico tenue">Cada subtarea suma su parte solo si pasan todos sus casos.</p>`
        : '';

    const editorial = pr.editorial
        ? `<h3>Editorial</h3><div class="enunciado">${markdown(pr.editorial)}</div>`
        : '';

    return `
        <div class="detalle-cabecera">
            <span class="codigo-problema">${esc(pr.codigo)}</span>
            <span>
                <h2>${esc(pr.titulo)}</h2>
                <span class="chico tenue">${esc(pr.nombre_dificultad)} &middot;
                    ${esc(pr.base)} puntos &middot; ${esc(pr.tiempo_ms)} ms &middot;
                    ${esc(pr.memoria_mb)} MB</span>
            </span>
            <button class="cerrar" type="button" aria-label="Cerrar el enunciado">cerrar</button>
        </div>

        <div class="enunciado">${markdown(pr.enunciado || '(sin enunciado)')}</div>
        ${ejemplos ? `<h3>Ejemplos</h3>${ejemplos}` : ''}
        ${subtareas}
        ${editorial}
        ${pr.fuente ? `<p class="chico tenue">${esc(pr.fuente)}</p>` : ''}

        <div class="comoentregar">
            <h3>Como entregar</h3>
            <p class="chico">Por privado al bot, todo en un mismo mensaje:</p>
            <pre class="codigo">!entrega ${esc(pr.codigo)}
n = int(input())
print(n)</pre>
            <p class="chico tenue">Antes podes correrlo contra los ejemplos sin gastar
               intentos con <strong>!probar ${esc(pr.codigo)}</strong></p>
        </div>`;
}
