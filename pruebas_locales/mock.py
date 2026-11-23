"""Simulador local del API y de S3 para probar los scripts de k6 (no reemplaza la prueba en AWS)."""
import json, re, time, uuid, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
PORT = int(sys.argv[1]); KEY = "clave-local-de-prueba-123"; VIG = 3; MAXB = 10485760
POL = {}
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body=b"", ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self): self.rfile.read(int(self.headers.get("Content-Length") or 0)); self.send(403, b"<Error>AccessDenied</Error>", "application/xml")
    do_PUT = do_GET
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); raw = self.rfile.read(n)
        if self.path == "/poc/documentos/url":
            if self.headers.get("x-api-key") != KEY: return self.send(403, b'{"message":"Forbidden"}')
            req = json.loads(raw or b"{}"); tipo = req.get("tipo")
            if tipo not in ("image/jpeg", "image/png", "application/pdf"): return self.send(400, b'{"error":"tipo no permitido"}')
            llave = f"entrantes/{req['siniestro']}/{uuid.uuid4()}.jpg"; firma = uuid.uuid4().hex
            POL[firma] = (llave, tipo, time.time() + VIG)
            body = {"url": f"http://127.0.0.1:{PORT}/s3/", "campos": {"key": llave, "Content-Type": tipo, "policy": "x", "x-amz-signature": firma}, "llave": llave, "vence_en_s": VIG}
            return self.send(201, json.dumps(body).encode())
        if self.path == "/s3/":
            lim = re.search(r"boundary=(.+)", self.headers["Content-Type"]).group(1).encode()
            partes = raw.split(b"--" + lim)[1:-1]
            nombres = [re.search(rb'name="([^"]+)"', p).group(1).decode() for p in partes]
            if nombres[-1] != "file": return self.send(400, b"file no es el ultimo campo")
            campos = {}
            for p in partes[:-1]:
                h, v = p.split(b"\r\n\r\n", 1); campos[re.search(rb'name="([^"]+)"', h).group(1).decode()] = v[:-2].decode()
            archivo = partes[-1].split(b"\r\n\r\n", 1)[1][:-2]
            pol = POL.get(campos.get("x-amz-signature"))
            if not pol: return self.send(403, b"firma")
            llave, tipo, vence = pol
            if time.time() > vence: return self.send(403, b"Policy expired")
            if campos.get("key") != llave or campos.get("Content-Type") != tipo: return self.send(403, b"Policy condition failed")
            if len(archivo) > MAXB: return self.send(400, b"EntityTooLarge")
            return self.send(204)
        self.send(404)
ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
