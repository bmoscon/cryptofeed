'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
import os
import re
import time
from contextlib import suppress
from urllib.parse import urlencode

from cryptofeed import _json as json
from cryptofeed.capture.pcap import (
    BASE_CLIENT_PORT, LINKTYPE_ETHERNET, META_ADDRESS, META_CONN_ID, META_EXCHANGE,
    META_KIND, META_ORDINAL, META_RESUMED, META_SUBSCRIPTION, PCAP_MAGIC_NS,
    HTTPStream, PcapFile, WSStream, ts_to_ns,
)
from cryptofeed.symbols import Symbols


LOG = logging.getLogger('cryptofeed.capture')

metadata_VERSION = 1
_CONN_KIND = re.compile(r'\.(?:ws|http)\.')


def capture_basename(path: str) -> str:
    if path.endswith('.zst'):
        path = path[:-4]

    return os.path.splitext(path)[0]


def metadata_path(pcap_path: str) -> str:
    return capture_basename(pcap_path) + '.meta.json'


def request_url(address: str, params) -> str:
    if not params:
        return address
    query = params if isinstance(params, str) else urlencode(params)

    return address + ('&' if '?' in address else '?') + query


def _version() -> str:
    try:
        from importlib.metadata import version
        return version('cryptofeed')
    except Exception:
        return 'unknown'


class _Live:
    __slots__ = ('conn', 'stream', 'kind', 'ordinal', 'record')

    def __init__(self, conn, stream, kind, ordinal, record):
        self.conn = conn
        self.stream = stream
        self.kind = kind
        self.ordinal = ordinal
        self.record = record


