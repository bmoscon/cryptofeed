"""
OrderBooks require a snapshot on initial subscription, hence connecting to a lot of symbols will eat up rate limits.

Use a 'http_proxy' to bypass this limitation.

Notes:
    1. 'http_proxy' will only be used for GET requests (not Websockets). For more information visit https://docs.aiohttp.org/en/stable/client_reference.html
    2. There is a "startup lag" with L2_BOOKS with binance because requests are made sequentially.
"""
from collections import defaultdict
from typing import Union

from yarl import URL

from cryptofeed import FeedHandler
from cryptofeed.defines import L2_BOOK, OPEN_INTEREST
from cryptofeed.exchange.binance_futures import BinanceFutures
from cryptofeed.exchanges import Binance


def callback(channel, symbols):
    counter = defaultdict(int)

    async def _callback(**kwargs):
        symbol = kwargs['symbol']
        feed = kwargs['feed']
        counter[symbol] += 1
        print(f'[{feed}] [{channel}] {symbol}: {counter[symbol]} msgs  ({len(counter)}/{len(symbols)} symbols)')

    return _callback


def main(proxy: Union[str, URL]):
    book_symbols = Binance.info()['symbols']
    oi_symbols = BinanceFutures.info()['symbols']
    oi_symbols = [symbol for symbol in oi_symbols if 'PINDEX' not in symbol]

    print(f'BINANCE - L2_BOOK: Subscribing to {len(book_symbols)} symbols')
    print(f'BINANCE_FUTURES - OPEN_INTEREST: Subscribing to {len(oi_symbols)} symbols')
    print(f'BINANCE_FUTURES - L2_BOOK: Subscribing to {len(oi_symbols)} symbols')

    f = FeedHandler()
    f.add_feed(Binance(http_proxy=proxy,
                       max_depth=3,
                       symbols=book_symbols,
                       channels=[L2_BOOK],
                       callbacks={L2_BOOK: callback(L2_BOOK, book_symbols)}))
    f.add_feed(BinanceFutures(http_proxy=proxy,
                              symbols=oi_symbols,
                              channels=[L2_BOOK, OPEN_INTEREST],
                              callbacks={OPEN_INTEREST: callback(OPEN_INTEREST, oi_symbols), L2_BOOK: callback(L2_BOOK, oi_symbols)}))
    f.run()


if __name__ == '__main__':
    proxy_url = input('Proxy: ')
    main(proxy=proxy_url)
