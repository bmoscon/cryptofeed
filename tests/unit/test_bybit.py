'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal

import pytest

from cryptofeed import _json as json
from cryptofeed.defines import BUY, BYBIT, FUNDING, INDEX, L2_BOOK, LIQUIDATIONS, OPEN_INTEREST, PERPETUAL, SELL, SPOT, TICKER, TRADES
from cryptofeed.exchanges import Bybit
from cryptofeed.symbols import Symbols


LINEAR = 'wss://stream.bybit.com/v5/public/linear'
SPOT_WS = 'wss://stream.bybit.com/v5/public/spot'

SYMBOLS = {'BTC-USDT-PERP': 'BTCUSDT', 'BTC-USDT': 'BTC/USDT'}
INFO = {'instrument_type': {'BTC-USDT-PERP': PERPETUAL, 'BTC-USDT': SPOT}, 'tick_size': {}}


class FakeConn:
    def __init__(self, address, subscription):
        self.address = address
        self.uuid = 'test'
        self.subscription = subscription


@pytest.fixture
def bybit_symbols():
    Symbols.clear()
    Symbols.set(BYBIT, SYMBOLS, INFO)
    yield
    Symbols.clear()


def make_feed(channels, callbacks):
    return Bybit(symbols=list(SYMBOLS), channels=channels, callbacks=callbacks,
                 config={'log': {'disabled': True}})


async def test_all_liquidation_payload(bybit_symbols):
    """The v5 allLiquidation topic replaced the retired liquidation topic: data is a list, and
    the field names are abbreviated."""
    received = []

    async def cb(obj, receipt_timestamp):
        received.append(obj)

    feed = make_feed([LIQUIDATIONS], {LIQUIDATIONS: cb})
    msg = json.dumps({
        "topic": "allLiquidation.BTCUSDT",
        "type": "snapshot",
        "ts": 1739502303204,
        "data": [{"T": 1739502302929, "s": "BTCUSDT", "S": "Sell", "v": "0.003", "p": "43511.70"}],
    })
    await feed.message_handler(msg, FakeConn(LINEAR, {'allLiquidation': ['BTCUSDT']}), 1739502303.3)

    assert len(received) == 1
    liq = received[0]
    assert liq.exchange == BYBIT
    assert liq.symbol == 'BTC-USDT-PERP'
    assert liq.side == SELL
    assert liq.quantity == Decimal('0.003')
    assert liq.price == Decimal('43511.70')
    # milliseconds on the wire, seconds on the object
    assert liq.timestamp == 1739502302.929


async def test_all_liquidation_side_mapping(bybit_symbols):
    received = []

    async def cb(obj, receipt_timestamp):
        received.append(obj)

    feed = make_feed([LIQUIDATIONS], {LIQUIDATIONS: cb})
    msg = json.dumps({
        "topic": "allLiquidation.BTCUSDT", "type": "snapshot", "ts": 1739502303204,
        "data": [{"T": 1739502302929, "s": "BTCUSDT", "S": "Buy", "v": "1", "p": "43511.70"},
                 {"T": 1739502302930, "s": "BTCUSDT", "S": "Sell", "v": "2", "p": "43512.70"}],
    })
    await feed.message_handler(msg, FakeConn(LINEAR, {'allLiquidation': ['BTCUSDT']}), 1739502303.3)

    assert [liq.side for liq in received] == [BUY, SELL]
    assert [liq.quantity for liq in received] == [Decimal('1'), Decimal('2')]


async def test_ticker_delta_without_snapshot_does_not_raise(bybit_symbols):
    received = []

    async def cb(obj, receipt_timestamp):
        received.append(obj)

    feed = make_feed([TICKER], {TICKER: cb})
    conn = FakeConn(LINEAR, {'tickers': ['BTCUSDT']})
    delta = json.dumps({
        "topic": "tickers.BTCUSDT", "type": "delta", "ts": 1786310526434,
        "data": {"symbol": "BTCUSDT", "bid1Price": "65102.50", "bid1Size": "4.518",
                 "ask1Price": "65102.60", "ask1Size": "2.514"},
    })
    await feed.message_handler(delta, conn, 1786310526.5)

    assert len(received) == 1
    assert received[0].bid == Decimal('65102.50')
    assert received[0].ask == Decimal('65102.60')


