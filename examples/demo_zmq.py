'''
Copyright (C) 2018-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from multiprocessing import Process

from cryptofeed.backends.zmq import BookZMQ, TradeZMQ
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Kraken

from cryptofeed.defines import L2_BOOK, TRADES


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

def main():
    try:
        p = Process(target=receiver, args=(5555,))
        p2 = Process(target=receiver, args=(5556,))

        p.start()
        p2.start()

        f = FeedHandler()
        f.add_feed(Kraken(channels=[L2_BOOK], pairs=['ETH-USD'], callbacks={L2_BOOK: BookZMQ(depth=1, port=5556)}))

        f.run()
    finally:
        p.terminate()
        p2.terminate()


if __name__ == '__main__':
    main()
