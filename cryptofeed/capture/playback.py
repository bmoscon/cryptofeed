'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
import time
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from cryptofeed import _json as json
from cryptofeed.capture.pcap import Capture, ns_to_ts, read_capture
from cryptofeed.capture.recorder import request_url, metadata_path
from cryptofeed.connection import AsyncConnection, HTTPAsyncConn, HTTPPoll, WSAsyncConn
from cryptofeed.exceptions import ConnectionClosed
from cryptofeed.symbols import Symbols


LOG = logging.getLogger('cryptofeed.capture')


class _Token:
    __slots__ = ('index', 'name', 'pending', 'exhausted')

    def __init__(self, index: int, name: str):
        self.index = index
        self.name = name
        self.pending = None
        self.exhausted = False


class PlaybackCoordinator:
    def __init__(self, pacing: str = 'fast', speed: float = 1.0, strict_order: bool = True, stall_timeout: float = 30.0):
        if pacing not in ('fast', 'realtime'):
            raise ValueError("pacing must be 'fast' or 'realtime'")
        self.pacing = pacing
        self.speed = speed
        self.strict = strict_order
        self.stall_timeout = stall_timeout
        self.stop_event = asyncio.Event()
        self.delivered = 0
        self.last_granted_ns = 0
        self.streams = 0
        self._tokens = []
        self._active = 0
        self._changed = asyncio.Event()
        self._t0_ns = None
        self._wall0 = None

    def register(self, name: str) -> _Token:
        token = _Token(len(self._tokens), name)
        self._tokens.append(token)
        self._active += 1
        self.streams += 1

        return token

    def _min_token(self) -> Optional[_Token]:
        best = None
        for token in self._tokens:
            if token.pending is not None and (best is None or token.pending < best.pending):
                best = token

        return best

    def reset_pending(self, token: _Token, ts_ns: Optional[int]):
        token.pending = (ts_ns, token.index) if ts_ns is not None else None
        self._changed.set()

    def stream_exhausted(self, token: _Token):
        if token.exhausted:
            return

        token.exhausted = True
        token.pending = None
        self._active -= 1

        if self._active <= 0:
            self.stop_event.set()

        self._changed.set()

    async def turn(self, token: _Token, ts_ns: int, next_ts_ns: Optional[int]) -> bool:
        entry = (ts_ns, token.index)
        token.pending = entry
        self._changed.set()

        if self._t0_ns is None:
            self._t0_ns = ts_ns
            self._wall0 = asyncio.get_running_loop().time()

        if self.strict:
            while True:
                if self.stop_event.is_set():
                    return False
                if token.pending != entry:
                    return False
                if self._min_token() is token:
                    break
                self._changed.clear()
                if self.stop_event.is_set() or token.pending != entry or self._min_token() is token:
                    continue
                try:
                    await asyncio.wait_for(self._changed.wait(), self.stall_timeout)
                except TimeoutError:
                    stuck = self._min_token()
                    if stuck is not None and stuck is not token:
                        LOG.warning('playback: stream %s stalled the timeline for %.0fs - skipping past it', stuck.name, self.stall_timeout)
                        stuck.pending = None
                        self._changed.set()

        if self.pacing == 'realtime':
            loop = asyncio.get_running_loop()
            delay = self._wall0 + (ts_ns - self._t0_ns) / 1e9 / self.speed - loop.time()

            if delay > 0:
                await asyncio.sleep(delay)

            if self.stop_event.is_set() or token.pending != entry:
                return False

        self.delivered += 1

        if ts_ns > self.last_granted_ns:
            self.last_granted_ns = ts_ns

        token.pending = (next_ts_ns, token.index) if next_ts_ns is not None else None
        self._changed.set()

        return True


