'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import socket
from time import sleep
from multiprocessing import Process

from yapic import json

from cryptofeed import FeedHandler
from cryptofeed.backends.socket import BookSocket, TradeSocket
from cryptofeed.defines import L2_BOOK, TRADES
from cryptofeed.exchanges import Coinbase


def receiver(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', port))

    while True:
        data, _ = sock.recvfrom(1024 * 64)
        data = data.decode()
        data = json.loads(data)
        if data['type'] == 'chunked':
            chunks = data['chunks']
            buffer = []
            buffer.append(data['data'])

            for _ in range(chunks - 1):
                data, _ = sock.recvfrom(1024 * 64)
                data = data.decode()
                data = json.loads(data)
                buffer.append(data['data'])
            data = json.loads(''.join(buffer))
        print(data)


def main():
    try:
        p = Process(target=receiver, args=(5555,))
        p.start()
        sleep(1)

        f = FeedHandler()
        f.add_feed(Coinbase(channels=[L2_BOOK, TRADES], symbols=['BTC-USD'],
                            callbacks={TRADES: TradeSocket('udp://127.0.0.1', port=5555),
                                       L2_BOOK: BookSocket('udp://127.0.0.1', port=5555),
                                       }))

        f.run()
    finally:
        p.terminate()


if __name__ == '__main__':
    main()
