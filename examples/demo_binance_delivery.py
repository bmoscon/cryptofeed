import asyncio
from datetime import datetime
from collections import defaultdict
from multiprocessing import Process
from yapic import json

from cryptofeed import FeedHandler
from cryptofeed.backends.zmq import CandlesZMQ, FundingZMQ, FuturesIndexZMQ, TickerZMQ, TradeZMQ, VolumeZMQ
from cryptofeed.defines import CANDLES, FUTURES_INDEX, L2_BOOK, FUNDING, TICKER, PERPETUAL, FUTURE, TRADES, VOLUME
from cryptofeed.exchanges import BinanceFutures, BinanceDelivery, Binance

binance_delivery_data_info = BinanceDelivery.info()
binance_futures_data_info = BinanceFutures.info()
binance_data_info = Binance.info()

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
    i = 0
    # print(f'BOOK lag: {receipt_timestamp - timestamp} Timestamp: {datetime.fromtimestamp(timestamp)} Receipt Timestamp: {datetime.fromtimestamp(receipt_timestamp)} Feed: {feed} Pair: {symbol} Snapshot: {book}')


async def ticker(**kwargs):
    print(kwargs)


async def trades(**kwargs):
    print(kwargs)

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

        binance_symbols = set()
        for instrument in BinanceDelivery.get_instrument_objects():
            binance_symbols.add(instrument.base + '-USDT')
        print(binance_symbols)

        f.add_feed(BinanceDelivery(candle_interval='1d', symbols=binance_delivery_symbols[PERPETUAL], channels=[FUTURES_INDEX, FUNDING, TICKER, TRADES, VOLUME], callbacks={
            FUNDING: FundingZMQ(port=5678), 
            TICKER: TickerZMQ(port=5679), 
            TRADES: TradeZMQ(port=5682), 
            FUTURES_INDEX: FuturesIndexZMQ(port=5684),
            VOLUME: VolumeZMQ(port=5685)}))
        f.add_feed(BinanceDelivery(candle_interval='1d', symbols=binance_delivery_symbols[FUTURE], channels=[FUTURES_INDEX, TICKER, TRADES, VOLUME], callbacks={
            TICKER: TickerZMQ(port=5687), 
            TRADES: TradeZMQ(port=5688), 
            FUTURES_INDEX: FuturesIndexZMQ(port=5689),
            VOLUME: VolumeZMQ(port=5690)}))
        f.add_feed(BinanceFutures(symbols=binance_futures_symbols[PERPETUAL], channels=[FUNDING], callbacks={FUNDING: FundingZMQ(port=5680)}))
        f.add_feed(Binance(symbols=list(binance_symbols), channels=[TICKER, TRADES, VOLUME], callbacks={
            TICKER: TickerZMQ(port=5681), 
            TRADES: TradeZMQ(port=5683),
            VOLUME: VolumeZMQ(port=5686)}))
        f.run()
    
    finally:
        p.terminate()

if __name__ == '__main__':
    main()
