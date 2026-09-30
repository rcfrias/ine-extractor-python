# extraer-datos-ine (Python)

SDK oficial en Python para la **[API de OCR para INE de Extraer Datos de INE](https://extraerdatosdeine.com)** — extrae CURP, nombre, clave de elector, dirección y todos los campos de una **credencial para votar mexicana (INE/IFE)** a partir de una imagen, en segundos.

- 🇲🇽 Diseñado para credenciales **INE e IFE** (todos los modelos).
- 🧩 **Cero dependencias.** Solo la librería estándar (`urllib`).
- 🔠 **Tipado** (`py.typed`): `IneData` con los 20 campos y errores tipados.
- 🐍 Compatible con **Python 3.9+**.
- 📲 **Links de captura**: tu cliente fotografía su INE desde su teléfono y los datos llegan a tu webhook.
- 🔏 **Verifica la firma** de los webhooks que te enviamos.

📚 Documentación de la API: **https://extraerdatosdeine.com/docs**
🔑 Consigue una API key con **20 extracciones gratis**: **https://extraerdatosdeine.com/register**

---

## Instalación

```bash
pip install extraer-datos-ine
```

## Uso rápido

```python
from extraer_datos_ine import IneExtractorClient

client = IneExtractorClient(api_key="ine_tu_api_key")

with open("ine_frente.jpg", "rb") as f:
    front = f.read()
with open("ine_reverso.jpg", "rb") as f:  # opcional, para CIC/OCR del reverso
    back = f.read()

result = client.extract(front=front, back=back)
print(result.data["curp"])          # 'PEGJ850101HDFRRL09'
print(result.data["claveElector"])  # 'PRGRJN85010109H100'
print(result.tokens_remaining)      # 19
```

### Consultar saldo de tokens

```python
print("Tokens disponibles:", client.get_balance())
```

## Formas de enviar la imagen

El método de envío se elige automáticamente según el tipo de `front`/`back`.

| Tipo de entrada | Ejemplo | Método HTTP usado |
|---|---|---|
| Binario | `bytes` / `bytearray` | `multipart/form-data` |
| Base64 | `"..."` o `{"base64": "..."}` | JSON base64 |
| URL | `{"url": "https://..."}` | JSON URL (la API descarga la imagen) |

```python
# Binario
client.extract(front=front_bytes, front_mime_type="image/png")

# Base64
client.extract(front={"base64": b64}, back={"base64": back_b64})

# URL HTTPS
client.extract(front={"url": url}, back={"url": back_url})
```

> `front` y `back` deben ser del **mismo tipo**: la API no mezcla métodos en una sola petición.

## Entregar a tu destino (`destination_id`)

Crea un destino (webhook, correo, chat…) en **Dashboard → Destinos** y pasa su id. Los datos se
entregan antes de que `extract()` responda, y el resultado viene en `result.delivery`:

```python
result = client.extract(front=front, destination_id="dst_...")
if result.delivery and not result.delivery.succeeded:
    print("La entrega falló:", result.delivery.error_code, result.delivery.http_status)
```

Un destino inexistente o pausado falla con `DESTINATION_NOT_FOUND` **antes** de gastar un token.
Una entrega fallida no deshace la extracción (el token se cobra y `result.data` viene completo);
no hay reintentos.

## Links de captura (BETA)

Tu cliente fotografía su INE (o pasaporte) desde su propio teléfono; los datos llegan a tu destino.
Ideal para un check-in o un alta: tu sistema muestra la URL como QR o la envía por mensaje.

```python
link = client.create_capture_link(
    "dst_...",                     # destino que recibe los datos
    document_type="ine",           # "ine" o "passport"
    reference="Reserva 1042",      # vuelve en el webhook (máx. 80 caracteres)
    require_back=True,             # pedir también el reverso
    requester_name="Hotel Sol",    # lo que ve tu cliente (máx. 60)
)
print(link.url)         # muéstrala como QR / envíala por WhatsApp
print(link.expires_at)  # plazo para abrirla
```

- **Un solo uso.** 15 minutos para abrir el link y 15 más desde que se abre.
- **`link.url` es una credencial y solo se devuelve una vez:** no la guardes en logs.
- Crear el link **no gasta tokens**; la captura gasta uno y **se reembolsa** si la extracción o la
  entrega fallan.
- Máximo **20 links vivos** por cuenta (`TOO_MANY_LIVE_LINKS`).
- Errores: `NOT_FOUND` (links desactivados para tu cuenta), `DESTINATION_NOT_FOUND`,
  `INVALID_DOCUMENT_TYPE`, `INVALID_REFERENCE`, `INVALID_NAME`, `INVALID_REQUESTER_NAME`.

## Recibir el webhook

Cada entrega lleva `X-Signature` (`sha256=` + HMAC-SHA256 de `timestamp + "." + cuerpo` con el
secreto de tu destino), `X-Signature-Timestamp` y `X-Idempotency-Key`. Verifícala **con el cuerpo
crudo**, sin re-serializarlo:

```python
import os
from flask import Flask, request
from extraer_datos_ine import IneExtractorError, parse_webhook

app = Flask(__name__)

@app.post("/webhooks/ine")
def ine_webhook():
    try:
        event = parse_webhook(
            os.environ["INE_WEBHOOK_SECRET"],  # whsec_…
            request.get_data(),                # cuerpo crudo
            request.headers.get("X-Signature"),
            request.headers.get("X-Signature-Timestamp"),
        )
    except IneExtractorError:
        return "", 401
    if event["event"] == "extraction.completed":
        print(event["reference"], event["data"]["curp"])
    return "", 204
```

Con FastAPI, usa `await request.body()` como cuerpo crudo.

El cuerpo es:

```json
{
  "version": "1",
  "event": "extraction.completed",
  "idempotencyKey": "…",
  "documentType": "ine",
  "source": "capture-link",
  "captureLinkId": "…",
  "reference": "Reserva 1042",
  "extractedAt": "2026-09-30T12:00:00.000Z",
  "data": { "curp": "…", "claveElector": "…" }
}
```

`source` es `"web"`, `"api"` o `"capture-link"`; `image` (`front`/`back` en base64) solo viene si
lo activaste en el destino. Usa `idempotencyKey` para descartar duplicados.

`verify_webhook_signature()` hace lo mismo y devuelve `True`/`False`. Por defecto rechaza firmas con
más de 300 s de antigüedad (`tolerance_seconds=0` lo desactiva).

## Manejo de errores

```python
from extraer_datos_ine import IneExtractorError

try:
    result = client.extract(front=front)
except IneExtractorError as err:
    if err.code == "INSUFFICIENT_TOKENS":
        print("Sin tokens. Recarga en:", err.enroll_url)
    elif err.code == "LOW_IMAGE_QUALITY":
        print("Imagen ilegible. Campos faltantes:", err.missing_fields)
    else:
        print(f"[{err.code}] {err.message}")
```

### Códigos de error

| `code` | HTTP | Significado |
|---|---|---|
| `MISSING_API_KEY` | 401 | No se envió la API key |
| `INVALID_API_KEY` | 401 | API key inválida o revocada |
| `MISSING_IMAGE` | 400 | Falta la imagen frontal |
| `INVALID_IMAGE_FORMAT` | 400 | Formato no soportado (usa JPEG, PNG o WebP) |
| `IMAGE_TOO_LARGE` | 400 | La imagen excede 10 MB |
| `INVALID_BASE64` | 400 | Error al decodificar base64 |
| `INVALID_MULTIPART` | 400 | Error al procesar el formulario multipart |
| `URL_FETCH_FAILED` | 400 | No se pudo descargar la imagen de la URL |
| `URL_INVALID` | 400 | URL inválida (debe ser HTTPS) |
| `URL_BLOCKED` | 400 | URL bloqueada por seguridad |
| `URL_TIMEOUT` | 400 | Timeout al descargar la imagen (10 s) |
| `UNSUPPORTED_CONTENT_TYPE` | 415 | Content-Type no soportado |
| `INSUFFICIENT_TOKENS` | 402 | Saldo insuficiente (ver `err.enroll_url`) |
| `LOW_IMAGE_QUALITY` | 422 | Imagen ilegible (ver `err.missing_fields`) |
| `EXTRACTION_FAILED` | 500 | Falló la extracción (el token se reembolsa) |
| `PROCESSING_ERROR` | 500 | Error procesando la imagen (token reembolsado) |
| `INTERNAL_ERROR` | 500 | Error interno del servidor |
| `DESTINATION_NOT_FOUND` | 400 | El destino no existe, no es tuyo o está pausado |
| `TOO_MANY_LIVE_LINKS` | 400 | Ya tienes 20 links de captura vivos |
| `NOT_FOUND` | 404 | Links de captura desactivados para tu cuenta |
| `INVALID_SIGNATURE` | — | Firma de webhook inválida o vencida (`parse_webhook`) |
| `NETWORK_ERROR` | — | Fallo de red (lado del cliente) |
| `TIMEOUT` | — | Se superó el `timeout` del cliente |

## Campos extraídos (`IneData`)

`nombre`, `apellidoPaterno`, `apellidoMaterno`, `domicilio`, `calle`, `colonia`, `codigoPostal`, `municipio`, `estado`, `seccion`, `curp`, `claveElector`, `anioRegistro`, `fechaNacimiento`, `sexo`, `vigencia`, `numeroVertical`, `ocr`, `cic`, `emision`.

Los cuatro últimos (`numeroVertical`, `ocr`, `cic`, `emision`) viven en el **reverso**: envía también `back` para obtenerlos.

## Configuración del cliente

```python
IneExtractorClient(
    api_key="ine_...",
    base_url="https://extraerdatosdeine.com/api/v1",  # default
    timeout=60.0,                                       # segundos
)
```

## Desarrollo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m unittest discover -s tests -v
pip install build && python -m build   # genera sdist + wheel en dist/
```

## Enlaces

- 🌐 Sitio: https://extraerdatosdeine.com
- 📚 Documentación de la API: https://extraerdatosdeine.com/docs
- 🔑 Crear cuenta (20 extracciones gratis): https://extraerdatosdeine.com/register
- 📦 SDK de JavaScript/TypeScript: https://www.npmjs.com/package/extraer-datos-ine

## Licencia

[MIT](./LICENSE) © Extraer Datos de INE
