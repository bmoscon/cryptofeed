"""Extension registry helper for CCXT configuration."""
from __future__ import annotations

import logging
from copy import deepcopy
from typing import Callable, Dict


LOG = logging.getLogger("feedhandler")


class CcxtConfigExtensions:
    """Registry for exchange-specific configuration hooks."""

    _hooks: Dict[str, Callable[[Dict[str, object]], Dict[str, object]]] = {}

    @classmethod
    def register(
        cls, exchange_id: str, hook: Callable[[Dict[str, object]], Dict[str, object]]
    ) -> None:
        """Register hook to mutate raw configuration prior to validation."""

        cls._hooks[exchange_id] = hook

    @classmethod
    def decorator(
        cls, exchange_id: str
    ) -> Callable[[Callable[[Dict[str, object]], Dict[str, object]]], Callable[[Dict[str, object]], Dict[str, object]]]:
        """Decorator helper for registering config extension hooks."""

        def wrapper(func: Callable[[Dict[str, object]], Dict[str, object]]) -> Callable[[Dict[str, object]], Dict[str, object]]:
            cls.register(exchange_id, func)
            return func

        return wrapper

    @classmethod
    def apply(cls, exchange_id: str, data: Dict[str, object]) -> Dict[str, object]:
        hook = cls._hooks.get(exchange_id)
        if hook is None:
            return data
        try:
            working = deepcopy(data)
            updated = hook(working)
        except Exception as exc:  # pragma: no cover - defensive logging
            LOG.error("Failed applying CCXT config extension for %s: %s", exchange_id, exc)
            raise
        if updated is None:
            return working
        if isinstance(updated, dict):
            return updated
        return data

    @classmethod
    def reset(cls) -> None:
        cls._hooks.clear()


__all__ = ["CcxtConfigExtensions"]
