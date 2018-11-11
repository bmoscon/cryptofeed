'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import requests


def gen_pairs():
    ret = {}
    pairs = requests.get('https://poloniex.com/public?command=returnTicker').json()
    for pair in pairs:
        ret[pairs[pair]['id']] = pair
    return ret

poloniex_id_pair_mapping = gen_pairs()
poloniex_pair_id_mapping = {value: key for key, value in poloniex_id_pair_mapping.items()}
poloniex_pair_mapping = {value.split("_")[1] + "-" + value.split("_")[0] : value for _, value in poloniex_id_pair_mapping.items()}
