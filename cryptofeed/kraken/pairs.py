'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import requests


def gen_pairs():
    ret = {}
    r = requests.get('https://api.kraken.com/0/public/AssetPairs')
    data = r.json()
    for pair in data['result']:
        alt = data['result'][pair]['altname']
        modifier = -3
        if ".d" in alt:
            modifier = -5
        normalized = alt[:modifier] + '-' + alt[modifier:]
        normalized = normalized.replace('XBT', 'BTC')
        normalized = normalized.replace('XDG', 'DOG')
        ret[normalized] = pair
    return ret


kraken_pair_mapping = gen_pairs()
