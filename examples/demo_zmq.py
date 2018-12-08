'''
Copyright (C) 2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from multiprocessing import Process

from cryptofeed.backends.zmq import BookZMQ, TradeZMQ
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase

from cryptofeed.defines import L3_BOOK, TRADES


def receiver(port):
    import zmq
    import time
    addr = 'tcp://127.0.0.1:{}'.format(port)
    ctx = zmq.Context.instance()
    s = ctx.socket(zmq.PULL)
    s.connect(addr)
    while True:
        data = s.recv_json()
        print(data)
        time.sleep(0.5)


def main():
    try:
        p = Process(target=receiver, args=(5555,))
        p2 = Process(target=receiver, args=(5556,))

        p.start()
        p2.start()

        f = FeedHandler()
        f.add_feed(Coinbase(channels=[L3_BOOK, TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeZMQ(), L3_BOOK: BookZMQ(depth=1, port=5556)}))

        f.run()
    finally:
        p.terminate()
        p2.terminate()


if __name__ == '__main__':
    main()
