'''
Copyright (C) 2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from multiprocessing import Process
import socket

from cryptofeed.backends.udp import TradeUDP, BookUDP
from cryptofeed import FeedHandler
from cryptofeed import Coinbase

from cryptofeed.defines import L3_BOOK, TRADES


def receiver(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', port))

    while True:
        data, _ = sock.recvfrom(1024 * 10)
        data = data.decode()
        print(data)


def main():
    try:
        p = Process(target=receiver, args=(5555,))
        p.start()

        f = FeedHandler()
        f.add_feed(Coinbase(channels=[L3_BOOK, TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeUDP(), L3_BOOK: BookUDP(depth=1)}))

        f.run()
    finally:
        p.terminate()


if __name__ == '__main__':
    main()