class _PlaybackMixin:
    def _playback_init(self, sessions_inbound: List[List[tuple]], coordinator: PlaybackCoordinator, token: _Token):
        self._sessions_inbound = sessions_inbound
        self._coordinator = coordinator
        self._token = token
        self._session_idx = -1
        self._open_flag = False
        self._closed_event = asyncio.Event()
        self.writes = []

    @property
    def is_open(self) -> bool:
        return self._open_flag

    async def _open(self):
        self._session_idx += 1
        self._open_flag = True
        self._closed_event = asyncio.Event()
        self._reset_counters()

    async def write(self, data, *args, **kwargs):
        self.writes.append(data)
        self.sent += 1

    async def close(self):
        if not self._open_flag:
            return

        self._open_flag = False
        self._coordinator.reset_pending(self._token, self._first_ts_from(self._session_idx + 1))
        self._closed_event.set()

    def _first_ts_from(self, session_idx: int) -> Optional[int]:
        for inbound in self._sessions_inbound[session_idx:]:
            if inbound:
                return inbound[0][0]

        return None

    async def _replay_read(self):
        if not self._open_flag:
            raise ConnectionClosed

        session_idx = self._session_idx
        if session_idx < len(self._sessions_inbound):
            inbound = self._sessions_inbound[session_idx]

            for i, (ts_ns, payload) in enumerate(inbound):
                if not self._open_flag:
                    return
                next_ts = inbound[i + 1][0] if i + 1 < len(inbound) else self._first_ts_from(session_idx + 1)
                if not await self._coordinator.turn(self._token, ts_ns, next_ts):
                    return
                if not self._open_flag:
                    return
                self.received += 1
                self.last_message = ns_to_ts(ts_ns)
                yield payload

            if session_idx + 1 < len(self._sessions_inbound):
                return

        self._coordinator.stream_exhausted(self._token)
        await self._closed_event.wait()


class PlaybackWSConnection(_PlaybackMixin, WSAsyncConn):
    def __init__(self, address: str, conn_id: str, subscription, sessions_inbound, coordinator, token):
        AsyncConnection.__init__(self, conn_id, subscription=subscription)
        self.address = address
        self.ws_kwargs = {}
        self._playback_init(sessions_inbound, coordinator, token)

    async def read(self):
        async for payload in self._replay_read():
            yield payload


class PlaybackPollConnection(_PlaybackMixin, HTTPPoll):
    def __init__(self, address, conn_id: str, sessions_inbound, coordinator, token):
        AsyncConnection.__init__(self, conn_id)
        self.address = address if isinstance(address, list) else [address]
        self.proxy = None
        self.sleep = 0
        self.delay = 0
        self._playback_init(sessions_inbound, coordinator, token)

    async def read(self, header=None):
        async for payload in self._replay_read():
            yield payload


class PlaybackHTTPConn(HTTPAsyncConn):
    def __init__(self, conn_id: str, responses: Dict[str, List[tuple]], coordinator: PlaybackCoordinator):
        AsyncConnection.__init__(self, f'{conn_id}.playback.http')
        self.proxy = None
        self._responses = {url: ([ts for ts, _ in entries], [body for _, body in entries]) for url, entries in responses.items()}
        self._coordinator = coordinator
        self.served = 0
        self._closed = False

    @property
    def is_open(self) -> bool:
        return not self._closed

    async def _open(self):
        pass

    async def close(self):
        self._closed = True

    async def _serve(self, url: str, request_body=None) -> str:
        entry = self._responses.get((url, request_body))
        if entry is None:
            known = ', '.join(sorted(f'{u} {b or ""}'.strip() for u, b in self._responses)[:10])
            raise ConnectionClosed(f'playback: no recorded response for {url!r} body={request_body!r} - the capture holds: [{known}]')

        timestamps, bodies = entry
        index = min(bisect_left(timestamps, self._coordinator.last_granted_ns), len(timestamps) - 1)
        self.received += 1
        self.last_message = time.time()
        self.served += 1

        return bodies[index]

    async def read(self, address: str, header=None, params=None, retry_count=0, retry_delay=60) -> str:
        return await self._serve(request_url(address, params))

    async def write(self, address: str, msg=None, header=None, retry_count=0, retry_delay=60):
        body = msg.decode() if isinstance(msg, (bytes, bytearray)) else msg
        return await self._serve(address, body)


@dataclass
class PlaybackResult:
    messages_processed: int
    callbacks: Dict[str, int]
    http_requests_served: int
    streams: int
    duration: float


class _ChannelCounter:
    def __init__(self):
        self.counts = defaultdict(int)

    def callback(self, channel: str):
        async def count(obj, receipt_timestamp):
            self.counts[channel] += 1
        return count


def _canonical_sub(subscription) -> Optional[tuple]:
    if not subscription:
        return None

    return tuple(sorted((chan, tuple(sorted(str(s) for s in syms))) for chan, syms in subscription.items()))


