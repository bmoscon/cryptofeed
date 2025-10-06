from __future__ import annotations

import base64

from tools.backpack_auth_check import build_signature, normalize_key


def test_normalize_hex_key():
    raw = bytes(range(32))
    key = normalize_key("".join(f"{b:02x}" for b in raw))
    assert key == raw


def test_build_signature_deterministic():
    raw = bytes(range(32))
    signature = build_signature(
        raw,
        method="GET",
        path="/api/v1/orders",
        body="",
        timestamp_us=1_700_000_000_123_456,
    )
    assert isinstance(signature, str)
    assert len(base64.b64decode(signature)) == 64
