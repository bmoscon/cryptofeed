'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import requests


def gen_pairs():
    ret = {}
    pairs = requests.get('https://api.binance.com/api/v1/exchangeInfo').json()
    for symbol in pairs['symbols']:
        split = len(symbol['baseAsset'])
        normalized = symbol['symbol'][:split] + '-' + symbol['symbol'][split:]
        ret[normalized] = symbol['symbol']
    return ret

binance_pair_mapping = gen_pairs()
