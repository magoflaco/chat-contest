// Donde vive la API del core.
//
// Produccion: el core corre en el VPS escuchando solo en 127.0.0.1:8100, y sale
// a internet a traves del tunel de Cloudflare como contest-api.itb.lat. El puerto
// 8000 de ese servidor lo usa otro proyecto, por eso el 8100.
//
// Para desarrollar en tu maquina, comenta la linea de produccion y descomenta la
// local. Este archivo se edita a mano y no necesita build de ningun tipo.

window.CONTEST_API = 'https://contest-api.itb.lat';
// window.CONTEST_API = 'http://127.0.0.1:8000';   // desarrollo local

// cada cuanto se refresca la tabla sola, en milisegundos. 0 lo desactiva.
window.CONTEST_REFRESCO_MS = 60000;
