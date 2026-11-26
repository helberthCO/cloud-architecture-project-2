"""Doble de prueba de boto3. Cada cliente expone solo los métodos que existen en el SDK real
(S3: generate_presigned_post, get_object, put_object_tagging, copy_object, delete_object;
EventBridge: put_events): un método mal escrito en las Lambdas falla aquí con AttributeError."""
import io
LLAMADAS = []
OBJ = {}


class _S3:
    def generate_presigned_post(self, Bucket, Key, Fields, Conditions, ExpiresIn):
        LLAMADAS.append(("presign", Bucket, Key, Fields, Conditions, ExpiresIn))
        return {"url": f"https://{Bucket}.s3.amazonaws.com/", "fields": dict(Fields, key=Key)}
    def get_object(self, Bucket, Key, Range):
        datos, ct = OBJ[Key]; return {"Body": io.BytesIO(datos[:16]), "ContentType": ct}
    def put_object_tagging(self, **kw): LLAMADAS.append(("tag", kw["Key"]))
    def copy_object(self, **kw): LLAMADAS.append(("copy", kw["Key"]))
    def delete_object(self, **kw): LLAMADAS.append(("delete", kw["Key"]))


class _Events:
    def put_events(self, Entries):
        e = Entries[0]
        assert e["EventBusName"] and e["Source"] == "segur-alpes.documentos", e
        LLAMADAS.append(("event", e["DetailType"], e["Detail"]))
        return {"FailedEntryCount": 0, "Entries": [{"EventId": "1"}]}


def client(svc, **kw):
    return {"s3": _S3, "events": _Events}[svc]()
