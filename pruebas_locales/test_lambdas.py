import json, os, sys
import pathlib; _r = pathlib.Path(__file__).parent; sys.path[:0] = [str(_r / "stub"), str(_r.parent / "lambdas")]
os.environ.update(BUCKET="b-prueba", BUS="bus", VIGENCIA_S="60")
import boto3, emitir_url, validar

r = emitir_url.handler({"body": json.dumps({"siniestro": "SIN1", "tipo": "image/jpeg"})}, None)
assert r["statusCode"] == 201, r; b = json.loads(r["body"]); assert b["llave"].startswith("entrantes/SIN1/") and b["llave"].endswith(".jpg")
pres = boto3.LLAMADAS[-1]; assert ["content-length-range", 1, 10485760] in pres[4] and {"Content-Type": "image/jpeg"} in pres[4] and pres[5] == 60
assert emitir_url.handler({"body": json.dumps({"siniestro": "SIN1", "tipo": "text/html"})}, None)["statusCode"] == 400
assert emitir_url.handler({"body": json.dumps({"siniestro": "../x", "tipo": "image/png"})}, None)["statusCode"] == 400
assert emitir_url.handler({"body": "{no json"}, None)["statusCode"] == 400

boto3.OBJ["entrantes/S1/a.jpg"] = (b"\xff\xd8\xff\xe0" + b"0" * 20, "image/jpeg")
boto3.OBJ["entrantes/S1/b.jpg"] = (b"MZ\x90\x00" + b"0" * 20, "image/jpeg")
boto3.OBJ["entrantes/S1/c.pdf"] = (b"%PDF-1.7" + b"0" * 20, "image/jpeg")
ev = lambda k: {"Records": [{"eventTime": "2026-11-22T18:00:00.123Z", "s3": {"bucket": {"name": "b"}, "object": {"key": k, "size": 24}}}]}
boto3.LLAMADAS.clear(); validar.handler(ev("entrantes/S1/a.jpg"), None)
assert boto3.LLAMADAS[0] == ("tag", "entrantes/S1/a.jpg") and boto3.LLAMADAS[1][1] == "DocumentoCargado"
for k in ("entrantes/S1/b.jpg", "entrantes/S1/c.pdf"):
    boto3.LLAMADAS.clear(); validar.handler(ev(k), None)
    assert boto3.LLAMADAS[0] == ("copy", "cuarentena/" + k.split("/", 1)[1]) and boto3.LLAMADAS[1] == ("delete", k) and boto3.LLAMADAS[2][1] == "DocumentoRechazado", boto3.LLAMADAS
print("pruebas de las Lambdas: OK")
