"""Pruebas de la verificación de firmas de webhook."""

import hashlib
import hmac
import json
import unittest

from extraer_datos_ine import (
    IneExtractorError,
    SIGNATURE_HEADER,
    parse_webhook,
    verify_webhook_signature,
)

SECRET = "whsec_test"
NOW = 1_790_000_000
BODY = json.dumps(
    {
        "version": "1",
        "event": "extraction.completed",
        "idempotencyKey": "k1",
        "documentType": "ine",
        "source": "capture-link",
        "captureLinkId": "cl_1",
        "reference": "Hab 204",
        "extractedAt": "2026-09-30T12:00:00.000Z",
        "data": {"curp": "PEGJ850101HDFRRL09"},
    }
)


def sign(body, ts, secret=SECRET):
    raw = body.encode("utf-8") if isinstance(body, str) else body
    return "sha256=" + hmac.new(secret.encode(), str(ts).encode() + b"." + raw, hashlib.sha256).hexdigest()


class WebhookTests(unittest.TestCase):
    def test_header_name(self):
        self.assertEqual(SIGNATURE_HEADER, "X-Signature")

    def test_round_trip_str_and_bytes(self):
        sig = sign(BODY, NOW)
        self.assertTrue(verify_webhook_signature(SECRET, BODY, sig, str(NOW), now=NOW))
        self.assertTrue(verify_webhook_signature(SECRET, BODY.encode(), sig, str(NOW), now=NOW))
        event = parse_webhook(SECRET, BODY, sig, str(NOW), now=NOW)
        self.assertEqual(event["event"], "extraction.completed")
        self.assertEqual(event["reference"], "Hab 204")

    def test_stale_timestamp_rejected(self):
        sig = sign(BODY, NOW)
        self.assertFalse(verify_webhook_signature(SECRET, BODY, sig, str(NOW), now=NOW + 301))
        self.assertTrue(verify_webhook_signature(SECRET, BODY, sig, str(NOW), now=NOW + 300))
        self.assertTrue(
            verify_webhook_signature(SECRET, BODY, sig, str(NOW), now=NOW + 10_000, tolerance_seconds=0)
        )

    def test_tampered_body_or_wrong_secret_rejected(self):
        sig = sign(BODY, NOW)
        self.assertFalse(verify_webhook_signature(SECRET, BODY.replace("204", "205"), sig, str(NOW), now=NOW))
        self.assertFalse(verify_webhook_signature("otro", BODY, sig, str(NOW), now=NOW))
        self.assertFalse(verify_webhook_signature(SECRET, BODY, sig, str(NOW + 1), now=NOW))

    def test_missing_or_malformed_inputs_rejected(self):
        sig = sign(BODY, NOW)
        self.assertFalse(verify_webhook_signature(SECRET, BODY, None, str(NOW), now=NOW))
        self.assertFalse(verify_webhook_signature(SECRET, BODY, sig, None, now=NOW))
        self.assertFalse(verify_webhook_signature(SECRET, BODY, sig, "abc", now=NOW))
        self.assertFalse(verify_webhook_signature("", BODY, sig, str(NOW), now=NOW))

    def test_parse_webhook_raises_invalid_signature(self):
        with self.assertRaises(IneExtractorError) as ctx:
            parse_webhook(SECRET, BODY, "sha256=00", str(NOW), now=NOW)
        self.assertEqual(ctx.exception.code, "INVALID_SIGNATURE")


if __name__ == "__main__":
    unittest.main()
