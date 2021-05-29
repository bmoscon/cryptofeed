'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.exchange.kucoin import KuCoin
from cryptofeed.defines import *
from cryptofeed.defines import FTX as FTX_str, EXX as EXX_str
from cryptofeed.provider.coingecko import Coingecko
from cryptofeed.exchange.binance import Binance
from cryptofeed.exchange.binance_futures import BinanceFutures
from cryptofeed.exchange.binance_delivery import BinanceDelivery
from cryptofeed.exchange.binance_us import BinanceUS
from cryptofeed.exchange.bitcoincom import BitcoinCom
from cryptofeed.exchange.bitfinex import Bitfinex
from cryptofeed.exchange.bitflyer import Bitflyer
from cryptofeed.exchange.bitmax import Bitmax
from cryptofeed.exchange.bitmex import Bitmex
from cryptofeed.exchange.bitstamp import Bitstamp
from cryptofeed.exchange.bittrex import Bittrex
from cryptofeed.exchange.blockchain import Blockchain
from cryptofeed.exchange.bybit import Bybit
from cryptofeed.exchange.coinbase import Coinbase
from cryptofeed.exchange.deribit import Deribit
from cryptofeed.exchange.exx import EXX
from cryptofeed.exchange.ftx import FTX
from cryptofeed.exchange.ftx_us import FTXUS
from cryptofeed.exchange.gateio import Gateio
from cryptofeed.exchange.gemini import Gemini
from cryptofeed.exchange.hitbtc import HitBTC
from cryptofeed.exchange.huobi import Huobi
from cryptofeed.exchange.huobi_dm import HuobiDM
from cryptofeed.exchange.huobi_swap import HuobiSwap
from cryptofeed.exchange.kraken import Kraken
from cryptofeed.exchange.kraken_futures import KrakenFutures
from cryptofeed.exchange.okcoin import OKCoin
from cryptofeed.exchange.okex import OKEx
from cryptofeed.exchange.poloniex import Poloniex
from cryptofeed.exchange.probit import Probit
from cryptofeed.exchange.upbit import Upbit

# Maps string name to class name for use with config
EXCHANGE_MAP = {
    BINANCE: Binance,
    BINANCE_US: BinanceUS,
    BINANCE_FUTURES: BinanceFutures,
    BINANCE_DELIVERY: BinanceDelivery,
    BITCOINCOM: BitcoinCom,
    BITFINEX: Bitfinex,
    BITFLYER: Bitflyer,
    BITMAX: Bitmax,
    BITMEX: Bitmex,
    BITSTAMP: Bitstamp,
    BITTREX: Bittrex,
    BLOCKCHAIN: Blockchain,
    BYBIT: Bybit,
    COINBASE: Coinbase,
    COINGECKO: Coingecko,
    DERIBIT: Deribit,
    EXX_str: EXX,
    FTX_str: FTX,
    FTX_US: FTXUS,
    GEMINI: Gemini,
    HITBTC: HitBTC,
    HUOBI_DM: HuobiDM,
    HUOBI_SWAP: HuobiSwap,
    HUOBI: Huobi,
    KRAKEN_FUTURES: KrakenFutures,
    KRAKEN: Kraken,
    KUCOIN: KuCoin,
    OKCOIN: OKCoin,
    OKEX: OKEx,
    POLONIEX: Poloniex,
    UPBIT: Upbit,
    GATEIO: Gateio,
    PROBIT: Probit,
}
