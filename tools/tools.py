'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from urllib.request import urlopen
import requests
import json


"""
Just random functions I used while developing the library.
They may come in handy again . . .
"""


def poloniex_get_ticker_map():
    """
    mappings between pair strings and pair IDs are not documented
    so we can use their ticker endpoint which has the mappings embedded
    """
    with urlopen("https://poloniex.com/public?command=returnTicker") as url:
        data = json.loads(url.read().decode())
        print("{")
        for key in data:
            print("'{}': {},".format(key, data[key]['id']))
        print("}")

        print("[", end='')
        for key in data:
            print("'{}', ".format(key), end='')
        print("]", end='')


def bittrex_get_trading_pairs():
    with urlopen('https://bittrex.com/api/v1.1/public/getmarkets') as url:
        data = json.loads(url.read().decode())
        print("[", end='')
        for market in data['result']:
            print("'{}', ".format(market['MarketName']), end='')
        print("]", end='')


def coinbase_get_trading_pairs():
    with urlopen('https://api.pro.coinbase.com/products') as url:
        data = json.loads(url.read().decode())
        print('[', end='')
        for pair in data:
            print("'" + pair['id'] + "',",)
        print("]")


def hitbtc_get_trading_pairs():
    with urlopen('https://api.hitbtc.com/api/2/public/symbol') as url:
        data = json.loads(url.read().decode())
        print('[', end='')
        for pair in data:
            print("'" + pair['id'] + "',",)
        print("]")


def cex_get_trading_pairs():
    r = requests.get('https://cex.io/api/currency_limits')
    print("[")
    for data in r.json()['data']['pairs']:
        print("'{}-{}',".format(data['symbol1'], data['symbol2']))
    print("]")


def exx_get_trading_pairs():
    r = requests.get('https://api.exx.com/data/v1/tickers')
    print("[")
    for key in r.json():
        print("'{}',".format(key))
    print("]")


def bitmex_instruments():
    r = requests.get('https://www.bitmex.com/api/v1/instrument/active')
    print("[")
    data = r.json()
    for d in data:
        print("'{}',".format(d['symbol']))
    print("]")


if __name__ == '__main__':
    bitmex_instruments()
