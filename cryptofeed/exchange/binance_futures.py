'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging

from yapic import json

from cryptofeed.defines import BINANCE_FUTURES, BINANCE, OPEN_INTEREST, TICKER
from cryptofeed.exchange.binance import Binance
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize

LOG = logging.getLogger('feedhandler')


class BinanceFutures(Binance):
    id = BINANCE_FUTURES

    def __init__(self, pairs=None, channels=None, callbacks=None, depth=1000, **kwargs):
        super().__init__(pairs=pairs, channels=channels, callbacks=callbacks, depth=depth, **kwargs)
        self.ws_endpoint = 'wss://fstream.binance.com'
        self.rest_endpoint = 'https://fapi.binance.com/fapi/v1'
        self.address = self._address()

    def _address(self):
        address = self.ws_endpoint + '/stream?streams='
        for chan in self.channels if not self.config else self.config:
            if chan == OPEN_INTEREST:
                continue
            for pair in self.pairs if not self.config else self.config[chan]:
                pair = pair.lower()
                # if chan == TICKER:
                #     stream = f"{pair}@bookTicker/"
                # else:
                stream = f"{pair}@{chan}/"
                address += stream
        if address == f"{self.ws_endpoint}/stream?streams=":
            return None
        return address[:-1]

    def _check_update_id(self, pair: str, msg: dict) -> (bool, bool):
        skip_update = False
        forced = not self.forced[pair]

        if forced and msg['u'] < self.last_update_id[pair]:
            skip_update = True
        elif forced and msg['U'] <= self.last_update_id[pair] <= msg['u']:
            self.last_update_id[pair] = msg['u']
            self.forced[pair] = True
        elif not forced and self.last_update_id[pair] == msg['pu']:
            self.last_update_id[pair] = msg['u']
        else:
            self._reset()
            LOG.warning("%s: Missing book update detected, resetting book", self.id)
            skip_update = True
        return skip_update, forced

    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        # Combined stream events are wrapped as follows: {"stream":"<streamName>","data":<rawPayload>}
        # streamName is of format <symbol>@<channel>
        pair, _ = msg['stream'].split('@', 1)
        msg = msg['data']

        pair = pair.upper()

        msg_type = msg.get('e')
        if msg_type == 'bookTicker':
            await self._ticker(msg, timestamp)
        elif msg_type == 'depthUpdate':
            await self._book(msg, pair, timestamp)
        elif msg_type == 'aggTrade':
            await self._trade(msg, timestamp)
        elif msg_type == 'forceOrder':
            await self._liquidations(msg, timestamp)
        elif msg_type == 'markPriceUpdate':
            await self._funding(msg, timestamp)
        else:
            LOG.warning("%s: Unexpected message received: %s", self.id, msg)

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {
          "e":"bookTicker",     // 事件类型
          "u":400900217,        // 更新ID
          "E": 1568014460893,   // 事件推送时间
          "T": 1568014460891,   // 撮合时间
          "s":"BNBUSDT",        // 交易对
          "b":"25.35190000",    // 买单最优挂单价格
          "B":"31.21000000",    // 买单最优挂单数量
          "a":"25.36520000",    // 卖单最优挂单价格
          "A":"40.66000000"     // 卖单最优挂单数量
        }
        """
        pair = pair_exchange_to_std(msg['s'])
        bid = Decimal(msg['b'])
        bid_size = Decimal(msg['B'])
        ask = Decimal(msg['a'])
        ask_size = Decimal(msg['A'])
        ts = msg['E']#/1e3
        await self.callback(TICKER, feed=self.id,
                            pair=pair,
                            bid=bid,
                            bid_size=bid_size,
                            ask=ask,
                            ask_size = ask_size,
                            timestamp=ts,
                            receipt_timestamp=timestamp)
