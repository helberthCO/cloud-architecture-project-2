#!/usr/bin/env python3
"""ASR-3 desde la red real del asegurado (por ejemplo, tu portátil en Bogotá). Solo biblioteca estándar.
Uso: API_URL=... API_KEY=... python3 individual.py [archivo] [repeticiones]"""
import json, os, statistics, sys, time, urllib.request, uuid

API, KEY = os.environ["API_URL"], os.environ["API_KEY"]
ARCHIVO = sys.argv[1] if len(sys.argv) > 1 else "evidencia_5mb.jpg"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 10
datos = open(ARCHIVO, "rb").read()


def multipart(campos):
    lim = uuid.uuid4().hex
    partes = [f'--{lim}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in campos.items()]
    cab = "".join(partes) + f'--{lim}\r\nContent-Disposition: form-data; name="file"; filename="e.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'
    return cab.encode() + datos + f"\r\n--{lim}--\r\n".encode(), f"multipart/form-data; boundary={lim}"


url_ms, carga_ms = [], []
for i in range(N):
    t0 = time.perf_counter()
    req = urllib.request.Request(API, json.dumps({"siniestro": f"BOG{i}", "tipo": "image/jpeg"}).encode(),
                                 {"Content-Type": "application/json", "x-api-key": KEY})
    d = json.load(urllib.request.urlopen(req))
    t1 = time.perf_counter()
    cuerpo, ctype = multipart(d["campos"])
    r = urllib.request.urlopen(urllib.request.Request(d["url"], cuerpo, {"Content-Type": ctype}))
    t2 = time.perf_counter()
    assert r.status == 204, r.status
    url_ms.append((t1 - t0) * 1000); carga_ms.append((t2 - t1) * 1000)
    print(f"{i + 1:2d}  URL {url_ms[-1]:6.0f} ms   carga {carga_ms[-1]:6.0f} ms   ~{len(datos) * 8 / (t2 - t1) / 1e6:5.1f} Mbps")


def p95(x):
    return sorted(x)[max(0, round(0.95 * len(x)) - 1)]


print(f"\nURL   p50 {statistics.median(url_ms):.0f} ms  p95 {p95(url_ms):.0f} ms   (meta < 300)")
print(f"Carga p50 {statistics.median(carga_ms):.0f} ms  p95 {p95(carga_ms):.0f} ms   (meta < 3000)")
print(f"Subida efectiva mediana ~{len(datos) * 8 / (statistics.median(carga_ms) / 1000) / 1e6:.1f} Mbps")
