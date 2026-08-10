'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.

Macro benchmark: replay recordings through the real message handlers and report throughput.

    uv run python tools/bench_replay.py                      # every recording
    uv run python tools/bench_replay.py --exchange KRAKEN --repeat 5
    uv run python tools/bench_replay.py --profile KRAKEN     # cProfile the hot path
'''
import argparse
import cProfile
import glob
import os
import pstats
import resource
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptofeed.capture import playback   # noqa: E402
from cryptofeed.exchanges import EXCHANGE_MAP            # noqa: E402
from cryptofeed.symbols import Symbols                   # noqa: E402


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(REPO_ROOT, 'sample_data')
CONFIG = os.path.join(REPO_ROOT, 'tests', 'config_test.yaml')


def peak_rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # linux reports kilobytes, macOS bytes
    return usage / 1024 / 1024 if sys.platform == 'darwin' else usage / 1024


def corpus_file(exchange: str):
    matches = sorted(glob.glob(os.path.join(CORPUS, f'{exchange}.jsonl*')))
    return matches[0] if matches else None


def replay_once(path: str) -> tuple:
    Symbols.clear()
    try:
        started = time.perf_counter()
        result = playback(path, config=CONFIG)
        return time.perf_counter() - started, result
    finally:
        Symbols.clear()


def run(exchanges: list, repeat: int):
    rows = []
    total_messages = total_seconds = 0.0
    baseline_rss = peak_rss_mb()

    for exchange in exchanges:
        path = corpus_file(exchange)
        if path is None:
            print(f'{exchange:22} no recording')
            continue
        try:
            best = None
            for _ in range(repeat):
                elapsed, result = replay_once(path)
                if best is None or elapsed < best[0]:
                    best = (elapsed, result)
        except Exception as e:
            print(f'{exchange:22} FAILED: {type(e).__name__}: {e}')
            continue

        elapsed, result = best
        messages = result['messages_processed']
        callbacks = sum(result['callbacks'].values())
        rate = messages / elapsed if elapsed else 0
        rows.append((exchange, messages, callbacks, elapsed, rate))
        total_messages += messages
        total_seconds += elapsed
        print(f'{exchange:22} {messages:>7} msgs  {callbacks:>7} callbacks  '
              f'{elapsed * 1000:>8.1f} ms  {rate:>10,.0f} msg/s')

    if rows:
        print(f'\n{"total":22} {int(total_messages):>7} msgs  '
              f'{"":>7}             {total_seconds * 1000:>8.1f} ms  '
              f'{total_messages / total_seconds:>10,.0f} msg/s')
        print(f'peak RSS {peak_rss_mb():.0f} MB (baseline {baseline_rss:.0f} MB)')
    return rows


def profile(exchange: str, sort: str, limit: int):
    path = corpus_file(exchange)
    if path is None:
        print(f'{exchange}: no recording')
        return 1
    Symbols.clear()
    profiler = cProfile.Profile()
    profiler.enable()
    playback(path, config=CONFIG)
    profiler.disable()
    Symbols.clear()
    pstats.Stats(profiler).strip_dirs().sort_stats(sort).print_stats(limit)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--exchange', action='append', metavar='ID', help='replay one exchange (repeatable)')
    parser.add_argument('--repeat', type=int, default=3, help='replays per exchange, best wins (default 3)')
    parser.add_argument('--profile', metavar='ID', help='cProfile one exchange instead of timing all')
    parser.add_argument('--sort', default='cumtime', help='profile sort key (default cumtime)')
    parser.add_argument('--limit', type=int, default=25, help='profile rows to print')
    args = parser.parse_args()

    if args.profile:
        return profile(args.profile, args.sort, args.limit)

    exchanges = args.exchange or sorted(EXCHANGE_MAP)
    unknown = [e for e in exchanges if e not in EXCHANGE_MAP]
    if unknown:
        parser.error(f'unknown exchange(s): {unknown}')

    print(f'replaying {len(exchanges)} recording(s), best of {args.repeat}\n')
    rows = run(exchanges, args.repeat)
    return 0 if rows else 1


if __name__ == '__main__':
    sys.exit(main())
