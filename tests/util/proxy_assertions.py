"""Utilities for asserting proxy log output in tests."""
from __future__ import annotations

from typing import Iterable


def assert_no_credentials(messages: Iterable[str]) -> None:
    """Ensure proxy log snippets contain no credential substrings."""
    for message in messages:
        if message and any(token in message for token in ("@", "user:", "password")):
            raise AssertionError(f"Proxy log leaked credentials: {message}")


def extract_logged_endpoints(call_args_list) -> list[str]:
    """Pull sanitized endpoint values from logger call args."""
    endpoints: list[str] = []
    for call in call_args_list:
        args = getattr(call, "args", ())
        if not args:
            continue
        if args[0] == "proxy: transport=%s exchange=%s scheme=%s endpoint=%s" and len(args) >= 5:
            endpoints.append(args[4])
    return endpoints
