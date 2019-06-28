import logging
import json
import requests

from cryptofeed.feed import Feed
from cryptofeed.defines import BYBIT, BUY, SELL, TRADES, BID, ASK, TICKER, L2_BOOK
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize

from sortedcontainers import SortedDict as sd
from decimal import Decimal
import time

LOG = logging.getLogger('feedhandler')

class Bybit(Feed):
    id = BYBIT

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://stream.bybit.com/realtime', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.__reset()

    def __reset(self):
        pass

    async def subscribe(self, websocket):
        self.__reset()

    async def message_handler(self, msg):
        msg_dict = json.loads(msg)

        if "success" in msg_dict.keys():
            LOG.debug("%s: Response from bybit accepted %s", self.id, msg)
        elif "trade" in msg_dict["topic"]:
            await self._trade(msg_dict)
        elif "orderBook25" in msg_dict["topic"]:
            await self._book(msg_dict)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, websocket):
        self.websocket = websocket
        self.__reset()
        client_id = 0
        for chan in self.channels if self.channels else self.config:
            for pair in self.pairs if self.pairs else self.config[chan]:
                client_id += 1
                await websocket.send(json.dumps(
                    {
                        "op": "subscribe",
                        "args": [f"{chan}.{pair}"]
                    }
                ))

    async def _trade(self, msg):
            """
            {"topic":"trade.BTCUSD",
            "data":[
                {
                    "timestamp":"2019-01-22T15:04:33.461Z",
                    "symbol":"BTCUSD",
                    "side":"Buy",
                    "size":980,
                    "price":3563.5,
                    "tick_direction":"PlusTick",
                    "trade_id":"9d229f26-09a8-42f8-aff3-0ba047b0449d",
                    "cross_seq":163261271}]}
            """
            data = msg['data']
            for trade in data:
                await self.callbacks[TRADES](
                    feed=self.id,
                    pair=trade['symbol'],
                    order_id=trade['trade_id'],
                    side=BUY if trade['side'] == 'Buy' else SELL,
                    amount=trade['size'],
                    price=trade['price'],
                    timestamp=timestamp_normalize(self.id, trade['timestamp'])
                )

    async def _book(self, msg):
      pair = msg['topic'].split('.')[1]
      data = msg['data']

      BIDS = []
      for bids in data["bids"]:
          bid = [bids['price'], bids['quantity']]
          BIDS.append(bid)

      ASKS = []
      for asks in data["asks"]:
          ask = [asks['price'], asks['quantity']]
          ASKS.append(ask)

      self.l2_book[pair] = {
            BID: sd({
                Decimal(price): Decimal(amount)
                for price, amount in BIDS
            }),
            ASK: sd({
                Decimal(price): Decimal(amount)
                for price, amount in ASKS
            })
        }

      await self.book_callback(pair, L2_BOOK, False, False, time.time())
