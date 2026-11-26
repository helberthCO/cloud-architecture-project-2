// ASR-4: intentos no autorizados contra el servicio de documentos y el almacenamiento. Un solo usuario, en orden.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { multipart } from './comun.js';

const API = __ENV.API_URL;
const KEY = __ENV.API_KEY;
const DIR = __ENV.DATOS || '/opt/poc/datos';
const PEQ = open(`${DIR}/evidencia_100kb.jpg`, 'b');
const GRANDE = open(`${DIR}/evidencia_11mb.jpg`, 'b');
const DISFRAZ = open(`${DIR}/ejecutable_disfrazado.jpg`, 'b');

export const options = { vus: 1, iterations: 1, thresholds: { checks: ['rate==1'] } };

function pedirUrl(tipo, conLlave = true) {
  const h = { 'Content-Type': 'application/json' };
  if (conLlave) h['x-api-key'] = KEY;
  return http.post(API, JSON.stringify({ siniestro: 'SEG1', tipo }), { headers: h });
}

function subir(d, datos, tipo, campos) {
  const m = multipart(campos || d.campos, datos, 'evidencia.jpg', tipo);
  return http.post(d.url, m.cuerpo, { headers: { 'Content-Type': m.tipo } });
}

export default function () {
  const res = [];
  const prueba = (nombre, esperado, r) => {
    const ok = check(r, { [nombre]: (x) => x.status === esperado });
    res.push(`${ok ? 'OK ' : 'FALLA'}  ${nombre}: esperado ${esperado}, obtenido ${r.status}`);
  };

  // 0. Control: una carga legítima debe funcionar
  const base = pedirUrl('image/jpeg').json();
  prueba('control: carga legítima', 204, subir(base, PEQ, 'image/jpeg'));
  const host = base.url;
  const llaveSubida = base.llave;

  // 1. Pedir URL sin llave de API
  prueba('URL sin llave de API', 403, pedirUrl('image/jpeg', false));
  // 2. Tipo de archivo no permitido
  prueba('tipo no permitido (ejecutable)', 400, pedirUrl('application/x-msdownload'));
  // 3. Firma alterada: se cambia la llave del objeto
  const d3 = pedirUrl('image/jpeg').json();
  const c3 = Object.assign({}, d3.campos, { key: 'entrantes/OTRO/sobrescribir.jpg' });
  prueba('firma alterada (otra llave)', 403, subir(d3, PEQ, 'image/jpeg', c3));
  // 4. Tipo declarado distinto al firmado
  const d4 = pedirUrl('image/jpeg').json();
  const c4 = Object.assign({}, d4.campos, { 'Content-Type': 'text/html' });
  prueba('tipo alterado (text/html)', 403, subir(d4, PEQ, 'text/html', c4));
  // 5. Archivo más grande que el límite firmado
  prueba('tamaño excedido (11 MB)', 400, subir(pedirUrl('image/jpeg').json(), GRANDE, 'image/jpeg'));
  // 6. Escritura directa sin firma
  prueba('PUT directo sin firma', 403, http.put(`${host}entrantes/SEG1/directo.jpg`, PEQ, { headers: { 'Content-Type': 'image/jpeg' } }));
  // 7. Lectura sin firma del archivo legítimo
  prueba('lectura sin firma', 403, http.get(`${host}${llaveSubida}`));
  // 8. Contenido disfrazado: S3 lo acepta, la función debe ponerlo en cuarentena (verificar en los registros)
  const d8 = pedirUrl('image/jpeg').json();
  prueba('ejecutable disfrazado de JPEG (aceptado por S3)', 204, subir(d8, DISFRAZ, 'image/jpeg'));
  res.push(`      -> buscar en los registros el evento DocumentoRechazado de ${d8.llave}`);
  // 9. URL vencida
  const d9 = pedirUrl('image/jpeg').json();
  sleep(d9.vence_en_s + 5);
  prueba(`URL vencida (${d9.vence_en_s + 5} s después)`, 403, subir(d9, PEQ, 'image/jpeg'));

  console.log('\nASR-4 · intentos no autorizados\n' + res.join('\n'));
}
