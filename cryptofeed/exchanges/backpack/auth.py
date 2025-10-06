from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from nacl.signing import SigningKey

from cryptofeed.exchanges.backpack.config import BackpackConfig


class BackpackAuthError(RuntimeError):
    """Raised when Backpack authentication cannot be performed."""


class BackpackAuthHelper:
    """Utility for generating Backpack ED25519 authentication headers."""

    def __init__(self, config: BackpackConfig):
        if not config.enable_private_channels or config.auth is None:
            raise BackpackAuthError("Authentication not enabled in BackpackConfig")

        self._config = config
        self._auth = config.auth
        self._signer = SigningKey(self._auth.private_key_bytes)

    @staticmethod
    def _ensure_path(path: str) -> str:
        if not path.startswith('/'):
            return '/' + path
        return path

    @staticmethod
    def _canonical_method(method: str) -> str:
        return method.upper()

    @staticmethod
    def _canonical_body(body: Optional[str]) -> str:
        if body is None:
            return ''
        return body

    @staticmethod
    def _current_timestamp_us() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1_000_000)

    def sign_message(self, *, timestamp_us: int, method: str, path: str, body: str) -> str:
        payload = f"{timestamp_us}{self._canonical_method(method)}{self._ensure_path(path)}{self._canonical_body(body)}"
        signature = self._signer.sign(payload.encode('utf-8')).signature
        return b64encode(signature).decode('ascii')

    def build_headers(self, *, method: str, path: str, body: Optional[str] = None, timestamp_us: Optional[int] = None) -> dict[str, str]:
        ts = timestamp_us if timestamp_us is not None else self._current_timestamp_us()
        signature = self.sign_message(timestamp_us=ts, method=method, path=path, body=self._canonical_body(body))

        headers = {
            "X-Timestamp": str(ts),
            "X-Window": str(self._config.window_ms),
            "X-API-Key": self._auth.api_key,
            "X-Signature": signature,
        }
        if self._auth.passphrase:
            headers["X-Passphrase"] = self._auth.passphrase
        return headers
