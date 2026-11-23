// Utilidades compartidas: multipart construido a mano para garantizar que "file" vaya de último (S3 lo exige).
export function ascii(s) {
  const u = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) u[i] = s.charCodeAt(i) & 0xff;
  return u;
}

export function multipart(campos, datos, nombre, tipo) {
  const limite = '----segurAlpes' + Math.random().toString(16).slice(2);
  let cab = '';
  for (const k of Object.keys(campos)) {
    cab += `--${limite}\r\nContent-Disposition: form-data; name="${k}"\r\n\r\n${campos[k]}\r\n`;
  }
  cab += `--${limite}\r\nContent-Disposition: form-data; name="file"; filename="${nombre}"\r\nContent-Type: ${tipo}\r\n\r\n`;
  const a = ascii(cab);
  const b = new Uint8Array(datos);
  const c = ascii(`\r\n--${limite}--\r\n`);
  const out = new Uint8Array(a.length + b.length + c.length);
  out.set(a, 0); out.set(b, a.length); out.set(c, a.length + b.length);
  return { cuerpo: out.buffer, tipo: `multipart/form-data; boundary=${limite}` };
}

export function p(m, k) {
  return m && m.values && m.values[k] !== undefined ? m.values[k].toFixed(0) : '-';
}
