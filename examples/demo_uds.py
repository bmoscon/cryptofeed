'''
Copyright (C) 2018-2023 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import os
from decimal import Decimal
from multiprocessing import Process

from yapic import json

from cryptofeed import FeedHandler
from cryptofeed.backends.socket import TickerSocket, TradeSocket
from cryptofeed.defines import TICKER, TRADES
from cryptofeed.exchanges import Coinbase


async def reader(reader, writer):
    while True:
        data = await reader.read(1024)
        message = data.decode()
        # if multiple messages are received back to back,
        # need to make sure they are formatted as if in an array
        message = message.replace("}{", "},{")
        message = f"[{message}]"
        message = json.loads(message, parse_float=Decimal)

        print(f"Received {message!r}")


async def main():
    server = await asyncio.start_unix_server(
        reader, path='temp.uds')

    await server.serve_forever()


def writer(path):
    f = FeedHandler()
    f.add_feed(Coinbase(channels=[TRADES, TICKER], symbols=['BTC-USD'], callbacks={TRADES: TradeSocket(path), TICKER: TickerSocket(path)}))

    f.run()


if __name__ == '__main__':
    try:
        p = Process(target=writer, args=('uds://temp.uds',))
        p.start()
        asyncio.run(main())
    finally:
        os.unlink('temp.uds')
