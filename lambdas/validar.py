"""Función por eventos (PoC): valida cada archivo subido y publica DocumentoCargado o DocumentoRechazado."""
import json, os, time, urllib.parse
from datetime import datetime
import boto3

S3 = boto3.client("s3")
EVENTOS = boto3.client("events")
BUS = os.environ["BUS"]
FIRMAS = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG\r\n\x1a\n": "image/png", b"%PDF-": "application/pdf"}


def tipo_real(cabecera):
    for firma, tipo in FIRMAS.items():
        if cabecera.startswith(firma):
            return tipo
    return None


def metrica(resultado, latencia_ms):
    # Formato EMF: CloudWatch crea la métrica LatenciaEventoMs sin llamadas adicionales
    print(json.dumps({
        "_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [{
            "Namespace": "SegurAlpesPoC", "Dimensions": [["Resultado"]],
            "Metrics": [{"Name": "LatenciaEventoMs", "Unit": "Milliseconds"}]}]},
        "Resultado": resultado, "LatenciaEventoMs": latencia_ms}))


def handler(event, context):
    for reg in event["Records"]:
        bucket = reg["s3"]["bucket"]["name"]
        llave = urllib.parse.unquote_plus(reg["s3"]["object"]["key"])
        tamano = reg["s3"]["object"].get("size", 0)
        obj = S3.get_object(Bucket=bucket, Key=llave, Range="bytes=0-15")
        real = tipo_real(obj["Body"].read())
        declarado = obj.get("ContentType")
        valido = real is not None and real == declarado
        if valido:
            S3.put_object_tagging(Bucket=bucket, Key=llave,
                                  Tagging={"TagSet": [{"Key": "estado", "Value": "validado"}]})
            destino, tipo_evento = llave, "DocumentoCargado"
        else:
            destino = "cuarentena/" + llave.split("/", 1)[1]
            S3.copy_object(Bucket=bucket, Key=destino, CopySource={"Bucket": bucket, "Key": llave})
            S3.delete_object(Bucket=bucket, Key=llave)
            tipo_evento = "DocumentoRechazado"
        EVENTOS.put_entries(Entries=[{
            "EventBusName": BUS, "Source": "segur-alpes.documentos", "DetailType": tipo_evento,
            "Detail": json.dumps({"llave": destino, "bytes": tamano, "tipo_declarado": declarado, "tipo_real": real})}])
        creado = datetime.fromisoformat(reg["eventTime"].replace("Z", "+00:00")).timestamp()
        metrica("validado" if valido else "rechazado", int((time.time() - creado) * 1000))
