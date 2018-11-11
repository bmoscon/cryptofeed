'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import requests


def gen_pairs():
    ret = {}

    r = requests.get('https://api.gemini.com/v1/symbols').json()
    for pair in r:
        std = "{}-{}".format(pair[:-3], pair[-3:])
        std = std.upper()
        ret[std] = pair
    return ret


gemini_pair_mapping = gen_pairs()
