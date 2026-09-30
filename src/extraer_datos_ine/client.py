"""Cliente HTTP para la API de Extraer Datos de INE (sin dependencias externas)."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
import uuid
from typing import Any, Callable, Optional

from .errors import IneExtractorError
from .types import CaptureLink, Delivery, ExtractResult, ImageSource

DEFAULT_BASE_URL = "https://extraerdatosdeine.com/api/v1"
DEFAULT_TIMEOUT = 60.0
# Cloudflare, in front of the API, answers 403 to urllib's default
# "Python-urllib/3.x" User-Agent, so every request names the SDK instead.
USER_AGENT = "extraer-datos-ine-python/1.1.0"

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
        destination_id: Optional[str] = None,
    ) -> ExtractResult:
        """Extrae los datos de una credencial INE/IFE.

        El método de envío se elige según el tipo de ``front``: ``bytes`` →
        multipart; ``str`` o ``{"base64": ...}`` → JSON base64; ``{"url": ...}``
        → JSON URL. ``front`` y ``back`` deben ser del mismo tipo.

        Con ``destination_id`` (header ``X-Destination-Id``) los datos se
        entregan además a uno de tus destinos antes de responder, y el
        resultado viene en ``result.delivery``. Un destino inexistente o
        pausado falla con ``DESTINATION_NOT_FOUND`` antes de gastar un token.

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

        headers = {"X-Destination-Id": destination_id} if destination_id else None

        if front_kind == "url":
            payload = {"image_front_url": _as_url(front)}
            if back is not None:
                payload["image_back_url"] = _as_url(back)
            body = self._request("POST", "/extract", json_body=payload, headers=headers)
        elif front_kind == "base64":
            payload = {"image_front": _as_base64(front)}
            if back is not None:
                payload["image_back"] = _as_base64(back)
            body = self._request("POST", "/extract", json_body=payload, headers=headers)
        else:
            files = {"image_front": ("image_front", bytes(front), front_mime_type)}  # type: ignore[arg-type]
            if back is not None:
                files["image_back"] = ("image_back", bytes(back), back_mime_type)  # type: ignore[arg-type]
            body = self._request("POST", "/extract", files=files, headers=headers)

        return ExtractResult(
            extraction_id=body["extraction_id"],
            data=body["data"],
            tokens_remaining=body["tokens_remaining"],
            upload_method=body["upload_method"],
            delivery=_parse_delivery(body.get("delivery")),
        )

    def create_capture_link(
        self,
        destination_id: str,
        *,
        document_type: str = "ine",
        reference: Optional[str] = None,
        require_back: bool = False,
        requester_name: Optional[str] = None,
        name: Optional[str] = None,
    ) -> CaptureLink:
        """Crea un link de captura (BETA) para que tu cliente fotografíe su
        identificación desde su teléfono.

        El link es de un solo uso: hay 15 minutos para abrirlo y 15 más desde
        que se abre. Los datos llegan a tu destino ``destination_id``. Crear el
        link no gasta tokens; la captura gasta uno y se reembolsa si la
        extracción o la entrega fallan. Máximo 20 links vivos por cuenta.

        ``document_type`` es ``"ine"`` o ``"passport"``; ``reference`` (máx. 80
        caracteres) vuelve en el webhook; ``requester_name`` (máx. 60) es el
        nombre que ve tu cliente.

        ``url`` es una credencial y solo se devuelve aquí: no la guardes en logs.
        """
        if not destination_id:
            raise IneExtractorError("Falta `destination_id`.", "INVALID_INPUT")
        payload: dict = {"destinationId": destination_id, "documentType": document_type}
        if reference is not None:
            payload["reference"] = reference
        if require_back:
            payload["requireBack"] = True
        if requester_name is not None:
            payload["requesterName"] = requester_name
        if name is not None:
            payload["name"] = name
        body = self._request("POST", "/capture-links", json_body=payload)
        return CaptureLink(
            id=body["id"],
            url=body["url"],
            reference=body.get("reference"),
            document_type=body["documentType"],
            require_back=bool(body.get("requireBack")),
            ask_guest_persona=bool(body.get("askGuestPersona")),
            expires_at=body["expiresAt"],
        )

    # -- internals ---------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict] = None,
        files: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> Any:
        url = self.base_url + path
        headers = {**(headers or {}), "X-API-Key": self.api_key, "User-Agent": USER_AGENT}
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


def _parse_delivery(raw: Any) -> Optional[Delivery]:
    if not isinstance(raw, dict):
        return None
    return Delivery(
        destination_id=raw.get("destination_id", ""),
        succeeded=bool(raw.get("succeeded")),
        http_status=raw.get("http_status"),
        latency_ms=raw.get("latency_ms"),
        error_code=raw.get("error_code"),
    )


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
