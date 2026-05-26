'''
Unit tests for the LMEX spot and futures connectors.

These tests exercise message parsing logic without any live network calls.
They inject synthetic symbol data into the Symbols singleton, create feed
instances, and push raw JSON payloads through the handlers, verifying
correct cryptofeed data types and field values.

Key connector facts under test:
  Spot:
    - TRADES via WebSocket (tradeHistoryApi:<SYMBOL>)
    - L2_BOOK via REST polling (_book_poll_handler)
    - ORDER_INFO via WebSocket (notificationsApi)

  Futures:
    - TRADES via WebSocket; WS uses internal symbol codes (e.g. BTCPFC)
    - L2_BOOK via REST polling
    - FUNDING via REST polling
    - Only perpetuals (timeBasedContract=False, symbol ends with -PERP)
    - Normalised quote currency taken from REST data (USDT, not USD)
    - Normalised symbols: BTC-USDT-PERP, ETH-USDT-PERP
'''
import json
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from cryptofeed.defines import (
    BUY, FILLED, FUNDING, L2_BOOK, LMEX, LMEX_FUTURES,
    OPEN, ORDER_INFO, PARTIAL, SELL, TRADES,
)
from cryptofeed.exchanges import LMEX as LMEXFeed, LMEXFutures
from cryptofeed.symbols import Symbols
from cryptofeed.types import Funding, OrderBook, Trade


# ---------------------------------------------------------------------------
# Shared test fixture helpers
# ---------------------------------------------------------------------------

# Spot: normalized_symbol -> exchange_symbol
_SPOT_NORM = {'BTC-USD': 'BTC-USD', 'ETH-EUR': 'ETH-EUR'}
# Futures: normalized_symbol -> exchange_symbol  (USDT-quoted perps)
_PERP_NORM = {'BTC-USDT-PERP': 'BTC-PERP', 'ETH-USDT-PERP': 'ETH-PERP'}

_SPOT_INFO = {
    'instrument_type': {'BTC-USD': 'spot', 'ETH-EUR': 'spot'},
    'tick_size': {'BTC-USD': Decimal('0.1')},
}
_PERP_INFO = {
    'instrument_type': {'BTC-USDT-PERP': 'perpetual', 'ETH-USDT-PERP': 'perpetual'},
    'contract_size': {'BTC-USDT-PERP': Decimal('0.00001')},
}


def _seed_symbols():
    '''Pre-populate the Symbols singleton so __init__ does not hit the network.'''
    Symbols.set(LMEX, _SPOT_NORM, _SPOT_INFO)
    Symbols.set(LMEX_FUTURES, _PERP_NORM, _PERP_INFO)


def _make_spot(symbols=None, channels=None, callbacks=None):
    _seed_symbols()
    return LMEXFeed(
        symbols=symbols or ['BTC-USD'],
        channels=channels or [TRADES],
        callbacks=callbacks or {},
    )


def _make_futures(symbols=None, channels=None, callbacks=None):
    _seed_symbols()
    return LMEXFutures(
        symbols=symbols or ['BTC-USDT-PERP'],
        channels=channels or [TRADES, FUNDING],
        callbacks=callbacks or {},
    )


# ---------------------------------------------------------------------------
# Timestamp normalization
# ---------------------------------------------------------------------------

class TestTimestampNormalize(unittest.TestCase):
    def test_spot_ms_to_seconds(self):
        self.assertAlmostEqual(LMEXFeed.timestamp_normalize(1_000), 1.0)
        self.assertAlmostEqual(LMEXFeed.timestamp_normalize(1_500_000), 1_500.0)

    def test_futures_ms_to_seconds(self):
        self.assertAlmostEqual(LMEXFutures.timestamp_normalize(60_000), 60.0)


# ---------------------------------------------------------------------------
# Spot: Symbol parsing
# ---------------------------------------------------------------------------

