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
| `segur-alpes-poc` | us-east-2 | API Gateway REST con llave de API y plan de uso por aliado · Lambda que emite la URL prefirmada POST (60 s de vigencia, tipo de archivo fijo, máximo 10 MB) · S3 cifrado con una llave de AWS KMS, sin acceso público, con versionado y solo TLS · Lambda que valida la firma binaria de cada archivo y publica `DocumentoCargado` o `DocumentoRechazado` en Amazon EventBridge · AWS CloudTrail con eventos de datos del bucket · registros de acceso del servidor de S3 · tablero de Amazon CloudWatch |
| `segur-alpes-poc-carga` | us-east-2 | Instancia EC2 con k6, en una VPC propia, que genera la concurrencia (50 usuarios simultáneos). Sin puertos abiertos: acceso por Session Manager. Se apaga sola a las 4 horas |

La cuenta usa la experiencia nueva de AWS, que asigna una sola región por proyecto (us-east-2) y no permite recursos en otras regiones; por eso las dos pilas van en la misma región, y la distancia de red real se mide con la prueba desde una conexión residencial en Bogotá. El blueprint de la arquitectura usa us-east-1; los servicios son los mismos.

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

Desde la consola web: en CloudFormation, **Create stack** → **Upload a template file** con `dist/1-principal.yaml` (parámetro `ApiKeyValue`), marcar la casilla de recursos de IAM y copiar `ApiUrl` de **Outputs**; después lo mismo con `dist/2-generador-carga.json` (parámetros `ApiUrl` y `ApiKeyValue`). Costo estimado: menos de USD 5 si se borra el mismo día.

Con la AWS CLI v2:

```bash
# 1. Llave de API del aliado de prueba
export API_KEY=$(openssl rand -hex 20)

# 2. Pila principal
aws cloudformation deploy --region us-east-2 --stack-name segur-alpes-poc \
  --template-file dist/1-principal.yaml --capabilities CAPABILITY_IAM \
  --parameter-overrides ApiKeyValue=$API_KEY
export API_URL=$(aws cloudformation describe-stacks --region us-east-2 --stack-name segur-alpes-poc \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)

# 3. Prueba rápida: debe responder 201 con url, campos, llave y vence_en_s
curl -s -X POST "$API_URL" -H "x-api-key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"siniestro":"PRUEBA1","tipo":"image/jpeg"}'

# 4. Generador de carga (crea su propia VPC)
aws cloudformation deploy --region us-east-2 --stack-name segur-alpes-poc-carga \
  --template-file dist/2-generador-carga.json --capabilities CAPABILITY_IAM \
  --parameter-overrides ApiUrl=$API_URL ApiKeyValue=$API_KEY
```

## Cómo correr las pruebas

En la instancia (EC2 → `segur-alpes-poc-carga` → Conectar → Session Manager), cuando `cat /opt/poc/estado` diga `LISTO`:

```bash
sudo /opt/poc/correr.sh individual   # 1 usuario, 20 cargas de 5 MB seguidas
sudo /opt/poc/correr.sh pico         # 50 usuarios simultáneos, 4 cargas cada uno (200 cargas)
sudo /opt/poc/correr.sh seguridad    # 8 intentos no autorizados, 1 archivo disfrazado y 1 control
```

Desde la red del usuario (la medición de la red real):

```bash
bash pruebas/generar_archivos.sh ./datos
API_URL=$API_URL API_KEY=$API_KEY python3 pruebas/individual.py datos/evidencia_5mb.jpg 20               # conexión nueva por solicitud
API_URL=$API_URL API_KEY=$API_KEY python3 pruebas/individual.py datos/evidencia_5mb.jpg 20 --reutilizar # conexión reutilizada, como una app
```

La evidencia se recoge en el tablero `segur-alpes-poc` de CloudWatch y con las consultas de `consultas.md`. Los registros de acceso del servidor de S3 llegan al bucket de auditoría en unas horas e incluyen los rechazos por firma inválida, que CloudTrail no registra.

