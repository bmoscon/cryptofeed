"""
OrderBooks require a snapshot on initial subscription, hence connecting to a lot of symbols will eat up rate limits.

Use a 'http_proxy' to bypass this limitation.
Use 'concurrent_http' to make concurrent HTTP requests (used in polling and http GETs)

Notes:
    1. 'http_proxy' will only be used for GET requests (not Websockets). For more information visit https://docs.aiohttp.org/en/stable/client_reference.html
    2. There is a "startup lag" with L2_BOOKS with binance because requests are made sequentially.
"""
import os
from collections import defaultdict
from random import shuffle
from time import time

from cryptofeed import FeedHandler
from cryptofeed.defines import L2_BOOK, OPEN_INTEREST, BINANCE, BINANCE_FUTURES
from cryptofeed.exchanges import Binance, BinanceFutures


class Counter:
    """Helper class to keep track and display callback times"""

    def __init__(self, feed_handler):
        self.counts = {}
        self.total = {}
        self.times = {}
        self.feed_handler = feed_handler

    @property
    def all_found(self):
        for value in self.times.values():
            if value is None:
                return False
        return True

    def callback(self, exchange, channel, symbols, concurrent_http):
        concurrency = "[concurrent_http]" if concurrent_http else "[sync_http]"
        key = f'{exchange}:{channel} {concurrency}'
        self.counts[key] = defaultdict(int)
        self.total[key] = len(symbols)
        self.times[key] = None

        start_time = time()

        async def _callback(**kwargs):
            symbol = kwargs['symbol']
            self.counts[key][symbol] += 1
            if self.counts[key][symbol] > 1:
                return
            if len(self.counts[key]) == self.total[key]:
                self.times[key] = time() - start_time
            self.print()

            if self.all_found:
                print('Found all')

        print(f'{key}: Subscribing to {self.total[key]} symbols')
        return _callback

    def print(self):
        texts = []
        for key in self.counts:
            text = f'{key}: found {len(self.counts[key])}/{self.total[key]}'
            completion_time = self.times[key]
            if completion_time:
                text += f' (took {completion_time} seconds)'
            texts.append(text)

        os.system('cls' if os.name == 'nt' else 'clear')  # clear output
        print('\n'.join(texts), flush=True)


def main(proxy):
    futures_symbols = BinanceFutures.info()['symbols']
    futures_symbols = [symbol for symbol in futures_symbols if 'PINDEX' not in symbol]
    shuffle(futures_symbols)
    futures_symbols = futures_symbols[:20]

    # use high volume pairs for quick l2_book updates
    book_symbols = ['ETH-BTC', 'LTC-BTC', 'ADA-BTC', 'BTC-USDT', 'ETH-USDT', 'LTC-USDT', 'BNB-BTC', 'BNB-ETH']

    f = FeedHandler()
    counter = Counter(f)
    f.add_feed(Binance(depth_interval='1000ms',
                       concurrent_http=False,
                       http_proxy=proxy,
                       max_depth=1,
                       symbols=book_symbols,
                       channels=[L2_BOOK],
                       callbacks={L2_BOOK: counter.callback(BINANCE, L2_BOOK, book_symbols, False)}))
    f.add_feed(Binance(depth_interval='1000ms',
                       concurrent_http=True,
                       http_proxy=proxy,
                       max_depth=1,
                       symbols=book_symbols,
                       channels=[L2_BOOK],
                       callbacks={L2_BOOK: counter.callback(BINANCE, L2_BOOK, book_symbols, True)}))
    f.add_feed(BinanceFutures(http_proxy=proxy,
                              open_interest_interval=1.0,
                              concurrent_http=False,
                              symbols=futures_symbols,
                              channels=[OPEN_INTEREST],
                              callbacks={OPEN_INTEREST: counter.callback(BINANCE_FUTURES, OPEN_INTEREST, futures_symbols, False)}))
    f.add_feed(BinanceFutures(http_proxy=proxy,
                              open_interest_interval=1.0,
                              concurrent_http=True,
                              symbols=futures_symbols,
                              channels=[OPEN_INTEREST],
                              callbacks={OPEN_INTEREST: counter.callback(BINANCE_FUTURES, OPEN_INTEREST, futures_symbols, True)}))

    f.run()


if __name__ == '__main__':
    proxy_url = input('Proxy (optional): ') or None
    main(proxy=proxy_url)
