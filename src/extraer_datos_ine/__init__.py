"""SDK oficial de Extraer Datos de INE — API de OCR para credenciales INE/IFE.

https://extraerdatosdeine.com/docs
"""

from .client import IneExtractorClient
from .errors import IneExtractorError
from .types import Base64Source, ExtractResult, ImageSource, IneData, UrlSource

__all__ = [
    "IneExtractorClient",
    "IneExtractorError",
    "ExtractResult",
    "IneData",
    "ImageSource",
    "UrlSource",
    "Base64Source",
]

__version__ = "1.0.0"
