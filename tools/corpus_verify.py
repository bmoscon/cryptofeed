'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.

Validate stored corpus v2 recordings without touching the network.

    uv run python tools/corpus_verify.py --all
    uv run python tools/corpus_verify.py --exchange KRAKEN
'''
import argparse
import glob
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptofeed import _json as json                                              # noqa: E402
from cryptofeed import _zstd                                                      # noqa: E402
from cryptofeed.capture import CaptureReader, corpus_filename, payload_of         # noqa: E402
from cryptofeed.exchanges import EXCHANGE_MAP                                     # noqa: E402


DEFAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sample_data')
REQUIRED = {'header': ('format', 'exchange', 'config'), 'connect': ('conn', 'ts', 'addr'),
            'send': ('conn', 'ts'), 'recv': ('conn', 'ts'), 'http': ('conn', 'ts', 'url')}


def decode(payload):
    if isinstance(payload, str):
        return payload
    for decompress in (lambda b: b.decode(),
                       lambda b: zlib.decompress(b, 16 + zlib.MAX_WBITS).decode(),   # gzip
                       lambda b: zlib.decompress(b, -15).decode()):                  # raw deflate
        try:
            return decompress(payload)
        except Exception:
            continue
    return None


def verify(path: str) -> dict:
    reader = CaptureReader(path)
    counts = {}
    for number, record in enumerate(reader.records(), start=2):
        kind = record.get('t')
        if kind not in REQUIRED:
            raise ValueError(f'line {number}: unknown record type {kind!r}')
        missing = [f for f in REQUIRED[kind] if f not in record]
        if missing:
            raise ValueError(f'line {number}: {kind} record missing {missing}')
        counts[kind] = counts.get(kind, 0) + 1

        if kind in ('recv', 'http'):
            payload = payload_of(record)
            if payload is None:
                raise ValueError(f'line {number}: {kind} record has no payload')
            text = decode(payload)
            if text is None:
                raise ValueError(f'line {number}: payload is neither text nor recognised compression')
            try:
                json.loads(text)
            except Exception as e:
                raise ValueError(f'line {number}: payload does not parse as JSON: {e}') from None

    if not counts.get('recv'):
        raise ValueError('no received frames - a recording with no market data is not usable')
    return {'exchange': reader.exchange, 'channels': sorted(reader.config), 'counts': counts,
            'size': os.path.getsize(path)}


def find(exchange: str, directory: str):
    for compressed in (True, False):
        path = os.path.join(directory, corpus_filename(exchange, compressed))
        if os.path.exists(path):
            return path
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--exchange', action='append', metavar='ID', help='exchange to verify (repeatable)')
    group.add_argument('--all', action='store_true', help='verify every stored recording')
    group.add_argument('--file', action='append', help='verify a specific capture file')
    parser.add_argument('--dir', default=DEFAULT_DIR, help='corpus directory')
    args = parser.parse_args()

    if args.file:
        paths = args.file
    elif args.all:
        paths = sorted(glob.glob(os.path.join(args.dir, f'*.jsonl{_zstd.SUFFIX}'))) + sorted(glob.glob(os.path.join(args.dir, '*.jsonl')))
    else:
        paths = []
        for exchange in args.exchange:
            path = find(exchange, args.dir)
            if path is None:
                print(f'{exchange:22} NO RECORDING')
                return 1
            paths.append(path)

    failures = []
    for path in paths:
        try:
            result = verify(path)
        except Exception as e:
            print(f'{os.path.basename(path):34} FAILED: {type(e).__name__}: {e}')
            failures.append(path)
            continue
        counts = result['counts']
        print(f"{result['exchange']:22} {counts.get('recv', 0):>6} frames  {counts.get('http', 0):>3} http  "
              f"{result['size'] / 1e6:>5.2f} MB  channels={','.join(result['channels'])}")

    if args.all:
        missing = [e for e in EXCHANGE_MAP if find(e, args.dir) is None]
        if missing:
            print(f'\nexchanges with no recording: {missing}')
            return 1
        print(f'\n{len(paths)} recordings verified, every exchange covered')

    if failures:
        print(f'\nfailed: {[os.path.basename(p) for p in failures]}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
