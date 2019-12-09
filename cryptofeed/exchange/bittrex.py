import logging
import json
from decimal import Decimal
import requests
import zlib
import base64

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.defines import BITTREX, BUY, SELL, TRADES, BID, ASK, L2_BOOK, TICKER
from cryptofeed.standards import timestamp_normalize, pair_exchange_to_std


LOG = logging.getLogger('feedhandler')


class Bittrex(Feed):
    id = BITTREX

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://socket.bittrex.com/signalr', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        r = requests.get('https://socket.bittrex.com/signalr/negotiate', params={'connectionData': json.dumps([{'name': 'c2'}]), 'clientProtocol': 1.5})
        token = r.json()['ConnectionToken']
        url = requests.Request('GET', 'https://socket.bittrex.com/signalr/connect', params={'transport': 'webSockets', 'connectionToken': token, 'connectionData': json.dumps([{"name": "c2"}]), 'clientProtocol': 1.5}).prepare().url
        url = url.replace('https://', 'wss://')
        self.address = url

    def __reset(self):
        self.l2_book = {}

    async def ticker(self, msg):
        for t in msg['D']:
            if (not self.config and t['M'] in self.pairs) or ('SubscribeToSummaryDeltas' in self.config and t['M'] in self.config['SubscribeToSummaryDeltas']):
                await self.callback(TICKER, feed=self.id, pair=pair_exchange_to_std(t['M']), bid=Decimal(t['B']), ask=Decimal(t['A']), timestamp=timestamp_normalize(self.id, t['T']))

    async def _snapshot(self, msg: dict, timestamp: float):
        pair = pair_exchange_to_std(msg['M'])
        self.l2_book[pair] = {
            BID: sd({entry['R']: entry['Q'] for entry in msg['Z']}),
            ASK: sd({entry['R']: entry['Q'] for entry in msg['S']})
        }
        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, False, timestamp)

    async def book(self, msg: dict, timestamp: float):
        pair = pair_exchange_to_std(msg['M'])
        if pair in self.l2_book:
            delta = {BID: [], ASK: []}
            for side, key in ((BID, 'Z'), (ASK, 'S')):
                for update in msg[key]:
                    price = update['R']
                    size = update['Q']
                    if size == 0:
                        delta[side].append((price, 0))
                        # changing because of error when no value
                        # del self.l2_book[pair][side][price]
                        self.l2_book[pair][side].pop(price, None)
                    else:
                        self.l2_book[pair][side][price] = size
                        delta[side].append((price, size))

            await self.book_callback(self.l2_book[pair], L2_BOOK, pair, False, delta, timestamp)

    async def trades(self, pair: str, msg: dict):
        # adding because of error
        trade_q = self.config.get(TRADES, [])
        if self.config and pair in trade_q or not self.config:
            pair = pair_exchange_to_std(pair)
            for trade in msg:
                await self.callback(TRADES, feed=self.id,
                                            order_id=trade['FI'],
                                            pair=pair,
                                            side=BUY if trade['OT'] == 'BUY' else SELL,
                                            amount=trade['Q'],
                                            price=trade['R'],
                                            timestamp=timestamp_normalize(self.id, trade['T']))

    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg)
        if 'M' in msg and len(msg['M']) > 0:
            for update in msg['M']:
                if update['M'] == 'uE':
                    # Book deltas + Trades
                    for message in update['A']:
                        data = json.loads(zlib.decompress(base64.b64decode(message), -zlib.MAX_WBITS).decode(), parse_float=Decimal)
                        await self.book(data, timestamp)
                        if 'f' in data and data['f']:
                            await self.trades(data['M'], data['f'])
                if update['M'] == 'uS':
                    # Tickers
                    for message in update['A']:
                        data = json.loads(zlib.decompress(base64.b64decode(message), -zlib.MAX_WBITS).decode(), parse_float=Decimal)
                        await self.ticker(data)
        elif 'R' in msg and isinstance(msg['R'], str):
            data = json.loads(zlib.decompress(base64.b64decode(msg['R']), -zlib.MAX_WBITS).decode(), parse_float=Decimal)
            await self._snapshot(data, timestamp)
        elif 'E' in msg:
            LOG.error("%s: Error from exchange %s", self.id, msg)

    async def subscribe(self, websocket):
        self.__reset()
        # H: Hub, M: Message, A: Args, I: Internal ID
        # For more signalR info see:
        # https://blog.3d-logic.com/2015/03/29/signalr-on-the-wire-an-informal-description-of-the-signalr-protocol/
        # http://blogs.microsoft.co.il/applisec/2014/03/12/signalr-message-format/
        for channel in set(self.channels) if not self.config else set(self.config):
            symbols = self.pairs if not self.config else list(self.config[channel])
            i = 0
            if channel == 'SubscribeToExchangeDeltas':
                for symbol in symbols:
                    msg = {'A': [symbol], 'H': 'c2', 'I': i, 'M': 'QueryExchangeState'}
                    await websocket.send(json.dumps(msg))
                    i += 1
            if channel == TRADES:
                channel = 'SubscribeToExchangeDeltas'
            for symbol in symbols:
                msg = {'A': [symbol] if channel != 'SubscribeToSummaryDeltas' else [], 'H': 'c2', 'I': i, 'M': channel}
                i += 1
                await websocket.send(json.dumps(msg))
