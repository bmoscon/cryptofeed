'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BITCOINCOM, BUY, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.standards import symbol_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class BitcoinCom(Feed):
    id = BITCOINCOM

    def __init__(self, **kwargs):
        super().__init__('wss://api.exchange.bitcoin.com/api/2/ws', **kwargs)
        self.__reset()

    def __reset(self):
        self.l2_book = {}
        self.seq_no = {}

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        for chan in set(self.channels or self.subscription):
            for pair in set(self.symbols or self.subscription[chan]):
                await conn.send(json.dumps(
                    {
                        "method": chan,
                        "params": {
                            "symbol": pair,
                        },
                        "id": chan + pair
                    }
                ))

    async def _trade(self, msg: dict, timestamp: float):
        for trade in msg['data']:
            await self.callback(TRADES, feed=self.id,
                                symbol=symbol_exchange_to_std(msg['symbol']),
                                side=BUY if trade['side'] == 'buy' else SELL,
                                amount=Decimal(trade['quantity']),
                                price=Decimal(trade['price']),
                                order_id=None,
                                timestamp=timestamp_normalize(self.id, trade['timestamp']),
                                receipt_timestamp=timestamp)

    async def _ticker(self, msg: dict, timestamp: float):
        await self.callback(TICKER, feed=self.id,
                            symbol=symbol_exchange_to_std(msg['symbol']),
                            bid=Decimal(msg['bid']),
                            ask=Decimal(msg['ask']),
                            timestamp=timestamp_normalize(self.id, msg['timestamp']),
                            receipt_timestamp=timestamp)

    async def _book_snapshot(self, msg: dict, timestamp: float):
        pair = symbol_exchange_to_std(msg['symbol'])
        self.l2_book[pair] = {
            BID: sd({
                Decimal(bid['price']): Decimal(bid['size']) for bid in msg['bid']
            }),
            ASK: sd({
                Decimal(ask['price']): Decimal(ask['size']) for ask in msg['ask']
            })
        }
        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, None, timestamp_normalize(self.id, msg['timestamp']), timestamp)

    async def _book_update(self, msg: dict, timestamp: float):
        delta = {BID: [], ASK: []}
        pair = symbol_exchange_to_std(msg['symbol'])
        for side in ('bid', 'ask'):
            s = BID if side == 'bid' else ASK
            for entry in msg[side]:
                price = Decimal(entry['price'])
                amount = Decimal(entry['size'])
                if amount == 0:
                    delta[s].append((price, 0))
                    del self.l2_book[pair][s][price]
                else:
                    delta[s].append((price, amount))
                    self.l2_book[pair][s][price] = amount
        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, False, delta, timestamp_normalize(self.id, msg['timestamp']), timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)
        if 'result' in msg and msg['result'] is True:
            return
        elif 'method' in msg:
            data = msg['params']

            if 'sequence' in data:
                if data['symbol'] not in self.seq_no:
                    self.seq_no[data['symbol']] = data['sequence']
                elif self.seq_no[data['symbol']] + 1 != data['sequence']:
                    LOG.warning("%s: missing sequence number. Received %d, expected %d", self.id, data['sequence'],
                                self.seq_no[data['symbol']] + 1)
                    raise MissingSequenceNumber
                self.seq_no[data['symbol']] = data['sequence']

            if msg['method'] == 'snapshotOrderbook':
                await self._book_snapshot(data, timestamp)
            elif msg['method'] == 'updateOrderbook':
                await self._book_update(data, timestamp)
            elif msg['method'] == 'snapshotTrades':
                return
            elif msg['method'] == 'updateTrades':
                await self._trade(data, timestamp)
            elif msg['method'] == 'ticker':
                await self._ticker(data, timestamp)
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)
