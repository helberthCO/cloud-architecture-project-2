# Consultas de CloudWatch Logs Insights (us-east-2)

Ajusta el intervalo de tiempo al de la prueba antes de ejecutar cada consulta.

## 1. Latencia del evento por resultado (ASR-3: evento publicado en menos de 10 s)

Grupo de registros: `/aws/lambda/segur-alpes-poc-validar`

```
filter ispresent(LatenciaEventoMs)
| stats count(*) as archivos, pct(LatenciaEventoMs, 50) as p50_ms, pct(LatenciaEventoMs, 95) as p95_ms, max(LatenciaEventoMs) as max_ms by Resultado
```

## 2. Eventos publicados por tipo (ASR-3: ningún archivo sin validar)

Grupo de registros: `/aws/events/segur-alpes-poc`

```
stats count(*) as eventos by `detail-type`
```

El número de `DocumentoCargado` debe ser igual al número de cargas exitosas que reportó k6 (más las de la prueba desde tu portátil y el control de la prueba de seguridad). `DocumentoRechazado` debe ser 1 por cada corrida de la prueba de seguridad.

Para ver el ejecutable disfrazado:

```
filter `detail-type` = "DocumentoRechazado"
| fields @timestamp, detail.llave, detail.tipo_declarado, detail.tipo_real
```

## 3. Accesos denegados que registró CloudTrail (ASR-4)

Grupo de registros: `/segur-alpes-poc/cloudtrail`

```
filter ispresent(errorCode)
| fields eventTime, eventName, errorCode, errorMessage, sourceIPAddress, requestParameters.key
| sort eventTime desc
```

CloudTrail no registra las solicitudes que fallan la autenticación (firma inválida o ausente). Esas quedan en los registros de acceso del servidor de S3, en el bucket de auditoría, que llegan en unas horas (ver el paso 4 del README).
