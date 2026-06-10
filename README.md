# extraer-datos-ine (Python)

SDK oficial en Python para la **[API de OCR para INE de Extraer Datos de INE](https://extraerdatosdeine.com)** — extrae CURP, nombre, clave de elector, dirección y todos los campos de una **credencial para votar mexicana (INE/IFE)** a partir de una imagen, en segundos.

- 🇲🇽 Diseñado para credenciales **INE e IFE** (todos los modelos).
- 🧩 **Cero dependencias.** Solo la librería estándar (`urllib`).
- 🔠 **Tipado** (`py.typed`): `IneData` con los 20 campos y errores tipados.
- 🐍 Compatible con **Python 3.9+**.

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
