"""Reusable authentication helpers for native exchanges."""
from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from nacl.signing import SigningKey


class NativeAuthError(RuntimeError):
    """Raised when native exchange authentication cannot be completed."""


@dataclass(frozen=True)
class Ed25519Credentials:
    """Container holding ED25519 API credentials."""

    api_key: str
    private_key: bytes
    passphrase: Optional[str] = None


class Ed25519AuthHelper:
    """Generic ED25519 signing helper with customizable header mapping."""

    DEFAULT_HEADERS: Dict[str, str] = {
        "timestamp": "X-Timestamp",
        "window": "X-Window",
        "api_key": "X-API-Key",
        "signature": "X-Signature",
        "passphrase": "X-Passphrase",
    }

    def __init__(
        self,
        *,
        credentials: Ed25519Credentials,
        window_ms: int = 5000,
        header_names: Optional[Dict[str, str]] = None,
    ) -> None:
        if not credentials.api_key:
            raise NativeAuthError("API key is required for ED25519 authentication")
        if not credentials.private_key:
            raise NativeAuthError("Private key is required for ED25519 authentication")

        self._credentials = credentials
        self._signer = SigningKey(credentials.private_key)
        self._window_ms = window_ms
        self._headers = dict(self.DEFAULT_HEADERS)
        if header_names:
            self._headers.update(header_names)

    @staticmethod
    def _ensure_path(path: str) -> str:
        return path if path.startswith('/') else '/' + path

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

    def sign_message(
        self,
        *,
        timestamp_us: int,
        method: str,
        path: str,
        body: str,
    ) -> str:
        payload = (
            f"{timestamp_us}{self._canonical_method(method)}"
            f"{self._ensure_path(path)}{body}"
        )
        signature = self._signer.sign(payload.encode('utf-8')).signature
        return b64encode(signature).decode('ascii')

    def build_headers(
        self,
        *,
        method: str,
        path: str,
        body: Optional[str] = None,
        timestamp_us: Optional[int] = None,
    ) -> Dict[str, str]:
        ts = timestamp_us if timestamp_us is not None else self._current_timestamp_us()
        canonical_body = self._canonical_body(body)
        signature = self.sign_message(
            timestamp_us=ts,
            method=method,
            path=path,
            body=canonical_body,
        )

        headers: Dict[str, str] = {
            self._headers["timestamp"]: str(ts),
            self._headers["window"]: str(self._window_ms),
            self._headers["api_key"]: self._credentials.api_key,
            self._headers["signature"]: signature,
        }
        if self._credentials.passphrase:
            headers[self._headers["passphrase"]] = self._credentials.passphrase
        return headers

    @property
    def window_ms(self) -> int:
        return self._window_ms
