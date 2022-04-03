'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.defines import *
from cryptofeed.defines import FTX as FTX_str, EXX as EXX_str, FMFW as FMFW_str, OKX as OKX_str
from .bitdotcom import BitDotCom
from .phemex import Phemex
from .ascendex import AscendEX
from .bequant import Bequant
from .binance import Binance
from .binance_delivery import BinanceDelivery
from .binance_futures import BinanceFutures
from .binance_us import BinanceUS
from .fmfw import FMFW
from .bitfinex import Bitfinex
from .bitflyer import Bitflyer
from .bitget import Bitget
from .bithumb import Bithumb
from .bitmex import Bitmex
from .bitstamp import Bitstamp
from .bittrex import Bittrex
from .blockchain import Blockchain
from .bybit import Bybit
from .coinbase import Coinbase
from .cryptodotcom import CryptoDotCom
from .delta import Delta
from .deribit import Deribit
from .dydx import dYdX
from .exx import EXX
from .ftx import FTX
from .ftx_us import FTXUS
from .gateio import Gateio
from .gemini import Gemini
from .hitbtc import HitBTC
from .huobi import Huobi
from .huobi_dm import HuobiDM
from .huobi_swap import HuobiSwap
from .independent_reserve import IndependentReserve
from .kraken import Kraken
from .kraken_futures import KrakenFutures
from .kucoin import KuCoin
from .okcoin import OKCoin
from .okx import OKX
from .poloniex import Poloniex
from .probit import Probit
from .upbit import Upbit

# Maps string name to class name for use with config
EXCHANGE_MAP = {
    ASCENDEX: AscendEX,
    BEQUANT: Bequant,
    BINANCE_DELIVERY: BinanceDelivery,
    BINANCE_FUTURES: BinanceFutures,
    BINANCE_US: BinanceUS,
    BINANCE: Binance,
    FMFW_str: FMFW,
    BITDOTCOM: BitDotCom,
    BITFINEX: Bitfinex,
    BITFLYER: Bitflyer,
    BITGET: Bitget,
    BITHUMB: Bithumb,
    BITMEX: Bitmex,
    BITSTAMP: Bitstamp,
    BITTREX: Bittrex,
    BLOCKCHAIN: Blockchain,
    BYBIT: Bybit,
    COINBASE: Coinbase,
    CRYPTODOTCOM: CryptoDotCom,
    DERIBIT: Deribit,
    DELTA: Delta,
    DYDX: dYdX,
    EXX_str: EXX,
    FTX_str: FTX,
    FTX_US: FTXUS,
    GATEIO: Gateio,
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
