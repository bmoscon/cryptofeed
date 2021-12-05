'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
#some new imports are required:
import operator
import time

import asyncio
from decimal import Decimal
import logging
from datetime import datetime as dt, timezone
from typing import AsyncGenerator, Dict, Optional, Tuple, Union

#import new defines
from cryptofeed.defines import (
    CANDLES, FUNDING, L2_BOOK, L3_BOOK, OPEN_INTEREST, 
    POSITIONS, TICKER, TRADES, TRANSACTIONS, BALANCES, 
    ORDER_INFO, FILLS, BID_PRICE, BID_AMOUNT, ASK_PRICE, ASK_AMOUNT, 
    START, END, TIMESTAMP, SIDE, AMOUNT, PRICE,
    SYMBOL, BID, ASK, FEED, ID, TICKER)

#import the new helper classes
from cryptofeed.util.payloads import Payload
from cryptofeed.util.keymapping import Keymap
from cryptofeed.symbols import Symbol, Symbols
from cryptofeed.connection import HTTPSync
from cryptofeed.exceptions import UnsupportedDataFeed, UnsupportedSymbol, UnsupportedTradingOption
from cryptofeed.config import Config


LOG = logging.getLogger('feedhandler')
REST_LOG = logging.getLogger('cryptofeed.rest')

class Exchange:
    id = NotImplemented
    symbol_endpoint = NotImplemented
    websocket_endpoint = NotImplemented
    sandbox_endpoint = NotImplemented
    _parse_symbol_data = NotImplemented
    websocket_channels = NotImplemented
    request_limit = NotImplemented
    valid_candle_intervals = NotImplemented
    candle_interval_map = NotImplemented
    http_sync = HTTPSync()

    def __init__(self, config=None, sandbox=False, subaccount=None, **kwargs):
        self.config = Config(config=config)
        self.sandbox = sandbox
        self.subaccount = subaccount

        keys = self.config[self.id.lower()] if self.subaccount is None else self.config[self.id.lower()][self.subaccount]
        self.key_id = keys.key_id
        self.key_secret = keys.key_secret
        self.key_passphrase = keys.key_passphrase
        self.account_name = keys.account_name

        if not Symbols.populated(self.id):
            self.symbol_mapping()
        self.normalized_symbol_mapping, _ = Symbols.get(self.id)
        self.exchange_symbol_mapping = {value: key for key, value in self.normalized_symbol_mapping.items()}

    @classmethod
    def timestamp_normalize(cls, ts: dt) -> float:
        return ts.timestamp()

    #introduce functions to convert timestamps back and forth. 
    @classmethod
    def exchange_ts_to_std_ts(cls, ts) -> float:
        raise NotImplementedError
  
    @classmethod
    def std_ts_to_exchange_ts(cls, ts) -> float:
        raise NotImplementedError

    @classmethod
    def normalize_order_options(cls, option: str):
        if option not in cls.order_options:
            raise UnsupportedTradingOption
        return cls.order_options[option]

    @classmethod
    def info(cls) -> Dict:
        """
        Return information about the Exchange for REST and Websocket data channels
        """
        symbols = cls.symbol_mapping()
        data = Symbols.get(cls.id)[1]
        data['symbols'] = list(symbols.keys())
        data['channels'] = {
            'rest': list(cls.rest_channels) if hasattr(cls, 'rest_channels') else [],
            'websocket': list(cls.websocket_channels.keys())
        }
        return data

    @classmethod
    def symbols(cls, refresh=False) -> list:
        return list(cls.symbol_mapping(refresh=refresh).keys())

    @classmethod
    def symbol_mapping(cls, refresh=False) -> Dict:
        if Symbols.populated(cls.id) and not refresh:
            return Symbols.get(cls.id)[0]
        try:
            LOG.debug("%s: reading symbol information from %s", cls.id, cls.symbol_endpoint)
            if isinstance(cls.symbol_endpoint, list):
                data = []
                for ep in cls.symbol_endpoint:
                    data.append(cls.http_sync.read(ep, json=True, uuid=cls.id))
            elif isinstance(cls.symbol_endpoint, dict):
                data = []
                for input, output in cls.symbol_endpoint.items():
                    for d in cls.http_sync.read(input, json=True, uuid=cls.id):
                        data.append(cls.http_sync.read(f"{output}{d}", json=True, uuid=cls.id))
            else:
                data = cls.http_sync.read(cls.symbol_endpoint, json=True, uuid=cls.id)

            syms, info = cls._parse_symbol_data(data)
            Symbols.set(cls.id, syms, info)
            return syms
        except Exception as e:
            LOG.error("%s: Failed to parse symbol information: %s", cls.id, str(e), exc_info=True)
            raise

    @classmethod
    def std_channel_to_exchange(cls, channel: str) -> str:
        try:
            return cls.websocket_channels[channel]
        except KeyError:
            raise UnsupportedDataFeed(f'{channel} is not supported on {cls.id}')

    @classmethod
    def exchange_channel_to_std(cls, channel: str) -> str:
        for chan, exch in cls.websocket_channels.items():
            if exch == channel:
                return chan
        raise ValueError(f'Unable to normalize channel {cls.id}')

    @classmethod
    def is_authenticated_channel(cls, channel: str) -> bool:
        return channel in (ORDER_INFO, FILLS, TRANSACTIONS, BALANCES, POSITIONS)

    def exchange_symbol_to_std_symbol(self, symbol: str) -> str:
        try:
            return self.exchange_symbol_mapping[symbol]
        except KeyError:
            raise UnsupportedSymbol(f'{symbol} is not supported on {self.id}')

    def std_symbol_to_exchange_symbol(self, symbol: Union[str, Symbol]) -> str:
        if isinstance(symbol, Symbol):
            symbol = symbol.normalized
        try:
            return self.normalized_symbol_mapping[symbol]
        except KeyError:
            raise UnsupportedSymbol(f'{symbol} is not supported on {self.id}')