class TestSpotSymbolParsing(unittest.TestCase):
    MARKET_SUMMARY = [
        {
            'symbol': 'BTC-USD', 'base': 'BTC', 'quote': 'USD',
            'active': True, 'futures': False,
            'minPriceIncrement': 0.1, 'minOrderSize': 0.00001,
        },
        {
            'symbol': 'ETH-EUR', 'base': 'ETH', 'quote': 'EUR',
            'active': True, 'futures': False,
            'minPriceIncrement': 0.01, 'minOrderSize': 0.001,
        },
        {
            # Perpetual — must be ignored by spot connector
            'symbol': 'BTC-PERP', 'base': 'BTC', 'quote': None,
            'active': True, 'futures': True,
        },
        {
            # Inactive — must be ignored
            'symbol': 'OLD-USD', 'base': 'OLD', 'quote': 'USD',
            'active': False, 'futures': False,
        },
    ]

    def test_returns_only_spot_symbols(self):
        ret, _ = LMEXFeed._parse_symbol_data(self.MARKET_SUMMARY)
        self.assertIn('BTC-USD', ret)
        self.assertIn('ETH-EUR', ret)
        self.assertNotIn('BTC-USDT-PERP', ret)
        self.assertNotIn('OLD-USD', ret)

    def test_exchange_symbol_preserved(self):
        ret, _ = LMEXFeed._parse_symbol_data(self.MARKET_SUMMARY)
        self.assertEqual(ret['BTC-USD'], 'BTC-USD')
        self.assertEqual(ret['ETH-EUR'], 'ETH-EUR')

    def test_tick_size_captured(self):
        _, info = LMEXFeed._parse_symbol_data(self.MARKET_SUMMARY)
        self.assertEqual(info['tick_size']['BTC-USD'], Decimal('0.1'))
        self.assertEqual(info['tick_size']['ETH-EUR'], Decimal('0.01'))


# ---------------------------------------------------------------------------
# Futures: Symbol parsing
# ---------------------------------------------------------------------------

class TestFuturesSymbolParsing(unittest.TestCase):
    MARKET_SUMMARY = [
        {
            # Perpetual — must be included; no 'futures' key, quote is USDT
            'symbol': 'BTC-PERP', 'base': 'BTC', 'quote': 'USDT',
            'active': True, 'timeBasedContract': False,
            'minPriceIncrement': 0.5, 'contractSize': 0.00001,
        },
        {
            'symbol': 'ETH-PERP', 'base': 'ETH', 'quote': 'USDT',
            'active': True, 'timeBasedContract': False,
            'minPriceIncrement': 0.05, 'contractSize': 0.001,
        },
        {
            # Dated/time-based future — must be excluded
            'symbol': 'BTC-260626', 'base': 'BTC', 'quote': 'USDT',
            'active': True, 'timeBasedContract': True,
        },
        {
            # Inactive — must be excluded
            'symbol': 'OLD-PERP', 'base': 'OLD', 'quote': 'USDT',
            'active': False, 'timeBasedContract': False,
        },
    ]

    def test_returns_only_perpetuals(self):
        ret, _ = LMEXFutures._parse_symbol_data(self.MARKET_SUMMARY)
        # Perpetuals are included (USDT-quoted)
        self.assertIn('BTC-USDT-PERP', ret)
        self.assertIn('ETH-USDT-PERP', ret)
        # Dated and inactive are excluded
        self.assertNotIn('BTC-USDT', ret)
        self.assertNotIn('OLD-USDT-PERP', ret)

    def test_exchange_symbol_preserved(self):
        ret, _ = LMEXFutures._parse_symbol_data(self.MARKET_SUMMARY)
        self.assertEqual(ret['BTC-USDT-PERP'], 'BTC-PERP')
        self.assertEqual(ret['ETH-USDT-PERP'], 'ETH-PERP')

    def test_contract_size_captured(self):
        _, info = LMEXFutures._parse_symbol_data(self.MARKET_SUMMARY)
        self.assertEqual(info['contract_size']['BTC-USDT-PERP'], Decimal('0.00001'))

    def test_quote_from_rest_not_hardcoded(self):
        '''Quote currency must come from the REST data, not a hardcoded constant.'''
        ret, _ = LMEXFutures._parse_symbol_data(self.MARKET_SUMMARY)
        # Should be USDT-quoted, NOT USD-quoted
        self.assertNotIn('BTC-USD-PERP', ret)
        self.assertIn('BTC-USDT-PERP', ret)


