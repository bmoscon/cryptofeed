from cryptofeed.standards import pair_exchange_to_std, pair_std_to_exchange
from cryptofeed.gdax.pairs import gdax_trading_pairs
from cryptofeed.poloniex.pairs import poloniex_trading_pairs
from cryptofeed.bitfinex.pairs import bitfinex_trading_pairs 


def test_gdax_pair_conversions():
    for pair in gdax_trading_pairs:
        assert(pair_exchange_to_std(pair) == pair_std_to_exchange(pair, 'GDAX'))


def test_poloniex_pair_conversions():
    for pair in poloniex_trading_pairs:
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, 'POLONIEX'))


def test_bitfinex_pair_conversions():
    for pair in bitfinex_trading_pairs:
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, 'BITFINEX'))