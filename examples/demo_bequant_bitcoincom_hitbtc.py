'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

from decimal import Decimal
from cryptofeed.connection import AsyncConnection
from cryptofeed.callback import BalancesCallback, TransactionsCallback, TickerCallback
import pprint
from cryptofeed import FeedHandler
from cryptofeed.defines import ASK, BEQUANT, HITBTC, BITCOINCOM, BID, L2_BOOK, ORDER_INFO, BALANCES, TRANSACTIONS, TICKER, CANDLES, TRADES

'''
Bequant, Bitcoin.com and HitBTC all share the same API.
This example demonstrates all features currently supported on these 3 exchanges
'''


async def ticker(t, receipt_timestamp):
    if t.timestamp is not None:
        assert isinstance(t.timestamp, float)
    assert isinstance(t.exchange, str)
    assert isinstance(t.bid, Decimal)
    assert isinstance(t.ask, Decimal)
    print(f'Ticker received at {receipt_timestamp}: {t}')


async def trade(t, receipt_timestamp):
    assert isinstance(t.timestamp, float)
    assert isinstance(t.side, str)
    assert isinstance(t.amount, Decimal)
    assert isinstance(t.price, Decimal)
    assert isinstance(t.exchange, str)
    print(f"Trade received at {receipt_timestamp}: {t}")


async def book(book, receipt_timestamp):
    print(f'Book received at {receipt_timestamp} for {book.exchange} - {book.symbol}, with {len(book.book)} entries. Top of book prices: {book.book.asks.index(0)[0]} - {book.book.bids.index(0)[0]}')
    if book.delta:
        print(f"Delta from last book contains {len(book.delta[BID]) + len(book.delta[ASK])} entries.")
    if book.sequence_number:
        assert isinstance(book.sequence_number, int)


async def candles_callback(c, receipt_timestamp):
    print(f"Candle received at {receipt_timestamp}: {c}")


# Private feeds, requiring API keys with correctly set privilages.
# Your API keys should be provided to the Feedhadler in one of the usual ways (.yaml file, dict, or env vars)
async def order(conn: AsyncConnection, **kwargs):
    print(f"Order Update on {conn.uuid}: {kwargs}")


async def balances(feed, accounts):
    for account in accounts:
        print(f'{feed} balances statement: {account}')


async def transactions(**kwargs):
    pprint.pp(f'New transaction {kwargs}')


def main():
    f = FeedHandler(config='config.yaml')
    f.add_feed(BEQUANT, channels=[TICKER], symbols=['ADA-USDT'], callbacks={TICKER: TickerCallback(ticker)})
    f.add_feed(BITCOINCOM, channels=[TICKER], symbols=['NEO-USDT'], callbacks={TICKER: TickerCallback(ticker)})
    f.add_feed(HITBTC, channels=[TICKER], symbols=['XLM-USDT'], callbacks={TICKER: TickerCallback(ticker)})
    f.add_feed(BEQUANT, channels=[L2_BOOK], symbols=['ALGO-USDT'], callbacks={L2_BOOK: (book)})
    f.add_feed(BITCOINCOM, channels=[L2_BOOK], symbols=['EOS-USDT'], callbacks={L2_BOOK: (book)})
    f.add_feed(HITBTC, channels=[L2_BOOK], symbols=['ATOM-USDT'], callbacks={L2_BOOK: (book)})
    f.add_feed(BEQUANT, channels=[CANDLES], candle_interval='30m', symbols=['ETH-USDT'], callbacks={CANDLES: candles_callback})
    f.add_feed(BITCOINCOM, channels=[CANDLES], candle_interval='1h', symbols=['TRX-USDT'], callbacks={CANDLES: candles_callback})
    f.add_feed(HITBTC, channels=[CANDLES], candle_interval='30m', symbols=['NEO-USDT'], callbacks={CANDLES: candles_callback})
    f.add_feed(BEQUANT, channels=[TRADES], symbols=['XLM-USDT'], callbacks={TRADES: trade})
    f.add_feed(BITCOINCOM, channels=[TRADES], symbols=['LINK-USDT'], callbacks={TRADES: trade})
    f.add_feed(HITBTC, channels=[TRADES], symbols=['DASH-USDT'], callbacks={TRADES: trade})

    # The following channels are authenticated (non public). Make sure you have set the correct privileges on your API key(s)
    f.add_feed(BEQUANT, subscription={ORDER_INFO: ['BTC-USD', 'ETH-USD']}, callbacks={ORDER_INFO: order})
    f.add_feed(BITCOINCOM, subscription={ORDER_INFO: ['EOS-USDT', 'ETH-USDT']}, callbacks={ORDER_INFO: order})
    f.add_feed(HITBTC, subscription={ORDER_INFO: ['BTC-USDT', 'ETH-USDT']}, callbacks={ORDER_INFO: order})
    f.add_feed(BEQUANT, timeout=-1, channels=[BALANCES], symbols=['XLM-USDT'], callbacks={BALANCES: BalancesCallback(balances)})
    f.add_feed(BITCOINCOM, timeout=-1, channels=[BALANCES], symbols=['LTC-USDT'], callbacks={BALANCES: BalancesCallback(balances)})
    f.add_feed(HITBTC, timeout=-1, channels=[BALANCES], symbols=['ADA-USDT'], callbacks={BALANCES: BalancesCallback(balances)})
    f.add_feed(BEQUANT, timeout=-1, channels=[TRANSACTIONS], symbols=['ADA-USDT'], callbacks={TRANSACTIONS: TransactionsCallback(transactions)})
    f.add_feed(BITCOINCOM, timeout=-1, channels=[TRANSACTIONS], symbols=['ZEC-USDT'], callbacks={TRANSACTIONS: TransactionsCallback(transactions)})
    f.add_feed(HITBTC, timeout=-1, channels=[TRANSACTIONS], symbols=['ADA-USDT'], callbacks={TRANSACTIONS: TransactionsCallback(transactions)})
    f.run()


if __name__ == '__main__':
    main()
