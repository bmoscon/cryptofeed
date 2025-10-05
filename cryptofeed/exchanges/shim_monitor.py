"""Utilities for tracking compatibility shim usage during migration."""
from __future__ import annotations

import logging
from threading import RLock
from typing import Dict


LOG = logging.getLogger("feedhandler")
_usage: Dict[str, int] = {}
_lock = RLock()


def record_shim_use(*, shim: str, canonical: str) -> None:
    """Record that a compatibility shim module has been imported."""

    with _lock:
        _usage[shim] = _usage.get(shim, 0) + 1

    LOG.warning(
        "compat shim import detected: %s -> %s (spec ccxt-generic-pro-exchange/7.4)",
        shim,
        canonical,
    )


def get_shim_usage() -> Dict[str, int]:
    """Return a snapshot of shim usage counters."""

    with _lock:
        return dict(_usage)


def reset_shim_usage() -> None:
    """Clear recorded shim usage (primarily for tests)."""

    with _lock:
        _usage.clear()


__all__ = ["record_shim_use", "get_shim_usage", "reset_shim_usage"]