# ---------------------------------------------------------------------------
# Spot: Trade message
# ---------------------------------------------------------------------------

class TestSpotTrade(unittest.IsolatedAsyncioTestCase):
    TRADE_MSG = {
        'topic': 'tradeHistoryApi:BTC-USD',
        'data': [
            {
                'symbol': 'BTC-USD',
                'side': 'SELL',
                'size': 0.0145,
                'price': 76653.1,
                'tradeId': 31626447,
                'timestamp': 1_700_000_000_000,
            }
        ],
    }

    async def test_trade_fields(self):
        captured = []

        async def cb(trade, _): captured.append(trade)

        feed = _make_spot(callbacks={TRADES: cb})
        await feed._trade(self.TRADE_MSG, 9999.0)

        self.assertEqual(len(captured), 1)
        t = captured[0]
        self.assertIsInstance(t, Trade)
        self.assertEqual(t.exchange, LMEX)
        self.assertEqual(t.symbol, 'BTC-USD')
        self.assertEqual(t.side, SELL)
        self.assertEqual(t.amount, Decimal('0.0145'))
        self.assertEqual(t.price, Decimal('76653.1'))
        self.assertAlmostEqual(t.timestamp, 1_700_000_000.0)
        self.assertEqual(t.id, '31626447')

    async def test_buy_side(self):
        captured = []

        async def cb(trade, _): captured.append(trade)

        feed = _make_spot(callbacks={TRADES: cb})
        msg = {
            'topic': 'tradeHistoryApi:BTC-USD',
            'data': [{'symbol': 'BTC-USD', 'side': 'BUY',
                      'size': 1.0, 'price': 50000.0,
                      'tradeId': 1, 'timestamp': 1_000}],
        }
        await feed._trade(msg, 0.0)
        self.assertEqual(captured[0].side, BUY)

    async def test_multiple_trades_in_one_message(self):
        captured = []

        async def cb(trade, _): captured.append(trade)

        feed = _make_spot(callbacks={TRADES: cb})
        msg = {
            'topic': 'tradeHistoryApi:BTC-USD',
            'data': [
                {'symbol': 'BTC-USD', 'side': 'BUY', 'size': 0.1, 'price': 50000.0, 'tradeId': 1, 'timestamp': 1_000},
                {'symbol': 'BTC-USD', 'side': 'SELL', 'size': 0.2, 'price': 50001.0, 'tradeId': 2, 'timestamp': 2_000},
            ],
        }
        await feed._trade(msg, 0.0)
        self.assertEqual(len(captured), 2)
        self.assertEqual(captured[0].side, BUY)
        self.assertEqual(captured[1].side, SELL)


# ---------------------------------------------------------------------------
# Spot: L2 order book via REST polling
# ---------------------------------------------------------------------------

