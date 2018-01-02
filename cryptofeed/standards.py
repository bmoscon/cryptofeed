'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

std_trading_pairs = {'BTC-USD': {'GDAX': 'BTC-USD', 'BITFINEX': 'tBTCUSD'}}

exchange_to_std = {'BTC-USD': 'BTC-USD', 'tBTCUSD': 'BTC-USD'}

def pair_std_to_exchange(pair, exchange):
    return std_trading_pairs[pair][exchange]


def pair_exchange_to_std(pair):
    return exchange_to_std[pair]
