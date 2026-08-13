'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal

import pytest

from cryptofeed.defines import BUY, POLONIEX, SELL, TRADES
from cryptofeed.exchanges.poloniex import Poloniex
from cryptofeed.symbols import Symbols


@pytest.fixture
def poloniex_with_trade_capture():
    trades = []

    async def capture_trade(trade, receipt_timestamp):
        trades.append((trade, receipt_timestamp))

    Symbols.clear()
    Symbols.set(
        POLONIEX,
        {
            'BTC-USDT': 'BTC_USDT',
            'ETH-USDT': 'ETH_USDT',
        },
        {'instrument_type': {'BTC-USDT': 'spot', 'ETH-USDT': 'spot'}},
    )
    feed = Poloniex(symbols=['BTC-USDT'], channels=[TRADES], callbacks={TRADES: capture_trade})
    yield feed, trades
    Symbols.clear()


def test_poloniex_trade_uses_quantity_as_amount_and_preserves_trade_id(poloniex_with_trade_capture):
    feed, trades = poloniex_with_trade_capture
    msg = {
        'channel': 'trades',
        'data': [{
            'symbol': 'BTC_USDT',
            'amount': '364.89973',
            'quantity': '0.017',
            'takerSide': 'sell',
            'createTime': 1661120814818,
            'price': '21464.69',
            'id': '60183607',
            'ts': 1661120814823,
        }],
    }

    asyncio.run(feed._trade(msg, 1234.5))

    assert len(trades) == 1
    trade, receipt_timestamp = trades[0]
    assert receipt_timestamp == 1234.5
    assert trade.exchange == POLONIEX
    assert trade.symbol == 'BTC-USDT'
    assert trade.side == SELL
    assert trade.amount == Decimal('0.017')
    assert trade.price == Decimal('21464.69')
    assert trade.timestamp == 1661120814.823
    assert trade.id == '60183607'
    assert trade.raw == msg


def test_poloniex_trade_emits_every_trade_in_batch(poloniex_with_trade_capture):
    feed, trades = poloniex_with_trade_capture
    msg = {
        'channel': 'trades',
        'data': [
            {
                'symbol': 'BTC_USDT',
                'amount': '248.3516391',
                'quantity': '0.01149',
                'takerSide': 'sell',
                'createTime': 1661123520381,
                'price': '21614.59',
                'id': '60184114',
                'ts': 1661123520386,
            },
            {
                'symbol': 'ETH_USDT',
                'amount': '180.5000',
                'quantity': '0.1000',
                'takerSide': 'buy',
                'createTime': 1661123521381,
                'price': '1805.00',
                'id': 60184115,
                'ts': 1661123521386,
            },
        ],
    }

    asyncio.run(feed._trade(msg, 1234.5))

    assert len(trades) == 2
    first, second = [entry[0] for entry in trades]
    assert first.exchange == POLONIEX
    assert first.symbol == 'BTC-USDT'
    assert first.side == SELL
    assert first.amount == Decimal('0.01149')
    assert first.id == '60184114'
    assert second.exchange == POLONIEX
    assert second.symbol == 'ETH-USDT'
    assert second.side == BUY
    assert second.amount == Decimal('0.1000')
    assert second.id == '60184115'