class TestSpotOrderBookREST(unittest.IsolatedAsyncioTestCase):
    '''Tests for _book_poll_handler (REST snapshot polling).'''

    REST_RESPONSE = json.dumps({
        'symbol': 'BTC-USD',
        'buyQuote': [
            {'price': '76731.9', 'size': '0.0016'},
            {'price': '76730.0', 'size': '0.005'},
        ],
        'sellQuote': [
            {'price': '76732.0', 'size': '0.0085'},
            {'price': '76733.0', 'size': '0.5'},
        ],
        'timestamp': 1_779_787_268_534,
    })

    async def test_snapshot_populates_book(self):
        feed = _make_spot()
        feed.book_callback = AsyncMock()

        await feed._book_poll_handler(self.REST_RESPONSE, MagicMock(), 0.0)

        book = feed._l2_book['BTC-USD']
        self.assertIsInstance(book, OrderBook)
        self.assertIn(Decimal('76731.9'), book.book.bids)
        self.assertIn(Decimal('76732.0'), book.book.asks)
        self.assertEqual(book.book.bids[Decimal('76731.9')], Decimal('0.0016'))
        self.assertEqual(book.book.asks[Decimal('76732.0')], Decimal('0.0085'))

    async def test_snapshot_calls_book_callback_no_delta(self):
        feed = _make_spot()
        feed.book_callback = AsyncMock()

        await feed._book_poll_handler(self.REST_RESPONSE, MagicMock(), 0.0)

        feed.book_callback.assert_awaited_once()
        _, kwargs = feed.book_callback.call_args
        self.assertIsNone(kwargs.get('delta'),
                          'REST snapshot must always pass delta=None')

    async def test_zero_size_levels_excluded(self):
        '''REST snapshots should skip levels with size == 0.'''
        data = json.dumps({
            'symbol': 'BTC-USD',
            'buyQuote': [{'price': '50000.0', 'size': '0.0'}],
            'sellQuote': [{'price': '50001.0', 'size': '1.0'}],
            'timestamp': 1_700_000_000_000,
        })
        feed = _make_spot()
        feed.book_callback = AsyncMock()

        await feed._book_poll_handler(data, MagicMock(), 0.0)

        book = feed._l2_book['BTC-USD']
        self.assertNotIn(Decimal('50000.0'), book.book.bids,
                         'Zero-size level must not be inserted')
        self.assertIn(Decimal('50001.0'), book.book.asks)

    async def test_numeric_prices_handled(self):
        '''Prices/sizes may be numbers instead of strings in some versions.'''
        data = json.dumps({
            'symbol': 'BTC-USD',
            'buyQuote': [{'price': 50000.0, 'size': 0.5}],
            'sellQuote': [{'price': 50001.0, 'size': 1.0}],
            'timestamp': 1_700_000_000_000,
        })
        feed = _make_spot()
        feed.book_callback = AsyncMock()

        await feed._book_poll_handler(data, MagicMock(), 0.0)

        book = feed._l2_book['BTC-USD']
        self.assertIn(Decimal('50000.0'), book.book.bids)


# ---------------------------------------------------------------------------
# Futures: Trade message (BTCPFC internal code conversion)
# ---------------------------------------------------------------------------

class TestFuturesTrade(unittest.IsolatedAsyncioTestCase):
    '''
    Futures WS sends trades with internal symbol codes (BTCPFC, ETHPFC).
    The connector must convert: base + "PFC" -> base + "-PERP" -> normalised.
    '''

    async def test_btcpfc_converted_to_std(self):
        captured = []

        async def cb(trade, _): captured.append(trade)

        feed = _make_futures(callbacks={TRADES: cb})
        msg = {
            'topic': 'tradeHistoryApi',
            'data': [
                {
                    'symbol': 'BTCPFC',
                    'side': 'SELL',
                    'size': 6530,
                    'price': 77099.9,
                    'tradeId': 35993384,
                    'timestamp': 1_779_800_209_269,
                }
            ],
        }
        await feed._trade(msg, 0.0)

        self.assertEqual(len(captured), 1)
        t = captured[0]
        self.assertIsInstance(t, Trade)
        self.assertEqual(t.exchange, LMEX_FUTURES)
        self.assertEqual(t.symbol, 'BTC-USDT-PERP')
        self.assertEqual(t.side, SELL)
        self.assertEqual(t.price, Decimal('77099.9'))
        self.assertEqual(t.amount, Decimal('6530'))
        self.assertEqual(t.id, '35993384')

    async def test_ethpfc_converted_to_std(self):
        captured = []

        async def cb(trade, _): captured.append(trade)

        feed = _make_futures(
            symbols=['BTC-USDT-PERP', 'ETH-USDT-PERP'],
            callbacks={TRADES: cb},
        )
        msg = {
            'topic': 'tradeHistoryApi',
            'data': [{'symbol': 'ETHPFC', 'side': 'BUY',
                      'size': 100, 'price': 3000.0,
                      'tradeId': 1, 'timestamp': 1_000}],
        }
        await feed._trade(msg, 0.0)

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].symbol, 'ETH-USDT-PERP')
        self.assertEqual(captured[0].side, BUY)

    async def test_multiple_trades_per_message(self):
        captured = []

        async def cb(trade, _): captured.append(trade)

        feed = _make_futures(callbacks={TRADES: cb})
        msg = {
            'topic': 'tradeHistoryApi',
            'data': [
                {'symbol': 'BTCPFC', 'side': 'BUY', 'size': 100, 'price': 50001.0, 'tradeId': 1, 'timestamp': 1_000},
                {'symbol': 'BTCPFC', 'side': 'SELL', 'size': 200, 'price': 50000.0, 'tradeId': 2, 'timestamp': 2_000},
            ],
        }
        await feed._trade(msg, 0.0)
        self.assertEqual(len(captured), 2)

    async def test_unknown_ws_code_skipped(self):
        '''Symbol codes not following the *PFC pattern should be silently skipped.'''
        captured = []

        async def cb(trade, _): captured.append(trade)

        feed = _make_futures(callbacks={TRADES: cb})
        msg = {
            'topic': 'tradeHistoryApi',
            'data': [{'symbol': 'UNKNOWN', 'side': 'BUY',
                      'size': 1, 'price': 100.0, 'tradeId': 99, 'timestamp': 1_000}],
        }
        await feed._trade(msg, 0.0)
        self.assertEqual(len(captured), 0)


