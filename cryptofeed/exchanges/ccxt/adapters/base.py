"""Base adapter classes and common utilities for CCXT conversions."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Dict, Optional

from cryptofeed.types import OrderBook, Trade

from .hooks import AdapterHookRegistry, apply_orderbook_hooks, apply_trade_hooks


LOG = logging.getLogger("feedhandler")


class AdapterValidationError(Exception):
    """Raised when adapter validation fails."""


class BaseTradeAdapter(ABC):
    """Base adapter for trade conversion with extension points."""

    def __init__(self, exchange: str = "ccxt") -> None:
        self.exchange = exchange

    def _apply_trade_hooks(self, raw_trade: Dict[str, Any]) -> Dict[str, Any]:
        return apply_trade_hooks(self.exchange, raw_trade)

    @abstractmethod
    def convert_trade(self, raw_trade: Dict[str, Any]) -> Optional[Trade]:
        """Convert raw trade data to a cryptofeed Trade object."""

    def validate_trade(self, raw_trade: Dict[str, Any]) -> bool:
        required = ["symbol", "side", "amount", "price", "timestamp", "id"]
        for field in required:
            if field not in raw_trade:
                LOG.warning(
                    "R3 trade validation failed for %s: missing %s",
                    self.exchange,
                    field,
                )
                raise AdapterValidationError(f"Missing required field: {field}")
        return True

    def normalize_timestamp(
        self, raw_timestamp: Any, payload: Optional[Dict[str, Any]] = None
    ) -> float:
        if isinstance(raw_timestamp, (int, float)):
            value = float(raw_timestamp)
            if raw_timestamp > 1e10:  # milliseconds
                value = value / 1000.0
        elif isinstance(raw_timestamp, str):
            value = float(raw_timestamp)
        else:
            raise AdapterValidationError(f"Invalid timestamp format: {raw_timestamp}")

        hook = AdapterHookRegistry.trade_normalizer(self.exchange, "timestamp")
        if hook is not None:
            try:
                override = hook(value, raw_timestamp, payload or {})
                if override is not None:
                    value = float(override)
            except Exception as exc:  # pragma: no cover - defensive guard
                LOG.warning(
                    "R3 trade timestamp hook failed for %s: %s", self.exchange, exc
                )
        return value

    def normalize_symbol(
        self, raw_symbol: str, payload: Optional[Dict[str, Any]] = None
    ) -> str:
        normalized = raw_symbol.replace("/", "-")
        hook = AdapterHookRegistry.trade_normalizer(self.exchange, "symbol")
        if hook is not None:
            try:
                override = hook(normalized, raw_symbol, payload or {})
                if override is not None:
                    normalized = str(override)
            except Exception as exc:  # pragma: no cover - defensive guard
                LOG.warning(
                    "R3 trade symbol hook failed for %s: %s", self.exchange, exc
                )
        return normalized

    def normalize_price(
        self, raw_price: Any, payload: Optional[Dict[str, Any]] = None
    ) -> Decimal:
        price_value = Decimal(str(raw_price))
        hook = AdapterHookRegistry.trade_normalizer(self.exchange, "price")
        if hook is not None:
            try:
                override = hook(price_value, raw_price, payload or {})
                if override is not None:
                    price_value = (
                        override
                        if isinstance(override, Decimal)
                        else Decimal(str(override))
                    )
            except Exception as exc:  # pragma: no cover - defensive guard
                LOG.warning(
                    "R3 trade price hook failed for %s: %s", self.exchange, exc
                )
        return price_value


class BaseOrderBookAdapter(ABC):
    """Base adapter for order book conversion with extension points."""

    def __init__(self, exchange: str = "ccxt") -> None:
        self.exchange = exchange

    def _apply_orderbook_hooks(self, raw_orderbook: Dict[str, Any]) -> Dict[str, Any]:
        return apply_orderbook_hooks(self.exchange, raw_orderbook)

    @abstractmethod
    def convert_orderbook(self, raw_orderbook: Dict[str, Any]) -> Optional[OrderBook]:
        """Convert raw book data to a cryptofeed OrderBook object."""

    def validate_orderbook(self, raw_orderbook: Dict[str, Any]) -> bool:
        required = ["symbol", "bids", "asks"]
        for field in required:
            if field not in raw_orderbook:
                LOG.warning(
                    "R3 order book validation failed for %s: missing %s",
                    self.exchange,
                    field,
                )
                raise AdapterValidationError(f"Missing required field: {field}")

        if not isinstance(raw_orderbook["bids"], list):
            LOG.warning("R3 order book invalid bids payload for %s", self.exchange)
            raise AdapterValidationError("Bids must be a list")
        if not isinstance(raw_orderbook["asks"], list):
            LOG.warning("R3 order book invalid asks payload for %s", self.exchange)
            raise AdapterValidationError("Asks must be a list")
        return True

    def normalize_prices(
        self,
        price_levels: list,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[Decimal, Decimal]:
        normalized: Dict[Decimal, Decimal] = {}
        for price, size in price_levels:
            normalized[Decimal(str(price))] = Decimal(str(size))

        hook = AdapterHookRegistry.orderbook_normalizer(self.exchange, "price_levels")
        if hook is not None:
            try:
                override = hook(normalized, price_levels, payload or {})
                if override is not None:
                    normalized = override
            except Exception as exc:  # pragma: no cover - defensive guard
                LOG.warning(
                    "R3 order book price hook failed for %s: %s", self.exchange, exc
                )
        return normalized

    def normalize_symbol(
        self, raw_symbol: str, payload: Optional[Dict[str, Any]] = None
    ) -> str:
        normalized = raw_symbol.replace("/", "-")
        hook = AdapterHookRegistry.orderbook_normalizer(self.exchange, "symbol")
        if hook is not None:
            try:
                override = hook(normalized, raw_symbol, payload or {})
                if override is not None:
                    normalized = str(override)
            except Exception as exc:  # pragma: no cover - defensive guard
                LOG.warning(
                    "R3 order book symbol hook failed for %s: %s",
                    self.exchange,
                    exc,
                )
        return normalized

    def normalize_timestamp(
        self, raw_timestamp: Any, payload: Optional[Dict[str, Any]] = None
    ) -> Optional[float]:
        if raw_timestamp is None:
            value: Optional[float] = None
        elif isinstance(raw_timestamp, (int, float)):
            value = float(raw_timestamp)
            if raw_timestamp > 1e10:
                value = value / 1000.0
        elif isinstance(raw_timestamp, str):
            value = float(raw_timestamp)
        else:
            raise AdapterValidationError(f"Invalid timestamp format: {raw_timestamp}")

        hook = AdapterHookRegistry.orderbook_normalizer(self.exchange, "timestamp")
        if hook is not None and value is not None:
            try:
                override = hook(value, raw_timestamp, payload or {})
                if override is not None:
                    value = float(override)
            except Exception as exc:  # pragma: no cover - defensive guard
                LOG.warning(
                    "R3 order book timestamp hook failed for %s: %s",
                    self.exchange,
                    exc,
                )
        return value
