'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import glob
import random

from cryptofeed.feedhandler import FeedHandler, _EXCHANGES
from cryptofeed.defines import BINANCE_FUTURES, BITFINEX, COINGECKO, L2_BOOK, TRADES, TICKER, CANDLES
from cryptofeed.raw_data_collection import AsyncFileCallback
from check_raw_dump import main as check_dump


def stop():
    loop = asyncio.get_event_loop()
    loop.stop()


def main():
    skip = [COINGECKO]
    files = glob.glob('*')
    for f in files:
        for e in _EXCHANGES.keys():
            if e + "." in f:
                skip.append(e.split(".")[0])

    print(f'Generating test data. This will take approximately {(len(_EXCHANGES) - len(set(skip))) * 1} minutes.')
    for exch_str, exchange in _EXCHANGES.items():
        if exch_str in skip:
            continue
        print(f"Collecting data for {exch_str}")
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

        fh = FeedHandler()
        fh.add_feed(exchange(raw_data_collection=('./', 10000, 104857600), symbols=symbols, channels=channels))
        fh.run(start_loop=False)

        loop = asyncio.get_event_loop()
        loop.call_later(60, stop)
        print("Starting feedhandler. Will run for 1 minute...")
        loop.run_forever()

        fh.stop()
        del fh

    print("Checking raw message dumps for errors...")
    for exch_str, _ in _EXCHANGES.items():
        for file in glob.glob(exch_str + "*"):
            try:
                print(f"Checking {file}")
                check_dump(file)
            except Exception as e:
                print(f"File {file} failed")
                print(e)


if __name__ == '__main__':
    main()
