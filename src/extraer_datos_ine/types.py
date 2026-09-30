"""Tipos del SDK de Extraer Datos de INE."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TypedDict, Union


class IneData(TypedDict, total=False):
    """Datos extraídos de una credencial INE/IFE.

    Todos los valores son ``str``. Los campos del reverso (``numeroVertical``,
    ``ocr``, ``cic``, ``emision``) solo se obtienen si envías también la imagen
    trasera. Un campo puede venir vacío si no es legible.
    """

    nombre: str
    apellidoPaterno: str
    apellidoMaterno: str
    domicilio: str
    calle: str
    colonia: str
    codigoPostal: str
    municipio: str
    estado: str
    seccion: str
    curp: str
    claveElector: str
    anioRegistro: str
    fechaNacimiento: str
    sexo: str
    vigencia: str
    numeroVertical: str
    ocr: str
    cic: str
    emision: str


@dataclass(frozen=True)
class Delivery:
    """Resultado de la entrega a tu destino (solo si enviaste ``destination_id``).

    Una entrega fallida no deshace la extracción: el token ya se cobró y los
    datos vienen igual en ``ExtractResult.data``. No hay reintentos.
    """

    destination_id: str
    succeeded: bool
    http_status: Optional[int]
    """Status HTTP que respondió tu destino (``None`` si no respondió)."""
    latency_ms: Optional[int]
    error_code: Optional[str]
    """Motivo del fallo (``None`` si la entrega tuvo éxito)."""


@dataclass(frozen=True)
class ExtractResult:
    """Resultado de una extracción exitosa."""

    extraction_id: str
    """Identificador de la extracción en el sistema."""
    data: IneData
    """Datos extraídos de la credencial."""
    tokens_remaining: int
    """Tokens restantes en tu cuenta tras esta extracción."""
    upload_method: str
    """Método de upload detectado por la API."""
    delivery: Optional[Delivery] = None
    """Resultado de la entrega a tu destino, si enviaste ``destination_id``."""


@dataclass(frozen=True)
class CaptureLink:
    """Link de captura de un solo uso, creado con ``create_capture_link``.

    ``url`` es una credencial: se devuelve una sola vez, no la guardes en logs.
    """

    id: str
    url: str
    """URL para tu cliente (muéstrala como QR o envíala por mensaje)."""
    reference: Optional[str]
    document_type: str
    """``"ine"`` o ``"passport"``."""
    require_back: bool
    ask_guest_persona: bool
    expires_at: str
    """ISO 8601: plazo para abrir el link (luego corre la ventana del invitado)."""


class UrlSource(TypedDict):
    """Imagen referenciada por URL HTTPS (la API la descarga)."""

    url: str


class Base64Source(TypedDict):
    """Imagen codificada en base64 (con o sin prefijo ``data:``)."""

    base64: str


# Una fuente de imagen puede ser binaria (bytes), base64 (str o dict) o URL (dict).
ImageSource = Union[bytes, bytearray, str, UrlSource, Base64Source]
