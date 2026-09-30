"""SDK oficial de Extraer Datos de INE — API de OCR para credenciales INE/IFE.

https://extraerdatosdeine.com/docs
"""

from .client import IneExtractorClient
from .errors import IneExtractorError
from .types import (
    Base64Source,
    CaptureLink,
    Delivery,
    ExtractResult,
    ImageSource,
    IneData,
    UrlSource,
)
from .webhooks import (
    IDEMPOTENCY_KEY_HEADER,
    SIGNATURE_HEADER,
    SIGNATURE_TIMESTAMP_HEADER,
    parse_webhook,
    verify_webhook_signature,
)

__all__ = [
    "IneExtractorClient",
    "IneExtractorError",
    "ExtractResult",
    "Delivery",
    "CaptureLink",
    "verify_webhook_signature",
    "parse_webhook",
    "SIGNATURE_HEADER",
    "SIGNATURE_TIMESTAMP_HEADER",
    "IDEMPOTENCY_KEY_HEADER",
    "IneData",
    "ImageSource",
    "UrlSource",
    "Base64Source",
]

__version__ = "1.1.0"
