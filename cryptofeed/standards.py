'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

_std_trading_pairs = {
    'BTC-USD': {
        'GDAX': 'BTC-USD',
        'BITFINEX': 'tBTCUSD',
        'GEMINI': 'BTCUSD',
        'HITBTC': 'BTCUSD'
    },
    'ETH-USD': {
        'GEMINI': 'ETHUSD',
        'GDAX': 'ETH-USD'
    },
    'ETH-BTC': {
        'GEMINI': 'ETHBTC',
        'GDAX': 'ETH-BTC'
    },
    'BCH-USD': {
        'GDAX': 'BCH-USD'
    },
    'LTC-EUR': {
        'GDAX': 'LTC-EUR'
    },
    'LTC-USD': {
        'GDAX': 'LTC-USD'
    },
    'LTC-BTC': {
        'GDAX': 'LTC-BTC'
    },
    'ETH-EUR': {
        'GDAX': 'ETH-EUR'
    },
    'BTC-GBP': {
        'GDAX': 'BTC-GBP'
    },
    'BTC-EUR': {
        'GDAX': 'BTC-EUR'
    }
}

_exchange_to_std = {
    'BTC-USD': 'BTC-USD',
    'tBTCUSD': 'BTC-USD',
    'BTCUSD': 'BTC-USD',
    'ETHUSD': 'ETH-USD',
    'ETH-USD': 'ETH-USD',
    'ETHBTC': 'ETH-BTC',
    'ETH-BTC': 'ETH-BTC',
    'BCH-USD': 'BCH-USD',
    'LTC-USD': 'LTC-USD',
    'LTC-EUR': 'LTC-EUR',
    'LTC-BTC': 'LTC-BTC',
    'ETH-EUR': 'ETH-EUR',
    'BTC-GBP': 'BTC-GBP',
    'BTC-EUR': 'BTC-EUR'
}


def pair_std_to_exchange(pair, exchange):
    return _std_trading_pairs[pair][exchange]


def pair_exchange_to_std(pair):
    return _exchange_to_std[pair]


_channel_to_exchange = {'ticker': {'HITBTC': 'subscribeTicker'}}


def std_channel_to_exchange(channel, exchange):
    if channel in _channel_to_exchange:
        if exchange in _channel_to_exchange[channel]:
            return _channel_to_exchange[channel][exchange]
    return channel
