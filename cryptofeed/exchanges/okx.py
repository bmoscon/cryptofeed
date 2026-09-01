'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Tuple, Union
from cryptofeed import _json as json
import asyncio
import logging
import time

from cryptofeed.connection import AsyncConnection, HTTPAsyncConn, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import CALL, FUTURES, OKX as OKX_str, LIQUIDATIONS, BUY, OPTION, PERPETUAL, PUT, SELL, FILLED, ASK, BID, FUNDING, L2_BOOK, OPEN_INTEREST, TICKER, TRADES, CANDLES, SPOT, UNFILLED
from cryptofeed.feed import Feed
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.symbols import Symbol
from cryptofeed.types import OrderBook, Trade, Ticker, Funding, OpenInterest, Liquidation, Candle


LOG = logging.getLogger(__name__)


class OKX(Feed):
    id = OKX_str
    keepalive_interval = 15.0

    async def keepalive(self, conn: AsyncConnection):
        await conn.write('ping')

    provides_sequence_number = True
    validates_sequence_number = True
    valid_candle_intervals = {'1M', '1W', '1D', '12H', '6H', '4H', '2H', '1H', '30m', '15m', '5m', '3m', '1m'}
    candle_interval_map = {'1M': 2630000, '1W': 604800, '1D': 86400, '12H': 43200, '6H': 21600, '4H': 14400, '2H': 7200, '1H': 3600, '30m': 1800, '15m': 900, '5m': 300, '3m': 180, '1m': 60}
    websocket_channels = {
        L2_BOOK: 'books',
        TRADES: 'trades',
        TICKER: 'tickers',
        FUNDING: 'funding-rate',
        OPEN_INTEREST: 'open-interest',
        LIQUIDATIONS: LIQUIDATIONS,
        CANDLES: 'candle'
    }
    websocket_endpoints = [
        WebsocketEndpoint('wss://ws.okx.com:8443/ws/v5/public', channel_filter=(websocket_channels[L2_BOOK], websocket_channels[TRADES], websocket_channels[TICKER], websocket_channels[FUNDING], websocket_channels[OPEN_INTEREST], websocket_channels[LIQUIDATIONS]), options={'compression': None}),
        WebsocketEndpoint('wss://ws.okx.com:8443/ws/v5/business', channel_filter=(websocket_channels[CANDLES],), options={'compression': None}),
    ]
    rest_endpoints = [RestEndpoint('https://www.okx.com', routes=Routes(['/api/v5/public/instruments?instType=SPOT', '/api/v5/public/instruments?instType=SWAP', '/api/v5/public/instruments?instType=FUTURES'], currencies='/api/v5/public/underlying?instType=OPTION', liquidations='/api/v5/public/liquidation-orders?instType={}&limit=100&state={}&uly={}', l2book='/api/v5/market/books?instId={}&sz={}'))]
    option_instruments = '/api/v5/public/instruments?instType=OPTION&uly={}'
    default_option_underlyings = ('BTC-USD', 'ETH-USD')
    request_limit = 20

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    async def _symbol_endpoint_prepare(cls, ep: RestEndpoint, conn: HTTPAsyncConn) -> Union[List[str], str]:
        underlyings = cls.default_option_underlyings
        try:
            response = json.loads(await conn.read(ep.route('currencies')), parse_float=Decimal)
            underlyings = response['data'][0] or underlyings
        except Exception as e:
            LOG.warning('%s: could not read the OPTION underlyings (%s) - requesting %s only', cls.id, e, ', '.join(underlyings))
        return ep.route('instruments') + [ep.address + cls.option_instruments.format(uly) for uly in sorted(underlyings)]

    @classmethod
    def _parse_symbol_data(cls, data: list) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data:
            for e in entry['data']:
                expiry = None
                otype = None
                stype = e['instType'].lower()
                strike = None

                if e.get('state') == 'preopen' or not e['instId']:
                    continue

                parts = e['instId'].split("-")

                if stype == SPOT:
                    base = e['baseCcy']
                    quote = e['quoteCcy']
                elif stype == FUTURES and len(parts) == 3:
                    # the quote carries the margin mode on the newer contracts, so this is
                    # BTC-USD-260828 but also BTC-USD_UM-260828 and BTC-USD_UM_XPERP-310404
                    base, quote, expiry = parts
                elif stype == OPTION and len(parts) == 5:
                    base, quote, expiry, strike, otype = parts
                    otype = PUT if otype == 'P' else CALL
                elif stype == 'swap' and len(parts) == 3:
                    # this is a perpetual swap (aka perpetual futures contract), not a real swap
                    stype = PERPETUAL
                    base, quote, _ = parts
                elif stype in (FUTURES, OPTION, 'swap'):
                    cls.unsupported_category(f'{e["instType"]} instId', e['instId'])
                    continue
                else:
                    cls.unsupported_category('instType', e['instType'])
                    continue

                s = Symbol(base, quote, expiry_date=expiry, type=stype, option_type=otype, strike_price=strike)
                ret[s.normalized] = e['instId']
                info['tick_size'][s.normalized] = e['tickSz']
                info['instrument_type'][s.normalized] = stype

        return ret, info

    async def _liquidations(self, pairs: list):
        last_update = defaultdict(dict)
        """
        for PERP liquidations, the following arguments are required: uly, state
        for FUTURES liquidations, the following arguments are required: uly, state, alias
        FUTURES, MARGIN and OPTION liquidation request not currently supported by the below
        """

        while True:
            for pair in pairs:
                if 'SWAP' in pair:
                    instrument_type = 'SWAP'
                    uly = pair.split("-")[0] + "-" + pair.split("-")[1]
                else:
                    continue

                for status in (FILLED, UNFILLED):
                    data = await self.http_conn.read(self.rest_endpoints[0].route('liquidations', sandbox=self.sandbox).format(instrument_type, status, uly))
                    data = json.loads(data, parse_float=Decimal)
                    timestamp = time.time()
                    if not data['data']:
                        LOG.info('%s: no liquidation data received for %s @ %s', self.id, pair, self.rest_endpoints[0].route('liquidations', sandbox=self.sandbox).format(instrument_type, status, uly))
                        continue
                    if len(data['data'][0]['details']) == 0 or (len(data['data'][0]['details']) > 0 and last_update.get(pair) == data['data'][0]['details'][0]):
                        continue
                    for entry in data['data'][0]['details']:
                        if pair in last_update:
                            if entry == last_update[pair].get(status):
                                break

                        liq = Liquidation(
                            self.id,
                            self.exchange_symbol_to_std_symbol(pair),
                            BUY if entry['side'] == 'buy' else SELL,
                            Decimal(entry['sz']),
                            Decimal(entry['bkPx']),
                            None,
                            status,
                            self.timestamp_normalize(int(entry['ts'])),
                            raw=data
                        )
                        await self.callback(LIQUIDATIONS, liq, timestamp)
                    last_update[pair][status] = data['data'][0]['details'][0]
                await asyncio.sleep(0.1)
            await asyncio.sleep(60)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__reset()

    def __reset(self):
        self._l2_book = {}
        self.seq_no = {}

    @classmethod
    def instrument_type(cls, symbol: str):
        return cls.info()['instrument_type'][symbol]

    async def _candle(self, msg: dict, timestamp: float):
        '''
        {
            "arg": {
                "channel": "candle1D",
                "instId": "BTC-USD-191227"
            },
            "data": [
                [
                    "1597026383085",     // ts
                    "8533.02",           // open
                    "8553.74",           // high
                    "8527.17",           // low
                    "8548.26",           // close
                    "45247",             // contracts, spot/margin -> amount of base ccy, derivatives -> contracts,
                    "529.5858061"        // currency, spot/margin -> amount of quote ccy, derivatives -> amount of base ccy
                ]
            ]
        }
        '''
        symbol = self.exchange_symbol_to_std_symbol(msg['arg']['instId'])
        ts = int(msg['data'][0][0]) / 1_000

        for entry in msg['data']:
            candle = Candle(
                self.id,
                symbol,
                ts,
                ts + self.candle_interval_map[self.candle_interval],
                self.candle_interval,
                None,
                Decimal(entry[1]),
                Decimal(entry[4]),
                Decimal(entry[2]),
                Decimal(entry[3]),
                Decimal(entry[5]),
                Decimal(entry[6]),
                timestamp,
                raw=msg
            )
            await self.callback(CANDLES, candle, timestamp)

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {"arg": {"channel": "tickers", "instId": "LTC-USD-200327"}, "data": [{"instType": "SWAP","instId": "LTC-USD-SWAP","last": "9999.99","lastSz": "0.1","askPx": "9999.99","askSz": "11","bidPx": "8888.88","bidSz": "5","open24h": "9000","high24h": "10000","low24h": "8888.88","volCcy24h": "2222","vol24h": "2222","sodUtc0": "2222","sodUtc8": "2222","ts": "1597026383085"}]}
        """
        pair = self.exchange_symbol_to_std_symbol(msg['arg']['instId'])
        for update in msg['data']:
            update_timestamp = self.timestamp_normalize(int(update['ts']))
            t = Ticker(
                self.id,
                pair,
                Decimal(update['bidPx']) if update['bidPx'] else Decimal(0),
                Decimal(update['askPx']) if update['askPx'] else Decimal(0),
                update_timestamp,
                raw=update
            )
            await self.callback(TICKER, t, timestamp)

    async def _open_interest(self, msg: dict, timestamp: float):
        """
        {
            'arg': {
                'channel': 'open-interest',
                'instId': 'BTC-USDT-SWAP
            },
            'data': [
                {
                    'instId': 'BTC-USDT-SWAP',
                    'instType': 'SWAP',
                    'oi':'565474',
                    'oiCcy': '5654.74',
                    'ts': '1630338003010'
                }
            ]
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['arg']['instId'])
        for update in msg['data']:
            oi = OpenInterest(
                self.id,
                symbol,
                Decimal(update['oi']),
                self.timestamp_normalize(int(update['ts'])),
                raw=update
            )
            await self.callback(OPEN_INTEREST, oi, timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        """
        {
            "arg": {
                "channel": "trades",
                "instId": "BTC-USD-191227"
            },
            "data": [
                {
                    "instId": "BTC-USD-191227",
                    "tradeId": "9",
                    "px": "0.016",
                    "sz": "50",
                    "side": "buy",
                    "ts": "1597026383085"
                }
            ]
        }
        """
        for trade in msg['data']:
            t = Trade(
                self.id,
                self.exchange_symbol_to_std_symbol(trade['instId']),
                BUY if trade['side'] == 'buy' else SELL,
                Decimal(trade['sz']),
                Decimal(trade['px']),
                self.timestamp_normalize(int(trade['ts'])),
                id=trade['tradeId'],
                raw=trade
            )
            await self.callback(TRADES, t, timestamp)

    async def _funding(self, msg: dict, timestamp: float):
        for update in msg['data']:
            f = Funding(
                self.id,
                self.exchange_symbol_to_std_symbol(update['instId']),
                None,
                Decimal(update['fundingRate']),
                self.timestamp_normalize(int(update['fundingTime'])),
                self.timestamp_normalize(int(update['ts'])),
                predicted_rate=Decimal(update['nextFundingRate']) if update['nextFundingRate'] != '' else None,
                raw=update
            )
            await self.callback(FUNDING, f, timestamp)

    def _sequence_ok(self, pair: str, update: dict) -> bool:
        sequence, previous = update.get('seqId'), update.get('prevSeqId')
        if sequence is None or previous is None:
            return True

        last = self.seq_no.get(pair)
        if previous == -1 or last is None:
            self.seq_no[pair] = sequence
            return True
        if sequence == last and previous == last:
            return False
        if previous != last:
            raise MissingSequenceNumber(f'{self.id}: {pair} book expected prevSeqId {last}, got {previous}')

        self.seq_no[pair] = sequence
        return True

    def _parse_snapshot(self, symbol: str, data) -> OrderBook:
        response = json.loads(data, parse_float=Decimal)
        if response.get('code') not in ('0', 0):
            raise ValueError(f"{self.id}: book snapshot for {symbol} returned code {response.get('code')!r}: {response.get('msg')!r}")
        if not response.get('data'):
            raise ValueError(f'{self.id}: book snapshot for {symbol} carried no data - is the instrument listed?')
        entry = response['data'][0]

        bids = {Decimal(price): Decimal(size) for price, size, *_ in entry['bids']}
        asks = {Decimal(price): Decimal(size) for price, size, *_ in entry['asks']}
        book = OrderBook(self.id, symbol, max_depth=self.max_depth, bids=bids, asks=asks)
        book.timestamp = self.timestamp_normalize(int(entry['ts'])) if entry.get('ts') else None
        book.sequence_number = int(entry['seqId']) if entry.get('seqId') is not None else None
        book.raw = entry
        return book

    async def _book(self, msg: dict, timestamp: float):
        if msg['action'] == 'snapshot':
            # snapshot
            pair = self.exchange_symbol_to_std_symbol(msg['arg']['instId'])
            for update in msg['data']:
                bids = {Decimal(price): Decimal(amount) for price, amount, *_ in update['bids']}
                asks = {Decimal(price): Decimal(amount) for price, amount, *_ in update['asks']}
                self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth, bids=bids, asks=asks)

                self.seq_no[pair] = update.get('seqId')
                await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(int(update['ts'])), raw=msg, sequence_number=update.get('seqId'))
        else:
            # update
            pair = self.exchange_symbol_to_std_symbol(msg['arg']['instId'])
            if pair not in self._l2_book:
                return
            for update in msg['data']:
                if not self._sequence_ok(pair, update):
                    continue
                delta = {BID: [], ASK: []}

                for side in ('bids', 'asks'):
                    s = BID if side == 'bids' else ASK
                    for price, amount, *_ in update[side]:
                        price = Decimal(price)
                        amount = Decimal(amount)
                        if amount == 0:
                            if price in self._l2_book[pair].book[s]:
                                delta[s].append((price, 0))
                                del self._l2_book[pair].book[s][price]
                        else:
                            delta[s].append((price, amount))
                            self._l2_book[pair].book[s][price] = amount

                await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(int(update['ts'])), raw=msg, delta=delta, sequence_number=update.get('seqId'))

    async def message_handler(self, msg: str, conn, timestamp: float):
        if msg == 'pong':
            return
        # DEFLATE compression, no header
        # msg = zlib.decompress(msg, -15)
        # not required, as websocket now set to "Per-Message Deflate"
        msg = json.loads(msg, parse_float=Decimal)

        if 'event' in msg:
            if msg['event'] == 'error':
                LOG.error("%s: Error: %s", self.id, msg)
            elif msg['event'] == 'subscribe':
                pass
            else:
                LOG.warning("%s: Unhandled event %s", self.id, msg)
        elif 'arg' in msg:
            if self.websocket_channels[L2_BOOK] in msg['arg']['channel']:
                await self._book(msg, timestamp)
            elif self.websocket_channels[TICKER] in msg['arg']['channel']:
                await self._ticker(msg, timestamp)
            elif self.websocket_channels[TRADES] in msg['arg']['channel']:
                await self._trade(msg, timestamp)
            elif self.websocket_channels[CANDLES] in msg['arg']['channel']:
                await self._candle(msg, timestamp)
            elif self.websocket_channels[FUNDING] in msg['arg']['channel']:
                await self._funding(msg, timestamp)
            elif self.websocket_channels[OPEN_INTEREST] in msg['arg']['channel']:
                await self._open_interest(msg, timestamp)
        else:
            LOG.warning("%s: Unhandled message %s", self.id, msg)

    async def subscribe(self, connection: AsyncConnection):
        channels = []
        for chan in connection.subscription:
            if chan == LIQUIDATIONS:
                self._spawn('liquidations', self._liquidations, connection.subscription[chan])
                continue
            for pair in connection.subscription[chan]:
                channels.append(self.build_subscription(chan, pair))

        if channels:
            await connection.write(json.dumps({"op": "subscribe", "args": channels}))

    def build_subscription(self, channel: str, ticker: str) -> dict:
        if channel in ['candle']:
            subscription_dict = {"channel": f"{channel}{self.candle_interval}",
                                 "instId": ticker}
        else:
            subscription_dict = {"channel": channel,
                                 "instId": ticker}
        return subscription_dict