class PcapRecorder:
    FLUSH_INTERVAL = 5.0

    def __init__(self, path: str, rotate_size: int = None, compress: bool = True):
        if os.path.isdir(path) or path.endswith(os.sep):
            os.makedirs(path, exist_ok=True)
            ext = '.pcap.zst' if compress else '.pcap'
            path = os.path.join(path, time.strftime('cryptofeed-%Y%m%d-%H%M%S') + ext)
        else:
            parent = os.path.dirname(os.path.abspath(path))
            os.makedirs(parent, exist_ok=True)
            if compress and not path.endswith('.zst'):
                path += '.zst'

        self._base_path = path
        self.rotate_size = rotate_size
        self.created = time.time()
        self._pcap = PcapFile(path)
        self.files = [path]
        self._feeds = []
        self._feed_meta = []
        self._live = {}
        self._ordinals = {}
        self._streams_meta = []
        self._next_port = BASE_CLIENT_PORT
        self._resume_next = set()
        self._flush_task = None
        self._closed = False
        self._dirty = True

    def register_feed(self, feed):
        self._feeds.append(feed)
        self._feed_meta.append({
            'exchange': feed.id,
            'symbols': [str(s) for s in feed._init_symbols] if feed._init_symbols else feed._init_symbols,
            'channels': list(feed._init_channels) if feed._init_channels else feed._init_channels,
            'subscription': {chan: [str(s) for s in syms] for chan, syms in feed._init_subscription.items()} if feed._init_subscription else feed._init_subscription,
            'kwargs': {
                'candle_interval': getattr(feed, 'candle_interval', None),
                'candle_closed_only': feed.candle_closed_only,
                'max_depth': feed.max_depth,
                'sandbox': feed.sandbox,
            },
        })
        self._dirty = True

    def _exchange_for(self, conn) -> str:
        best = ''
        for feed in self._feeds:
            if conn.id.startswith(feed.id + '.') and len(feed.id) > len(best):
                best = feed.id

        return best if best else _CONN_KIND.split(conn.id, maxsplit=1)[0]

    def _alloc_port(self) -> int:
        port = self._next_port
        self._next_port += 1
        if self._next_port > 65535:
            LOG.warning('capture: client port space exhausted - reusing ports, streams may collide')
            self._next_port = BASE_CLIENT_PORT
        return port

    def _ensure_flush_task(self):
        if self._flush_task is None and not self._closed:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
            self._flush_task = loop.create_task(self._flush_loop(), name='cryptofeed.capture.flush')

    async def _flush_loop(self):
        while True:
            await asyncio.sleep(self.FLUSH_INTERVAL)
            self._pcap.flush()
            if self._dirty:
                self._dirty = False
                self._write_metadata()

    async def on_ws_open(self, conn, timestamp: float):
        self._ensure_flush_task()
        ordinal = self._ordinals.get(id(conn), 0) + 1
        self._ordinals[id(conn)] = ordinal
        self._open_ws(conn, timestamp, ordinal, resumed=False)

    def _open_ws(self, conn, timestamp: float, ordinal: int, resumed: bool) -> _Live:
        self._close_stale(conn, timestamp)
        port = self._alloc_port()
        subscription = conn.subscription if conn.subscription else None
        meta = {META_CONN_ID: conn.id, META_EXCHANGE: self._exchange_for(conn), META_ADDRESS: conn.address, META_ORDINAL: str(ordinal)}

        if subscription:
            meta[META_SUBSCRIPTION] = json.dumps(subscription)

        if resumed:
            meta[META_RESUMED] = '1'

        stream = WSStream(self._pcap, port, ts_to_ns(timestamp), conn.address, meta)
        record = {'stream': len(self._streams_meta), 'kind': 'ws', 'file': os.path.basename(self._pcap.path),
                  'conn_id': conn.id, 'exchange': meta[META_EXCHANGE], 'connect_ordinal': ordinal,
                  'client_port': port, 'address': conn.address, 'subscription': subscription,
                  'resumed': resumed, 'opened': timestamp, 'closed': None, 'messages': 0}

        self._streams_meta.append(record)
        live = _Live(conn, stream, 'ws', ordinal, record)
        self._live[id(conn)] = live
        self._dirty = True

        return live

    def _close_stale(self, conn, timestamp: float):
        stale = self._live.pop(id(conn), None)
        if stale is not None:
            stale.stream.close(ts_to_ns(timestamp))
            stale.record['closed'] = timestamp

    async def on_ws_message(self, conn, data, timestamp: float):
        live = self._live.get(id(conn))
        if live is None:
            LOG.debug('capture: %s message after session close - not recorded', conn.id)
            return

        live.stream.message(ts_to_ns(timestamp), data)
        live.record['messages'] += 1
        self._dirty = True
        self._maybe_rotate(timestamp)

    async def on_ws_send(self, conn, data, timestamp: float):
        live = self._live.get(id(conn))
        if live is None:
            return

        live.stream.sent(ts_to_ns(timestamp), data)
        self._maybe_rotate(timestamp)

    async def on_http(self, conn, address: str, params, header, data, timestamp: float):
        self._record_http(conn, 'GET', request_url(address, params), data, None, timestamp)

    async def on_http_post(self, conn, address: str, msg, data, timestamp: float):
        self._record_http(conn, 'POST', address, data, msg, timestamp)

    async def on_http_poll(self, conn, address: str, header, data, timestamp: float):
        self._record_http(conn, 'GET', address, data, None, timestamp)

    def _open_http(self, conn, timestamp: float, ordinal: int, resumed: bool) -> _Live:
        self._close_stale(conn, timestamp)
        port = self._alloc_port()
        meta = {META_CONN_ID: conn.id, META_EXCHANGE: self._exchange_for(conn), META_ORDINAL: str(ordinal)}

        if getattr(conn, 'address', None):
            meta[META_KIND] = 'poll'

        if resumed:
            meta[META_RESUMED] = '1'

        stream = HTTPStream(self._pcap, port, ts_to_ns(timestamp), meta)
        record = {'stream': len(self._streams_meta), 'kind': 'http', 'file': os.path.basename(self._pcap.path),
                  'conn_id': conn.id, 'exchange': meta[META_EXCHANGE], 'connect_ordinal': ordinal,
                  'client_port': port, 'address': getattr(conn, 'address', None),
                  'resumed': resumed, 'opened': timestamp, 'closed': None, 'requests': 0}

        self._streams_meta.append(record)
        live = _Live(conn, stream, 'http', ordinal, record)
        self._live[id(conn)] = live
        self._dirty = True

        return live

    def _record_http(self, conn, method: str, url: str, response_body, request_body, timestamp: float):
        self._ensure_flush_task()
        live = self._live.get(id(conn))

        if live is None:
            if id(conn) in self._resume_next:
                self._resume_next.discard(id(conn))
                live = self._open_http(conn, timestamp, self._ordinals[id(conn)], resumed=True)
            else:
                ordinal = self._ordinals.get(id(conn), 0) + 1
                self._ordinals[id(conn)] = ordinal
                live = self._open_http(conn, timestamp, ordinal, resumed=False)

        live.stream.exchange(ts_to_ns(timestamp), method, url, response_body, request_body=request_body)
        live.record['requests'] += 1
        self._dirty = True
        self._maybe_rotate(timestamp)

    async def on_close(self, conn):
        live = self._live.pop(id(conn), None)
        if live is None:
            return

        now = time.time()
        live.stream.close(ts_to_ns(now))
        live.record['closed'] = now
        self._dirty = True

    def _maybe_rotate(self, timestamp: float):
        if self.rotate_size is None or self._pcap.size < self.rotate_size:
            return

        self._pcap.close()
        base = capture_basename(self._base_path)
        path = f'{base}.{len(self.files)}{self._base_path[len(base):]}'
        LOG.info('capture: rotating to %s', path)
        self._pcap = PcapFile(path)
        self.files.append(path)

        for live in list(self._live.values()):
            del self._live[id(live.conn)]
            if live.kind == 'ws':
                self._open_ws(live.conn, timestamp, live.ordinal, resumed=True)
            else:
                self._resume_next.add(id(live.conn))
        self._dirty = True

    def _write_metadata(self):
        path = metadata_path(self._base_path)
        doc = {
            'version': metadata_VERSION,
            'cryptofeed_version': _version(),
            'created': self.created,
            'format': {'container': 'pcap', 'magic': f'0x{PCAP_MAGIC_NS:08x}', 'linktype': LINKTYPE_ETHERNET},
            'files': [os.path.basename(f) for f in self.files],
            'feeds': self._feed_meta,
            'streams': self._streams_meta,
        }

        tmp = path + '.tmp'
        try:
            with open(tmp, 'w') as fp:
                fp.write(json.dumps(doc))
            os.replace(tmp, path)
        except (OSError, TypeError, ValueError):
            LOG.warning('capture: unable to write metadata %s', path, exc_info=True)

    async def aclose(self):
        if self._closed:
            return
        self._closed = True
        if self._flush_task is not None:
            self._flush_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._flush_task
            self._flush_task = None

        now = time.time()
        for live in self._live.values():
            live.stream.close(ts_to_ns(now))
            live.record['closed'] = now
        self._live.clear()

        for entry, feed in zip(self._feed_meta, self._feeds):
            if Symbols.populated(feed.id):
                normalized, info = Symbols.get(feed.id)
                entry['symbols_snapshot'] = {'normalized': normalized, 'info': info}

        self._pcap.close()
        self._write_metadata()