# ---------------------------------------------------------------------------
# Futures: L2 order book via REST polling
# ---------------------------------------------------------------------------

class TestFuturesOrderBookREST(unittest.IsolatedAsyncioTestCase):
    REST_RESPONSE = json.dumps({
        'symbol': 'BTC-PERP',
        'buyQuote': [
            {'price': '77054.5', 'size': '108350'},
            {'price': '77054.0', 'size': '50000'},
        ],
        'sellQuote': [
            {'price': '77054.7', 'size': '98250'},
            {'price': '77055.0', 'size': '30000'},
        ],
        'timestamp': 1_779_800_650_027,
    })

    async def test_snapshot_populates_book(self):
        feed = _make_futures(channels=[L2_BOOK, TRADES])
        _seed_symbols()
        feed.book_callback = AsyncMock()

        await feed._book_poll_handler(self.REST_RESPONSE, MagicMock(), 0.0)

        book = feed._l2_book['BTC-USDT-PERP']
        self.assertIsInstance(book, OrderBook)
        self.assertIn(Decimal('77054.5'), book.book.bids)
        self.assertIn(Decimal('77054.7'), book.book.asks)

    async def test_book_callback_called_no_delta(self):
        feed = _make_futures(channels=[L2_BOOK, TRADES])
        _seed_symbols()
        feed.book_callback = AsyncMock()

        await feed._book_poll_handler(self.REST_RESPONSE, MagicMock(), 0.0)

        feed.book_callback.assert_awaited_once()
        _, kwargs = feed.book_callback.call_args
        self.assertIsNone(kwargs.get('delta'))


# ---------------------------------------------------------------------------
# Futures: Funding rate (REST poll)
# ---------------------------------------------------------------------------

class TestFuturesFunding(unittest.IsolatedAsyncioTestCase):
    MARKET_SUMMARY = [
        {
            'symbol': 'BTC-PERP',
            'last': 50000.0,
            'fundingRate': 0.0001,
            'timeBasedContract': False,
            'active': True,
            'timestamp': 1_700_000_000_000,
        }
    ]

    async def test_funding_emitted(self):
        captured = []

        async def cb(funding, _): captured.append(funding)

        feed = _make_futures(callbacks={FUNDING: cb})
        feed.subscription = {FUNDING: ['BTC-USDT-PERP']}

        raw = json.dumps(self.MARKET_SUMMARY)
        await feed._funding_handler(raw, MagicMock(), 0.0)

        self.assertEqual(len(captured), 1)
        f = captured[0]
        self.assertIsInstance(f, Funding)
        self.assertEqual(f.exchange, LMEX_FUTURES)
        self.assertEqual(f.symbol, 'BTC-USDT-PERP')
        self.assertEqual(f.rate, Decimal('0.0001'))
        self.assertEqual(f.mark_price, Decimal('50000.0'))
        self.assertAlmostEqual(f.timestamp, 1_700_000_000.0)

    async def test_funding_filters_by_subscription(self):
        '''Symbols not in the subscription list must be silently skipped.'''
        captured = []

        async def cb(funding, _): captured.append(funding)

        feed = _make_futures(callbacks={FUNDING: cb})
        feed.subscription = {FUNDING: ['ETH-USDT-PERP']}  # BTC not subscribed

        raw = json.dumps(self.MARKET_SUMMARY)
        await feed._funding_handler(raw, MagicMock(), 0.0)

        self.assertEqual(len(captured), 0)

    async def test_dated_futures_excluded_from_funding(self):
        '''Time-based contracts must never generate a FUNDING callback.'''
        captured = []

        async def cb(funding, _): captured.append(funding)

        feed = _make_futures(callbacks={FUNDING: cb})
        feed.subscription = {FUNDING: ['BTC-USDT-PERP']}

        dated = [{'symbol': 'BTC-260626', 'last': 50200.0, 'fundingRate': 0.0,
                  'timeBasedContract': True, 'active': True, 'timestamp': 1_000}]
        await feed._funding_handler(json.dumps(dated), MagicMock(), 0.0)

        self.assertEqual(len(captured), 0)


