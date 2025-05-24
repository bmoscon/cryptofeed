from typing import Dict, List, Optional, Union, Any, Tuple
from decimal import Decimal

class Trade:
    exchange: str
    symbol: str
    price: Decimal
    amount: Decimal
    side: str
    id: Optional[str]
    type: Optional[str]
    timestamp: float
    raw: Optional[Union[Dict[str, Any], List[Any]]]

    def __init__(
        self,
        exchange: str,
        symbol: str,
        side: str,
        amount: Decimal,
        price: Decimal,
        timestamp: float,
        id: Optional[str] = None,
        type: Optional[str] = None,
        raw: Optional[Union[Dict[str, Any], List[Any]]] = None,
    ) -> None: ...
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Trade": ...
    def to_dict(
        self, numeric_type: Optional[type] = None, none_to: bool = False
    ) -> Dict[str, Any]: ...

class Ticker:
    exchange: str
    symbol: str
    bid: Decimal
    ask: Decimal
    timestamp: Optional[float]
    raw: Optional[Any]

    def __init__(
        self,
        exchange: str,
        symbol: str,
        bid: Decimal,
        ask: Decimal,
        timestamp: Optional[float],
        raw: Optional[Any] = None,
    ) -> None: ...
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Ticker": ...
    def to_dict(
        self, numeric_type: Optional[type] = None, none_to: bool = False
    ) -> Dict[str, Any]: ...

class OrderBook:
    exchange: str
    symbol: str
    book: Any  # _OrderBook
    delta: Optional[Dict[str, List[Tuple[Decimal, Decimal]]]]
    sequence_number: Optional[int]
    checksum: Optional[Union[str, int]]
    timestamp: Optional[float]
    raw: Optional[Union[Dict[str, Any], List[Any]]]

    def __init__(
        self,
        exchange: str,
        symbol: str,
        bids: Optional[List[Tuple[Decimal, Decimal]]] = None,
        asks: Optional[List[Tuple[Decimal, Decimal]]] = None,
        max_depth: int = 0,
        truncate: bool = False,
        checksum_format: Optional[str] = None,
    ) -> None: ...
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "OrderBook": ...
    def _delta(self, numeric_type: type) -> Dict[str, List[Tuple[Any, Any]]]: ...
    def to_dict(
        self,
        delta: bool = False,
        numeric_type: Optional[type] = None,
        none_to: bool = False,
    ) -> Dict[str, Any]: ...

class Liquidation:
    exchange: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    id: str
    status: str
    timestamp: Optional[float]
    raw: Optional[Dict[str, Any]]

    def __init__(
        self,
        exchange: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        id: str,
        status: str,
        timestamp: Optional[float],
        raw: Optional[Dict[str, Any]] = None,
    ) -> None: ...
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Liquidation": ...
    def to_dict(
        self, numeric_type: Optional[type] = None, none_to: bool = False
    ) -> Dict[str, Any]: ...

class Funding:
    exchange: str
    symbol: str
    mark_price: Optional[Decimal]
    rate: Optional[Decimal]
    next_funding_time: Optional[float]
    predicted_rate: Optional[Decimal]
    timestamp: float
    raw: Optional[Any]

    def __init__(
        self,
        exchange: str,
        symbol: str,
        mark_price: Optional[Decimal],
        rate: Optional[Decimal],
        next_funding_time: Optional[float],
        timestamp: float,
        predicted_rate: Optional[Decimal] = None,
        raw: Optional[Any] = None,
    ) -> None: ...
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Funding": ...
    def to_dict(
        self, numeric_type: Optional[type] = None, none_to: bool = False
    ) -> Dict[str, Any]: ...

class Candle:
    exchange: str
    symbol: str
    start: float
    stop: float
    interval: str
    trades: Optional[int]
    open: Decimal
    close: Decimal
    high: Decimal
    low: Decimal
    volume: Decimal
    closed: bool
    timestamp: Optional[float]
    raw: Optional[Union[Dict[str, Any], List[Any]]]

    def __init__(
        self,
        exchange: str,
        symbol: str,
        start: float,
        stop: float,
        interval: str,
        trades: Optional[int],
        open: Decimal,
        close: Decimal,
        high: Decimal,
        low: Decimal,
        volume: Decimal,
        closed: bool,
        timestamp: Optional[float],
        raw: Optional[Union[Dict[str, Any], List[Any]]] = None,
    ) -> None: ...
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Candle": ...
    def to_dict(
        self, numeric_type: Optional[type] = None, none_to: bool = False
    ) -> Dict[str, Any]: ...

class Index:
    exchange: str
    symbol: str
    price: Decimal
    timestamp: float
    raw: Optional[Dict[str, Any]]

    def __init__(
        self,
        exchange: str,
        symbol: str,
        price: Decimal,
        timestamp: float,
        raw: Optional[Dict[str, Any]] = None,
    ) -> None: ...
    def to_dict(
        self, numeric_type: Optional[type] = None, none_to: bool = False
    ) -> Dict[str, Any]: ...