Pruebas sin AWS: `cd pruebas_locales && python3 test_lambdas.py`.

## Resultados

Pruebas ejecutadas el 22/11/2026 (individual, red real, seguridad y pico con la cuota de 10 ejecuciones simultáneas de Lambda) y el 23/11/2026 (pico de 50 usuarios con la cuota de 1.000), en us-east-2. El análisis completo está en el documento de la Entrega 2.

**ASR-3: carga de evidencias**

| Prueba | Cargas | URL p95 (meta < 300 ms) | Carga p95 (meta < 3 s) | Cumple |
|---|---|---|---|---|
| Individual (generador en us-east-2) | 20 de 20 | 71 ms | 106 ms | Sí |
| Red residencial en Bogotá, conexión nueva por solicitud | 20 de 20 | 963 ms | 2.151 ms | La URL no |
| Red residencial en Bogotá, conexión reutilizada | 20 de 20 | 189 ms | 2.226 ms | Sí |
| Pico, 50 usuarios × 4 cargas (cuota de 1.000) | 200 de 200 | 826 ms | 622 ms | La URL no (arranque en frío) |
| Pico con la cuota de 10 (10, 5 y 2 usuarios) | 293 de 400 | 26–47 ms | 138–185 ms | No: 6–34 % de rechazos por throttling |

| Medida | Resultado | Cumple |
|---|---|---|
| Evento publicado, operación normal (meta p95 < 10 s) | p95 1,7 s | Sí |
| Evento publicado, pico de 50 usuarios | p95 2,0 s | Sí |
| Evento publicado, pico con la cuota de 10 | p95 22,9 s | No |
| Eventos `DocumentoCargado` frente a cargas exitosas | 200 de 200 y 293 de 293 | Sí |

**ASR-4: intentos no autorizados**

| Medida | Resultado | Cumple |
|---|---|---|
| Intentos no autorizados exitosos (meta 0 de 8) | 0 de 8 | Sí |
| Ejecutable disfrazado de JPEG | En cuarentena, con evento `DocumentoRechazado` | Sí |
| Intentos registrados | 6 de 6 en CloudTrail; los 2 que rechaza el API Gateway solo como métrica 4XX | Parcial |

**Qué explica los incumplimientos**

- La cuenta nueva tenía una cuota de 10 ejecuciones simultáneas de Lambda, compartida: la función que valida dejaba sin capacidad a la que emite la URL. Con la cuota de 1.000 no hubo rechazos.
- Con 50 usuarios que empiezan a la vez, Lambda crea 50 entornos para la función que emite la URL (≈ 0,5 s de arranque cada uno); ya iniciada, firma en 5,3 ms (p95). Se mitiga con concurrencia aprovisionada; en la arquitectura completa, con réplicas mínimas del servicio de documentos.
- Desde Bogotá, el saludo TLS a Ohio suma cerca de 300 ms cuando la conexión no se reutiliza.

**Corrección durante la prueba.** La primera versión de `lambdas/validar.py` llamaba a `put_entries`, un método que no existe en el cliente de EventBridge; el correcto es `put_events`. Las pruebas locales no lo detectaron porque el doble de prueba tenía el mismo error. Se corrigió en la función desplegada en AWS y en este repositorio, junto con el doble de prueba, que ahora solo expone los métodos reales del SDK. Todas las medidas de eventos son posteriores a la corrección.

Video de la prueba: https://youtu.be/snSUJYZ4RIs

## Borrar todo

1. Borrar la pila `segur-alpes-poc-carga`.
2. Vaciar en la consola de S3 los buckets `segur-alpes-poc-evidencias-<cuenta>` y `segur-alpes-poc-auditoria-<cuenta>` (el vaciado de la consola borra también las versiones).
3. Borrar la pila `segur-alpes-poc`. La llave KMS queda programada para borrarse en 7 días.
