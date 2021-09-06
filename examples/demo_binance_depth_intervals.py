from time import time

from decimal import Decimal
from cryptofeed import FeedHandler
from cryptofeed.defines import L2_BOOK
from cryptofeed.exchanges.binance import Binance
from cryptofeed.exchanges.binance_futures import BinanceFutures
from cryptofeed.exchanges import BinanceDelivery


# Ask limit orders I manually placed in the book (20+ levels away from mid) prior to starting cryptofeed
# These should ALL be in the internal OB if market moves upwards
# Some may not be if the price level gets updated while cf is running (eg. by another participant)
ASKS_TO_LOOK_FOR = [
    (Decimal('266.0'), Decimal('0.06')),
    (Decimal('266.1'), Decimal('0.06')),
    (Decimal('266.2'), Decimal('0.06')),  # added this one AFTER starting cf (will be in the book)
    (Decimal('266.3'), Decimal('0.06')),
]


def timer(interval):
    then = time()

    async def abook(feed, symbol, book, timestamp, receipt_timestamp):
        nonlocal then
        now = time()

        delta = (now - then) * 1000

        asks = book['ask'].items()[:20]

        asks_debug = [f'{px:.2f}|{sz:.3f}' for px, sz in asks]

        print(f'\nSnap at {timestamp} (truncated book from {len(book["ask"])} to {len(asks)}):')
        print(', '.join(asks_debug))

        max_px_in_book = asks[-1][0]

        for px, sz in ASKS_TO_LOOK_FOR:
            if max_px_in_book <= px:
                continue
            else:
                if px not in [p for p, _ in asks]:
                    # print(f'ERROR. {px:.2f} not in book but should be!!')
                    pass

        then = now

    return abook


def main():
    f = FeedHandler()
    # intervals = '100ms', '1000ms'
    f.add_feed(Binance(depth_interval='100ms',
                       symbols=['DASH-BUSD'],
                       channels=[L2_BOOK],
                       callbacks={L2_BOOK: timer('100ms')},
                       concurrent_http=True))
    f.run()


if __name__ == '__main__':
    main()