class OpenInterest:
    exchange: str
    symbol: str
    open_interest: Decimal
    timestamp: Optional[float]
    raw: Optional[Dict[str, Any]]

    def __init__(
        self,
        exchange: str,
        symbol: str,
        open_interest: Decimal,
        timestamp: Optional[float],
        raw: Optional[Dict[str, Any]] = None,
    ) -> None: ...
    def to_dict(
        self, numeric_type: Optional[type] = None, none_to: bool = False
    ) -> Dict[str, Any]: ...

class Order:
    exchange: Optional[str]
    symbol: str
    client_order_id: str
    side: str
    type: str
    price: Decimal
    amount: Decimal
    account: Optional[str]
    timestamp: Optional[float]

    def __init__(
        self,
        symbol: str,
        client_order_id: str,
        side: str,
        type: str,
        price: Decimal,
        amount: Decimal,
        timestamp: Optional[float],
        account: Optional[str] = None,
        exchange: Optional[str] = None,
    ) -> None: ...
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Order": ...
    def to_dict(
        self, numeric_type: Optional[type] = None, none_to: bool = False
    ) -> Dict[str, Any]: ...

class OrderInfo:
    exchange: str
    symbol: str
    id: str
    client_order_id: Optional[str]
    side: str
    status: str
    type: str
    price: Decimal
    amount: Decimal
    remaining: Optional[Decimal]
    account: Optional[str]
    timestamp: Optional[float]
    raw: Optional[Union[Dict[str, Any], List[Any]]]

    def __init__(
        self,
        exchange: str,
        symbol: str,
        id: str,
        side: str,
        status: str,
        type: str,
        price: Decimal,
        amount: Decimal,
        remaining: Optional[Decimal],
        timestamp: Optional[float],
        client_order_id: Optional[str] = None,
        account: Optional[str] = None,
        raw: Optional[Union[Dict[str, Any], List[Any]]] = None,
    ) -> None: ...
    def set_status(self, status: str) -> None: ...
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "OrderInfo": ...
    def to_dict(
        self, numeric_type: Optional[type] = None, none_to: bool = False
    ) -> Dict[str, Any]: ...

class Balance:
    exchange: str
    currency: str
    balance: Decimal
    reserved: Optional[Decimal]
    raw: Optional[Dict[str, Any]]

    def __init__(
        self,
        exchange: str,
        currency: str,
        balance: Decimal,
        reserved: Optional[Decimal],
        raw: Optional[Dict[str, Any]] = None,
    ) -> None: ...
    def to_dict(
        self, numeric_type: Optional[type] = None, none_to: bool = False
    ) -> Dict[str, Any]: ...

class L1Book:
    exchange: str
    symbol: str
    bid_price: Decimal
    bid_size: Decimal
    ask_price: Decimal
    ask_size: Decimal
    timestamp: float
    raw: Optional[Dict[str, Any]]

    def __init__(
        self,
        exchange: str,
        symbol: str,
        bid_price: Decimal,
        bid_size: Decimal,
        ask_price: Decimal,
        ask_size: Decimal,
        timestamp: float,
        raw: Optional[Dict[str, Any]] = None,
    ) -> None: ...
    def to_dict(
        self, numeric_type: Optional[type] = None, none_to: bool = False
    ) -> Dict[str, Any]: ...

class Transaction:
    exchange: str
    currency: str
    type: str
    status: str
    amount: Decimal
    timestamp: float
    raw: Optional[Dict[str, Any]]

    def __init__(
        self,
        exchange: str,
        currency: str,
        type: str,
        status: str,
        amount: Decimal,
        timestamp: float,
        raw: Optional[Dict[str, Any]] = None,
    ) -> None: ...
    def to_dict(
        self, numeric_type: Optional[type] = None, none_to: bool = False
    ) -> Dict[str, Any]: ...

class Fill:
    exchange: str
    symbol: str
    price: Decimal
    amount: Decimal
    side: str
    fee: Optional[Decimal]
    id: str
    order_id: str
    liquidity: str
    type: str
    account: Optional[str]
    timestamp: float
    raw: Optional[Union[Dict[str, Any], List[Any]]]

    def __init__(
        self,
        exchange: str,
        symbol: str,
        side: str,
        amount: Decimal,
        price: Decimal,
        fee: Optional[Decimal],
        id: str,
        order_id: str,
        type: str,
        liquidity: str,
        timestamp: float,
        account: Optional[str] = None,
        raw: Optional[Union[Dict[str, Any], List[Any]]] = None,
    ) -> None: ...
    def to_dict(
        self, numeric_type: Optional[type] = None, none_to: bool = False
    ) -> Dict[str, Any]: ...

class Position:
    exchange: str
    symbol: str
    position: Decimal
    entry_price: Decimal
    side: str
    unrealised_pnl: Optional[Decimal]
    timestamp: Optional[float]
    raw: Optional[Union[Dict[str, Any], List[Any]]]

    def __init__(
        self,
        exchange: str,
        symbol: str,
        position: Decimal,
        entry_price: Decimal,
        side: str,
        unrealised_pnl: Optional[Decimal],
        timestamp: Optional[float],
        raw: Optional[Union[Dict[str, Any], List[Any]]] = None,
    ) -> None: ...
    def to_dict(
        self, numeric_type: Optional[type] = None, none_to: bool = False
    ) -> Dict[str, Any]: ...
