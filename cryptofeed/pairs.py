'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


Pair generation code for exchanges
'''

import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import requests
from requests import Response

from cryptofeed.defines import *


LOG = logging.getLogger('feedhandler')

PAIR_SEP = '-'

_pairs_retrieval_cache: Dict[str, Dict[str, str]] = {}
_exchange_info = defaultdict(lambda: defaultdict(dict))


def raise_failure_explanation(feed_id: str, exception: BaseException, responses: Dict[str, Optional[Response]]):
    LOG.critical('%s: encountered %r while processing response from exchange API', feed_id, exception)
    if len(responses) > 1:
        LOG.critical('%s: content of one of the %s responses was unexpected', feed_id, len(responses))
    for url, r in responses.items():
        if url:
            LOG.critical('%s: requested URL: %s', feed_id, url)
        if r:
            LOG.critical('%s: unexpected response: %s', feed_id, r.text)
    raise ValueError(f'Cryptofeed stopped because of an unexpected response from {feed_id}') from exception


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
        raise_failure_explanation(exchange, why, {endpoint: r})


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
                # We will repair FUNDING soon on Binance, and enable the following line
                continue # normalized = norm.get(pair[1:], pair[1:])
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
        raise_failure_explanation('BITFINEX', why, {"tickers?symbols=ALL": r1, "pub:map:currency:sym": r2})


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
        raise_failure_explanation('BITFLYER', why, {endpoint: r})


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
        raise_failure_explanation('BYBIT', why, {"": r})


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
        raise_failure_explanation(exchange, why, {endpoint: r})


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
        raise_failure_explanation('COINBASE', why, {"": r})


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
        raise_failure_explanation('GEMINI', why, {"": r})


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
        raise_failure_explanation('HITBTC', why, {"": r})


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
        raise_failure_explanation('POLONIEX', why, {"": r})


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
        raise_failure_explanation('BITSTAMP', why, {"": r})


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
        raise_failure_explanation('KRAKEN', why, {"": r})


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
        raise_failure_explanation('EXX', why, {"": r})


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
        raise_failure_explanation('HUOBI', why, {url: r})


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
        raise_failure_explanation('HUOBI_DM', why, {"": r})


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
        raise_failure_explanation('HUOBI_SWAP', why, {"": r})


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
        raise_failure_explanation('OKCOIN', why, {"": r})


def okex_pairs() -> Dict[str, str]:
    # We will support soon OKEx options, and enable this following line
    option_urls = []  # okex_compute_option_urls_from_underlyings()
    other_urls = ['https://www.okex.com/api/spot/v3/instruments',
                  'https://www.okex.com/api/swap/v3/instruments/ticker',
                  'https://www.okex.com/api/futures/v3/instruments/ticker']
    # To respect rate limit constraints per endpoint, we alternate options and other instrument types
    urls: List[str] = []
    for i in range(max(len(option_urls), len(other_urls))):
        if i < len(option_urls):
            urls.append(option_urls[i])
        if i < len(other_urls):
            urls.append(other_urls[i])
    # Collect together the pairs of each endpoint
    pairs: Dict[str, str] = {}
    for u in urls:
        time.sleep(0.2)
        pairs.update(okex_pairs_from_one_url(u))
    return pairs


def okex_compute_option_urls_from_underlyings() -> List[str]:
    url = 'https://www.okex.com/api/option/v3/underlying'
    r = None
    try:
        r = requests.get(url)
        return [f'https://www.okex.com/api/option/v3/instruments/{underlying}' for underlying in r.json()]
    except Exception as why:
        raise_failure_explanation('OKEX', why, {url: r})


def okex_pairs_from_one_url(url: str) -> Dict[str, str]:
    r = None
    try:
        r = requests.get(url)
        return {e['instrument_id']: e['instrument_id'] for e in r.json()}
    except Exception as why:
        raise_failure_explanation('OKEX', why, {url: r})


def bittrex_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://api.bittrex.com/api/v1.1/public/getmarkets')
        r = r.json()['result']
        return {f"{e['MarketCurrency']}{PAIR_SEP}{e['BaseCurrency']}": e['MarketName'] for e in r if e['IsActive']}
    except Exception as why:
        raise_failure_explanation('BITTREX', why, {"": r})


def bitcoincom_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://api.exchange.bitcoin.com/api/2/public/symbol')
        return {f"{data['baseCurrency']}{PAIR_SEP}{data['quoteCurrency'].replace('USD', 'USDT')}": data['id'] for data in r.json()}
    except Exception as why:
        raise_failure_explanation('BITCOINCOM', why, {"": r})


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
        raise_failure_explanation('BITMAX', why, {"": r})


def upbit_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://api.upbit.com/v1/market/all')
        return {f"{data['market'].split('-')[1]}{PAIR_SEP}{data['market'].split('-')[0]}": data['market'] for data in r.json()}
    except Exception as why:
        raise_failure_explanation('UPBIT', why, {"": r})


def blockchain_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get("https://api.blockchain.com/mercury-gateway/v1/instruments")
        return {data["symbol"].replace("-", PAIR_SEP): data["symbol"] for data in r.json()}
    except Exception as why:
        raise_failure_explanation('BLOCKCHAIN', why, {"": r})


def gateio_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get("https://api.gateio.ws/api/v4/spot/currency_pairs")
        return {data["id"].replace("_", PAIR_SEP): data['id'] for data in r.json()}
    except Exception as why:
        raise_failure_explanation('GATEIO', why, {"": r})


def bitmex_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get("https://www.bitmex.com/api/v1/instrument/active")
        return {entry['symbol']: entry['symbol'] for entry in r.json()}
    except Exception as why:
        raise_failure_explanation('BITMEX', why, {"": r})


def deribit_pairs() -> Dict[str, str]:
    url = r = None
    try:
        currencies = ['BTC', 'ETH']
        kind = ['future', 'option']
        data = []
        for c in currencies:
            for k in kind:
                url = f"https://www.deribit.com/api/v2/public/get_instruments?currency={c}&expired=false&kind={k}"
                r = requests.get(url)
                data.extend(r.json()['result'])
        return {d['instrument_name']: d['instrument_name'] for d in data}
    except Exception as why:
        raise_failure_explanation('DERIBIT', why, {url: r})


def kraken_future_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://futures.kraken.com/derivatives/api/v3/instruments')
        data = r.json()['instruments']
        return {d['symbol']: d['symbol'] for d in data if d['tradeable'] is True}
    except Exception as why:
        raise_failure_explanation('KRAKEN_FUTURES', why, {"": r})


def probit_pairs() -> Dict[str, str]:
    # doc: https://docs-en.probit.com/reference-link/market
    r = None
    try:
        r = requests.get('https://api.probit.com/api/exchange/v1/market')
        return {entry['id']: entry['id'] for entry in r.json()['data']}
    except Exception as why:
        raise_failure_explanation('PROBIT', why, {"": r})


def coingecko_pairs() -> Dict[str, str]:
    r = None
    try:
        r = requests.get('https://api.coingecko.com/api/v3/coins/list')
        return {entry['symbol'].upper(): entry['id'] for entry in r.json()}
    except Exception as why:
        raise_failure_explanation('COINGECKO', why, {"": r})


def whale_alert_coins(key_id: str) -> Dict[str, str]:
    r = None
    try:
        r = requests.get(f'https://api.whale-alert.io/v1/status?api_key={key_id}')
        # Same symbols, but on different blockchains (for instance USDT), are naturally overwritten.
        return {s.upper(): s for b in r.json()['blockchains'] for s in b['symbols'] if s}
    except Exception as why:
        raise_failure_explanation('WHALES_ALERT', why, {"": r})


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
