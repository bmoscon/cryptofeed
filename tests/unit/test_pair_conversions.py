from cryptofeed.standards import pair_exchange_to_std, pair_std_to_exchange
from cryptofeed.gdax.pairs import gdax_trading_pairs


def test_gdax_pair_conversions():
    for pair in gdax_trading_pairs:
        assert(pair_exchange_to_std(pair) == pair)
        assert(pair_std_to_exchange(pair, 'GDAX') == pair)
