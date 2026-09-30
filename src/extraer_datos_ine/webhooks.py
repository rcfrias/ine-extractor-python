"""Verificación de los webhooks que envía Extraer Datos de INE.

La firma es ``sha256=`` + HMAC-SHA256(secreto, ``timestamp + "." + cuerpo``),
en el header ``X-Signature``; el timestamp va en ``X-Signature-Timestamp``.

El cuerpo de una extracción es::

    {"version": "1", "event": "extraction.completed", "idempotencyKey": "...",
     "documentType": "ine" | "passport",
     "source": "web" | "api" | "capture-link",
     "captureLinkId": str | None, "reference": str | None,
     "extractedAt": "2026-...Z", "data": {...},
     "image": {"front": "<base64>", "back": "<base64>"}}  # solo si lo activaste

https://extraerdatosdeine.com/docs
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional, Union

from .errors import IneExtractorError

SIGNATURE_HEADER = "X-Signature"
SIGNATURE_TIMESTAMP_HEADER = "X-Signature-Timestamp"
IDEMPOTENCY_KEY_HEADER = "X-Idempotency-Key"

DEFAULT_TOLERANCE_SECONDS = 300

RawBody = Union[bytes, bytearray, str]


def verify_webhook_signature(
    secret: str,
    raw_body: RawBody,
    signature: Optional[str],
    timestamp: Optional[str],
    *,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    now: Optional[int] = None,
) -> bool:
    """Comprueba que una entrega a tu webhook viene de Extraer Datos de INE.

    ``raw_body`` es el cuerpo CRUDO, exactamente como llegó (no lo
    re-serialices). Rechaza firmas con más de ``tolerance_seconds`` de
    antigüedad (0 lo desactiva). Devuelve False, nunca lanza.
    """
    if not secret or not signature or not timestamp or not timestamp.isdigit():
        return False
    if tolerance_seconds > 0:
        current = int(time.time()) if now is None else now
        if abs(current - int(timestamp)) > tolerance_seconds:
            return False
    body = raw_body if isinstance(raw_body, (bytes, bytearray)) else raw_body.encode("utf-8")
    digest = hmac.new(
        secret.encode("utf-8"), timestamp.encode("ascii") + b"." + bytes(body), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest("sha256=" + digest, signature)


def parse_webhook(
    secret: str,
    raw_body: RawBody,
    signature: Optional[str],
    timestamp: Optional[str],
    *,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    now: Optional[int] = None,
) -> Dict[str, Any]:
    """Verifica la firma y devuelve el cuerpo interpretado.

    Lanza :class:`IneExtractorError` con ``INVALID_SIGNATURE`` si la firma no
    es válida.
    """
    if not verify_webhook_signature(
        secret, raw_body, signature, timestamp, tolerance_seconds=tolerance_seconds, now=now
    ):
        raise IneExtractorError("Firma de webhook inválida o vencida.", "INVALID_SIGNATURE")
    try:
        return json.loads(raw_body)
    except ValueError as exc:
        raise IneExtractorError("El cuerpo del webhook no es JSON.", "INVALID_INPUT") from exc
