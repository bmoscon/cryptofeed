from time import time
import asyncio
import websockets
from websockets import ConnectionClosed
from socket import error as socket_error

from cryptofeed import GDAX
from cryptofeed.defines import L3_BOOK, L3_BOOK_UPDATE


loop = asyncio.new_event_loop()


class EndTest(Exception):
    pass


class GDAXTestFeed(GDAX):
    async def synthesize_feed(self, func, *args, **kwargs):
        interval = self.intervals[func.__name__]
        low_range = interval - .01
        high_range = interval + .01
        start_time = time()
        last = start_time
        while True:
            call_time = time()
            print(f'Call times {last} and {call_time} in range {call_time - last}')
            if last != start_time:
                assert low_range <= (call_time - last) <= high_range, \
                    f'Call times {last} and {call_time} not within acceptable range of {interval} ({call_time - last})'
            last = call_time
            message = await func(*args, **kwargs)
            asyncio.ensure_future(self.message_handler(message))
            await asyncio.sleep(
                interval - ((time() - start_time) % interval)
            )


class TestHandler:
    def __init__(self, run_for=120, retries=10, timeout_interval=5):
        self.end_time = time() + run_for
        self.retries = retries
        self.timeout = {}
        self.last_msg = {}
        self.timeout_interval = timeout_interval

    def run(self, feed):

        try:
            asyncio.get_event_loop().run_until_complete(self._run(feed))
        except KeyboardInterrupt:
            pass
        except Exception as e:
            pass

    def _run(self, feed):
        yield from asyncio.ensure_future(self._connect(feed))

    async def _connect(self, feed):
        retries = 0
        delay = 1
        while retries <= self.retries:
            self.last_msg[feed.id] = None
            try:
                async with websockets.connect(feed.address) as websocket:
                    # connection was successful, reset retry count and delay
                    retries = 0
                    delay = 1
                    await feed.subscribe(websocket)
                    await self._handler(websocket, feed.message_handler)
            except (ConnectionClosed, ConnectionAbortedError, ConnectionResetError, socket_error) as e:
                await asyncio.sleep(delay)
                retries += 1
                delay = delay * 2

    async def _handler(self, websocket, handler):
        async for message in websocket:
            if time() >= self.end_time:
                print('ENDING')
                raise EndTest
            await handler(message)


def test_gdax_with_periodic_snapshots():

    f = TestHandler()
    try:
        f.run(GDAXTestFeed(pairs=['BTC-USD', 'ETH-BTC', 'LTC-BTC'],
                           channels=[L3_BOOK_UPDATE, L3_BOOK],
                           intervals={'_book_snapshot': 5}))
    except Exception as e:
        assert e == EndTest
