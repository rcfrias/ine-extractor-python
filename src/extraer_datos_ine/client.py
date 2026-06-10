"""Cliente HTTP para la API de Extraer Datos de INE (sin dependencias externas)."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
import uuid
from typing import Any, Callable, Optional

from .errors import IneExtractorError
from .types import ExtractResult, ImageSource

DEFAULT_BASE_URL = "https://extraerdatosdeine.com/api/v1"
DEFAULT_TIMEOUT = 60.0

# Firma de un "opener" inyectable (para tests): recibe un Request y un timeout
# y devuelve un objeto con .status / .getcode() y .read(), o lanza HTTPError.
Opener = Callable[[urllib.request.Request, float], Any]


class IneExtractorClient:
    """Cliente para la API de Extraer Datos de INE.

    Ejemplo::

        from extraer_datos_ine import IneExtractorClient

        client = IneExtractorClient(api_key="ine_tu_api_key")
        with open("ine_frente.jpg", "rb") as f:
            front = f.read()
        result = client.extract(front=front)
        print(result.data["curp"], result.data["claveElector"])

    https://extraerdatosdeine.com/docs
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        opener: Optional[Opener] = None,
    ) -> None:
        if not api_key:
            raise IneExtractorError("Falta `api_key`.", "INVALID_INPUT")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # `opener` es un punto de inyección para tests; por defecto usa urllib.
        self._opener: Opener = opener or (
            lambda req, timeout: urllib.request.urlopen(req, timeout=timeout)
        )

    def get_balance(self) -> int:
        """Consulta el saldo de tokens de tu cuenta."""
        body = self._request("GET", "/balance")
        return int(body["balance"])

    def extract(
        self,
        front: ImageSource,
        back: Optional[ImageSource] = None,
        *,
        front_mime_type: str = "image/jpeg",
        back_mime_type: str = "image/jpeg",
    ) -> ExtractResult:
        """Extrae los datos de una credencial INE/IFE.

        El método de envío se elige según el tipo de ``front``: ``bytes`` →
        multipart; ``str`` o ``{"base64": ...}`` → JSON base64; ``{"url": ...}``
        → JSON URL. ``front`` y ``back`` deben ser del mismo tipo.

        Lanza :class:`IneExtractorError` ante saldo insuficiente, imagen
        ilegible, error de red, timeout, etc. Revisa ``error.code``.
        """
        if front is None:
            raise IneExtractorError("Falta la imagen frontal (`front`).", "MISSING_IMAGE")

        front_kind = _kind_of(front)
        if back is not None and _kind_of(back) != front_kind:
            raise IneExtractorError(
                "`front` y `back` deben ser del mismo tipo (binario, base64 o url).",
                "INVALID_INPUT",
            )

        if front_kind == "url":
            payload = {"image_front_url": _as_url(front)}
            if back is not None:
                payload["image_back_url"] = _as_url(back)
            body = self._request("POST", "/extract", json_body=payload)
        elif front_kind == "base64":
            payload = {"image_front": _as_base64(front)}
            if back is not None:
                payload["image_back"] = _as_base64(back)
            body = self._request("POST", "/extract", json_body=payload)
        else:
            files = {"image_front": ("image_front", bytes(front), front_mime_type)}  # type: ignore[arg-type]
            if back is not None:
                files["image_back"] = ("image_back", bytes(back), back_mime_type)  # type: ignore[arg-type]
            body = self._request("POST", "/extract", files=files)

        return ExtractResult(
            extraction_id=body["extraction_id"],
            data=body["data"],
            tokens_remaining=body["tokens_remaining"],
            upload_method=body["upload_method"],
        )

    # -- internals ---------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict] = None,
        files: Optional[dict] = None,
    ) -> Any:
        url = self.base_url + path
        headers = {"X-API-Key": self.api_key}
        data: Optional[bytes] = None

        if files is not None:
            content_type, data = _encode_multipart(files)
            headers["Content-Type"] = content_type
        elif json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            resp = self._opener(req, self.timeout)
            status = getattr(resp, "status", None) or resp.getcode()
            raw = resp.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            body = _parse_json(raw)
            raise IneExtractorError.from_response(exc.code, body) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise IneExtractorError(
                    f"La petición excedió el timeout de {self.timeout}s.", "TIMEOUT"
                ) from exc
            raise IneExtractorError(str(exc.reason), "NETWORK_ERROR") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise IneExtractorError(
                f"La petición excedió el timeout de {self.timeout}s.", "TIMEOUT"
            ) from exc

        body = _parse_json(raw)
        if status >= 400 or (isinstance(body, dict) and body.get("success") is False):
            raise IneExtractorError.from_response(status, body)
        return body


def _kind_of(src: ImageSource) -> str:
    if isinstance(src, (bytes, bytearray)):
        return "binary"
    if isinstance(src, str):
        return "base64"
    if isinstance(src, dict):
        if "url" in src:
            return "url"
        if "base64" in src:
            return "base64"
    raise IneExtractorError(
        "Fuente de imagen no soportada. Usa bytes, str (base64), {'base64': ...} o {'url': ...}.",
        "INVALID_INPUT",
    )


def _as_url(src: ImageSource) -> str:
    if isinstance(src, dict) and "url" in src:
        return str(src["url"])
    raise IneExtractorError("Se esperaba {'url': ...}.", "INVALID_INPUT")


def _as_base64(src: ImageSource) -> str:
    if isinstance(src, str):
        return src
    if isinstance(src, dict) and "base64" in src:
        return str(src["base64"])
    raise IneExtractorError("Se esperaba una cadena base64.", "INVALID_INPUT")


def _encode_multipart(files: dict) -> tuple[str, bytes]:
    """Codifica un cuerpo multipart/form-data. `files` mapea nombre -> (filename, bytes, mime)."""
    boundary = "----ineextractor" + uuid.uuid4().hex
    crlf = b"\r\n"
    body = bytearray()
    for name, (filename, content, mime) in files.items():
        body += b"--" + boundary.encode() + crlf
        body += (
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'
        ).encode() + crlf
        body += f"Content-Type: {mime}".encode() + crlf + crlf
        body += content + crlf
    body += b"--" + boundary.encode() + b"--" + crlf
    return f"multipart/form-data; boundary={boundary}", bytes(body)


def _parse_json(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        return {}
