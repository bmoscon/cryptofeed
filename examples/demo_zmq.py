'''
Copyright (C) 2018-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from multiprocessing import Process
import json

from cryptofeed.backends.zmq import BookZMQ, TickerZMQ
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Kraken, Coinbase

from cryptofeed.defines import L2_BOOK, TRADES, TICKER


def receiver(port):
    import zmq
    import time
    addr = 'tcp://127.0.0.1:{}'.format(port)
    ctx = zmq.Context.instance()
    s = ctx.socket(zmq.SUB)
    # empty subscription for all data, could be book for just book data, etc
    s.setsockopt(zmq.SUBSCRIBE, b'')

    s.bind(addr)
    while True:
        data = s.recv_string()
        key, msg = data.split(" ", 1)
        print(key)
        print(json.loads(msg))

def main():
    try:
        p = Process(target=receiver, args=(5678,))

        p.start()

        f = FeedHandler()
        f.add_feed(Kraken(max_depth=1, channels=[L2_BOOK], pairs=['ETH-USD'], callbacks={L2_BOOK: BookZMQ(port=5678)}))
        f.add_feed(Coinbase(channels=[TICKER], pairs=['BTC-USD'], callbacks={TICKER: TickerZMQ(port=5678)}))

        f.run()

    finally:
        p.terminate()


if __name__ == '__main__':
    main()
