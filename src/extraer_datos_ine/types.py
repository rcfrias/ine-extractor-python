"""Tipos del SDK de Extraer Datos de INE."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict, Union


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


class UrlSource(TypedDict):
    """Imagen referenciada por URL HTTPS (la API la descarga)."""

    url: str


class Base64Source(TypedDict):
    """Imagen codificada en base64 (con o sin prefijo ``data:``)."""

    base64: str


# Una fuente de imagen puede ser binaria (bytes), base64 (str o dict) o URL (dict).
ImageSource = Union[bytes, bytearray, str, UrlSource, Base64Source]
