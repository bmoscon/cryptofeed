import pytest

from cryptofeed.defines import BID, ASK
from cryptofeed.exchanges.poloniex import Poloniex


poloniex = Poloniex(config='config.yaml')


def test_get_ticker():
    ticker = poloniex.ticker_sync('ETH-BTC')
    assert ticker['bid'] > 0


def test_order_book():
    order_book = poloniex.l2_book_sync('ETH-BTC')

    assert BID in order_book
    assert ASK in order_book
    assert len(order_book[BID]) > 0


def test_trade_history():
    trade_history = list(next(poloniex.trades_sync('ETH-BTC', start='2020-12-30 00:00:00', end='2020-12-31 00:00:00')))
    assert len(trade_history) > 0
    assert float(trade_history[0]['amount']) > 0
