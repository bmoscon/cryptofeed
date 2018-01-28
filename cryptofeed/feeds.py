
from cryptofeed.exchanges import BITFINEX
from cryptofeed.defines import L2_BOOK, L3_BOOK, TRADES, TICKER




_exchange_to_feed_map = {
        
}

_feed_to_exchange_map = {
    L2_BOOK: {BITFINEX: 'book-P0-F0-25'},
    L3_BOOK: {BITFINEX: 'book-R0-F0-100' },
    TRADES:  { },
    TICKER:  { },
}


def feed_to_exchange(exchange, feed):
    return _feed_to_exchange_map[feed][exchange]
