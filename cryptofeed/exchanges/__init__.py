'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.defines import *
from cryptofeed.defines import EXX as EXX_str, FMFW as FMFW_str, OKX as OKX_str
from .bitdotcom import BitDotCom
from .phemex import Phemex
from .ascendex import AscendEX
from .ascendex_futures import AscendEXFutures
from .bequant import Bequant
from .binance import Binance
from .binance_delivery import BinanceDelivery
from .binance_futures import BinanceFutures
from .binance_us import BinanceUS
from .binance_tr import BinanceTR
from .fmfw import FMFW
from .bitfinex import Bitfinex
from .bitflyer import Bitflyer
from .bitget import Bitget
from .bithumb import Bithumb
from .bitmex import Bitmex
from .bitstamp import Bitstamp
from .blockchain import Blockchain
from .bybit import Bybit
from .coinbase import Coinbase
from .cryptodotcom import CryptoDotCom
from .delta import Delta
from .deribit import Deribit
from .dydx import dYdX
from .exx import EXX
from .gateio import Gateio
from .gateio_futures import GateioFutures
from .gemini import Gemini
from .hitbtc import HitBTC
from .huobi import Huobi
from .huobi_dm import HuobiDM
from .huobi_swap import HuobiSwap
from .independent_reserve import IndependentReserve
from .kraken import Kraken
from .kraken_futures import KrakenFutures
from .kucoin import KuCoin
from .okx import OKX
from .okcoin import OKCoin
from .poloniex import Poloniex
from .probit import Probit
from .upbit import Upbit

# Maps string name to class name for use with config
EXCHANGE_MAP = {
    ASCENDEX: AscendEX,
    ASCENDEX_FUTURES: AscendEXFutures,
    BEQUANT: Bequant,
    BINANCE_DELIVERY: BinanceDelivery,
    BINANCE_FUTURES: BinanceFutures,
    BINANCE_US: BinanceUS,
    BINANCE_TR: BinanceTR,
    BINANCE: Binance,
    FMFW_str: FMFW,
    BITDOTCOM: BitDotCom,
    BITFINEX: Bitfinex,
    BITFLYER: Bitflyer,
    BITGET: Bitget,
    BITHUMB: Bithumb,
    BITMEX: Bitmex,
    BITSTAMP: Bitstamp,
    BLOCKCHAIN: Blockchain,
    BYBIT: Bybit,
    COINBASE: Coinbase,
    CRYPTODOTCOM: CryptoDotCom,
    DERIBIT: Deribit,
    DELTA: Delta,
    DYDX: dYdX,
    EXX_str: EXX,
    GATEIO: Gateio,
    GATEIO_FUTURES: GateioFutures,
    GEMINI: Gemini,
    HITBTC: HitBTC,
    HUOBI_DM: HuobiDM,
    HUOBI_SWAP: HuobiSwap,
    HUOBI: Huobi,
    INDEPENDENT_RESERVE: IndependentReserve,
    KRAKEN_FUTURES: KrakenFutures,
    KRAKEN: Kraken,
    KUCOIN: KuCoin,
    OKCOIN: OKCoin,
    OKX_str: OKX,
    PHEMEX: Phemex,
    POLONIEX: Poloniex,
    PROBIT: Probit,
    UPBIT: Upbit,
}
