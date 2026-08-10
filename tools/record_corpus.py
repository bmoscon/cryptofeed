'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.

Record the replay corpus used by the playback test layer.

Every exchange in EXCHANGE_MAP must have a stored recording (modernization plan D6), and
regenerating one must be a single command:

    uv run python tools/record_corpus.py --exchange KRAKEN
    uv run python tools/record_corpus.py --missing
    uv run python tools/record_corpus.py --all --seconds 45
'''
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptofeed import FeedHandler                                  # noqa: E402
from cryptofeed.defines import CANDLES                             # noqa: E402
from cryptofeed.exchanges import EXCHANGE_MAP                       # noqa: E402
from cryptofeed.capture import CaptureWriter                        # noqa: E402
from cryptofeed.symbols import Symbols                              # noqa: E402

from corpus_verify import find as find_recording, verify            # noqa: E402
from cryptofeed.capture import playback                             # noqa: E402

EXPECTATIONS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tests', 'playback', 'expected_counts.json')
TEST_CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tests', 'config_test.yaml')


def update_expectations(exchange: str, path: str):
    import json as _json

    Symbols.clear()
    try:
        result = playback(path, config=TEST_CONFIG, checksum_validation=True, cross_check=True)
    finally:
        Symbols.clear()
    with open(EXPECTATIONS) as fp:
        expectations = _json.load(fp)
    previous = expectations.get(exchange)
    expectations[exchange] = dict(sorted(result['callbacks'].items()))
    with open(EXPECTATIONS, 'w') as fp:
        _json.dump(dict(sorted(expectations.items())), fp, indent=2, sort_keys=True)
        fp.write('\n')
    return previous, expectations[exchange]

DEFAULT_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sample_data')
LIQUID_SYMBOLS = {
    'COINBASE': ['BTC-USD', 'ETH-USD'],
    'BYBIT': ['BTC-USDT-PERP', 'ETH-USDT-PERP', 'SOL-USDT-PERP', 'DOGE-USDT-PERP', 'BTC-USDT', 'ETH-USDT'],
}
SAMPLE_SIZE = {'BINANCE': 4, 'BINANCE_US': 4, 'COINBASE': 2}


def existing(exchange: str, out: str) -> list:
    path = find_recording(exchange, out)
    return [path] if path else []


LIQUID_BASES = ('BTC', 'ETH', 'SOL', 'XBT')
LIQUID_QUOTES = ('USD', 'USDT', 'USDC')


def rank(symbol: str) -> tuple:
    parts = symbol.split('-')
    base, quote = parts[0], (parts[1] if len(parts) > 1 else '')
    return (base not in LIQUID_BASES, quote not in LIQUID_QUOTES, len(parts), symbol)


async def pick_symbols(exchange: str, cls, count: int) -> list:
    symbols = list(await cls.load_symbols())
    if exchange in LIQUID_SYMBOLS:
        available = set(symbols)
        chosen = [s for s in LIQUID_SYMBOLS[exchange] if s in available]
        if chosen:
            return chosen
        print(f'  {exchange}: none of the preferred symbols are listed, ranking by liquidity instead')
    if not symbols:
        raise RuntimeError(f'{exchange}: no symbols available')
    return sorted(symbols, key=rank)[:count]


def pick_interval(cls):
    valid = cls.valid_candle_intervals
    if valid is NotImplemented or not valid:
        return None
    for preferred in ('1m', '5m', '1M'):
        if preferred in valid:
            return preferred
    return sorted(valid)[0]


async def record(exchange: str, cls, seconds: int, out: str):
    channels = sorted(c for c in cls.websocket_channels if not cls.is_authenticated_channel(c))
    symbols = await pick_symbols(exchange, cls, SAMPLE_SIZE.get(exchange, 10))
    kwargs = {}
    interval = pick_interval(cls)
    if interval and CANDLES in channels:
        kwargs['candle_interval'] = interval
        kwargs['candle_closed_only'] = False

    print(f'  channels={channels} symbols={symbols}' + (f' interval={interval}' if interval else ''))
    Symbols.clear()
    fh = FeedHandler(capture=CaptureWriter(out), config={'uvloop': False, 'log': {'disabled': True}})
    fh.add_feed(cls(symbols=symbols, channels=channels, **kwargs))
    asyncio.get_running_loop().call_later(seconds, fh.request_stop)
    await fh.run_async(install_signal_handlers=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--exchange', action='append', metavar='ID', help='exchange id to record (repeatable)')
    group.add_argument('--all', action='store_true', help='record every exchange')
    group.add_argument('--missing', action='store_true', help='record only exchanges with no stored recording')
    parser.add_argument('--seconds', type=int, default=30, help='how long to stream each exchange (default 30)')
    parser.add_argument('--out', default=DEFAULT_OUT, help='corpus directory')
    parser.add_argument('--force', action='store_true', help='replace an existing recording')
    parser.add_argument('--no-expectations', dest='expectations', action='store_false',
                        help='do not update tests/playback/expected_counts.json')
    args = parser.parse_args()

    if args.all:
        targets = list(EXCHANGE_MAP)
    elif args.missing:
        targets = [e for e in EXCHANGE_MAP if not existing(e, args.out)]
        if not targets:
            print('every exchange already has a recording')
            return 0
    else:
        targets = args.exchange
        unknown = [e for e in targets if e not in EXCHANGE_MAP]
        if unknown:
            parser.error(f'unknown exchange(s): {unknown}. Known: {sorted(EXCHANGE_MAP)}')

    os.makedirs(args.out, exist_ok=True)
    failures = []
    for exchange in targets:
        old = existing(exchange, args.out)
        if old and not args.force:
            print(f'{exchange}: already recorded ({len(old)} files) - pass --force to replace')
            continue
        print(f'{exchange}: recording {args.seconds}s')
        for path in old:
            os.remove(path)
        try:
            asyncio.run(record(exchange, EXCHANGE_MAP[exchange], args.seconds, args.out))
        except Exception as e:
            print(f'  FAILED to record: {type(e).__name__}: {e}')
            failures.append(exchange)
            continue

        files = existing(exchange, args.out)
        if not files:
            print('  FAILED: recording produced no file')
            failures.append(exchange)
            continue
        try:
            result = verify(files[0])
        except Exception as e:
            print(f'  FAILED verification: {type(e).__name__}: {e}')
            failures.append(exchange)
            continue
        counts = result['counts']
        print(f"  wrote {os.path.basename(files[0])}: {counts.get('recv', 0)} frames, {counts.get('http', 0)} http, {result['size'] / 1024:.0f} KB")

        if args.expectations:
            try:
                previous, current = update_expectations(exchange, files[0])
            except Exception as e:
                print(f'  FAILED to replay the new recording: {type(e).__name__}: {e}')
                failures.append(exchange)
                continue
            print(f'  expectations {previous} -> {current}')

    if failures:
        print(f'\nfailed: {failures}')
        return 1
    print('\nall recordings verified')
    return 0


if __name__ == '__main__':
    sys.exit(main())