async def test_reset_does_not_clobber_the_other_connection(bybit_symbols):
    async def cb(obj, receipt_timestamp):
        pass

    feed = make_feed([TICKER], {TICKER: cb})
    linear = FakeConn(LINEAR, {'tickers': ['BTCUSDT']})
    spot = FakeConn(SPOT_WS, {'tickers': ['BTC/USDT']})

    snapshot = json.dumps({
        "topic": "tickers.BTCUSDT", "type": "snapshot", "ts": 1786310525127,
        "data": {"symbol": "BTCUSDT", "bid1Price": "65102.50", "ask1Price": "65102.60",
                 "markPrice": "65102.52", "indexPrice": "65128.59", "openInterest": "59889.098",
                 "fundingRate": "0.0001", "nextFundingTime": "1786320000000"},
    })
    await feed.message_handler(snapshot, linear, 1786310525.2)
    assert 'BTC-USDT-PERP' in feed.tickers

    await feed.subscribe(_RecordingConn(spot))
    assert 'BTC-USDT-PERP' in feed.tickers, 'spot subscribe discarded the linear snapshot'


async def test_spot_ticker_is_not_attributed_to_the_perpetual(bybit_symbols):
    received = []

    async def cb(obj, receipt_timestamp):
        received.append(obj)

    feed = make_feed([TICKER], {TICKER: cb})
    msg = json.dumps({
        "topic": "tickers.BTCUSDT", "type": "snapshot", "ts": 1786310525127,
        "data": {"symbol": "BTCUSDT", "lastPrice": "65132.4", "highPrice24h": "65305.6",
                 "bid1Price": "65130.0", "ask1Price": "65131.0"},
    })
    await feed.message_handler(msg, FakeConn(SPOT_WS, {'tickers': ['BTC/USDT']}), 1786310525.2)

    assert len(received) == 1
    assert received[0].symbol == 'BTC-USDT'


async def test_spot_ticker_without_perpetual_fields(bybit_symbols):
    received = []

    async def cb(obj, receipt_timestamp):
        received.append(obj)

    channels = [TICKER, FUNDING, OPEN_INTEREST, INDEX]
    feed = make_feed(channels, {c: cb for c in channels})
    subscription = {'tickers': ['BTC/USDT'], 'funding': ['BTC/USDT'],
                    'open_interest': ['BTC/USDT'], 'index': ['BTC/USDT']}
    msg = json.dumps({
        "topic": "tickers.BTCUSDT", "type": "snapshot", "ts": 1786310525127,
        "data": {"symbol": "BTCUSDT", "lastPrice": "65132.4", "bid1Price": "65130.0", "ask1Price": "65131.0"},
    })
    await feed.message_handler(msg, FakeConn(SPOT_WS, subscription), 1786310525.2)

    # only the ticker is derivable from a spot payload
    assert len(received) == 1
    assert received[0].symbol == 'BTC-USDT'


def test_public_market_data_only(bybit_symbols):
    from cryptofeed.defines import FILLS, ORDER_INFO
    assert ORDER_INFO not in Bybit.websocket_channels
    assert FILLS not in Bybit.websocket_channels
    assert Bybit.websocket_channels[LIQUIDATIONS] == 'allLiquidation'
    assert all('realtime_private' not in ep.address for ep in Bybit.websocket_endpoints)
    # every declared channel is public
    assert not any(Bybit.is_authenticated_channel(c) for c in Bybit.websocket_channels)
    assert set(Bybit.websocket_channels) >= {TRADES, L2_BOOK, TICKER, LIQUIDATIONS}


class _RecordingConn:
    def __init__(self, conn):
        self.address = conn.address
        self.uuid = conn.uuid
        self.subscription = conn.subscription
        self.sent = []

    async def write(self, msg):
        self.sent.append(msg)
