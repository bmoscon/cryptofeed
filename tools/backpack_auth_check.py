"""CLI helper for validating Backpack ED25519 credentials."""
from __future__ import annotations

import argparse
import base64
import sys

from nacl.signing import SigningKey


def normalize_key(value: str) -> bytes:
    value = value.strip()
    try:
        raw = bytes.fromhex(value)
        if len(raw) == 32:
            return raw
    except ValueError:
        pass

    raw = base64.b64decode(value, validate=True)
    if len(raw) != 32:
        raise ValueError("Backpack keys must be 32 bytes")
    return raw


def build_signature(private_key: bytes, *, method: str, path: str, body: str, timestamp_us: int) -> str:
    signer = SigningKey(private_key)
    payload = f"{timestamp_us}{method.upper()}{path if path.startswith('/') else '/' + path}{body}".encode("utf-8")
    return base64.b64encode(signer.sign(payload).signature).decode("ascii")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Backpack ED25519 credentials and preview a signature.")
    parser.add_argument("--api-key", dest="api_key", required=True)
    parser.add_argument("--public-key", dest="public_key", required=True)
    parser.add_argument("--private-key", dest="private_key", required=True)
    parser.add_argument("--method", default="GET")
    parser.add_argument("--path", default="/api/v1/orders")
    parser.add_argument("--body", default="")
    parser.add_argument("--timestamp", type=int, default=1_700_000_000_000_000)

    args = parser.parse_args(argv)

    try:
        private_key = normalize_key(args.private_key)
        public_key = normalize_key(args.public_key)
    except ValueError as exc:  # pragma: no cover - defensive CLI usage
        parser.error(str(exc))

    signature = build_signature(
        private_key,
        method=args.method,
        path=args.path,
        body=args.body,
        timestamp_us=args.timestamp,
    )

    print("Backpack credential check")
    print(f"API key: {args.api_key}")
    print(f"Public key (base64): {base64.b64encode(public_key).decode('ascii')}")
    print(f"Private key (base64): {base64.b64encode(private_key).decode('ascii')}")
    print(f"Sample signature: {signature}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