class Replayer:
    def __init__(self, capture: Union[str, List[str], Capture], exchange: str = None, pacing: str = 'fast',
                 speed: float = 1.0, strict_order: bool = True, stall_timeout: float = 30.0,
                 on_error: str = 'reconnect'):
        if on_error not in ('reconnect', 'raise'):
            raise ValueError("on_error must be 'reconnect' or 'raise'")
        self.on_error = on_error
        if isinstance(capture, Capture):
            self.capture = capture
            self.metadata = None
        else:
            paths = [capture] if isinstance(capture, str) else list(capture)
            self.capture = read_capture(paths)
            self.metadata = self._load_metadata(paths[0])

        exchanges = sorted({s.exchange for s in self.capture.ws} | {s.exchange for s in self.capture.http})

        if exchange is None:
            if len(exchanges) == 1:
                exchange = exchanges[0]
            elif not exchanges:
                raise ValueError('capture contains no streams')
            else:
                raise ValueError(f'capture contains multiple exchanges {exchanges} - pass exchange=')
        elif exchange not in exchanges:
            raise ValueError(f'capture has no streams for {exchange} - it contains {exchanges}')

        self.exchange = exchange
        self.coordinator = PlaybackCoordinator(pacing=pacing, speed=speed, strict_order=strict_order, stall_timeout=stall_timeout)
        self.http_conn = None

        ws_groups = defaultdict(list)
        for session in self.capture.ws:
            if session.exchange == exchange:
                ws_groups[session.conn_id].append(session)

        for group in ws_groups.values():
            group.sort(key=lambda s: s.connect_ordinal)

        self._ws_groups = sorted(ws_groups.values(), key=lambda g: g[0].opened_ns)
        self._ws_assigned = [False] * len(self._ws_groups)

        http_groups = defaultdict(list)
        for session in self.capture.http:
            if session.exchange == exchange:
                http_groups[session.conn_id].append(session)

        self._poll_groups = []
        pool_requests = []

        for conn_id, group in sorted(http_groups.items(), key=lambda item: item[1][0].opened_ns):
            group.sort(key=lambda s: s.opened_ns)
            if self._is_poll(conn_id, group):
                self._poll_groups.append(group)
            else:
                for session in group:
                    pool_requests.extend(session.requests)
        self._poll_assigned = [False] * len(self._poll_groups)

        pool_requests.sort(key=lambda r: r[0])
        self._http_pool = defaultdict(list)
        for ts_ns, method, url, body, request_body in pool_requests:
            self._http_pool[(url, request_body)].append((ts_ns, body))

    @staticmethod
    def _load_metadata(pcap_path: str):
        try:
            with open(metadata_path(pcap_path)) as fp:
                return json.loads(fp.read())
        except OSError:
            return None

    def _is_poll(self, conn_id: str, group) -> bool:
        if any(session.poll for session in group):
            return True
        if self.metadata:
            for record in self.metadata.get('streams', []):
                if record.get('conn_id') == conn_id and record.get('kind') == 'http':
                    return record.get('address') is not None

        return conn_id.count('.http.') >= 2

    def wrap_connection(self, conn: AsyncConnection) -> AsyncConnection:
        if isinstance(conn, HTTPPoll):
            for i, group in enumerate(self._poll_groups):
                if self._poll_assigned[i]:
                    continue

                self._poll_assigned[i] = True
                sessions_inbound = [[(ts_ns, body) for ts_ns, method, url, body, _ in session.requests] for session in group]
                token = self.coordinator.register(conn.id)

                return PlaybackPollConnection(conn.address, conn.id, sessions_inbound, self.coordinator, token)

            raise ValueError(f'playback: no recorded HTTP poll stream available for {conn.id}')

        if isinstance(conn, WSAsyncConn):
            want = (conn.address, _canonical_sub(conn.subscription))

            for i, group in enumerate(self._ws_groups):
                if self._ws_assigned[i]:
                    continue

                if (group[0].address, _canonical_sub(group[0].subscription)) == want:
                    self._ws_assigned[i] = True
                    sessions_inbound = [[(ts_ns, payload) for ts_ns, direction, payload in session.messages if direction == 'in'] for session in group]
                    token = self.coordinator.register(conn.id)

                    return PlaybackWSConnection(conn.address, conn.id, conn.subscription, sessions_inbound, self.coordinator, token)

            recorded = [(g[0].address, g[0].subscription) for g in self._ws_groups]
            raise ValueError(f'playback: no recorded stream matches {conn.id} at {conn.address} with subscription {conn.subscription!r}. Recorded streams: {recorded!r}.')
        return conn


    def prepare(self, feed):
        if feed.id != self.exchange:
            raise ValueError(f'feed {feed.id} does not match capture exchange {self.exchange}')

        feed.timeout = -1
        feed.start_delay = 0
        feed.keepalive_interval = None

        if self.on_error == 'raise':
            feed.retries = 0
            if feed.exceptions is None:
                feed.exceptions = [Exception]
        else:
            feed.retries = -1

        self.http_conn = PlaybackHTTPConn(feed.id, self._http_pool, self.coordinator)
        feed.http_conn = self.http_conn
        feed._wrap_connection = self.wrap_connection
        self._prepare_symbols(feed)

    def _metadata_feed_entry(self, exchange: str):
        for entry in (self.metadata or {}).get('feeds', []):
            if entry.get('exchange') == exchange:
                return entry
        return None

    def _prepare_symbols(self, feed):
        Symbols.data.pop(feed.id, None)
        entry = self._metadata_feed_entry(feed.id)
        snapshot = entry.get('symbols_snapshot') if entry else None
        if not self._http_pool or (snapshot and self._missing_symbol_routes(feed)):
            if snapshot:
                Symbols.set(feed.id, snapshot['normalized'], snapshot['info'])
            elif not self._http_pool:
                raise ValueError(f'{feed.id}: capture has no recorded HTTP traffic and no symbol snapshot - '
                                 'symbols cannot be loaded offline. Record from a fresh process for a self-contained capture.')

    def _missing_symbol_routes(self, feed) -> list:
        try:
            urls = []
            for endpoint in feed.rest_endpoints:
                route = endpoint.route('instruments', sandbox=feed.sandbox)
                urls.extend(route if isinstance(route, list) else [route])
            recorded_urls = {url for url, _ in self._http_pool}
            return [url for url in urls if url not in recorded_urls]
        except Exception:
            return []

    def build_feed(self, callbacks=None, config=None):
        entry = self._metadata_feed_entry(self.exchange)
        if entry is None:
            raise ValueError(f'no metadata metadata for {self.exchange} - pass a constructed feed to playback() instead')
        from cryptofeed.exchanges import EXCHANGE_MAP
        kwargs = {key: value for key, value in (entry.get('kwargs') or {}).items() if value is not None}
        if entry.get('subscription'):
            kwargs['subscription'] = entry['subscription']
        else:
            kwargs['symbols'] = entry.get('symbols')
            kwargs['channels'] = entry.get('channels')
        return EXCHANGE_MAP[self.exchange](config=config, callbacks=callbacks, **kwargs)


