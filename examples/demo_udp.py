'''
Copyright (C) 2018-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from multiprocessing import Process
import socket

from cryptofeed.backends.socket import TradeSocket, BookSocket
from cryptofeed.backends.aggregate import Throttle
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase
from cryptofeed.defines import L2_BOOK, TRADES


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
        f.add_feed(
            Coinbase(
                channels=[
                    L2_BOOK,
                    TRADES],
                pairs=['BTC-USD'],
                callbacks={
                    TRADES: TradeSocket(
                        'udp://127.0.0.1',
                        port=5555),
                    L2_BOOK: Throttle(
                        BookSocket(
                            'udp://127.0.0.1',
                            port=5555,
                            depth=10),
                        window=1)}))

        f.run()
    finally:
        p.terminate()


if __name__ == '__main__':
    main()
