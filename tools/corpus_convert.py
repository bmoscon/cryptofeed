'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.

Convert a corpus v1 recording (delimiter-separated text, one file per connection) into the
v2 format (one zstd JSONL file per exchange).

    uv run python tools/corpus_convert.py --all
    uv run python tools/corpus_convert.py --exchange KRAKEN --keep
'''
import argparse
import ast
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptofeed import _json as json                                  # noqa: E402
from cryptofeed import _zstd                                          # noqa: E402
from cryptofeed.capture import FORMAT_VERSION, corpus_filename        # noqa: E402
from cryptofeed.exchanges import EXCHANGE_MAP                         # noqa: E402


DEFAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sample_data')


def bytes_repr_to_bytes(text: str) -> bytes:
    return ast.parse(text).body[0].value.value


def v1_files(exchange: str, directory: str) -> dict:
    found = {'meta': [], 'http': [], 'ws': []}
    for path in sorted(glob.glob(os.path.join(directory, f'{exchange}.*'))):
        name = os.path.basename(path)
        if name.endswith('.jsonl') or name.endswith('.jsonl' + _zstd.SUFFIX):
            continue
        if '.ws.' in name:
            found['ws'].append(path)
        elif '.http.' in name:
            found['http'].append(path)
        else:
            found['meta'].append(path)
    return found


def conn_id(path: str) -> str:
    name = os.path.basename(path)
    return name.rsplit('.', 1)[0]


def parse_http_line(line: str):
    url, rest = line.split(' -> ', 1)
    ts, data = rest.split(': ', 1)
    headers = None
    if ' header: ' in data:
        data, header_text = data.rsplit(' header: ', 1)
        headers = json.loads(header_text.strip())
    return url.strip(), float(ts), data.strip(), headers


def convert(exchange: str, directory: str, compress: bool = True) -> tuple:
    files = v1_files(exchange, directory)
    if not any(files.values()):
        raise FileNotFoundError(f'{exchange}: no v1 recording in {directory}')

    records = []
    config = None
    candle_interval = None
    recorded = None

    # metadata file: the feed configuration plus any HTTP responses captured by the old
    # synchronous symbol loader
    for path in files['meta']:
        for line in open(path, encoding='utf-8', errors='ignore'):
            line = line.rstrip('\n')
            if not line:
                continue
            if line.startswith('configuration:'):
                config = json.loads(line.split(': ', 1)[1])
                continue
            if ' -> ' in line:
                url, ts, data, headers = parse_http_line(line)
                recorded = recorded or ts
                record = {'t': 'http', 'conn': f'{exchange}.http.sync', 'ts': ts, 'url': url, 'data': data}
                if headers:
                    record['headers'] = headers
                records.append(record)

    for path in files['http']:
        for line in open(path, encoding='utf-8', errors='ignore'):
            line = line.rstrip('\n')
            if not line or ' -> ' not in line:
                continue
            url, ts, data, headers = parse_http_line(line)
            recorded = recorded or ts
            record = {'t': 'http', 'conn': conn_id(path), 'ts': ts, 'url': url, 'data': data}
            if headers:
                record['headers'] = headers
            records.append(record)

    for path in files['ws']:
        conn = conn_id(path)
        for line in open(path, encoding='utf-8', errors='ignore'):
            line = line.rstrip('\n')
            if not line:
                continue
            if line.startswith('wss') or line.startswith('ws:'):
                if ' <-> ' in line:
                    addr, ts = line.split(' <-> ', 1)
                    records.append({'t': 'connect', 'conn': conn, 'ts': float(ts), 'addr': addr.strip()})
                elif ' <- ' in line:
                    addr, rest = line.split(' <- ', 1)
                    ts, data = rest.split(': ', 1)
                    records.append({'t': 'send', 'conn': conn, 'ts': float(ts), 'addr': addr.strip(), 'data': data})
                continue
            ts, data = line.split(': ', 1)
            record = {'t': 'recv', 'conn': conn, 'ts': float(ts)}
            if data.startswith("b'") or data.startswith('b"'):
                import base64
                record['b64'] = base64.b64encode(bytes_repr_to_bytes(data)).decode()
            else:
                record['data'] = data
            records.append(record)

    if config is None:
        raise ValueError(f'{exchange}: no configuration line found, cannot write a v2 header')

    header = {'t': 'header', 'format': FORMAT_VERSION, 'exchange': exchange, 'config': config,
              'candle_interval': candle_interval, 'recorded': recorded, 'converted_from': 1}

    out = os.path.join(directory, corpus_filename(exchange, compress))
    payload = ('\n'.join([json.dumps(header)] + [json.dumps(r) for r in records]) + '\n').encode()
    with (_zstd.open(out, 'wb') if compress else open(out, 'wb')) as fp:
        fp.write(payload)

    before = sum(os.path.getsize(p) for group in files.values() for p in group)
    return out, before, os.path.getsize(out), len(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--exchange', action='append', metavar='ID', help='exchange to convert (repeatable)')
    group.add_argument('--all', action='store_true', help='convert every exchange with a v1 recording')
    parser.add_argument('--dir', default=DEFAULT_DIR, help='corpus directory')
    parser.add_argument('--keep', action='store_true', help='keep the v1 files instead of deleting them')
    parser.add_argument('--no-compress', action='store_true', help='write plain .jsonl')
    args = parser.parse_args()

    targets = [e for e in EXCHANGE_MAP if any(v1_files(e, args.dir).values())] if args.all else args.exchange
    if not targets:
        print('nothing to convert')
        return 0

    total_before = total_after = 0
    failures = []
    for exchange in targets:
        try:
            out, before, after, count = convert(exchange, args.dir, compress=not args.no_compress)
        except Exception as e:
            print(f'{exchange:22} FAILED: {type(e).__name__}: {e}')
            failures.append(exchange)
            continue
        total_before += before
        total_after += after
        print(f'{exchange:22} {count:>6} records  {before / 1e6:>7.2f} MB -> {after / 1e6:>6.2f} MB  {os.path.basename(out)}')
        if not args.keep:
            for path in [p for g in v1_files(exchange, args.dir).values() for p in g]:
                os.remove(path)

    print(f'\ntotal {total_before / 1e6:.1f} MB -> {total_after / 1e6:.1f} MB '
          f'({total_after / total_before * 100:.1f}%)' if total_before else '')
    if failures:
        print(f'failed: {failures}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
