'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import requests


def gen_pairs():
    r = requests.get('https://api.pro.coinbase.com/products').json()

    return {data['id'] : data['id'] for data in r}


coinbase_pair_mapping = gen_pairs()
