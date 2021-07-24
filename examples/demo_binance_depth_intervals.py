from time import time

from cryptofeed import FeedHandler
from cryptofeed.defines import L2_BOOK
from cryptofeed.exchange.binance import Binance
from cryptofeed.exchange.binance_futures import BinanceFutures
from cryptofeed.exchanges import BinanceDelivery


def timer(interval):
    then = time()

    async def abook(feed, symbol, book, timestamp, receipt_timestamp):
        nonlocal then
        now = time()

        delta = (now - then) * 1000
        print(
            f'{f"{feed}":<16} {f"[depth@{interval}]":<14} {int(delta):>4}ms ago, Timestamp: {timestamp}, Receipt: {receipt_timestamp}, Snapshot: {book}')
        then = now

    return abook


def main():
    f = FeedHandler()
    # intervals = '100ms', '1000ms'
    f.add_feed(Binance(depth_interval='1000ms',
                       max_depth=1,
                       symbols=Binance.info()['symbols'][:1],
                       channels=[L2_BOOK],
                       callbacks={L2_BOOK: timer('1000ms')}))

    # default interval is 100ms, '100ms', '250ms', '500ms'
    f.add_feed(BinanceDelivery(max_depth=1,
                               symbols=BinanceDelivery.info()['symbols'][:1],
                               channels=[L2_BOOK],
                               callbacks={L2_BOOK: timer('100ms')}))
    # intervals = '100ms', '250ms', '500ms'
    f.add_feed(BinanceFutures(depth_interval='500ms',
                              max_depth=1,
                              symbols=BinanceFutures.info()['symbols'][:1],
                              channels=[L2_BOOK],
                              callbacks={L2_BOOK: timer('500ms')}))
    f.run()


if __name__ == '__main__':
    main()