class RestExchange:
    api = NotImplemented
    sandbox_api = NotImplemented
    rest_channels = NotImplemented
    order_options = NotImplemented
    '''
    add new class variables, see the BinanceRestMixin class for a demo 
    '''
    api_endpoints = NotImplemented
    methods = NotImplemented
    payload_as_params = NotImplemented

    def _sync_run_coroutine(self, coroutine):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coroutine)

    def _sync_run_generator(self, generator: AsyncGenerator):
        loop = asyncio.get_event_loop()

        try:
            while True:
                yield loop.run_until_complete(generator.__anext__())
        except StopAsyncIteration:
            return

    def _datetime_normalize(self, timestamp: Union[str, int, float, dt]) -> float:
        if isinstance(timestamp, (float, int)):
            return timestamp
        if isinstance(timestamp, dt):
            return timestamp.replace(tzinfo=timezone.utc).timestamp()
        if isinstance(timestamp, str):
            try:
                return dt.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                return dt.strptime(timestamp, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()

    def _interval_normalize(self, start, end) -> Tuple[Optional[float], Optional[float]]:
        if start:
            start = self._datetime_normalize(start)
            if not end:
                end = dt.now()
        if end:
            end = self._datetime_normalize(end)
        return start, end if start else None

    # public / non account specific
    def ticker_sync(self, symbol: str, retry_count=1, retry_delay=60):
        co = self.ticker(symbol, retry_count=retry_count, retry_delay=retry_delay)
        return self._sync_run_coroutine(co)

    async def ticker(self, symbol: str, retry_count=1, retry_delay=60):
        raise NotImplementedError

    def candles_sync(self, symbol: str, start=None, end=None, interval='1m', retry_count=1, retry_delay=60):
        gen = self.candles(symbol, start=start, end=end, interval=interval, retry_count=retry_count, retry_delay=retry_delay)
        return self._sync_run_generator(gen)

    async def candles(self, symbol: str, start=None, end=None, interval='1m', retry_count=1, retry_delay=60):
        raise NotImplementedError

    def trades_sync(self, symbol: str, start=None, end=None, retry_count=1, retry_delay=60):
        gen = self.trades(symbol, start=start, end=end, retry_count=retry_count, retry_delay=retry_delay)
        return self._sync_run_generator(gen)

    async def trades(self, symbol: str, start=None, end=None, retry_count=1, retry_delay=60):
        raise NotImplementedError

    def funding_sync(self, symbol: str, retry_count=1, retry_delay=60):
        co = self.funding(symbol, retry_count=retry_count, retry_delay=retry_delay)
        return self._sync_run_coroutine(co)

    async def funding(self, symbol: str, retry_count=1, retry_delay=60):
        raise NotImplementedError

    def open_interest_sync(self, symbol: str, retry_count=1, retry_delay=60):
        co = self.open_interest(symbol, retry_count=retry_count, retry_delay=retry_delay)
        return self._sync_run_coroutine(co)

    async def open_interest(self, symbol: str, retry_count=1, retry_delay=60):
        raise NotImplementedError

    def l2_book_sync(self, symbol: str, retry_count=1, retry_delay=60):
        co = self.l2_book(symbol, retry_count=retry_count, retry_delay=retry_delay)
        return self._sync_run_coroutine(co)

    async def l2_book(self, symbol: str, retry_count=1, retry_delay=60):
        raise NotImplementedError

    def l3_book_sync(self, symbol: str, retry_count=1, retry_delay=60):
        co = self.l3_book(symbol, retry_count=retry_count, retry_delay=retry_delay)
        return self._sync_run_coroutine(co)

    async def l3_book(self, symbol: str, retry_count=1, retry_delay=60):
        raise NotImplementedError

    # account specific
    def place_order_sync(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, **kwargs):
        co = self.place_order(symbol, side, order_type, amount, price, **kwargs)
        return self._sync_run_coroutine(co)

    async def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, **kwargs):
        raise NotImplementedError

    def cancel_order_sync(self, order_id: str, **kwargs):
        co = self.cancel_order(order_id, **kwargs)
        return self._sync_run_coroutine(co)

    async def cancel_order(self, order_id: str, **kwargs):
        raise NotImplementedError

    def orders_sync(self, symbol: str = None):
        co = self.orders(symbol)
        return self._sync_run_coroutine(co)

    async def orders(self, symbol: str = None):
        raise NotImplementedError

    def order_status_sync(self, order_id: str):
        co = self.order_status(order_id)
        return self._sync_run_coroutine(co)

    async def order_status(self, order_id: str):
        raise NotImplementedError

    def trade_history_sync(self, symbol: str = None, start=None, end=None):
        co = self.trade_history(symbol, start, end)
        return self._sync_run_coroutine(co)

    async def trade_history(self, symbol: str = None, start=None, end=None):
        raise NotImplementedError

    def balances_sync(self):
        co = self.balances()
        return self._sync_run_coroutine(co)

    async def balances(self):
        raise NotImplementedError

    def positions_sync(self, **kwargs):
        co = self.positions(**kwargs)
        return self._sync_run_coroutine(co)

    async def positions(self, **kwargs):
        raise NotImplementedError

    def ledger_sync(self, aclass=None, asset=None, ledger_type=None, start=None, end=None):
        co = self.ledger(aclass, asset, ledger_type, start, end)
        return self._sync_run_coroutine(co)

    async def ledger(self, aclass=None, asset=None, ledger_type=None, start=None, end=None):
        raise NotImplementedError
    
    '''below are the backbone functions. These work by setting the payload class (see payloads.py in cryptofeed.utils),
    making a request, and post_processing the response'''

    async def _rest_ticker(self, payload : Payload, keymap : Keymap, symbol : str) -> dict:
        payload[SYMBOL] = self.std_symbol_to_exchange_symbol(symbol)
        ex_response = await self._request(TICKER, payload)
        return self._process_ticker(ex_response, keymap)

    async def _rest_l2_book(self, payload : Payload, keymap : Keymap, symbol : str) -> dict:
        payload[SYMBOL] = self.std_symbol_to_exchange_symbol(symbol)
        ex_response = await self._request(L2_BOOK, payload)
        return self._process_L2_book(ex_response, keymap)

    async def _rest_trades(self, payload : Payload, keymap : Keymap, symbol : str, start = None, 
                end = None, max_timeframe = None,) -> list:
        payload[SYMBOL] = self.std_symbol_to_exchange_symbol(symbol)
        if start:
            async for data in self._historical_trades(payload, keymap, symbol, start, end, max_timeframe):
                return data
        else:
            ex_response = await self._request(TRADES, payload)
            return self._process_trades(ex_response, keymap)

    '''
    because reponses are unified within the base RestExchange, methods such as pooling for historical data can 
    easily be done here.
    '''
    async def _historical_trades(self, payload, keymap, symbol, start, end, 
                           max_timeframe):
        start = start
        end = time.time() if not end else end
        end_point = start + max_timeframe if max_timeframe else end
        payload[START] = self.std_ts_to_exchange_ts(start)
        payload[END] = self.std_ts_to_exchange_ts(end_point) if payload[END] is not None else None
        while True:
            ex_response = await self._request(TRADES, payload)
            new_data = self._process_trades(ex_response, keymap)
            if (new_data[-1][TIMESTAMP] == start - 0.0001) or (end  < start + max_timeframe if max_timeframe else False):
                break
            yield new_data
            start = new_data[-1][TIMESTAMP] + 0.0001
            end_point = start + max_timeframe if max_timeframe else end
            payload[START] = self.std_ts_to_exchange_ts(start)
            payload[END] = self.std_ts_to_exchange_ts(end_point) if payload[END] is not None else None

    '''
    The actual request function is below, most of the requied feilds are defined in dictionaries on the 
    RestMixin class
    '''

    async def _request(self, command: str, payload : dict) -> dict:
        payload = payload()
        resp = await self.http_conn.request(
                                    url = self.api_calls[command][1],
                                    method = self.api_calls[command][0],
                                    payload = payload if payload else None, 
                                    )
        return resp
    '''
    this is really where the magic works, values from the response can easily be extracted using the supplied
    keymap (see keymaps.py in cryptofeed.util) and some minimal postprocessing is applied to get the data in the wanted 
    format
    '''

    def _process_ticker(self, ex_response : dict, keymap : Keymap) -> dict:
        data = {
            SYMBOL : None,
            FEED   : None,
            BID    : None,
            ASK    : None
        }
        
        data.update(**keymap(ex_response))
        data[SYMBOL], data[FEED] = data[SYMBOL][0], data[FEED][0]
        data[BID], data[ASK] = data[BID][0], data[ASK][0]
        return data
    
    def _process_trades(self, ex_response : dict, keymap : Keymap) -> list:
        data = {
            TIMESTAMP   : None,
            SYMBOL      : None,
            ID          : None,
            FEED        : None,
            SIDE        : None,
            AMOUNT      : None,
            PRICE       : None
            
        }

        data.update(keymap(ex_response))
        sequence_length = len(next(val for val in data.values() if type(val) is list))
        
        if sequence_length == 0:
            LOG.warn(
                f'No data could be retrived for {TRADES} api call to {self.id}... returning an empty list'
                )
            return []

        
        data.update({k : list((*v,) * sequence_length) for k, v in data.items() if k in keymap.retrive_apriori_data().keys() or v is None})
        return sorted(
            [dict(zip(data.keys(), a)) for a in zip(*data.values())],
            key=operator.itemgetter(TIMESTAMP)
        )
        
    def _process_L2_book(self, ex_resp, keymap : Keymap):
        unified_resp = keymap(ex_resp) 
        
        # zip prices and amounts into sorted dictionary of type bids and asks
        return {
            BID : sorted(
                [{Decimal(a[0]) : Decimal(a[1]) for a in zip(unified_resp[BID_PRICE], unified_resp[BID_AMOUNT])}],
                ),
            ASK : sorted( 
                [{Decimal(a[0]) : Decimal(a[1]) for a in zip(unified_resp[ASK_PRICE], unified_resp[ASK_AMOUNT])}],
            )
        }    

    def __getitem__(self, key):
        if key == TRADES:
            return self.trades
        elif key == CANDLES:
            return self.candles
        elif key == FUNDING:
            return self.funding
        elif key == L2_BOOK:
            return self.l2_book
        elif key == L3_BOOK:
            return self.l3_book
        elif key == TICKER:
            return self.ticker
        elif key == OPEN_INTEREST:
            return self.open_interest
