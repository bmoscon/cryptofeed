'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

_std_trading_pairs = {'BTC-USD': {'GDAX': 'BTC-USD', 'BITFINEX': 'tBTCUSD', 'GEMINI': 'BTCUSD', 'HITBTC': 'BTCUSD'},
                     'ETH-USD': {'GEMINI': 'ETHUSD'},
                     'ETH-BTC': {'GEMINI': 'ETHBTC'}
                     }

_exchange_to_std = {'BTC-USD': 'BTC-USD',
                    'tBTCUSD': 'BTC-USD',
                    'BTCUSD': 'BTC-USD',
                    'ETHUSD': 'ETH-USD',
                    'ETH-USD': 'ETH-USD',
                    'ETHBTC': 'ETH-BTC',
                    'ETH-BTC': 'ETH-BTC'
                    }

def pair_std_to_exchange(pair, exchange):
    return _std_trading_pairs[pair][exchange]


def pair_exchange_to_std(pair):
    return _exchange_to_std[pair]

_channel_to_exchange = {
    'ticker': {'HITBTC': 'subscribeTicker'}
}

def std_channel_to_exchange(channel, exchange):
    if channel in _channel_to_exchange:
        if exchange in _channel_to_exchange[channel]:
            return _channel_to_exchange[channel][exchange]
    return channel
