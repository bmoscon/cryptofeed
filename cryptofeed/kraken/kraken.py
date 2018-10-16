import asyncio
from decimal import Decimal
import time

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import RestFeed
from cryptofeed.defines import TRADES, BID, ASK, TICKER, L2_BOOK
from cryptofeed.exchanges import KRAKEN
from cryptofeed.standards import pair_exchange_to_std

import aiohttp


class Kraken(RestFeed):
    id = KRAKEN

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('https://api.kraken.com/0/public/', pairs, channels, callbacks, **kwargs)

    def __reset(self):
        self.last_trade_update = None

    async def _trades(self, session, pair):
        if self.last_trade_update is None:
            async with session.get("{}Trades?pair={}".format(self.address, pair)) as response:
                data = await response.json()
                self.last_trade_update = data['result']['last']
        else:
            async with session.get("{}Trades?pair={}&since={}".format(self.address, pair, self.last_trade_update)) as response:
                data = await response.json()
                self.last_trade_update = data['result']['last']
                if data['result'][pair] == []:
                    return
                else:
                    for trade in data['result'][pair]:
                        # <price>, <volume>, <time>, <buy/sell>, <market/limit>, <miscellaneous>
                        price, amount, timestamp, side, _, _ = trade
                        await self.callbacks[TRADES](feed=self.id,
                                                    pair=pair_exchange_to_std(pair),
                                                    side=BID if side == 'b' else ASK,
                                                    amount=Decimal(amount),
                                                    price=Decimal(price),
                                                    order_id=None,
                                                    timestamp=timestamp)

    async def _ticker(self, session, pair):
        async with session.get("{}Ticker?pair={}&count=100".format(self.address, pair)) as response:
            data = await response.json()
            bid = Decimal(data['result'][pair]['b'][0])
            ask = Decimal(data['result'][pair]['a'][0])
            await self.callbacks[TICKER](feed=self.id,
                                         pair=pair_exchange_to_std(pair),
                                         bid=bid,
                                         ask=ask)

    async def _book(self, session, pair):
        async with session.get("{}Depth?pair={}".format(self.address, pair)) as response:
            data = await response.json()
            ts = time.time()
            data = data['result'][pair]

            book = {BID: sd(), ASK: sd()}
            for bids in data['bids']:
                price, amount, _ = bids
                price = Decimal(price)
                amount = Decimal(amount)
                book[BID][price] = amount
            for bids in data['asks']:
                price, amount, _ = bids
                price = Decimal(price)
                amount = Decimal(amount)
                book[ASK][price] = amount
            await self.callbacks[L2_BOOK](feed=self.id,
                                          pair=pair_exchange_to_std(pair),
                                          book=book,
                                          timestamp=ts)

    async def subscribe(self):
        self.__reset()
        return

    async def message_handler(self):
        async with aiohttp.ClientSession() as session:
            for chan in self.channels:
                for pair in self.pairs:
                    if chan == TRADES:
                        await self._trades(session, pair)
                    elif chan == TICKER:
                        await self._ticker(session, pair)
                    elif chan == L2_BOOK:
                        await self._book(session, pair)
                    # KRAKEN's documentation suggests no more than 1 request a second
                    # to avoid being rate limited
                    await asyncio.sleep(1)
