'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.

Recording and replay of raw exchange traffic

A recording is one zstd compressed JSONL file per exchange.
The first line is a header naming the exchange and the feed configuration.
Every later line is one typed record. Payloads are JSON string values and binary
frames are base64.

    {"t":"header","format":2,"exchange":"KRAKEN","config":{"trades":["BTC-USD"]},...}
    {"t":"connect","conn":"KRAKEN.ws.1","addr":"wss://ws.kraken.com","ts":1618678132.368}
    {"t":"send","conn":"KRAKEN.ws.1","ts":1618678132.83,"addr":"wss://...","data":"{...}"}
    {"t":"recv","conn":"KRAKEN.ws.1","ts":1618678132.91,"data":"{...}"}
    {"t":"recv","conn":"HUOBI.ws.1","ts":1618678133.02,"b64":"H4sIAAAA..."}
    {"t":"http","conn":"KRAKEN.http.0","ts":1618678132.35,"url":"https://...","data":"{...}"}
'''
import asyncio
import base64
import functools
import os
import time
from collections import defaultdict

from cryptofeed import _json as json
from cryptofeed import _zstd


FORMAT_VERSION = 2


def corpus_filename(exchange: str, compressed: bool = True) -> str:
    return f'{exchange}.jsonl{_zstd.SUFFIX}' if compressed else f'{exchange}.jsonl'


def exchange_from_conn(conn_id: str) -> str:
    for marker in ('.ws.', '.http.'):
        if marker in conn_id:
            return conn_id.split(marker)[0]
    return conn_id


class CaptureWriter:
    def __init__(self, path: str, batch: int = 500, compress: bool = True):
        self.path = path
        self.batch = batch
        self.compress = compress and _zstd.AVAILABLE
        self._buffers = defaultdict(list)
        self._files = {}
        self._locks = defaultdict(asyncio.Lock)

    def filename(self, exchange: str) -> str:
        return os.path.join(self.path, corpus_filename(exchange, self.compress))

    def _open(self, exchange: str):
        if exchange not in self._files:
            os.makedirs(self.path, exist_ok=True)
            path = self.filename(exchange)
            self._files[exchange] = _zstd.open(path, 'wb') if self.compress else open(path, 'wb')
        return self._files[exchange]

    def header(self, exchange: str, config: dict, candle_interval: str = None, recorded: float = None):
        """Write the header. Called once per exchange, before any traffic is recorded."""
        record = {
            't': 'header',
            'format': FORMAT_VERSION,
            'exchange': exchange,
            'config': config,
            'candle_interval': candle_interval,
            'recorded': recorded if recorded is not None else time.time(),
        }
        self._open(exchange).write((json.dumps(record) + '\n').encode())

    async def __call__(self, data, timestamp: float, uuid: str, endpoint: str = None, send: str = None, connect: str = None, header: str = None):
        record = {'conn': uuid, 'ts': timestamp}
        if connect:
            record.update(t='connect', addr=connect)
        elif endpoint:
            record.update(t='http', url=endpoint)
            _set_payload(record, data)
            if header:
                record['headers'] = header
        elif send:
            record.update(t='send', addr=send)
            _set_payload(record, data)
        else:
            record['t'] = 'recv'
            _set_payload(record, data)

        exchange = exchange_from_conn(uuid)
        buffer = self._buffers[exchange]
        buffer.append(json.dumps(record))
        if len(buffer) >= self.batch:
            await self.flush(exchange)

    async def flush(self, exchange: str = None):
        for name in [exchange] if exchange else list(self._buffers):
            buffer = self._buffers.get(name)
            if not buffer:
                continue
            payload = ('\n'.join(buffer) + '\n').encode()
            self._buffers[name] = []
            async with self._locks[name]:
                # compression and disk are blocking; batches are infrequent
                await asyncio.to_thread(self._open(name).write, payload)

    async def close(self):
        await self.flush()
        for handle in self._files.values():
            await asyncio.to_thread(handle.close)
        self._files.clear()

    # the feed handler calls stop() on shutdown
    def stop(self):
        for name, buffer in self._buffers.items():
            if buffer:
                self._open(name).write(('\n'.join(buffer) + '\n').encode())
                self._buffers[name] = []
        for handle in self._files.values():
            handle.close()
        self._files.clear()


def _set_payload(record: dict, data):
    if data is None:
        return
    if isinstance(data, bytes):
        # binary frames (gzip/deflate venues) will be base64
        record['b64'] = base64.b64encode(data).decode()
    else:
        record['data'] = data


class CaptureReader:
    def __init__(self, path: str):
        self.path = path
        self.header = None
        with self._open() as fp:
            first = fp.readline()
        if not first:
            raise ValueError(f'{path}: empty capture file')
        self.header = json.loads(first)
        if self.header.get('t') != 'header':
            raise ValueError(f'{path}: first record is not expected header')
        if self.header.get('format') != FORMAT_VERSION:
            raise ValueError(f'{path}: unsupported capture format {self.header.get("format")!r}, expected {FORMAT_VERSION}')

    def _open(self):
        if self.path.endswith(_zstd.SUFFIX):
            return _zstd.open(self.path, 'rb')
        return open(self.path, 'rb')

    @property
    def exchange(self) -> str:
        return self.header['exchange']

    @property
    def config(self) -> dict:
        return self.header['config']

    @property
    def candle_interval(self):
        return self.header.get('candle_interval')

    def records(self):
        with self._open() as fp:
            fp.readline()  # header
            for line in fp:
                if line.strip():
                    yield json.loads(line)

    def count(self, kind: str = 'recv') -> int:
        return sum(1 for r in self.records() if r['t'] == kind)


def payload_of(record: dict):
    if 'b64' in record:
        return base64.b64decode(record['b64'])
    return record.get('data')


def playback(path: str, callbacks: dict = None, config: str = 'config.yaml', **feed_kwargs) -> dict:
    return asyncio.run(_playback(path, callbacks, config, feed_kwargs))


async def _playback(path: str, callbacks: dict, config: str, feed_kwargs: dict = None) -> dict:
    from cryptofeed.connection import HTTPAsyncConn, WebsocketEndpoint
    from cryptofeed.exchanges import EXCHANGE_MAP

    reader = CaptureReader(path)
    callback_stats = defaultdict(int)

    http_records = []
    by_url = defaultdict(list)
    for record in reader.records():
        if record['t'] == 'http':
            by_url[record['url']].append(len(http_records))
            http_records.append((payload_of(record), record.get('headers')))
    consumed = set()

    def next_response(url):
        for index in by_url.get(url, []):
            if index not in consumed:
                return index
        for index in range(len(http_records)):
            if index not in consumed:
                return index
        return None

    class FakeWS:
        def __init__(self):
            self.conn_type = 'wss'
            self.uuid = '1'
            # exchanges running several endpoints may key off the address
            self.address = None
            self.subscription = {}

        async def write(self, *args, **kwargs):
            pass

        async def read(self, url, **kwargs):
            index = next_response(url)
            if index is None:
                raise KeyError(f'{path}: no recorded HTTP response left for {url}')
            consumed.add(index)
            data, headers = http_records[index]
            return (data, headers) if headers else data

    ws = FakeWS()

    async def internal_cb(*args, **kwargs):
        callback_stats[kwargs['cb_type']] += 1

    subscription = reader.config
    if not callbacks:
        callbacks = {ctype: functools.partial(internal_cb, cb_type=ctype) for ctype in subscription}
    else:
        for ctype in callbacks:
            callbacks[ctype] = [callbacks[ctype], functools.partial(internal_cb, cb_type=ctype)]

    cls = EXCHANGE_MAP[reader.exchange]
    kwargs = dict(feed_kwargs or {})
    if reader.candle_interval:
        kwargs.setdefault('candle_interval', reader.candle_interval)

    feed = None
    original_read = HTTPAsyncConn.read
    HTTPAsyncConn.read = ws.read
    try:
        feed = cls(candle_closed_only=False, config=config, subscription=subscription, callbacks=callbacks, **kwargs)
        await feed._setup()
        if not feed.websocket_endpoints:
            # venues that resolve their endpoint in _pre_connect never connect during playback
            feed.websocket_endpoints = [WebsocketEndpoint('wss://playback.invalid')]

        # several exchanges read conn.subscription while subscribing or resetting state
        # (Bybit resets its ticker snapshots from it, Gemini seeds its books from it), so the
        # replay connection carries the same subscription a live one would
        ws.subscription = {
            feed.std_channel_to_exchange(channel): [feed.std_symbol_to_exchange_symbol(s) for s in symbols]
            for channel, symbols in subscription.items()
        }

        handlers = {}
        for _, subscribe, handler, _auth in feed.connect():
            await subscribe(ws)
            handlers['handler'] = handler
        handler = handlers['handler']

        addresses = {}
        counter = 0
        for record in reader.records():
            kind = record['t']
            if kind == 'connect':
                addresses[record['conn']] = record['addr']
                continue
            if kind != 'recv':
                continue
            ws.address = addresses.get(record['conn'])
            message = payload_of(record)
            counter += 1
            try:
                await handler(message, ws, record['ts'])
            except Exception:
                print(f'Playback failed on message: {message}')
                raise
        return {'messages_processed': counter, 'callbacks': dict(callback_stats)}
    finally:
        if feed is not None:
            await feed.shutdown()
        HTTPAsyncConn.read = original_read
