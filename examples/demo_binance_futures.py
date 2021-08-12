import asyncio
from datetime import datetime
from collections import defaultdict
from multiprocessing import Process
from yapic import json

from cryptofeed import FeedHandler
from cryptofeed.backends.zmq import FundingZMQ
from cryptofeed.defines import L2_BOOK, FUNDING, PERPETUAL
from cryptofeed.exchanges import BinanceFutures, BinanceDelivery

binance_delivery_data_info = BinanceDelivery.info()
binance_futures_data_info = BinanceFutures.info()

import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

def receiver(port):
    async def listen():
        while True:
            data = await s.recv_string()
            print(data)
            key, msg = data.split(" ", 1)
            print(key)
            # print(json.loads(msg))
            msg = json.loads(msg)
            res[msg['feed']][msg['symbol']] = msg['rate']
            d = res[msg['feed']]
            res[msg['feed']] = dict(sorted(d.items(), key=lambda item: item[1], reverse=True))
            print(res)
    res = defaultdict(dict)
    
    import zmq
    addr = 'tcp://127.0.0.1:{}'.format(port)
    ctx = zmq.asyncio.Context.instance()
    s = ctx.socket(zmq.SUB)
    # empty subscription for all data, could be book for just book data, etc
    s.setsockopt(zmq.SUBSCRIBE, b'')

    s.bind(addr)
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(listen())

async def abook(feed, symbol, book, timestamp, receipt_timestamp):
    print(f'BOOK lag: {receipt_timestamp - timestamp} Timestamp: {datetime.fromtimestamp(timestamp)} Receipt Timestamp: {datetime.fromtimestamp(receipt_timestamp)} Feed: {feed} Pair: {symbol} Snapshot: {book}')


async def delta(feed, symbol, delta, timestamp, receipt_timestamp):
    print(f'DELTA lag: {receipt_timestamp - timestamp} Timestamp: {datetime.fromtimestamp(timestamp)} Receipt Timestamp: {datetime.fromtimestamp(receipt_timestamp)} Feed: {feed} Pair: {symbol} Delta: {delta}')

async def funding(feed, symbol, timestamp, receipt_timestamp, mark_price, rate, next_funding_time):
    print(f'FUNDING lag: {receipt_timestamp - timestamp} Feed: {feed} Pair: {symbol} Mark Price: {mark_price} Rate: {rate} Next Funding Time: {next_funding_time}')

def main():
    try:
        # p = Process(target=receiver, args=(5678,))
        # p.start()

        f = FeedHandler()
        # print(binance_delivery_data_info)
        # print(binance_futures_data_info)
        binance_futures_symbols = defaultdict(list)
        for instrument in BinanceFutures.get_instrument_objects():
            binance_futures_symbols[instrument.instrument_type].append(instrument.instrument_name)
        print(binance_futures_symbols)

        binance_delivery_symbols = defaultdict(list)
        for instrument in BinanceDelivery.get_instrument_objects():
            binance_delivery_symbols[instrument.instrument_type].append(instrument.instrument_name)
        print(binance_delivery_symbols)

        # f.add_feed(BinanceDelivery(symbols=binance_delivery_symbols[PERPETUAL], channels=[FUNDING], callbacks={FUNDING: FundingZMQ(port=5678)}))
        f.add_feed(BinanceFutures(symbols=binance_futures_symbols[PERPETUAL], channels=[FUNDING], callbacks={FUNDING: FundingZMQ(port=5679)}))
        f.run()
    
    finally:
        p.terminate()

if __name__ == '__main__':
    main()
