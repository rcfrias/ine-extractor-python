"""Errores del SDK de Extraer Datos de INE."""

from __future__ import annotations

from typing import Any, Optional


class IneExtractorError(Exception):
    """Error ante cualquier respuesta no exitosa de la API o un fallo de red.

    Inspecciona :attr:`code` para reaccionar de forma programática.

    Códigos de la API: ``MISSING_API_KEY``, ``INVALID_API_KEY``,
    ``MISSING_IMAGE``, ``INVALID_IMAGE_FORMAT``, ``IMAGE_TOO_LARGE``,
    ``INVALID_BASE64``, ``INVALID_MULTIPART``, ``URL_FETCH_FAILED``,
    ``URL_INVALID``, ``URL_BLOCKED``, ``URL_TIMEOUT``,
    ``UNSUPPORTED_CONTENT_TYPE``, ``INSUFFICIENT_TOKENS``,
    ``LOW_IMAGE_QUALITY``, ``EXTRACTION_FAILED``, ``PROCESSING_ERROR``,
    ``INTERNAL_ERROR``, ``DESTINATION_NOT_FOUND``, ``TOO_MANY_LIVE_LINKS``,
    ``INVALID_DOCUMENT_TYPE``, ``INVALID_REFERENCE``, ``INVALID_NAME``,
    ``INVALID_REQUESTER_NAME``, ``NOT_FOUND``.

    Códigos propios del SDK: ``NETWORK_ERROR``, ``TIMEOUT``, ``INVALID_INPUT``,
    ``INVALID_SIGNATURE``.

    https://extraerdatosdeine.com/docs
    """

    def __init__(
        self,
        message: str,
        code: str,
        *,
        status: Optional[int] = None,
        extraction_id: Optional[str] = None,
        missing_fields: Optional[list[str]] = None,
        enroll_url: Optional[str] = None,
        block_reason: Optional[str] = None,
        response: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.extraction_id = extraction_id
        self.missing_fields = missing_fields
        self.enroll_url = enroll_url
        self.block_reason = block_reason
        self.response = response

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"[{self.code}] {self.message}"

    @classmethod
    def from_response(cls, status: int, body: Any) -> "IneExtractorError":
        """Construye el error a partir de una respuesta de la API."""
        b = body if isinstance(body, dict) else {}
        code = b.get("code") if isinstance(b.get("code"), str) else "INTERNAL_ERROR"
        message = (
            b.get("error")
            if isinstance(b.get("error"), str)
            else f"La API respondió con status {status}"
        )
        missing = b.get("missing_fields")
        return cls(
            message,
            code,
            status=status,
            extraction_id=b.get("extraction_id") if isinstance(b.get("extraction_id"), str) else None,
            missing_fields=missing if isinstance(missing, list) else None,
            enroll_url=b.get("enroll_url") if isinstance(b.get("enroll_url"), str) else None,
            block_reason=b.get("block_reason") if isinstance(b.get("block_reason"), str) else None,
            response=body,
        )
