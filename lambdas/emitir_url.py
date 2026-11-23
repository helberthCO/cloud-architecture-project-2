"""Servicio de documentos (PoC): emite una URL prefirmada POST para subir una evidencia directo a S3 (valet key)."""
import json, os, uuid
import boto3
from botocore.config import Config

S3 = boto3.client("s3", config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))
BUCKET = os.environ["BUCKET"]
VIGENCIA = int(os.environ.get("VIGENCIA_S", "60"))
MAX_BYTES = int(os.environ.get("MAX_BYTES", "10485760"))
TIPOS = {"image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf"}


def respuesta(codigo, cuerpo):
    return {"statusCode": codigo, "headers": {"Content-Type": "application/json"}, "body": json.dumps(cuerpo)}


def handler(event, context):
    try:
        req = json.loads(event.get("body") or "{}")
    except ValueError:
        return respuesta(400, {"error": "cuerpo invalido"})
    tipo = req.get("tipo")
    siniestro = str(req.get("siniestro", ""))
    if tipo not in TIPOS:
        return respuesta(400, {"error": "tipo no permitido", "permitidos": list(TIPOS)})
    if not siniestro.isalnum() or len(siniestro) > 32:
        return respuesta(400, {"error": "siniestro invalido"})
    llave = f"entrantes/{siniestro}/{uuid.uuid4()}{TIPOS[tipo]}"
    post = S3.generate_presigned_post(
        BUCKET, llave,
        Fields={"Content-Type": tipo},
        Conditions=[{"Content-Type": tipo}, ["content-length-range", 1, MAX_BYTES]],
        ExpiresIn=VIGENCIA,
    )
    return respuesta(201, {"url": post["url"], "campos": post["fields"], "llave": llave, "vence_en_s": VIGENCIA})
