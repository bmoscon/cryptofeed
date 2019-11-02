'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


Pair generation code for exchanges
'''
import requests

from cryptofeed.defines import BITSTAMP, BITFINEX, COINBASE, GEMINI, HITBTC, POLONIEX, KRAKEN, BINANCE, BINANCE_US, EXX, HUOBI, HUOBI_US, HUOBI_DM, OKCOIN, OKEX, COINBENE, BYBIT, FTX, BITTREX, BITCOINCOM, BITMAX


def gen_pairs(exchange):
    return _exchange_function_map[exchange]()


def binance_pairs():
    ret = {}
    pairs = requests.get('https://api.binance.com/api/v1/exchangeInfo').json()
    for symbol in pairs['symbols']:
        split = len(symbol['baseAsset'])
        normalized = symbol['symbol'][:split] + '-' + symbol['symbol'][split:]
        ret[normalized] = symbol['symbol']
    return ret


def binance_us_pairs():
    ret = {}
    pairs = requests.get('https://api.binance.us/api/v1/exchangeInfo').json()
    for symbol in pairs['symbols']:
        split = len(symbol['baseAsset'])
        normalized = symbol['symbol'][:split] + '-' + symbol['symbol'][split:]
        ret[normalized] = symbol['symbol']
    return ret


def bitfinex_pairs():
    ret = {}
    r = requests.get('https://api.bitfinex.com/v2/tickers?symbols=ALL').json()
    for data in r:
        pair = data[0]
        if pair[0] == 'f':
            continue
        else:
            normalized = pair[1:-3] + '-' + pair[-3:]
            normalized = normalized.replace('UST', 'USDT')
            ret[normalized] = pair

    return ret


def bybit_pairs():
    pairs = {"BTC-USD": "BTCUSD", "ETH-USD": "ETHUSD", "EOS-USD": "EOSUSD", "XRP-USD": "XRPUSD"}
    return pairs


def ftx_pairs():
    ret = {}
    r = requests.get('https://ftx.com/api/markets').json()
    for data in r['result']:
        normalized = data['name'].replace("/", "-")
        pair = data['name']
        ret[normalized] = pair
    return ret


def coinbase_pairs():
    r = requests.get('https://api.pro.coinbase.com/products').json()
    return {data['id']: data['id'] for data in r}


def gemini_pairs():
    ret = {}
    r = requests.get('https://api.gemini.com/v1/symbols').json()

    for pair in r:
        std = "{}-{}".format(pair[:-3], pair[-3:])
        std = std.upper()
        ret[std] = pair
        ret[std] = pair.upper()

    return ret


def hitbtc_pairs():
    ret = {}
    pairs = requests.get('https://api.hitbtc.com/api/2/public/symbol').json()
    for symbol in pairs:
        split = len(symbol['baseCurrency'])
        normalized = symbol['id'][:split] + '-' + symbol['id'][split:]
        ret[normalized] = symbol['id']
    return ret


def poloniex_id_pair_mapping():
    ret = {}
    pairs = requests.get('https://poloniex.com/public?command=returnTicker').json()
    for pair in pairs:
        ret[pairs[pair]['id']] = pair
    return ret


def poloniex_pairs():
    return {value.split("_")[1] + "-" + value.split("_")[0]: value for _, value in poloniex_id_pair_mapping().items()}


def bitstamp_pairs():
    ret = {}
    r = requests.get('https://www.bitstamp.net/api/v2/trading-pairs-info/').json()
    for data in r:
        normalized = data['name'].replace("/", "-")
        pair = data['url_symbol']
        ret[normalized] = pair
    return ret


def kraken_pairs():
    ret = {}
    r = requests.get('https://api.kraken.com/0/public/AssetPairs')
    data = r.json()
    for pair in data['result']:
        alt = data['result'][pair]['altname']
        modifier = -3
        if ".d" in alt:
            modifier = -5
        normalized = alt[:modifier] + '-' + alt[modifier:]
        exch = normalized.replace("-", "/")
        normalized = normalized.replace('XBT', 'BTC')
        normalized = normalized.replace('XDG', 'DOG')
        ret[normalized] = exch
    return ret


def kraken_rest_pairs():
    ret = {}
    r = requests.get('https://api.kraken.com/0/public/AssetPairs')
    data = r.json()
    for pair in data['result']:
        alt = data['result'][pair]['altname']
        modifier = -3
        if ".d" in alt:
            modifier = -5
        normalized = alt[:modifier] + '-' + alt[modifier:]
        exch = normalized.replace("-", "")
        normalized = normalized.replace('XBT', 'BTC')
        normalized = normalized.replace('XDG', 'DOG')
        ret[normalized] = exch
    return ret


def exx_pairs():
    r = requests.get('https://api.exx.com/data/v1/tickers').json()

    exchange = [key.upper() for key in r.keys()]
    pairs = [key.replace("_", "-") for key in exchange]
    return {pair: exchange for pair, exchange in zip(pairs, exchange)}


def huobi_pairs():
    r = requests.get('https://api.huobi.pro/v1/common/symbols').json()
    return {'{}-{}'.format(e['base-currency'].upper(), e['quote-currency'].upper()) : '{}{}'.format(e['base-currency'], e['quote-currency']) for e in r['data']}


def huobi_us_pairs():
    r = requests.get('https://api.huobi.com/v1/common/symbols').json()
    return {'{}-{}'.format(e['base-currency'].upper(), e['quote-currency'].upper()) : '{}{}'.format(e['base-currency'], e['quote-currency']) for e in r['data']}


def huobi_dm_pairs():
    """
    Mapping is, for instance: {"BTC_CW":"BTC190816"}
    See comments in exchange/houbi_dm.py
    """
    mapping  = {
        "this_week": "CW",
        "next_week": "NW",
        "quarter": "CQ"
    }
    r = requests.get('https://www.hbdm.com/api/v1/contract_contract_info').json()
    pairs = {}
    for e in r['data']:
       pairs["{}_{}".format(e['symbol'], mapping[e['contract_type']])] = e['contract_code']
    return pairs


def okcoin_pairs():
    r = requests.get('https://www.okcoin.com/api/spot/v3/instruments').json()
    return {e['instrument_id'] : e['instrument_id'] for e in r}


def okex_pairs():
    r = requests.get('https://www.okex.com/api/spot/v3/instruments').json()
    data = {e['instrument_id'] : e['instrument_id'] for e in r}
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
    return {f"{e['baseAsset']}-{e['quoteAsset']}" : e['ticker'] for e in r['symbol']}


def bittrex_pairs():
    r = requests.get('https://api.bittrex.com/api/v1.1/public/getmarkets').json()
    r = r['result']
    return {f"{e['MarketCurrency']}-{e['BaseCurrency']}": e['MarketName'] for e in r if e['IsActive']}


def bitcoincom_pairs():
    r = requests.get('https://api.exchange.bitcoin.com/api/2/public/symbol').json()
    return {f"{data['baseCurrency']}-{data['quoteCurrency'].replace('USD', 'USDT')}": data['id'] for data in r}


def bitmax_pairs():
    r = requests.get('https://bitmax.io/api/v1/products').json()
    return {f"{data['baseAsset']}-{data['quoteAsset']}": data['symbol'] for data in r}

_exchange_function_map = {
    BITFINEX: bitfinex_pairs,
    COINBASE: coinbase_pairs,
    GEMINI: gemini_pairs,
    HITBTC: hitbtc_pairs,
    POLONIEX: poloniex_pairs,
    BITSTAMP: bitstamp_pairs,
    KRAKEN: kraken_pairs,
    KRAKEN+'REST': kraken_rest_pairs,
    BINANCE: binance_pairs,
    BINANCE_US: binance_us_pairs,
    EXX: exx_pairs,
    HUOBI: huobi_pairs,
    HUOBI_US: huobi_us_pairs,
    HUOBI_DM: huobi_dm_pairs,
    OKCOIN: okcoin_pairs,
    OKEX: okex_pairs,
    COINBENE: coinbene_pairs,
    BYBIT: bybit_pairs,
    FTX: ftx_pairs,
    BITTREX: bittrex_pairs,
    BITCOINCOM: bitcoincom_pairs,
    BITMAX: bitmax_pairs
}
