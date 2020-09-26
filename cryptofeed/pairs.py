'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


Pair generation code for exchanges
'''

import logging
from collections import defaultdict

import requests

from cryptofeed.defines import *


LOG = logging.getLogger('feedhandler')

PAIR_SEP = '-'


_pairs_retrieval_cache = dict()
_exchange_info = defaultdict(lambda: defaultdict(dict))


def set_pair_separator(symbol: str):
    global PAIR_SEP
    PAIR_SEP = symbol


def gen_pairs(exchange):
    if exchange not in _pairs_retrieval_cache:
        LOG.info("%s: Getting list of pairs", exchange)
        pairs = _exchange_function_map[exchange]()
        LOG.info("%s: %s pairs", exchange, len(pairs))
        _pairs_retrieval_cache[exchange] = pairs
    return _pairs_retrieval_cache[exchange]


def _binance_pairs(endpoint: str, exchange: str):
    ret = {}
    pairs = requests.get(endpoint).json()
    for symbol in pairs['symbols']:
        split = len(symbol['baseAsset'])
        normalized = symbol['symbol'][:split] + PAIR_SEP + symbol['symbol'][split:]
        ret[normalized] = symbol['symbol']
        _exchange_info[exchange]['tick_size'][normalized] = symbol['filters'][0]['tickSize']
    return ret


def binance_pairs():
    return _binance_pairs('https://api.binance.com/api/v1/exchangeInfo', BINANCE)


def binance_us_pairs():
    return _binance_pairs('https://api.binance.us/api/v1/exchangeInfo', BINANCE_US)


def binance_jersey_pairs():
    return _binance_pairs('https://api.binance.je/api/v1/exchangeInfo', BINANCE_JERSEY)


def binance_futures_pairs():
    return _binance_pairs('https://fapi.binance.com/fapi/v1/exchangeInfo', BINANCE_FUTURES)


def bitfinex_pairs():
    ret = {}
    r = requests.get('https://api.bitfinex.com/v2/tickers?symbols=ALL').json()
    for data in r:
        pair = data[0]
        if pair[0] == 'f':
            continue
        normalized = pair[1:-3] + PAIR_SEP + pair[-3:]
        normalized = normalized.replace('UST', 'USDT')
        ret[normalized] = pair
    return ret


def bybit_pairs():
    ret = {}
    r = requests.get('https://api.bybit.com/v2/public/symbols').json()
    for pair in r['result']:
        normalized = f"{pair['base_currency']}{PAIR_SEP}{pair['quote_currency']}"
        ret[normalized] = pair['name']
        _exchange_info[BYBIT]['tick_size'][normalized] = pair['price_filter']['tick_size']

    return ret


def _ftx_helper(endpoint: str, exchange: str):
    ret = {}
    r = requests.get(endpoint).json()
    for data in r['result']:
        normalized = data['name'].replace("/", PAIR_SEP)
        pair = data['name']
        ret[normalized] = pair
        _exchange_info[exchange]['tick_size'][normalized] = data['priceIncrement']
    return ret


def ftx_pairs():
    return _ftx_helper('https://ftx.com/api/markets', FTX)


def ftx_us_pairs():
    return _ftx_helper('https://ftx.us/api/markets', FTX_US)


def coinbase_pairs():
    r = requests.get('https://api.pro.coinbase.com/products').json()
    ret = {}
    for data in r:
        normalized = data['id'].replace("-", PAIR_SEP)
        ret[normalized] = data['id']
        _exchange_info[COINBASE]['tick_size'][normalized] = data['quote_increment']
    return ret


def gemini_pairs():
    ret = {}
    r = requests.get('https://api.gemini.com/v1/symbols').json()

    for pair in r:
        std = f"{pair[:-3]}{PAIR_SEP}{pair[-3:]}"
        std = std.upper()
        ret[std] = pair.upper()

    return ret


def hitbtc_pairs():
    ret = {}
    pairs = requests.get('https://api.hitbtc.com/api/2/public/symbol').json()
    for symbol in pairs:
        split = len(symbol['baseCurrency'])
        normalized = symbol['id'][:split] + PAIR_SEP + symbol['id'][split:]
        ret[normalized] = symbol['id']
        _exchange_info[HITBTC]['tick_size'][normalized] = symbol['tickSize']

    return ret


def poloniex_id_pair_mapping():
    ret = {}
    pairs = requests.get('https://poloniex.com/public?command=returnTicker').json()
    for pair in pairs:
        ret[pairs[pair]['id']] = pair
    return ret


def poloniex_pairs():
    return {value.split("_")[1] + PAIR_SEP + value.split("_")[0]: value for _, value in poloniex_id_pair_mapping().items()}


def bitstamp_pairs():
    ret = {}
    r = requests.get('https://www.bitstamp.net/api/v2/trading-pairs-info/').json()
    for data in r:
        normalized = data['name'].replace("/", PAIR_SEP)
        pair = data['url_symbol']
        ret[normalized] = pair
    return ret


def kraken_pairs():
    ret = {}
    r = requests.get('https://api.kraken.com/0/public/AssetPairs')
    data = r.json()
    for pair in data['result']:
        if 'wsname' not in data['result'][pair] or '.d' in pair:
            # https://blog.kraken.com/post/259/introducing-the-kraken-dark-pool/
            # .d is for dark pool pairs
            continue

        base, quote = data['result'][pair]['wsname'].split("/")

        normalized = f"{base}{PAIR_SEP}{quote}"
        exch = data['result'][pair]['wsname']
        normalized = normalized.replace('XBT', 'BTC')
        normalized = normalized.replace('XDG', 'DOG')
        ret[normalized] = exch
    return ret


def kraken_rest_pairs():
    return {normalized: exchange.replace("/", "") for normalized, exchange in kraken_pairs().items()}


def exx_pairs():
    r = requests.get('https://api.exx.com/data/v1/tickers').json()

    exchange = [key.upper() for key in r.keys()]
    pairs = [key.replace("_", PAIR_SEP) for key in exchange]
    return dict(zip(pairs, exchange))


def huobi_common_pairs(url: str):
    r = requests.get(url).json()
    return {'{}{}{}'.format(e['base-currency'].upper(), PAIR_SEP, e['quote-currency'].upper()): '{}{}'.format(e['base-currency'], e['quote-currency']) for e in r['data']}


def huobi_pairs():
    return huobi_common_pairs('https://api.huobi.pro/v1/common/symbols')


def huobi_us_pairs():
    return huobi_common_pairs('https://api.huobi.com/v1/common/symbols')


def huobi_dm_pairs():
    """
    Mapping is, for instance: {"BTC_CW":"BTC190816"}
    See comments in exchange/huobi_dm.py
    """
    mapping = {
        "this_week": "CW",
        "next_week": "NW",
        "quarter": "CQ",
        "next_quarter": "NQ"
    }
    r = requests.get('https://www.hbdm.com/api/v1/contract_contract_info').json()
    pairs = {}
    for e in r['data']:
        pairs[f"{e['symbol']}_{mapping[e['contract_type']]}"] = e['contract_code']
        _exchange_info[HUOBI_DM]['tick_size'][e['contract_code']] = e['price_tick']
        _exchange_info[HUOBI_DM]['short_code_mappings'][f"{e['symbol']}_{mapping[e['contract_type']]}"] = e['contract_code']

    return pairs


def huobi_swap_pairs():
    r = requests.get('https://api.hbdm.com/swap-api/v1/swap_contract_info').json()
    pairs = {}
    for e in r['data']:
        pairs[e['contract_code']] = e['contract_code']
        _exchange_info[HUOBI_SWAP]['tick_size'][e['contract_code']] = e['price_tick']

    return pairs


def okcoin_pairs():
    r = requests.get('https://www.okcoin.com/api/spot/v3/instruments').json()
    ret = {}
    for e in r:
        ret[e['instrument_id']] = e['instrument_id']
        _exchange_info[OKCOIN]['tick_size'][e['instrument_id']] = e['tick_size']
    return ret


def okex_pairs():
    r = requests.get('https://www.okex.com/api/spot/v3/instruments').json()
    data = {e['instrument_id']: e['instrument_id'] for e in r}
    # swaps
    r = requests.get('https://www.okex.com/api/swap/v3/instruments/ticker').json()
    for update in r:
        data[update['instrument_id']] = update['instrument_id']
    # futures
    r = requests.get('https://www.okex.com/api/futures/v3/instruments/ticker').json()
    for update in r:
        data[update['instrument_id']] = update['instrument_id']
    return data


def coinbene_pairs():
    r = requests.get('http://api.coinbene.com/v1/market/symbol').json()
    return {f"{e['baseAsset']}{PAIR_SEP}{e['quoteAsset']}": e['ticker'] for e in r['symbol']}


def bittrex_pairs():
    r = requests.get('https://api.bittrex.com/api/v1.1/public/getmarkets').json()
    r = r['result']
    return {f"{e['MarketCurrency']}{PAIR_SEP}{e['BaseCurrency']}": e['MarketName'] for e in r if e['IsActive']}


def bitcoincom_pairs():
    r = requests.get('https://api.exchange.bitcoin.com/api/2/public/symbol').json()
    return {f"{data['baseCurrency']}{PAIR_SEP}{data['quoteCurrency'].replace('USD', 'USDT')}": data['id'] for data in r}


def bitmax_pairs():
    r = requests.get('https://bitmax.io/api/v1/products').json()
    return {f"{data['baseAsset']}{PAIR_SEP}{data['quoteAsset']}": data['symbol'] for data in r}


def upbit_pairs():
    r = requests.get('https://api.upbit.com/v1/market/all').json()
    return {f"{data['market'].split('-')[1]}{PAIR_SEP}{data['market'].split('-')[0]}": data['market'] for data in r}


def blockchain_pairs():
    r = requests.get("https://api.blockchain.com/mercury-gateway/v1/instruments").json()
    return {data["symbol"].replace("-", PAIR_SEP): data["symbol"] for data in r}


def gateio_pairs():
    r = requests.get("https://api.gateio.ws/api/v4/spot/currency_pairs").json()
    return {data['id'].replace("_", PAIR_SEP): data['id'] for data in r}


def bitmex_pairs():
    r = requests.get("https://www.bitmex.com/api/v1/instrument/active").json()
    return {entry['symbol']: entry['symbol'] for entry in r}


def deribit_pairs():
    currencies = ['BTC', 'ETH']
    kind = ['future', 'option']
    data = []
    for c in currencies:
        for k in kind:
            data.extend(requests.get(f"https://www.deribit.com/api/v2/public/get_instruments?currency={c}&expired=false&kind={k}").json()['result'])
    return {d['instrument_name']: d['instrument_name'] for d in data}


def kraken_future_pairs():
    data = requests.get("https://futures.kraken.com/derivatives/api/v3/instruments").json()['instruments']
    return {d['symbol']: d['symbol'] for d in data if d['tradeable'] is True}


_exchange_function_map = {
    BITFINEX: bitfinex_pairs,
    COINBASE: coinbase_pairs,
    GEMINI: gemini_pairs,
    HITBTC: hitbtc_pairs,
    POLONIEX: poloniex_pairs,
    BITSTAMP: bitstamp_pairs,
    KRAKEN: kraken_pairs,
    KRAKEN + 'REST': kraken_rest_pairs,
    BINANCE: binance_pairs,
    BINANCE_US: binance_us_pairs,
    BINANCE_JERSEY: binance_jersey_pairs,
    BINANCE_FUTURES: binance_futures_pairs,
    BLOCKCHAIN: blockchain_pairs,
    EXX: exx_pairs,
    HUOBI: huobi_pairs,
    HUOBI_DM: huobi_dm_pairs,
    HUOBI_SWAP: huobi_swap_pairs,
    OKCOIN: okcoin_pairs,
    OKEX: okex_pairs,
    COINBENE: coinbene_pairs,
    BYBIT: bybit_pairs,
    FTX: ftx_pairs,
    FTX_US: ftx_us_pairs,
    BITTREX: bittrex_pairs,
    BITCOINCOM: bitcoincom_pairs,
    BITMAX: bitmax_pairs,
    UPBIT: upbit_pairs,
    GATEIO: gateio_pairs,
    BITMEX: bitmex_pairs,
    DERIBIT: deribit_pairs,
    KRAKEN_FUTURES: kraken_future_pairs
}
