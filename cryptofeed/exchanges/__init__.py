'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.defines import *
from cryptofeed.defines import HTX as HTX_str
from cryptofeed.defines import OKX as OKX_str
from .phemex import Phemex
from .binance import Binance
from .binance_delivery import BinanceDelivery
from .binance_futures import BinanceFutures
from .binance_us import BinanceUS
from .bitfinex import Bitfinex
from .bitflyer import Bitflyer
from .bitget import Bitget
from .bithumb import Bithumb
from .bitstamp import Bitstamp
from .bybit import Bybit
from .coinbase import Coinbase
from .cryptodotcom import CryptoDotCom
from .deribit import Deribit
from .gateio import Gateio
from .gateio_futures import GateioFutures
from .gemini import Gemini
from .htx import HTX
from .htx_swap import HTXSwap
from .dydx import dYdX
from .hyperliquid import Hyperliquid
from .mexc import MEXCSpot
from .independent_reserve import IndependentReserve
from .kraken import Kraken
from .kraken_futures import KrakenFutures
from .kucoin import KuCoin
from .kucoin_futures import KuCoinFutures
from .okx import OKX
from .poloniex import Poloniex
from .upbit import Upbit

# Maps string name to class name for use with config
EXCHANGE_MAP = {
    BINANCE_DELIVERY: BinanceDelivery,
    BINANCE_FUTURES: BinanceFutures,
    BINANCE_US: BinanceUS,
    BINANCE: Binance,
    BITFINEX: Bitfinex,
    BITFLYER: Bitflyer,
    BITGET: Bitget,
    BITHUMB: Bithumb,
    BITSTAMP: Bitstamp,
    BYBIT: Bybit,
    COINBASE: Coinbase,
    CRYPTODOTCOM: CryptoDotCom,
    DERIBIT: Deribit,
    GATEIO: Gateio,
    GATEIO_FUTURES: GateioFutures,
    GEMINI: Gemini,
    HTX_SWAP: HTXSwap,
    HTX_str: HTX,
    DYDX: dYdX,
    HYPERLIQUID: Hyperliquid,
    MEXC: MEXCSpot,
    INDEPENDENT_RESERVE: IndependentReserve,
    KRAKEN_FUTURES: KrakenFutures,
    KRAKEN: Kraken,
    KUCOIN: KuCoin,
    KUCOIN_FUTURES: KuCoinFutures,
    OKX_str: OKX,
    PHEMEX: Phemex,
    POLONIEX: Poloniex,
    UPBIT: Upbit,
}
