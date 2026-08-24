'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


pcap codec for cryptofeed captures.

Writes decrypted exchange traffic (websocket messages and HTTP request/response
pairs) into standard pcap files by synthesizing Ethernet/IPv4/TCP framing around
the application payloads. One synthetic TCP conversation per connect-cycle of
each cryptofeed connection. The server side of every conversation is port 80 so
Wireshark's HTTP dissector runs, sees the synthesized websocket upgrade, and
dissects the frames automatically.

The reader in this module parses only the canonical form produced by the writer
(in-order segments, no retransmits, fixed header sizes) - it is not a general
pcap reader and raises on anything it did not write.
'''
import base64
import hashlib
import struct
from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urlsplit

from cryptofeed import _json as json
from cryptofeed.capture._zstd import ZSTD_MAGIC, open_read as zstd_open_read, open_write as zstd_open_write


PCAP_MAGIC_NS = 0xa1b23c4d
LINKTYPE_ETHERNET = 1
SNAPLEN = 262144

CLIENT_MAC = bytes.fromhex('024346440001')
SERVER_MAC = bytes.fromhex('024346440002')
CLIENT_IP = bytes([10, 0, 0, 1])
SERVER_IP = bytes([10, 0, 0, 2])
SERVER_PORT = 80
BASE_CLIENT_PORT = 40000
MAX_SEGMENT = 65495

WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
WS_KEY = base64.b64encode(b'cryptofeed-pcap!').decode()
WS_ACCEPT = base64.b64encode(hashlib.sha1((WS_KEY + WS_GUID).encode()).digest()).decode()

META_CONN_ID = 'X-Cryptofeed-Conn-Id'
META_EXCHANGE = 'X-Cryptofeed-Exchange'
META_ADDRESS = 'X-Cryptofeed-Address'
META_ORDINAL = 'X-Cryptofeed-Connect-Ordinal'
META_SUBSCRIPTION = 'X-Cryptofeed-Subscription'
META_RESUMED = 'X-Cryptofeed-Resumed'
META_URL = 'X-Cryptofeed-Url'
META_KIND = 'X-Cryptofeed-Kind'

FIN, SYN, PSH, ACK = 0x01, 0x02, 0x08, 0x10


def ts_to_ns(ts: float) -> int:
    m, e = float(ts).as_integer_ratio()
    return (m * 1_000_000_000 + (e >> 1)) // e


def ns_to_ts(ns: int) -> float:
    return ns / 1_000_000_000


def _checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b'\x00'

    s = sum(struct.unpack(f'!{len(data) // 2}H', data))

    while s >> 16:
        s = (s & 0xffff) + (s >> 16)

    return ~s & 0xffff


def _tcp_packet(client_to_server: bool, client_port: int, seq: int, ack: int, flags: int, payload: bytes, ip_id: int) -> bytes:
    if client_to_server:
        src_ip, dst_ip, src_mac, dst_mac = CLIENT_IP, SERVER_IP, CLIENT_MAC, SERVER_MAC
        sport, dport = client_port, SERVER_PORT
    else:
        src_ip, dst_ip, src_mac, dst_mac = SERVER_IP, CLIENT_IP, SERVER_MAC, CLIENT_MAC
        sport, dport = SERVER_PORT, client_port

    tcp_len = 20 + len(payload)
    ip = struct.pack('!BBHHHBBH4s4s', 0x45, 0, 20 + tcp_len, ip_id, 0x4000, 64, 6, 0, src_ip, dst_ip)
    ip = ip[:10] + struct.pack('!H', _checksum(ip)) + ip[12:]

    tcp = struct.pack('!HHIIBBHHH', sport, dport, seq & 0xffffffff, ack & 0xffffffff, 5 << 4, flags, 65535, 0, 0)
    pseudo = struct.pack('!4s4sBBH', src_ip, dst_ip, 0, 6, tcp_len)
    tcp = tcp[:16] + struct.pack('!H', _checksum(pseudo + tcp + payload)) + tcp[18:]

    return dst_mac + src_mac + b'\x08\x00' + ip + tcp + payload


def ws_frame(payload: bytes, opcode: int, masked: bool) -> bytes:
    header = bytearray([0x80 | opcode])
    mask_bit = 0x80 if masked else 0
    n = len(payload)

    if n < 126:
        header.append(mask_bit | n)
    elif n < 65536:
        header.append(mask_bit | 126)
        header += struct.pack('!H', n)
    else:
        header.append(mask_bit | 127)
        header += struct.pack('!Q', n)

    if masked:
        header += b'\x00\x00\x00\x00'

    return bytes(header) + payload


def _http_block(lines: List[str]) -> bytes:
    return ('\r\n'.join(lines) + '\r\n\r\n').encode()


class PcapFile:
    FLUSH_BYTES = 1 << 20

    def __init__(self, path: str):
        self.path = path
        self._fp = zstd_open_write(path) if path.endswith('.zst') else open(path, 'wb')
        self._buf = bytearray(struct.pack('<IHHiIII', PCAP_MAGIC_NS, 2, 4, 0, 0, SNAPLEN, LINKTYPE_ETHERNET))
        self._written = 0

    @property
    def size(self) -> int:
        return self._written + len(self._buf)

    def add_record(self, ts_ns: int, frame: bytes):
        sec, nsec = divmod(ts_ns, 1_000_000_000)
        self._buf += struct.pack('<IIII', sec, nsec, len(frame), len(frame))
        self._buf += frame

        if len(self._buf) >= self.FLUSH_BYTES:
            self.flush()

    def flush(self):
        if self._fp is None:
            return

        if self._buf:
            self._fp.write(self._buf)
            self._written += len(self._buf)
            self._buf = bytearray()

        self._fp.flush()

    def close(self):
        if self._fp is None:
            return

        self.flush()
        self._fp.close()
        self._fp = None


class TcpStream:
    def __init__(self, pcap: PcapFile, client_port: int, ts_ns: int):
        self.pcap = pcap
        self.client_port = client_port
        self._ip_id = 0
        self.client_seq = 1
        self.server_seq = 1
        self.closed = False
        self._packet(ts_ns, True, SYN, b'', 0, 0)
        self._packet(ts_ns, False, SYN | ACK, b'', 0, 1)
        self._packet(ts_ns, True, ACK, b'', 1, 1)

    def _packet(self, ts_ns: int, client_to_server: bool, flags: int, payload: bytes, seq: int, ack: int):
        self._ip_id = (self._ip_id + 1) & 0xffff
        self.pcap.add_record(ts_ns, _tcp_packet(client_to_server, self.client_port, seq, ack, flags, payload, self._ip_id))

    def send(self, ts_ns: int, client_to_server: bool, payload: bytes):
        view = memoryview(payload)

        for off in range(0, len(payload), MAX_SEGMENT):
            seg = bytes(view[off:off + MAX_SEGMENT])

            if client_to_server:
                self._packet(ts_ns, True, PSH | ACK, seg, self.client_seq, self.server_seq)
                self.client_seq += len(seg)
            else:
                self._packet(ts_ns, False, PSH | ACK, seg, self.server_seq, self.client_seq)
                self.server_seq += len(seg)

    def close(self, ts_ns: int):
        if self.closed:
            return

        self.closed = True
        self._packet(ts_ns, True, FIN | ACK, b'', self.client_seq, self.server_seq)
        self.client_seq += 1
        self._packet(ts_ns, False, FIN | ACK, b'', self.server_seq, self.client_seq)
        self.server_seq += 1
        self._packet(ts_ns, True, ACK, b'', self.client_seq, self.server_seq)


class WSStream:
    def __init__(self, pcap: PcapFile, client_port: int, ts_ns: int, address: str, meta: Dict[str, str]):
        parsed = urlsplit(address)
        path = parsed.path or '/'

        if parsed.query:
            path += '?' + parsed.query

        self.tcp = TcpStream(pcap, client_port, ts_ns)
        request = [f'GET {path} HTTP/1.1', f'Host: {parsed.netloc}', 'Upgrade: websocket', 'Connection: Upgrade', f'Sec-WebSocket-Key: {WS_KEY}', 'Sec-WebSocket-Version: 13']
        request += [f'{key}: {value}' for key, value in meta.items()]
        self.tcp.send(ts_ns, True, _http_block(request))
        self.tcp.send(ts_ns, False, _http_block(['HTTP/1.1 101 Switching Protocols', 'Upgrade: websocket',
                                                 'Connection: Upgrade', f'Sec-WebSocket-Accept: {WS_ACCEPT}']))

    def message(self, ts_ns: int, data: Union[str, bytes]):
        if isinstance(data, str):
            self.tcp.send(ts_ns, False, ws_frame(data.encode(), 0x1, False))
        else:
            self.tcp.send(ts_ns, False, ws_frame(bytes(data), 0x2, False))

    def sent(self, ts_ns: int, data: Union[str, bytes]):
        if isinstance(data, str):
            self.tcp.send(ts_ns, True, ws_frame(data.encode(), 0x1, True))
        else:
            self.tcp.send(ts_ns, True, ws_frame(bytes(data), 0x2, True))

    def close(self, ts_ns: int):
        self.tcp.close(ts_ns)


class HTTPStream:
    def __init__(self, pcap: PcapFile, client_port: int, ts_ns: int, meta: Dict[str, str]):
        self.meta = dict(meta)
        self.tcp = TcpStream(pcap, client_port, ts_ns)

    def exchange(self, ts_ns: int, method: str, url: str, response_body: Union[str, bytes], request_body: Union[str, bytes, None] = None):
        parsed = urlsplit(url)
        path = parsed.path or '/'

        if parsed.query:
            path += '?' + parsed.query

        request = [f'{method} {path} HTTP/1.1', f'Host: {parsed.netloc}', f'{META_URL}: {url}']
        request += [f'{key}: {value}' for key, value in self.meta.items()]
        body = b''

        if request_body is not None:
            body = request_body.encode() if isinstance(request_body, str) else bytes(request_body)
            request.append(f'Content-Length: {len(body)}')

        self.tcp.send(ts_ns, True, _http_block(request) + body)

        response = response_body.encode() if isinstance(response_body, str) else bytes(response_body)
        head = ['HTTP/1.1 200 OK', 'Content-Type: application/json; charset=utf-8',
                f'Content-Length: {len(response)}', 'Connection: keep-alive']
        self.tcp.send(ts_ns, False, _http_block(head) + response)

    def close(self, ts_ns: int):
        self.tcp.close(ts_ns)


@dataclass
class WSSession:
    conn_id: str
    exchange: str
    address: str
    subscription: Optional[dict]
    connect_ordinal: int
    client_port: int
    opened_ns: int
    resumed: bool = False
    # ts_ns, 'in' | 'out', payload
    messages: List[Tuple[int, str, Union[str, bytes]]] = field(default_factory=list)


@dataclass
class HTTPSession:
    conn_id: str
    exchange: str
    client_port: int
    opened_ns: int
    resumed: bool = False
    poll: bool = False
    # ts_ns, method, url, response_body, request_body
    requests: List[Tuple[int, str, str, str, Optional[str]]] = field(default_factory=list)


@dataclass
class Capture:
    ws: List[WSSession] = field(default_factory=list)
    http: List[HTTPSession] = field(default_factory=list)


class _Direction:
    def __init__(self):
        self.chunks = []
        self.starts = []
        self.length = 0

    def add(self, ts_ns: int, payload: bytes):
        self.chunks.append((ts_ns, payload))
        self.starts.append(self.length)
        self.length += len(payload)

    def data(self) -> bytes:
        return b''.join(payload for _, payload in self.chunks)

    def ts_at(self, offset: int) -> int:
        return self.chunks[bisect_right(self.starts, offset) - 1][0]


def _iter_records(path: str):
    with open(path, 'rb') as raw:
        compressed = raw.read(4) == ZSTD_MAGIC

    with (zstd_open_read(path) if compressed else open(path, 'rb')) as fp:
        header = fp.read(24)

        if len(header) < 24:
            raise ValueError(f'{path}: truncated pcap header')
        magic = struct.unpack('<I', header[:4])[0]

        if magic != PCAP_MAGIC_NS:
            raise ValueError(f'{path}: not a cryptofeed capture (magic 0x{magic:08x}, expected nanosecond pcap 0x{PCAP_MAGIC_NS:08x})')

        while True:
            rec = fp.read(16)

            if not rec:
                return
            if len(rec) < 16:
                raise ValueError(f'{path}: truncated record header')

            sec, nsec, caplen, origlen = struct.unpack('<IIII', rec)
            frame = fp.read(caplen)

            if len(frame) < caplen:
                raise ValueError(f'{path}: truncated record')

            yield sec * 1_000_000_000 + nsec, frame


def _parse_headers(block: bytes) -> Tuple[str, Dict[str, str]]:
    lines = block.decode().split('\r\n')
    headers = {}

    for line in lines[1:]:
        if not line:
            continue
        key, _, value = line.partition(': ')
        headers[key.lower()] = value

    return lines[0], headers


def _split_http_head(data: bytes, offset: int, context: str) -> Tuple[str, Dict[str, str], int]:
    end = data.find(b'\r\n\r\n', offset)

    if end == -1:
        raise ValueError(f'{context}: missing HTTP header terminator')

    first, headers = _parse_headers(data[offset:end])

    return first, headers, end + 4


def _parse_ws_frames(direction: _Direction, offset: int, tag: str, context: str):
    data = direction.data()
    out = []

    while offset < len(data):
        if offset + 2 > len(data):
            raise ValueError(f'{context}: truncated websocket frame header')

        opcode = data[offset] & 0x0f
        masked = bool(data[offset + 1] & 0x80)
        n = data[offset + 1] & 0x7f
        cursor = offset + 2

        if n == 126:
            n = struct.unpack('!H', data[cursor:cursor + 2])[0]
            cursor += 2
        elif n == 127:
            n = struct.unpack('!Q', data[cursor:cursor + 8])[0]
            cursor += 8

        if masked:
            cursor += 4

        if cursor + n > len(data):
            raise ValueError(f'{context}: truncated websocket frame payload')

        payload = data[cursor:cursor + n]

        if opcode == 0x1:
            out.append((direction.ts_at(offset), tag, payload.decode()))
        elif opcode == 0x2:
            out.append((direction.ts_at(offset), tag, payload))
        else:
            raise ValueError(f'{context}: unexpected websocket opcode 0x{opcode:x}')
        offset = cursor + n

    return out


def _parse_ws_session(client: _Direction, server: _Direction, client_port: int, opened_ns: int, context: str) -> WSSession:
    _, headers, offset_c = _split_http_head(client.data(), 0, context)
    _, _, offset_s = _split_http_head(server.data(), 0, context)

    subscription = headers.get(META_SUBSCRIPTION.lower())
    session = WSSession(
        conn_id=headers.get(META_CONN_ID.lower(), ''),
        exchange=headers.get(META_EXCHANGE.lower(), ''),
        address=headers.get(META_ADDRESS.lower(), ''),
        subscription=json.loads(subscription) if subscription else None,
        connect_ordinal=int(headers.get(META_ORDINAL.lower(), 1)),
        client_port=client_port,
        opened_ns=opened_ns,
        resumed=META_RESUMED.lower() in headers,
    )

    inbound = _parse_ws_frames(server, offset_s, 'in', context)
    outbound = _parse_ws_frames(client, offset_c, 'out', context)
    merged = []
    i = j = 0

    while i < len(inbound) or j < len(outbound):
        if j >= len(outbound) or (i < len(inbound) and inbound[i][0] < outbound[j][0]):
            merged.append(inbound[i])
            i += 1
        else:
            merged.append(outbound[j])
            j += 1

    session.messages = merged

    return session


def _parse_http_session(client: _Direction, server: _Direction, client_port: int, opened_ns: int, context: str) -> HTTPSession:
    session = HTTPSession(conn_id='', exchange='', client_port=client_port, opened_ns=opened_ns)
    requests = []
    data = client.data()
    offset = 0

    while offset < len(data):
        start = offset
        request_line, headers, offset = _split_http_head(data, offset, context)
        n = int(headers.get('content-length', 0))
        request_body = data[offset:offset + n].decode() if n else None
        offset += n
        method = request_line.split(' ', 1)[0]
        requests.append((client.ts_at(start), method, headers.get(META_URL.lower(), ''), request_body))
        session.conn_id = headers.get(META_CONN_ID.lower(), session.conn_id)
        session.exchange = headers.get(META_EXCHANGE.lower(), session.exchange)
        session.resumed = session.resumed or META_RESUMED.lower() in headers
        session.poll = session.poll or headers.get(META_KIND.lower()) == 'poll'

    responses = []
    data = server.data()
    offset = 0

    while offset < len(data):
        _, headers, offset = _split_http_head(data, offset, context)
        n = int(headers.get('content-length', 0))
        responses.append(data[offset:offset + n].decode())
        offset += n

    if len(requests) != len(responses):
        raise ValueError(f'{context}: {len(requests)} requests but {len(responses)} responses')

    session.requests = [(ts, method, url, body, request_body) for (ts, method, url, request_body), body in zip(requests, responses)]

    return session


def read_capture(paths: Union[str, List[str]]) -> Capture:
    if isinstance(paths, str):
        paths = [paths]

    capture = Capture()
    ws_index = {}
    http_index = {}

    for path in paths:
        streams = {}
        for ts_ns, frame in _iter_records(path):
            if len(frame) < 54 or frame[12:14] != b'\x08\x00':
                raise ValueError(f'{path}: unexpected non-IPv4 frame')
            if frame[23] != 6 or (frame[14] >> 4) != 4 or (frame[14] & 0x0f) != 5:
                raise ValueError(f'{path}: unexpected IP framing')

            sport, dport = struct.unpack('!HH', frame[34:38])
            client_to_server = dport == SERVER_PORT
            client_port = sport if client_to_server else dport
            total_len = struct.unpack('!H', frame[16:18])[0]
            payload = frame[54:14 + total_len]

            if client_port not in streams:
                streams[client_port] = (ts_ns, _Direction(), _Direction())
            if payload:
                _, client, server = streams[client_port]
                (client if client_to_server else server).add(ts_ns, payload)

        for client_port in sorted(streams, key=lambda p: streams[p][0]):
            opened_ns, client, server = streams[client_port]

            if not client.length and not server.length:
                continue
            if not client.length:
                raise ValueError(f'{path}: stream on port {client_port} has no client data')

            context = f'{path}:port {client_port}'
            _, headers, _ = _split_http_head(client.data(), 0, context)

            if headers.get('upgrade') == 'websocket':
                session = _parse_ws_session(client, server, client_port, opened_ns, context)
                key = (session.conn_id, session.connect_ordinal)
                if session.resumed and key in ws_index:
                    ws_index[key].messages.extend(session.messages)
                else:
                    ws_index[key] = session
                    capture.ws.append(session)
            else:
                session = _parse_http_session(client, server, client_port, opened_ns, context)
                key = session.conn_id
                if session.resumed and key in http_index:
                    http_index[key].requests.extend(session.requests)
                else:
                    http_index[key] = session
                    capture.http.append(session)

    capture.ws.sort(key=lambda s: s.opened_ns)
    capture.http.sort(key=lambda s: s.opened_ns)

    return capture