# ---------------------------------------------------------------------------
# Message handler routing — Spot
# ---------------------------------------------------------------------------

class TestSpotMessageHandlerRouting(unittest.IsolatedAsyncioTestCase):
    async def _make_feed(self):
        feed = _make_spot()
        feed._trade = AsyncMock()
        feed._order_info = AsyncMock()
        return feed

    async def test_routes_trade(self):
        feed = await self._make_feed()
        msg = json.dumps({'topic': 'tradeHistoryApi:BTC-USD', 'data': []})
        await feed.message_handler(msg, MagicMock(), 0.0)
        feed._trade.assert_awaited_once()

    async def test_routes_notifications(self):
        feed = await self._make_feed()
        msg = json.dumps({'topic': 'notificationsApi', 'data': []})
        await feed.message_handler(msg, MagicMock(), 0.0)
        feed._order_info.assert_awaited_once()

    async def test_ignores_pong(self):
        feed = await self._make_feed()
        msg = json.dumps({'event': 'pong'})
        await feed.message_handler(msg, MagicMock(), 0.0)
        feed._trade.assert_not_awaited()

    async def test_ignores_subscribe_ack(self):
        feed = await self._make_feed()
        msg = json.dumps({'event': 'subscribe', 'channel': ['tradeHistoryApi:BTC-USD']})
        await feed.message_handler(msg, MagicMock(), 0.0)
        feed._trade.assert_not_awaited()


# ---------------------------------------------------------------------------
# Message handler routing — Futures
# ---------------------------------------------------------------------------

class TestFuturesMessageHandlerRouting(unittest.IsolatedAsyncioTestCase):
    async def _make_feed(self):
        feed = _make_futures()
        feed._trade = AsyncMock()
        feed._order_info = AsyncMock()
        return feed

    async def test_routes_trade_no_suffix(self):
        '''Futures WS emits topic "tradeHistoryApi" (no symbol suffix).'''
        feed = await self._make_feed()
        msg = json.dumps({'topic': 'tradeHistoryApi', 'data': []})
        await feed.message_handler(msg, MagicMock(), 0.0)
        feed._trade.assert_awaited_once()

    async def test_routes_trade_with_suffix(self):
        '''Connector also accepts topic "tradeHistoryApi:BTC-PERP" for robustness.'''
        feed = await self._make_feed()
        msg = json.dumps({'topic': 'tradeHistoryApi:BTC-PERP', 'data': []})
        await feed.message_handler(msg, MagicMock(), 0.0)
        feed._trade.assert_awaited_once()

    async def test_routes_notifications(self):
        feed = await self._make_feed()
        msg = json.dumps({'topic': 'notificationsApi', 'data': []})
        await feed.message_handler(msg, MagicMock(), 0.0)
        feed._order_info.assert_awaited_once()

    async def test_ignores_pong(self):
        feed = await self._make_feed()
        msg = json.dumps({'event': 'pong'})
        await feed.message_handler(msg, MagicMock(), 0.0)
        feed._trade.assert_not_awaited()


if __name__ == '__main__':
    unittest.main(verbosity=2)
