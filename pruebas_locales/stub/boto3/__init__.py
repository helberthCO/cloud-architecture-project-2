import io
LLAMADAS = []
OBJ = {}
class _C:
    def __init__(self, svc): self.svc = svc
    def generate_presigned_post(self, b, k, Fields, Conditions, ExpiresIn):
        LLAMADAS.append(("presign", b, k, Fields, Conditions, ExpiresIn)); return {"url": f"https://{b}.s3.amazonaws.com/", "fields": dict(Fields, key=k)}
    def get_object(self, Bucket, Key, Range):
        datos, ct = OBJ[Key]; return {"Body": io.BytesIO(datos[:16]), "ContentType": ct}
    def put_object_tagging(self, **kw): LLAMADAS.append(("tag", kw["Key"]))
    def copy_object(self, **kw): LLAMADAS.append(("copy", kw["Key"]))
    def delete_object(self, **kw): LLAMADAS.append(("delete", kw["Key"]))
    def put_events(self, Entries): LLAMADAS.append(("event", Entries[0]["DetailType"], Entries[0]["Detail"]))
def client(svc, **kw): return _C(svc)
