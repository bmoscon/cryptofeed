'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


Pair generation code for exchanges
'''

import logging
from collections import defaultdict
from typing import Dict, List

import requests

from cryptofeed.defines import *

LOG = logging.getLogger('feedhandler')

PAIR_SEP = '-'

_pairs_retrieval_cache = dict()
_exchange_info = defaultdict(lambda: defaultdict(dict))


def set_pair_separator(symbol: str):
    global PAIR_SEP
    PAIR_SEP = symbol


def gen_pairs(exchange: str, key_id=None) -> Dict[str, str]:
    if exchange not in _pairs_retrieval_cache:
        LOG.info("%s: Getting list of pairs", exchange)
        pairs = _exchange_function_map[exchange](key_id) if key_id else _exchange_function_map[exchange]()
        LOG.info("%s: %s pairs", exchange, len(pairs))
        _pairs_retrieval_cache[exchange] = pairs
    return _pairs_retrieval_cache[exchange]


def _binance_pairs(endpoint: str, exchange: str):
    ret = {}
    pairs = requests.get(endpoint).json()
    try:
        for symbol in pairs['symbols']:
            split = len(symbol['baseAsset'])
            normalized = symbol['symbol'][:split] + PAIR_SEP + symbol['symbol'][split:]
            ret[normalized] = symbol['symbol']
            _exchange_info[exchange]['tick_size'][normalized] = symbol['filters'][0]['tickSize']
            if "contractType" in symbol:
                _exchange_info[exchange]['contract_type'] = symbol['contractType']
    except KeyError:
        LOG.critical("GET BINANCE pairs %s: Unexpected response: %r", exchange, pairs)
        raise
    return ret


def binance_pairs() -> Dict[str, str]:
    return _binance_pairs('https://api.binance.com/api/v1/exchangeInfo', BINANCE)


def binance_us_pairs() -> Dict[str, str]:
    return _binance_pairs('https://api.binance.us/api/v1/exchangeInfo', BINANCE_US)


def binance_futures_pairs() -> Dict[str, str]:
    return _binance_pairs('https://fapi.binance.com/fapi/v1/exchangeInfo', BINANCE_FUTURES)


def binance_delivery_pairs() -> Dict[str, str]:
    return _binance_pairs('https://dapi.binance.com/dapi/v1/exchangeInfo', BINANCE_DELIVERY)


def bitfinex_pairs() -> Dict[str, str]:
    # doc: https://docs.bitfinex.com/docs/ws-general#supported-pairs
    tickers: List[List[str]] = requests.get("https://api.bitfinex.com/v2/tickers?symbols=ALL").json()
    norm: List[List[str]] = requests.get("https://api-pub.bitfinex.com/v2/conf/pub:map:currency:sym").json()[0]
    norm: Dict[str, str] = dict(norm)
    for k, v in dict(norm).items():
        if k[-2:] == "F0" or '-' in v:  # Do not convert BTCF0 -> BTC or PBTCETH -> PBTC-ETH
            del norm[k]
    ret = {}
    for pair in [t[0] for t in tickers]:
        if pair[0] == 'f':
            pass  # normalized = norm.get(pair[1:], pair[1:])
        else:
            if len(pair) == 7:
                base, quote = pair[1:4], pair[4:]
            else:
                base, quote = pair[1:].split(':')
                assert ':' in pair
            normalized = norm.get(base, base) + PAIR_SEP + norm.get(quote, quote)
            # Bitfinex uses BCHN, other exchanges use BCH
            if "BCHN" in normalized:
                normalized = normalized.replace("BCHN", "BCH")

            ret[normalized.upper()] = pair
    return ret


def bitflyer_pairs() -> Dict[str, str]:
    ret = {}
    endpoints = ['https://api.bitflyer.com/v1/getmarkets/eu', 'https://api.bitflyer.com/v1/getmarkets/usa', 'https://api.bitflyer.com/v1/getmarkets']
    for endpoint in endpoints:
        r = requests.get(endpoint).json()
        for entry in r:
            normalized = entry['product_code'].replace("_", PAIR_SEP)
            ret[normalized] = entry['product_code']
    return ret


def bybit_pairs() -> Dict[str, str]:
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


def ftx_pairs() -> Dict[str, str]:
    return _ftx_helper('https://ftx.com/api/markets', FTX)


def ftx_us_pairs() -> Dict[str, str]:
    return _ftx_helper('https://ftx.us/api/markets', FTX_US)


def coinbase_pairs() -> Dict[str, str]:
    r = requests.get('https://api.pro.coinbase.com/products').json()
    ret = {}
    for data in r:
        normalized = data['id'].replace("-", PAIR_SEP)
        ret[normalized] = data['id']
        _exchange_info[COINBASE]['tick_size'][normalized] = data['quote_increment']
    return ret


def gemini_pairs() -> Dict[str, str]:
    ret = {}
    r = requests.get('https://api.gemini.com/v1/symbols').json()

    for pair in r:
        std = f"{pair[:-3]}{PAIR_SEP}{pair[-3:]}"
        std = std.upper()
        ret[std] = pair.upper()

    return ret


def hitbtc_pairs() -> Dict[str, str]:
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


def poloniex_pairs() -> Dict[str, str]:
    return {value.split("_")[1] + PAIR_SEP + value.split("_")[0]: value for _, value in poloniex_id_pair_mapping().items()}


def bitstamp_pairs() -> Dict[str, str]:
    ret = {}
    r = requests.get('https://www.bitstamp.net/api/v2/trading-pairs-info/').json()
    for data in r:
        normalized = data['name'].replace("/", PAIR_SEP)
        pair = data['url_symbol']
        ret[normalized] = pair
    return ret


def kraken_pairs() -> Dict[str, str]:
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


def kraken_rest_pairs() -> Dict[str, str]:
    return {normalized: exchange.replace("/", "") for normalized, exchange in kraken_pairs().items()}


def exx_pairs() -> Dict[str, str]:
    r = requests.get('https://api.exx.com/data/v1/tickers').json()

    exchange = [key.upper() for key in r.keys()]
    pairs = [key.replace("_", PAIR_SEP) for key in exchange]
    return dict(zip(pairs, exchange))


def huobi_common_pairs(url: str):
    r = requests.get(url).json()
    return {'{}{}{}'.format(e['base-currency'].upper(), PAIR_SEP, e['quote-currency'].upper()): '{}{}'.format(e['base-currency'], e['quote-currency']) for e in r['data']}


def huobi_pairs() -> Dict[str, str]:
    return huobi_common_pairs('https://api.huobi.pro/v1/common/symbols')


def huobi_us_pairs() -> Dict[str, str]:
    return huobi_common_pairs('https://api.huobi.com/v1/common/symbols')


def huobi_dm_pairs() -> Dict[str, str]:
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


def huobi_swap_pairs() -> Dict[str, str]:
    r = requests.get('https://api.hbdm.com/swap-api/v1/swap_contract_info').json()
    pairs = {}
    for e in r['data']:
        pairs[e['contract_code']] = e['contract_code']
        _exchange_info[HUOBI_SWAP]['tick_size'][e['contract_code']] = e['price_tick']

    return pairs


def okcoin_pairs() -> Dict[str, str]:
    r = requests.get('https://www.okcoin.com/api/spot/v3/instruments').json()
    ret = {}
    for e in r:
        ret[e['instrument_id']] = e['instrument_id']
        _exchange_info[OKCOIN]['tick_size'][e['instrument_id']] = e['tick_size']
    return ret


def okex_pairs() -> Dict[str, str]:
    r = None
    try:
        # spot
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
    except Exception as why:
        LOG.exception("OKEX unexpected response: %r %r", r, why)
        raise


def bittrex_pairs() -> Dict[str, str]:
    r = requests.get('https://api.bittrex.com/api/v1.1/public/getmarkets').json()
    r = r['result']
    return {f"{e['MarketCurrency']}{PAIR_SEP}{e['BaseCurrency']}": e['MarketName'] for e in r if e['IsActive']}


def bitcoincom_pairs() -> Dict[str, str]:
    r = requests.get('https://api.exchange.bitcoin.com/api/2/public/symbol').json()
    return {f"{data['baseCurrency']}{PAIR_SEP}{data['quoteCurrency'].replace('USD', 'USDT')}": data['id'] for data in r}


def bitmax_pairs() -> Dict[str, str]:
    r = None
    ret = {}
    try:
        r = requests.get('https://bitmax.io/api/pro/v1/products')
        for entry in r.json()['data']:
            # Only "Normal" status symbols are tradeable
            if entry['status'] == 'Normal':
                normalized = f"{entry['baseAsset']}{PAIR_SEP}{entry['quoteAsset']}"
                ret[normalized] = entry['symbol']
                _exchange_info[BITMAX]['tick_size'][normalized] = entry['tickSize']
        return ret
    except Exception as why:
        LOG.error("BITMAX Unexpected message: %r %r", r.text, why)
        raise


def upbit_pairs() -> Dict[str, str]:
    r = requests.get('https://api.upbit.com/v1/market/all').json()
    return {f"{data['market'].split('-')[1]}{PAIR_SEP}{data['market'].split('-')[0]}": data['market'] for data in r}


def blockchain_pairs() -> Dict[str, str]:
    r = requests.get("https://api.blockchain.com/mercury-gateway/v1/instruments").json()
    return {data["symbol"].replace("-", PAIR_SEP): data["symbol"] for data in r}


def gateio_pairs() -> Dict[str, str]:
    r = requests.get("https://api.gateio.ws/api/v4/spot/currency_pairs").json()
    return {data['id'].replace("_", PAIR_SEP): data['id'] for data in r}


def bitmex_pairs() -> Dict[str, str]:
    r = requests.get("https://www.bitmex.com/api/v1/instrument/active").json()
    return {entry['symbol']: entry['symbol'] for entry in r}


def deribit_pairs() -> Dict[str, str]:
    currencies = ['BTC', 'ETH']
    kind = ['future', 'option']
    data = []
    for c in currencies:
        for k in kind:
            data.extend(requests.get(f"https://www.deribit.com/api/v2/public/get_instruments?currency={c}&expired=false&kind={k}").json()['result'])
    return {d['instrument_name']: d['instrument_name'] for d in data}


def kraken_future_pairs() -> Dict[str, str]:
    data = requests.get("https://futures.kraken.com/derivatives/api/v3/instruments").json()['instruments']
    return {d['symbol']: d['symbol'] for d in data if d['tradeable'] is True}


def probit_pairs() -> Dict[str, str]:
    r = requests.get("https://api.probit.com/api/exchange/v1/market").json()
    return {entry['id']: entry['id'] for entry in r['data']}


def coingecko_pairs() -> Dict[str, str]:
    data = requests.get('https://api.coingecko.com/api/v3/coins/list').json()
    return {entry['symbol'].upper(): entry['id'] for entry in data}


def whale_alert_coins(key_id: str):
    data = requests.get('https://api.whale-alert.io/v1/status?api_key={!s}'.format(key_id)).json()
    # Same symbols, but on different blockchains (for instance USDT), are naturally overwritten.
    return {s.upper(): s for b in data['blockchains'] for s in b['symbols'] if s}


_exchange_function_map = {
    BITFINEX: bitfinex_pairs,
    BITFLYER: bitflyer_pairs,
    COINBASE: coinbase_pairs,
    GEMINI: gemini_pairs,
    HITBTC: hitbtc_pairs,
    POLONIEX: poloniex_pairs,
    PROBIT: probit_pairs,
    BITSTAMP: bitstamp_pairs,
    KRAKEN: kraken_pairs,
    KRAKEN + 'REST': kraken_rest_pairs,
    BINANCE: binance_pairs,
    BINANCE_US: binance_us_pairs,
    BINANCE_FUTURES: binance_futures_pairs,
    BINANCE_DELIVERY: binance_delivery_pairs,
    BLOCKCHAIN: blockchain_pairs,
    EXX: exx_pairs,
    HUOBI: huobi_pairs,
    HUOBI_DM: huobi_dm_pairs,
    HUOBI_SWAP: huobi_swap_pairs,
    OKCOIN: okcoin_pairs,
    OKEX: okex_pairs,
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
    KRAKEN_FUTURES: kraken_future_pairs,
    COINGECKO: coingecko_pairs,
    WHALE_ALERT: whale_alert_coins
}
