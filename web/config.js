// Donde vive la API del core.
//
// En local queda el valor de abajo. Para publicar en Cloudflare Pages, cambialo
// por la URL publica de tu VPS (con https, o el navegador va a bloquear el pedido
// por contenido mixto).
//
// Este archivo se edita al desplegar y no necesita build de ningun tipo.

window.CONTEST_API = 'http://127.0.0.1:8000';

// cada cuanto se refresca la tabla sola, en milisegundos. 0 lo desactiva.
window.CONTEST_REFRESCO_MS = 60000;
