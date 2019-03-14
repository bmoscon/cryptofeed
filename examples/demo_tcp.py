'''
Copyright (C) 2018-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from multiprocessing import Process
import json
from decimal import Decimal

from cryptofeed.backends.socket import TradeSocket
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase
from cryptofeed.defines import TRADES


async def reader(reader, writer):
    while True:
        data = await reader.read(1024)
        message = data.decode()
        # if multiple messages are received back to back,
        # need to make sure they are formatted as if in an array
        message = message.replace("}{", "},{")
        message = f"[{message}]"
        message = json.loads(message, parse_float=Decimal)

        addr = writer.get_extra_info('peername')

        print(f"Received {message!r} from {addr!r}")


async def main():
    server = await asyncio.start_server(
        reader, '127.0.0.1', 8080)

    await server.serve_forever()


def writer(addr, port):
    f = FeedHandler()
    f.add_feed(Coinbase(channels=[TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeSocket(addr, port=port)}))
    f.run()


if __name__ == '__main__':
    p = Process(target=writer, args=('tcp://127.0.0.1', 8080))
    p.start()
    asyncio.run(main())
