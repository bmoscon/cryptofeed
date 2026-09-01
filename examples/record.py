'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import argparse
import asyncio

from cryptofeed import FeedHandler
from cryptofeed.capture.recorder import metadata_path
from cryptofeed.connection import connection_stats
from cryptofeed.defines import L2_BOOK, TRADES


def parse_args():
    parser = argparse.ArgumentParser(description='record live exchange data to a pcap capture')
    parser.add_argument('exchange', help='exchange id, e.g. COINBASE')
    parser.add_argument('symbols', nargs='+', help='normalized symbols, e.g. BTC-USD')
    parser.add_argument('--channels', nargs='+', default=[TRADES, L2_BOOK], help='channels to subscribe')
    parser.add_argument('--duration', type=float, default=60.0, help='seconds to record')
    parser.add_argument('--out', default='captures/', help='output pcap file or directory')
    parser.add_argument('--rotate', type=int, default=None, help='rotate the capture at this many bytes')
    return parser.parse_args()


async def main():
    args = parse_args()
    from cryptofeed.capture import PcapRecorder
    recorder = PcapRecorder(args.out, rotate_size=args.rotate)
    fh = FeedHandler(record=recorder)
    fh.add_feed(args.exchange, symbols=args.symbols, channels=args.channels, callbacks={})

    async def stop_later():
        await asyncio.sleep(args.duration)
        print(f'{args.duration:.0f}s elapsed - stopping')
        fh.request_stop()

    stopper = asyncio.get_running_loop().create_task(stop_later())
    try:
        await fh.run_async()
    finally:
        stopper.cancel()

    print(f'\ncapture: {", ".join(recorder.files)}')
    print(f'metadata: {metadata_path(recorder.files[0])}')
    for conn_id, stats in connection_stats().items():
        print(f'  {conn_id}: received={stats.received} sent={stats.sent}')


if __name__ == '__main__':
    asyncio.run(main())
