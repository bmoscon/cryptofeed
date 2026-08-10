'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import glob
from pathlib import Path

import pytest

from cryptofeed.capture import CaptureReader, payload_of
from cryptofeed.exchanges import EXCHANGE_MAP
from cryptofeed.symbols import Symbols


CORPUS = Path(__file__).parents[2] / 'sample_data'
CONFIG = str(Path(__file__).parents[1] / 'config_test.yaml')
VENUES = ('KRAKEN', 'BYBIT', 'KUCOIN', 'KRAKEN_FUTURES', 'COINBASE')
MAX_FRAMES = 1000
ROUNDS = 5


def corpus_file(exchange: str):
    matches = glob.glob(str(CORPUS / f'{exchange}.jsonl*'))
    return matches[0] if matches else None


class RecordedHTTP:
    def __init__(self, exchange: str):
        self.exchange = exchange
        self.responses = []
        self.original = None

    def install(self):
        from cryptofeed.connection import HTTPAsyncConn

        self.original = HTTPAsyncConn.read
        responses, exchange = self.responses, self.exchange

        async def fake_read(conn, url, **kwargs):
            if not responses:
                raise RuntimeError(f'{exchange}: no recorded HTTP response left for {url} - a benchmark must never reach the network')
            data, headers = responses.pop(0)
            return (data, headers) if headers else data

        HTTPAsyncConn.read = fake_read

    def restore(self):
        from cryptofeed.connection import HTTPAsyncConn

        HTTPAsyncConn.read = self.original


class FakeConn:
    conn_type = 'wss'
    uuid = 'bench'

    def __init__(self):
        self.address = None
        self.subscription = {}

    async def write(self, *args, **kwargs):
        pass


async def build_feed(exchange: str, reader: CaptureReader):
    from cryptofeed.connection import WebsocketEndpoint

    async def noop(obj, receipt_timestamp):
        pass

    cls = EXCHANGE_MAP[exchange]
    kwargs = {'candle_interval': reader.candle_interval} if reader.candle_interval else {}
    feed = cls(candle_closed_only=False, config=CONFIG, subscription=reader.config,
               callbacks={c: noop for c in reader.config}, **kwargs)
    await feed._setup()
    if not feed.websocket_endpoints:
        feed.websocket_endpoints = [WebsocketEndpoint('wss://bench.invalid')]

    conn = FakeConn()
    conn.subscription = {
        feed.std_channel_to_exchange(channel): [feed.std_symbol_to_exchange_symbol(s) for s in symbols]
        for channel, symbols in reader.config.items()
    }
    handler = None
    for _, subscribe, message_handler, _auth in feed.connect():
        await subscribe(conn)
        handler = message_handler
    return handler, conn


@pytest.mark.parametrize('exchange', VENUES)
def test_message_handler(benchmark, exchange):
    path = corpus_file(exchange)
    if path is None:
        pytest.skip(f'no recording for {exchange}')

    reader = CaptureReader(path)
    http_records = [(payload_of(r), r.get('headers')) for r in reader.records() if r['t'] == 'http']
    addresses = {r['conn']: r['addr'] for r in reader.records() if r['t'] == 'connect'}
    frames = [(payload_of(r), addresses.get(r['conn']), r['ts'])
              for r in reader.records() if r['t'] == 'recv'][:MAX_FRAMES]
    if not frames:
        pytest.skip(f'{exchange} recording has no frames')

    recorded = RecordedHTTP(exchange)
    recorded.install()
    state = {}

    def setup():
        Symbols.clear()
        recorded.responses[:] = list(http_records)
        state['handler'], state['conn'] = asyncio.run(build_feed(exchange, reader))
        return (), {}

    def run():
        handler, conn = state['handler'], state['conn']

        async def replay():
            for payload, address, timestamp in frames:
                conn.address = address
                await handler(payload, conn, timestamp)

        asyncio.run(replay())

    try:
        benchmark.pedantic(run, setup=setup, rounds=ROUNDS, iterations=1)
    finally:
        recorded.restore()
        Symbols.clear()

    benchmark.extra_info['frames'] = len(frames)
    mean = benchmark.stats.stats.mean if benchmark.stats else None
    if mean:
        benchmark.extra_info['frames_per_second'] = round(len(frames) / mean)
