// ASR-3: carga de evidencias de 5 MB con URL prefirmada.
// ESCENARIO=individual (1 usuario, 20 cargas seguidas) o pico (50 usuarios simultáneos, 4 cargas cada uno).
import http from 'k6/http';
import { check } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';
import { multipart, p } from './comun.js';

const API = __ENV.API_URL;
const KEY = __ENV.API_KEY;
const ESC = __ENV.ESCENARIO || 'pico';
const ARCHIVO = open(__ENV.ARCHIVO || '/opt/poc/datos/evidencia_5mb.jpg', 'b');

const urlMs = new Trend('url_ms', true);
const cargaMs = new Trend('carga_ms', true);
const totalMs = new Trend('total_ms', true);
const fallas = new Rate('fallas');
const subidas = new Counter('subidas_ok');

const ESCENARIOS = {
  individual: { executor: 'per-vu-iterations', vus: 1, iterations: 20, maxDuration: '10m' },
  pico: { executor: 'per-vu-iterations', vus: 50, iterations: 4, maxDuration: '10m' },
};

export const options = {
  scenarios: { [ESC]: ESCENARIOS[ESC] },
  thresholds: {
    url_ms: ['p(95)<300'],
    carga_ms: ['p(95)<3000'],
    fallas: ['rate==0'],
  },
  summaryTrendStats: ['min', 'med', 'p(90)', 'p(95)', 'max'],
};

export default function () {
  const t0 = Date.now();
  const r1 = http.post(API, JSON.stringify({ siniestro: `SIN${__VU}x${__ITER}`, tipo: 'image/jpeg' }), {
    headers: { 'Content-Type': 'application/json', 'x-api-key': KEY },
    tags: { paso: 'url' },
  });
  const t1 = Date.now();
  urlMs.add(t1 - t0);
  if (!check(r1, { 'URL emitida (201)': (r) => r.status === 201 })) {
    fallas.add(1);
    return;
  }
  const d = r1.json();
  const m = multipart(d.campos, ARCHIVO, 'evidencia.jpg', 'image/jpeg');
  const r2 = http.post(d.url, m.cuerpo, { headers: { 'Content-Type': m.tipo }, tags: { paso: 'carga' }, timeout: '60s' });
  const t2 = Date.now();
  cargaMs.add(t2 - t1);
  totalMs.add(t2 - t0);
  const ok = check(r2, { 'archivo cargado (204)': (r) => r.status === 204 });
  fallas.add(!ok);
  if (ok) subidas.add(1);
}

export function handleSummary(data) {
  const M = data.metrics;
  const n = M.subidas_ok ? M.subidas_ok.values.count : 0;
  const tasa = M.fallas ? (M.fallas.values.rate * 100).toFixed(2) : '-';
  const cumple = (k) => (M[k] && M[k].thresholds && Object.values(M[k].thresholds).every((t) => t.ok) ? 'CUMPLE' : 'NO CUMPLE');
  const txt = [
    `\nASR-3 · escenario ${ESC} · ${new Date().toISOString()}`,
    `Cargas exitosas: ${n} · fallas: ${tasa} %`,
    `URL prefirmada (ms)  p50 ${p(M.url_ms, 'med')}  p95 ${p(M.url_ms, 'p(95)')}  max ${p(M.url_ms, 'max')}  -> meta p95 < 300   ${cumple('url_ms')}`,
    `Carga de 5 MB (ms)   p50 ${p(M.carga_ms, 'med')}  p95 ${p(M.carga_ms, 'p(95)')}  max ${p(M.carga_ms, 'max')}  -> meta p95 < 3000  ${cumple('carga_ms')}`,
    `Total por evidencia  p50 ${p(M.total_ms, 'med')}  p95 ${p(M.total_ms, 'p(95)')}  max ${p(M.total_ms, 'max')}`,
    '',
  ].join('\n');
  const out = { stdout: txt };
  out[`${__ENV.RESULTADOS || '/opt/poc/resultados'}/carga-${ESC}.json`] = JSON.stringify(data, null, 1);
  return out;
}
