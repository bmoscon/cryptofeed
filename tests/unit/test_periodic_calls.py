from time import time
import asyncio

from cryptofeed import GDAX, FeedHandler
from cryptofeed.defines import L3_BOOK, L3_BOOK_UPDATE
from cryptofeed.callback import BookCallback, L3BookUpdateCallback
from cryptofeed.utils import call_periodically


loop = asyncio.new_event_loop()


def test_call_periodically(loop=loop):
    async def _test_call_periodically():
        interval = .5
        sleep_interval = .2
        max_calls = 20
        call_times = []
        count = 0

        async def dummy_func():
            nonlocal count, call_times
            count += 1
            call_times.append(time())
            # simulate work
            await asyncio.sleep(sleep_interval)
            if count == max_calls:
                raise Exception
            return 'done'

        low_range = interval - .01
        high_range = interval + .01

        try:
            await call_periodically(interval, dummy_func)
        except:
            pass

        for idx in range(len(call_times)-1):
            a, b = call_times[idx], call_times[idx+1]
            assert low_range <= (b - a) <= high_range, \
                f'Call times {a} and {b} not within acceptable range of {interval} ({b - a})'
    loop.run_until_complete(_test_call_periodically())


def test_gdax_with_periodic_snapshots():

    async def l3book(feed, pair, msg_type, ts, seq, side, price, size):
        print(
            f'Feed: {feed} Pair: {pair}  Message Type: {msg_type} Timestamp: {ts} '
            f'Sequence: {seq} Side: {side} Price: {price} Size: {size}'
        )

    async def l3snapshot(feed, pair, book):
        print(f'Feed: {feed} Pair: {pair} Bids: {book["bid"].items()[:10:-1]} Asks: {book["ask"].items()[:10]}')

    f = FeedHandler()
    f.add_feed(GDAX(pairs=['BTC-USD'],
                    channels=[L3_BOOK_UPDATE, L3_BOOK],
                    callbacks={L3_BOOK_UPDATE: L3BookUpdateCallback(l3book),
                               L3_BOOK: BookCallback(l3snapshot)},
                    intervals={'_book_snapshot': 3}))
    f.run()
