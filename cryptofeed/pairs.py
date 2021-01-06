'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


Pair generation code for exchanges
'''

import logging
from collections import defaultdict
from typing import Dict, List, Tuple

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
    r = None
    try:
        ret = {}
        r = requests.get(endpoint)
        for symbol in r.json()['symbols']:
            split = len(symbol['baseAsset'])
            normalized = symbol['symbol'][:split] + PAIR_SEP + symbol['symbol'][split:]
            ret[normalized] = symbol['symbol']
            _exchange_info[exchange]['tick_size'][normalized] = symbol['filters'][0]['tickSize']
            if "contractType" in symbol:
                _exchange_info[exchange]['contract_type'] = symbol['contractType']
        return ret
    except Exception as why:
        LOG.critical('%s: encountered %r while processing exchangeInfo response from exchange API', exchange, why)
        LOG.critical('%s: unexpected response: %r', exchange, r.text if r else r)
        raise ValueError(f'Cryptofeed stopped because of an unexpected response from {exchange}') from why


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
    r1 = r2 = None
    try:
        r1 = requests.get('https://api.bitfinex.com/v2/tickers?symbols=ALL')
        r2 = requests.get('https://api-pub.bitfinex.com/v2/conf/pub:map:currency:sym')
        tickers: List[List[str]] = r1.json()
        norm: List[Tuple[str, str]] = r2.json()[0]
        norm: Dict[str, str] = dict(norm)
        for k, v in dict(norm).items():
            if k[-2:] == 'F0' or '-' in v:  # Do not convert BTCF0 -> BTC or PBTCETH -> PBTC-ETH
                del norm[k]
        norm['BCHN'] = 'BCH'  # Bitfinex uses BCHN, other exchanges use BCH

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
                ret[normalized.upper()] = pair
        return ret
    except ValueError as why:
        LOG.critical('BITFINEX: encountered %r while processing response from exchange API', why)
        LOG.critical('BITFINEX: content of one of the two exchange responses was unexpected')
        LOG.critical('BITFINEX: 1. response from tickers?symbols=ALL: %r', r1.text if r1 else r1)
        LOG.critical('BITFINEX: 2. response from pub:map:currency:sym: %r', r2.text if r2 else r2)
        raise ValueError('Cryptofeed stopped because of an unexpected response from BITFINEX') from why


def bitflyer_pairs() -> Dict[str, str]:
    endpoint = r = None
    try:
        ret = {}
        endpoints = ['https://api.bitflyer.com/v1/getmarkets/eu', 'https://api.bitflyer.com/v1/getmarkets/usa', 'https://api.bitflyer.com/v1/getmarkets']
        for endpoint in endpoints:
            r = requests.get(endpoint)
            for entry in r.json():
                normalized = entry['product_code'].replace("_", PAIR_SEP)
                ret[normalized] = entry['product_code']
        return ret
    except Exception as why:
        LOG.critical('BITFLYER: encountered %r while processing response from exchange API', why)
        LOG.critical('BITFLYER: unexpected response %r from URL %s', r.text if r else r, endpoint)
        raise ValueError('Cryptofeed stopped because of an unexpected response from BITFLYER') from why


def bybit_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://api.bybit.com/v2/public/symbols')
        ret = {}
        for pair in r.json()['result']:
            normalized = f"{pair['base_currency']}{PAIR_SEP}{pair['quote_currency']}"
            ret[normalized] = pair['name']
            _exchange_info[BYBIT]['tick_size'][normalized] = pair['price_filter']['tick_size']
        return ret
    except Exception as why:
        LOG.critical('BYBIT: encountered %r while processing response from exchange API', why)
        LOG.critical('BYBIT: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from BYBIT') from why


def _ftx_helper(endpoint: str, exchange: str):
    r = None
    try:
        r = requests.get(endpoint)
        ret = {}
        for data in r.json()['result']:
            normalized = data['name'].replace("/", PAIR_SEP)
            pair = data['name']
            ret[normalized] = pair
            _exchange_info[exchange]['tick_size'][normalized] = data['priceIncrement']
        return ret
    except Exception as why:
        LOG.critical('%s: encountered %r while processing response from exchange API', exchange, why)
        LOG.critical('%s: unexpected response: %r', exchange, r.text if r else r)
        raise ValueError(f'Cryptofeed stopped because of an unexpected response from {exchange}') from why


def ftx_pairs() -> Dict[str, str]:
    return _ftx_helper('https://ftx.com/api/markets', FTX)


def ftx_us_pairs() -> Dict[str, str]:
    return _ftx_helper('https://ftx.us/api/markets', FTX_US)


def coinbase_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://api.pro.coinbase.com/products')
        ret = {}
        for data in r.json():
            normalized = data['id'].replace("-", PAIR_SEP)
            ret[normalized] = data['id']
            _exchange_info[COINBASE]['tick_size'][normalized] = data['quote_increment']
        return ret
    except Exception as why:
        LOG.critical('COINBASE: encountered %r while processing response from exchange API', why)
        LOG.critical('COINBASE: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from COINBASE') from why


def gemini_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://api.gemini.com/v1/symbols')
        ret = {}
        for pair in r.json():
            std = f"{pair[:-3]}{PAIR_SEP}{pair[-3:]}"
            std = std.upper()
            ret[std] = pair.upper()
        return ret
    except Exception as why:
        LOG.critical('GEMINI: encountered %r while processing response from exchange API', why)
        LOG.critical('GEMINI: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from GEMINI') from why


def hitbtc_pairs() -> Dict[str, str]:
    r = None
    try:
        ret = {}
        r = requests.get('https://api.hitbtc.com/api/2/public/symbol')
        for symbol in r.json():
            split = len(symbol['baseCurrency'])
            normalized = symbol['id'][:split] + PAIR_SEP + symbol['id'][split:]
            ret[normalized] = symbol['id']
            _exchange_info[HITBTC]['tick_size'][normalized] = symbol['tickSize']
        return ret
    except Exception as why:
        LOG.critical('HITBTC: encountered %r while processing response from exchange API', why)
        LOG.critical('HITBTC: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from HITBTC') from why


def poloniex_id_pair_mapping():
    r = None
    try:
        r = requests.get('https://poloniex.com/public?command=returnTicker')
        pairs = r.json()
        ret = {}
        for pair in pairs:
            ret[pairs[pair]['id']] = pair
        return ret
    except Exception as why:
        LOG.critical('POLONIEX: encountered %r while processing response from exchange API', why)
        LOG.critical('POLONIEX: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from POLONIEX') from why


def poloniex_pairs() -> Dict[str, str]:
    return {value.split("_")[1] + PAIR_SEP + value.split("_")[0]: value for _, value in poloniex_id_pair_mapping().items()}


def bitstamp_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://www.bitstamp.net/api/v2/trading-pairs-info/')
        ret = {}
        for data in r.json():
            normalized = data['name'].replace("/", PAIR_SEP)
            pair = data['url_symbol']
            ret[normalized] = pair
        return ret
    except Exception as why:
        LOG.critical('BITSTAMP: encountered %r while processing response from exchange API', why)
        LOG.critical('BITSTAMP: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from BITSTAMP') from why


def kraken_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://api.kraken.com/0/public/AssetPairs')
        data = r.json()
        ret = {}
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
    except Exception as why:
        LOG.critical('KRAKEN: encountered %r while processing response from exchange API', why)
        LOG.critical('KRAKEN: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from KRAKEN') from why


def kraken_rest_pairs() -> Dict[str, str]:
    return {normalized: exchange.replace("/", "") for normalized, exchange in kraken_pairs().items()}


def exx_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://api.exx.com/data/v1/tickers')
        exchange = [key.upper() for key in r.json().keys()]
        pairs = [key.replace("_", PAIR_SEP) for key in exchange]
        return dict(zip(pairs, exchange))
    except Exception as why:
        LOG.critical('EXX: encountered %r while processing response from exchange API', why)
        LOG.critical('EXX: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from EXX') from why


def huobi_common_pairs(url: str):
    r = None
    try:
        r = requests.get(url)
        ret = {}
        for e in r.json()['data']:
            normalized = f"{e['base-currency'].upper()}{PAIR_SEP}{e['quote-currency'].upper()}"
            pair = f"{e['base-currency']}{e['quote-currency']}"
            ret[normalized] = pair
        return ret
    except Exception as why:
        LOG.critical('HUOBI: encountered %r while processing response URL: %r', why, url)
        LOG.critical('HUOBI: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from HUOBI') from why


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
    r = None
    try:
        r = requests.get('https://www.hbdm.com/api/v1/contract_contract_info')
        pairs = {}
        for e in r.json()['data']:
            pairs[f"{e['symbol']}_{mapping[e['contract_type']]}"] = e['contract_code']
            _exchange_info[HUOBI_DM]['tick_size'][e['contract_code']] = e['price_tick']
            _exchange_info[HUOBI_DM]['short_code_mappings'][f"{e['symbol']}_{mapping[e['contract_type']]}"] = e['contract_code']
        return pairs
    except Exception as why:
        LOG.critical('HUOBI_DM: encountered %r while processing response from exchange API', why)
        LOG.critical('HUOBI_DM: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from HUOBI_DM') from why


def huobi_swap_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://api.hbdm.com/swap-api/v1/swap_contract_info')
        pairs = {}
        for e in r.json()['data']:
            pairs[e['contract_code']] = e['contract_code']
            _exchange_info[HUOBI_SWAP]['tick_size'][e['contract_code']] = e['price_tick']
        return pairs
    except Exception as why:
        LOG.critical('HUOBI_SWAP: encountered %r while processing response from exchange API', why)
        LOG.critical('HUOBI_SWAP: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from HUOBI_SWAP') from why


def okcoin_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://www.okcoin.com/api/spot/v3/instruments')
        ret = {}
        for e in r.json():
            ret[e['instrument_id']] = e['instrument_id']
            _exchange_info[OKCOIN]['tick_size'][e['instrument_id']] = e['tick_size']
        return ret
    except Exception as why:
        LOG.critical('OKCOIN: encountered %r while processing response from exchange API', why)
        LOG.critical('OKCOIN: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from OKCOIN') from why


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
        LOG.critical('OKEX: encountered %r while processing response from exchange API', why)
        LOG.critical('OKEX: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from OKEX') from why


def bittrex_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://api.bittrex.com/api/v1.1/public/getmarkets')
        r = r.json()['result']
        return {f"{e['MarketCurrency']}{PAIR_SEP}{e['BaseCurrency']}": e['MarketName'] for e in r if e['IsActive']}
    except Exception as why:
        LOG.critical('BITTREX: encountered %r while processing response from exchange API', why)
        LOG.critical('BITTREX: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from BITTREX') from why


def bitcoincom_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://api.exchange.bitcoin.com/api/2/public/symbol')
        return {f"{data['baseCurrency']}{PAIR_SEP}{data['quoteCurrency'].replace('USD', 'USDT')}": data['id'] for data in r.json()}
    except Exception as why:
        LOG.critical('BITCOINCOM: encountered %r while processing response from exchange API', why)
        LOG.critical('BITCOINCOM: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from BITCOINCOM') from why


def bitmax_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://bitmax.io/api/pro/v1/products')
        ret = {}
        for entry in r.json()['data']:
            # Only "Normal" status symbols are tradeable
            if entry['status'] == 'Normal':
                normalized = f"{entry['baseAsset']}{PAIR_SEP}{entry['quoteAsset']}"
                ret[normalized] = entry['symbol']
                _exchange_info[BITMAX]['tick_size'][normalized] = entry['tickSize']
        return ret
    except Exception as why:
        LOG.critical('BITMAX: encountered %r while processing response from exchange API', why)
        LOG.critical('BITMAX: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from BITMAX') from why


def upbit_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://api.upbit.com/v1/market/all')
        return {f"{data['market'].split('-')[1]}{PAIR_SEP}{data['market'].split('-')[0]}": data['market'] for data in r.json()}
    except Exception as why:
        LOG.critical('UPBIT: encountered %r while processing response from exchange API', why)
        LOG.critical('UPBIT: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from UPBIT') from why


def blockchain_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get("https://api.blockchain.com/mercury-gateway/v1/instruments")
        return {data["symbol"].replace("-", PAIR_SEP): data["symbol"] for data in r.json()}
    except Exception as why:
        LOG.critical('BLOCKCHAIN: encountered %r while processing response from exchange API', why)
        LOG.critical('BLOCKCHAIN: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from BLOCKCHAIN') from why


def gateio_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get("https://api.gateio.ws/api/v4/spot/currency_pairs")
        return {data["id"].replace("_", PAIR_SEP): data['id'] for data in r.json()}
    except Exception as why:
        LOG.critical('GATEIO: encountered %r while processing response from exchange API', why)
        LOG.critical('GATEIO: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from GATEIO') from why


def bitmex_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get("https://www.bitmex.com/api/v1/instrument/active")
        return {entry['symbol']: entry['symbol'] for entry in r.json()}
    except Exception as why:
        LOG.critical('BITMEX: encountered %r while processing response from exchange API', why)
        LOG.critical('BITMEX: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from BITMEX') from why


def deribit_pairs() -> Dict[str, str]:
    r = None
    try:
        currencies = ['BTC', 'ETH']
        kind = ['future', 'option']
        data = []
        for c in currencies:
            for k in kind:
                r = requests.get(f"https://www.deribit.com/api/v2/public/get_instruments?currency={c}&expired=false&kind={k}")
                data.extend(r.json()['result'])
        return {d['instrument_name']: d['instrument_name'] for d in data}
    except Exception as why:
        LOG.critical('DERIBIT: encountered %r while processing response from exchange API', why)
        LOG.critical('DERIBIT: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from DERIBIT') from why


def kraken_future_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://futures.kraken.com/derivatives/api/v3/instruments')
        data = r.json()['instruments']
        return {d['symbol']: d['symbol'] for d in data if d['tradeable'] is True}
    except Exception as why:
        LOG.critical('KRAKEN_FUTURES: encountered %r while processing response from exchange API', why)
        LOG.critical('KRAKEN_FUTURES: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from KRAKEN_FUTURES') from why


def probit_pairs() -> Dict[str, str]:
    # doc: https://docs-en.probit.com/reference-link/market
    r = None
    try:
        r = requests.get('https://api.probit.com/api/exchange/v1/market')
        return {entry['id']: entry['id'] for entry in r.json()['data']}
    except Exception as why:
        LOG.critical('PROBIT: encountered %r while processing response from exchange API', why)
        LOG.critical('PROBIT: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from PROBIT') from why


def coingecko_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://api.coingecko.com/api/v3/coins/list')
        return {entry['symbol'].upper(): entry['id'] for entry in r.json()}
    except Exception as why:
        LOG.critical('COINGECKO: encountered %r while processing response from exchange API', why)
        LOG.critical('COINGECKO: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from COINGECKO') from why


def whale_alert_coins(key_id: str) -> Dict[str, str]:
    r = None
    try:
        r = requests.get(f'https://api.whale-alert.io/v1/status?api_key={key_id}')
        # Same symbols, but on different blockchains (for instance USDT), are naturally overwritten.
        return {s.upper(): s for b in r.json()['blockchains'] for s in b['symbols'] if s}
    except Exception as why:
        LOG.critical('WHALES_ALERT: encountered %r while processing response from exchange API', why)
        LOG.critical('WHALES_ALERT: unexpected response: %r', r.text if r else r)
        raise ValueError('Cryptofeed stopped because of an unexpected response from WHALES_ALERT') from why


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
