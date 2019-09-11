import logging
import json
from decimal import Decimal

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.defines import BYBIT, BUY, SELL, TRADES, BID, ASK, L2_BOOK
from cryptofeed.standards import timestamp_normalize, pair_exchange_to_std as normalize_pair


LOG = logging.getLogger('feedhandler')


class Bybit(Feed):
    id = BYBIT

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://stream.bybit.com/realtime', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)

    def __reset(self):
        self.l2_book = {}

    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg)

        if "success" in msg:
            if msg['success']:
                LOG.debug("%s: Subscription success %s", self.id, msg)
            else:
                LOG.error("%s: Error from exchange %s", self.id, msg)
        elif "trade" in msg["topic"]:
            await self._trade(msg)
        elif "order_book_25L1" in msg["topic"]:
            await self._book(msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, websocket):
        self.__reset()
        for chan in self.channels if self.channels else self.config:
            for pair in self.pairs if self.pairs else self.config[chan]:
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
            await self.callback(TRADES,
                feed=self.id,
                pair=normalize_pair(trade['symbol']),
                order_id=trade['trade_id'],
                side=BUY if trade['side'] == 'Buy' else SELL,
                amount=Decimal(trade['size']),
                price=Decimal(trade['price']),
                timestamp=timestamp_normalize(self.id, trade['timestamp'])
            )

    async def _book(self, msg):
        pair = normalize_pair(msg['topic'].split('.')[1])
        update_type = msg['type']
        data = msg['data']
        forced = False
        delta = {BID: [], ASK: []}


        if update_type == 'snapshot':
            self.l2_book[pair] = {BID: sd({}), ASK: sd({})}
            for update in data:
                side = BID if update['side'] == 'Buy' else ASK
                self.l2_book[pair][side][Decimal(update['price'])] = Decimal(update['size'])
            forced = True
        else:
            for delete in data['delete']:
                side = BID if delete['side'] == 'Buy' else ASK
                price = Decimal(delete['price'])
                delta[side].append((price, 0))
                del self.l2_book[pair][side][price]

            for utype in ('update', 'insert'):
                for update in data[utype]:
                    side = BID if update['side'] == 'Buy' else ASK
                    price = Decimal(update['price'])
                    amount = Decimal(update['size'])
                    delta[side].append((price, amount))
                    self.l2_book[pair][side][price] = amount

        # timestamp is in microseconds
        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, msg['timestamp_e6'] / 1000000)
