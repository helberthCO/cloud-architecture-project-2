# SegurAlpes · Prueba de concepto: carga de evidencias con URL prefirmada

Prueba de concepto de la Entrega 2 del proyecto de **ARTI4207 Architecting for the Cloud** (MATI, Universidad de los Andes, 2026-20). SegurAlpes es una aseguradora digital de microseguros para MiPymes que moderniza su plataforma desde Oracle Cloud Infrastructure hacia una arquitectura cloud native; esta prueba valida en AWS uno de los puntos de sensibilidad de la arquitectura propuesta.

## Qué evalúa

**ASR-3 · Rendimiento en la carga de evidencias.** Como asegurado, cuando subo desde el celular las fotos y facturas de mi siniestro, quiero que cada archivo quede cargado en pocos segundos para no abandonar el reporte.

| Elemento | Valor |
|---|---|
| Fuente | Asegurado desde el celular |
| Estímulo | Carga de una evidencia de 5 MB; 50 cargas simultáneas durante un evento climático |
| Artefacto | Servicio de documentos (URL prefirmada), almacenamiento de objetos y función de validación |
| Entorno | Operación normal, con una conexión de subida de al menos 20 Mbps |
| Respuesta | El cliente obtiene una URL prefirmada, sube el archivo directo al almacenamiento y una función lo valida y publica el evento |
| Medida | Carga en menos de 3 s (p95); URL emitida en menos de 300 ms (p95); evento publicado en menos de 10 s; ningún archivo sin validar |

**ASR-4 · Seguridad de los documentos**, en la parte comprobable en horas: ningún intento no autorizado tiene éxito y los intentos quedan registrados.

Los dos dependen de la misma decisión, la carga directa con URL prefirmada (patrón *valet key*): es un punto de compensación entre rendimiento y seguridad.

## Arquitectura de la prueba

| Pila | Región | Contenido |
|---|---|---|
| `segur-alpes-poc` | us-east-1 | API Gateway REST con llave de API y plan de uso por aliado · Lambda que emite la URL prefirmada POST (60 s de vigencia, tipo de archivo fijo, máximo 10 MB) · S3 cifrado con una llave de AWS KMS, sin acceso público, con versionado y solo TLS · Lambda que valida la firma binaria de cada archivo y publica `DocumentoCargado` o `DocumentoRechazado` en Amazon EventBridge · AWS CloudTrail con eventos de datos del bucket · registros de acceso del servidor de S3 · tablero de Amazon CloudWatch |
| `segur-alpes-poc-carga` | sa-east-1 | Instancia EC2 con k6 que simula usuarios en Suramérica. Sin puertos abiertos: acceso por Session Manager. Se apaga sola a las 4 horas |

Diferencias con la arquitectura completa: la URL la emite una Lambda y no el servicio de documentos en Kubernetes (el ASR mide la carga directa, que no pasa por ese cómputo); no hay CDN ni WAF delante del API; el bucket no tiene bloqueo de escritura única, para poder borrar la prueba; la infraestructura se define en CloudFormation para desplegarla sin instalar herramientas.

## Estructura del repositorio

| Ruta | Contenido |
|---|---|
| `dist/` | Plantillas listas para desplegar (generadas) |
| `plantillas/` | Plantilla fuente de la pila principal |
| `lambdas/` | Código de las dos funciones |
| `pruebas/` | Pruebas de carga y de seguridad (k6), prueba desde la red del usuario (Python) y generador de archivos de prueba |
| `pruebas_locales/` | Pruebas unitarias de las funciones y simulador local del API y de S3 para validar los scripts sin AWS |
| `consultas.md` | Consultas de CloudWatch Logs Insights para recoger la evidencia |
| `resultados/` | Resúmenes de las corridas |
| `generar.py` | Regenera `dist/` a partir de las fuentes |

## Cómo desplegarla

Requisitos: cuenta de AWS con permisos de administrador y AWS CLI v2 configurada (también se puede hacer desde la consola web cargando las plantillas de `dist/`). Costo estimado: menos de USD 5 si se borra el mismo día.

```bash
# 1. Llave de API del aliado de prueba
export API_KEY=$(openssl rand -hex 20)

# 2. Pila principal en us-east-1
aws cloudformation deploy --region us-east-1 --stack-name segur-alpes-poc \
  --template-file dist/1-principal-us-east-1.yaml --capabilities CAPABILITY_IAM \
  --parameter-overrides ApiKeyValue=$API_KEY
export API_URL=$(aws cloudformation describe-stacks --region us-east-1 --stack-name segur-alpes-poc \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)

# 3. Prueba rápida: debe responder 201 con url, campos, llave y vence_en_s
curl -s -X POST "$API_URL" -H "x-api-key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"siniestro":"PRUEBA1","tipo":"image/jpeg"}'

# 4. Generador de carga en sa-east-1 (si no hay VPC por defecto: aws ec2 create-default-vpc --region sa-east-1)
aws cloudformation deploy --region sa-east-1 --stack-name segur-alpes-poc-carga \
  --template-file dist/2-carga-sa-east-1.json --capabilities CAPABILITY_IAM \
  --parameter-overrides ApiUrl=$API_URL ApiKeyValue=$API_KEY
```

## Cómo correr las pruebas

En la instancia (EC2 → `segur-alpes-poc-carga` → Conectar → Session Manager), cuando `cat /opt/poc/estado` diga `LISTO`:

```bash
sudo /opt/poc/correr.sh individual   # 1 usuario, 20 cargas de 5 MB seguidas
sudo /opt/poc/correr.sh pico         # 50 usuarios simultáneos, 4 cargas cada uno (200 cargas)
sudo /opt/poc/correr.sh seguridad    # 8 intentos no autorizados, 1 archivo disfrazado y 1 control
```

Desde la red del usuario:

```bash
bash pruebas/generar_archivos.sh ./datos
API_URL=$API_URL API_KEY=$API_KEY python3 pruebas/individual.py datos/evidencia_5mb.jpg 10
```

La evidencia se recoge en el tablero `segur-alpes-poc` de CloudWatch y con las consultas de `consultas.md`. Los registros de acceso del servidor de S3 llegan al bucket de auditoría en unas horas e incluyen los rechazos por firma inválida, que CloudTrail no registra.

Pruebas sin AWS: `cd pruebas_locales && python3 test_lambdas.py`.

## Resultados

| Prueba | URL p95 (meta < 300 ms) | Carga p95 (meta < 3 s) | Fallas | Cumple |
|---|---|---|---|---|
| Individual (sa-east-1) | — | — | — | — |
| Pico, 50 usuarios (sa-east-1) | — | — | — | — |
| Red residencial (Bogotá) | — | — | — | — |

| Medida | Resultado | Cumple |
|---|---|---|
| Evento publicado (meta p95 < 10 s) | — | — |
| Eventos `DocumentoCargado` frente a cargas exitosas | — | — |
| Intentos no autorizados exitosos (meta 0 de 8) | — | — |
| Ejecutable disfrazado en cuarentena | — | — |

Video de la prueba: *pendiente*.

## Borrar todo

1. Borrar la pila `segur-alpes-poc-carga` en sa-east-1.
2. Vaciar en la consola de S3 los buckets `segur-alpes-poc-evidencias-<cuenta>` y `segur-alpes-poc-auditoria-<cuenta>` (el vaciado de la consola borra también las versiones).
3. Borrar la pila `segur-alpes-poc` en us-east-1. La llave KMS queda programada para borrarse en 7 días.
