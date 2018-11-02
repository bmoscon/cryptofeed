'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import requests


def gen_pairs():
    ret = {}
    pairs = requests.get('https://api.hitbtc.com/api/2/public/symbol').json()
    for symbol in pairs:
        split = len(symbol['baseCurrency'])
        normalized = symbol['id'][:split] + '-' + symbol['id'][split:]
        ret[normalized] = symbol['id']
    return ret

hitbtc_pair_mapping = gen_pairs()