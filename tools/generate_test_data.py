'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import glob
import random

import uvloop

from cryptofeed.feedhandler import FeedHandler
from cryptofeed.exchanges import EXCHANGE_MAP
from cryptofeed.raw_data_collection import AsyncFileCallback
from cryptofeed.defines import BINANCE_FUTURES, BITFINEX, COINGECKO, L2_BOOK, TRADES, TICKER, CANDLES, EXX
from check_raw_dump import main as check_dump

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


def stop():
    loop = asyncio.get_event_loop()
    loop.stop()


def main():
    skip = [COINGECKO, EXX]
    files = glob.glob('*')
    for f in files:
        for e in EXCHANGE_MAP.keys():
            if e + "." in f:
                skip.append(e.split(".")[0])

    print(f'Generating test data. This will take approximately {(len(EXCHANGE_MAP) - len(set(skip))) * 0.5} minutes.')
    loop = asyncio.get_event_loop()
    for exch_str, exchange in EXCHANGE_MAP.items():
        if exch_str in skip:
            continue

        print(f"Collecting data for {exch_str}")
        fh = FeedHandler(raw_data_collection=AsyncFileCallback("./"), config={'uvloop': False, 'log': {'filename': 'feedhandler.log', 'level': 'WARNING'}, 'rest': {'log': {'filename': 'rest.log', 'level': 'WARNING'}}})
        info = exchange.info()
        channels = list(set.intersection(set(info['channels']), set([L2_BOOK, TRADES, TICKER, CANDLES])))
        sample_size = 10
        while True:
            try:
                symbols = random.sample(info['symbols'], sample_size)

                if exch_str == BINANCE_FUTURES:
                    symbols = [s for s in symbols if 'PINDEX' not in s]
                elif exch_str == BITFINEX:
                    symbols = [s for s in symbols if '-' in s]

            except ValueError:
                sample_size -= 1
            else:
                break

        fh.add_feed(exchange(symbols=symbols, channels=channels))
        fh.run(start_loop=False)

        loop.call_later(31, stop)
        print("Starting feedhandler. Will run for 30 seconds...")
        loop.run_forever()

        fh.stop(loop=loop)
        del fh

    print("Checking raw message dumps for errors...")
    for exch_str, _ in EXCHANGE_MAP.items():
        for file in glob.glob(exch_str + "*"):
            try:
                print(f"Checking {file}")
                check_dump(file)
            except Exception as e:
                print(f"File {file} failed")
                print(e)


if __name__ == '__main__':
    main()