async def playback_async(capture: Union[str, List[str], Capture], exchange: str = None, feed=None, callbacks: dict = None,
                         pacing: str = 'fast', speed: float = 1.0, strict_order: bool = True,
                         stall_timeout: float = 30.0, on_error: str = 'reconnect', config=None) -> PlaybackResult:
    replayer = Replayer(capture, exchange=exchange, pacing=pacing, speed=speed,
                        strict_order=strict_order, stall_timeout=stall_timeout, on_error=on_error)
    if feed is None:
        feed = replayer.build_feed(callbacks=callbacks, config=config)
    elif callbacks:
        for channel, cbs in callbacks.items():
            feed.callbacks[channel] = list(feed.callbacks[channel]) + (cbs if isinstance(cbs, list) else [cbs])

    counter = _ChannelCounter()
    for channel in list(feed.callbacks):
        feed.callbacks[channel] = list(feed.callbacks[channel]) + [counter.callback(channel)]

    replayer.prepare(feed)
    loop = asyncio.get_running_loop()
    start = loop.time()
    await feed.run(replayer.coordinator.stop_event)
    return PlaybackResult(
        messages_processed=replayer.coordinator.delivered,
        callbacks=dict(sorted(counter.counts.items())),
        http_requests_served=replayer.http_conn.served if replayer.http_conn else 0,
        streams=replayer.coordinator.streams,
        duration=loop.time() - start,
    )


def playback(capture: Union[str, List[str], Capture], exchange: str = None, feed=None, callbacks: dict = None,
             pacing: str = 'fast', speed: float = 1.0, strict_order: bool = True,
             stall_timeout: float = 30.0, on_error: str = 'reconnect', config=None) -> PlaybackResult:
    return asyncio.run(playback_async(capture, exchange=exchange, feed=feed, callbacks=callbacks,
                                      pacing=pacing, speed=speed, strict_order=strict_order,
                                      stall_timeout=stall_timeout, on_error=on_error, config=config))
