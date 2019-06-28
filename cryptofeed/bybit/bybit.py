import logging
import json
import requests

from cryptofeed.feed import Feed
from cryptofeed.defines import BYBIT, BUY, SELL, TRADES, BID, ASK, TICKER, L2_BOOK
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize

from sortedcontainers import SortedDict as sd
from decimal import Decimal

LOG = logging.getLogger('feedhandler')


class Bybit(Feed):
    id = BYBIT

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://stream.bybit.com/realtime', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.__reset()

        instruments = ["BTCUSD", "EOSUSD", "ETHUSD", "XRPUSD"]
        self.pairs = pairs

        for pair in self.pairs:
            if pair not in instruments:
                raise ValueError(f"{pair} is not active on {self.id}")


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
            for trade in msg['data']:
                await self.callbacks[TRADES](
                    feed=self.id,
                    pair=trade['symbol'],
                    order_id=trade['trade_id'],
                    side=BUY if trade['side'] == 'Buy' else SELL,
                    amount=Decimal(trade['size']),
                    price=Decimal(trade['price']),
                    timestamp=trade['timestamp']
                )
