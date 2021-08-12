import pytest

from cryptofeed.defines import ASK, BID, KRAKEN
from cryptofeed.exchanges.kraken import Kraken


kraken = Kraken(config='config.yaml')


def test_get_order_book():
    book = kraken.l2_book_sync('BTC-USD')
    assert len(book[BID]) > 0


def test_get_recent_trades():
    trades = list(kraken.trades_sync('BTC-USD'))[0]
    assert len(trades) > 0
    assert trades[0]['feed'] == KRAKEN
    assert trades[0]['symbol'] == 'BTC-USD'


def test_ticker():
    t = kraken.ticker_sync('BTC-USD')
    assert t['symbol'] == 'BTC-USD'
    assert t['feed'] == KRAKEN
    assert BID in t
    assert ASK in t


def test_historical_trades():
    trades = []
    for t in kraken.trades_sync('BTC-USD', start='2021-01-01 00:00:01', end='2021-01-01 00:00:05'):
        trades.extend(t)
    assert len(trades) == 13

    trades = []
    for t in kraken.trades_sync('BTC-USD', start='2021-01-01 00:00:01', end='2021-01-01 01:00:00'):
        trades.extend(t)
    assert len(trades) == 2074


@pytest.mark.skipif(not kraken.key_id or not kraken.key_secret, reason="No api key provided")
def test_trade_history():
    trade_history = kraken.trade_history_sync()
    # for trade in trade_history:
    #     for k, v in trade.items():
    #         print(f"{k} => {v}")
    assert len(trade_history) != 0

@pytest.mark.skipif(not kraken.key_id or not kraken.key_secret, reason="No api key provided")
def test_ledger():
    ledger = kraken.ledger_sync()
    # for trade in trade_history:
    #     for k, v in trade.items():
    #         print(f"{k} => {v}")
    assert len(ledger) != 0