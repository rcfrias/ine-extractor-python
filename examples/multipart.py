"""Extrae datos desde archivos locales (multipart).

Ejecuta:  INE_API_KEY=ine_xxx python examples/multipart.py ./frente.jpg ./reverso.jpg
"""

import os
import sys

from extraer_datos_ine import IneExtractorClient, IneExtractorError


def main() -> int:
    args = sys.argv[1:]
    front_path = args[0] if args else "frente.jpg"
    back_path = args[1] if len(args) > 1 else None

    client = IneExtractorClient(api_key=os.environ["INE_API_KEY"])

    with open(front_path, "rb") as f:
        front = f.read()
    back = None
    if back_path:
        with open(back_path, "rb") as f:
            back = f.read()

    try:
        result = client.extract(front=front, back=back)
    except IneExtractorError as err:
        print(f"[{err.code}] {err.message}", file=sys.stderr)
        if err.code == "INSUFFICIENT_TOKENS" and err.enroll_url:
            print("Recarga tokens en:", err.enroll_url, file=sys.stderr)
        return 1

    data = result.data
    print("CURP:", data.get("curp"))
    print("Clave de elector:", data.get("claveElector"))
    print("Nombre:", f"{data.get('nombre')} {data.get('apellidoPaterno')} {data.get('apellidoMaterno')}")
    print("Tokens restantes:", result.tokens_remaining)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
