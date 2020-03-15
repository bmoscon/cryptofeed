import logging
import json
from decimal import Decimal
import requests
import zlib
import base64

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.defines import UPBIT, BUY, SELL, TRADES, BID, ASK, L2_BOOK, TICKER
from cryptofeed.standards import timestamp_normalize, pair_exchange_to_std


LOG = logging.getLogger('feedhandler')


class Upbit(Feed):
    id = UPBIT

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://api.upbit.com/websocket/v1', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.__reset()

    def __reset(self):
        pass

    async def _trade(self, msg: dict, timestamp: float):
        """
        trade msg example

        {
            'ty': 'trade'             // Event type
            'cd': 'KRW-BTC',          // Symbol
            'tp': 6759000.0,          // Trade Price
            'tv': 0.03243003,         // Trade volume(amount)
            'tms': 1584257228806,     // Timestamp
            'ttms': 1584257228000,    // Trade Timestamp
            'ab': 'BID',              // 'BID' or 'ASK'
            'cp': 64000.0,            // Change of price
            'pcp': 6823000.0,         // Previous closing price
            'sid': 1584257228000000,  // Sequential ID
            'st': 'SNAPSHOT',         // 'SNAPSHOT' or 'REALTIME'
            'td': '2020-03-15',       // Trade date utc
            'ttm': '07:27:08',        // Trade time utc
            'c': 'FALL',              // Change
        }
        """

        price = Decimal(msg['tp'])
        amount = Decimal(msg['tv'])
        await self.callback(TRADES, feed=self.id,
                                     order_id=msg['sid'],
                                     pair=pair_exchange_to_std(msg['cd']),
                                     side=BUY if msg['ab'] == 'BID' else SELL,
                                     amount=amount,
                                     price=price,
                                     timestamp=timestamp_normalize(self.id, msg['ttms']),
                                     receipt_timestamp=timestamp_normalize(self.id, msg['tms']))

    async def _book(self, msg: dict, timestamp: float):
        pass
    async def _ticker(self, msg: dict, timestamp: float):
        pass
  
    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg)
        if msg['ty'] == "trade":
            await self._trade(msg, timestamp)
        elif msg['ty'] == "orderbook":
            await self._book(msg, timestamp)
        elif msg['ty'] == "ticker":
            await self._ticker(msg, timestamp)
        else:
            LOG.warning("%s: Unhandled message %s", self.id, msg)

    async def subscribe(self, websocket):
        """
        Doc : https://docs.upbit.com/docs/upbit-quotation-websocket
        
        For subscription, ticket information is commonly required.
        In order to reduce the data size, format parameter is set to 'SIMPLE' instead of 'DEFAULT'
        

        Examples (Note that the positions of the base and quote currencies are swapped.)

        1. In order to get TRADES of "BTC-KRW" and "XRP-BTC" markets. 
        > [{"ticket":"UNIQUE_TICKET"},{"type":"trade","codes":["KRW-BTC","BTC-XRP"]}]

        2. In order to get ORDERBOOK of "BTC-KRW" and "XRP-BTC" markets. 
        > [{"ticket":"UNIQUE_TICKET"},{"type":"orderbook","codes":["KRW-BTC","BTC-XRP"]}]

        3. In order to get TRADES of "BTC-KRW" and ORDERBOOK of "ETH-KRW"
        > [{"ticket":"UNIQUE_TICKET"},{"type":"trade","codes":["KRW-BTC"]},{"type":"orderbook","codes":["KRW-ETH"]}]

        4. In order to get TRADES of "BTC-KRW", ORDERBOOK of "ETH-KRW and TICKER of "EOS-KRW"
        > [{"ticket":"UNIQUE_TICKET"},{"type":"trade","codes":["KRW-BTC"]},{"type":"orderbook","codes":["KRW-ETH"]},{"type":"ticker", "codes":["KRW-EOS"]}]

        5. In order to get TRADES of "BTC-KRW", ORDERBOOK of "ETH-KRW and TICKER of "EOS-KRW" with in shorter format
        > [{"ticket":"UNIQUE_TICKET"},{"format":"SIMPLE"},{"type":"trade","codes":["KRW-BTC"]},{"type":"orderbook","codes":["KRW-ETH"]},{"type":"ticker", "codes":["KRW-EOS"]}]
        """
        
        self.__reset()
        chans = [{"ticket":"UNIQUE_TICKET"}, {"format":"SIMPLE"}]
        for channel in self.channels if not self.config else self.config:
            codes = list()
            for pair in self.pairs if not self.config else self.config[channel]:
                codes.append(pair)
            
            if channel == L2_BOOK:
                chans.append({"type": "orderbook", "codes": codes})
            if channel == TRADES:
                chans.append({"type": "trade", "codes": codes})
            if channel == TICKER:
                chans.append({"type": "ticker", "codes": codes})

        await websocket.send(json.dumps(chans))
