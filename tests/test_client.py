"""Pruebas del cliente (sin red): se inyecta un `opener` falso."""

import io
import json
import unittest
import urllib.error

from extraer_datos_ine import IneExtractorClient, IneExtractorError


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._raw = json.dumps(body).encode("utf-8")

    def read(self):
        return self._raw

    def getcode(self):
        return self.status


def ok_opener(status, body):
    """Opener que registra la última petición y devuelve una respuesta OK."""
    calls = []

    def opener(req, timeout):
        calls.append(req)
        return FakeResponse(status, body)

    opener.calls = calls
    return opener


def http_error_opener(status, body):
    """Opener que lanza HTTPError (como urllib ante 4xx/5xx)."""

    def opener(req, timeout):
        fp = io.BytesIO(json.dumps(body).encode("utf-8"))
        raise urllib.error.HTTPError(req.full_url, status, "error", {}, fp)

    return opener


class ClientTests(unittest.TestCase):
    def test_requires_api_key(self):
        with self.assertRaises(IneExtractorError):
            IneExtractorClient("")

    def test_get_balance(self):
        opener = ok_opener(200, {"success": True, "balance": 42})
        client = IneExtractorClient("ine_test", opener=opener)
        self.assertEqual(client.get_balance(), 42)
        req = opener.calls[0]
        self.assertEqual(req.full_url, "https://extraerdatosdeine.com/api/v1/balance")
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(req.headers["X-api-key"], "ine_test")

    def test_extract_binary_multipart(self):
        opener = ok_opener(
            200,
            {
                "success": True,
                "extraction_id": "ext_123",
                "data": {"curp": "PEGJ850101HDFRRL09"},
                "tokens_remaining": 19,
                "upload_method": "multipart",
            },
        )
        client = IneExtractorClient("ine_test", opener=opener)
        result = client.extract(front=b"\xff\xd8\xff")
        self.assertEqual(result.extraction_id, "ext_123")
        self.assertEqual(result.tokens_remaining, 19)
        self.assertEqual(result.data["curp"], "PEGJ850101HDFRRL09")
        req = opener.calls[0]
        self.assertTrue(req.headers["Content-type"].startswith("multipart/form-data"))
        self.assertIn(b'name="image_front"', req.data)

    def test_extract_url_json(self):
        opener = ok_opener(
            200,
            {
                "success": True,
                "extraction_id": "ext_url",
                "data": {},
                "tokens_remaining": 5,
                "upload_method": "url",
            },
        )
        client = IneExtractorClient("ine_test", opener=opener)
        client.extract(
            front={"url": "https://cdn.example.com/f.jpg"},
            back={"url": "https://cdn.example.com/b.jpg"},
        )
        req = opener.calls[0]
        self.assertEqual(req.headers["Content-type"], "application/json")
        payload = json.loads(req.data)
        self.assertEqual(payload["image_front_url"], "https://cdn.example.com/f.jpg")
        self.assertEqual(payload["image_back_url"], "https://cdn.example.com/b.jpg")

    def test_insufficient_tokens_error(self):
        opener = http_error_opener(
            402,
            {
                "success": False,
                "error": "Saldo insuficiente",
                "code": "INSUFFICIENT_TOKENS",
                "enroll_url": "https://extraerdatosdeine.com/dashboard/tokens/enroll",
            },
        )
        client = IneExtractorClient("ine_test", opener=opener)
        with self.assertRaises(IneExtractorError) as ctx:
            client.extract(front=b"\x01\x02")
        err = ctx.exception
        self.assertEqual(err.code, "INSUFFICIENT_TOKENS")
        self.assertEqual(err.status, 402)
        self.assertEqual(err.enroll_url, "https://extraerdatosdeine.com/dashboard/tokens/enroll")

    def test_low_quality_error(self):
        opener = http_error_opener(
            422,
            {
                "success": False,
                "error": "Imagen de baja calidad",
                "code": "LOW_IMAGE_QUALITY",
                "extraction_id": "ext_lq",
                "missing_fields": ["curp", "claveElector"],
            },
        )
        client = IneExtractorClient("ine_test", opener=opener)
        with self.assertRaises(IneExtractorError) as ctx:
            client.extract(front=b"\x01")
        err = ctx.exception
        self.assertEqual(err.code, "LOW_IMAGE_QUALITY")
        self.assertEqual(err.extraction_id, "ext_lq")
        self.assertEqual(err.missing_fields, ["curp", "claveElector"])

    def test_mixed_sources_rejected_before_request(self):
        opener = ok_opener(200, {"success": True})
        client = IneExtractorClient("ine_test", opener=opener)
        with self.assertRaises(IneExtractorError) as ctx:
            client.extract(front=b"\x01", back={"url": "https://x/y.jpg"})
        self.assertEqual(ctx.exception.code, "INVALID_INPUT")
        self.assertEqual(len(opener.calls), 0)


if __name__ == "__main__":
    unittest.main()
