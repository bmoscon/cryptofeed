'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal

from cryptofeed.symbols import binance_symbols
from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, FundingCallback, TickerCallback, TradeCallback, FuturesIndexCallback, OpenInterestCallback
from cryptofeed.defines import BID, ASK, BLOCKCHAIN, COINBASE, FUNDING, GEMINI, L2_BOOK, L3_BOOK, OPEN_INTEREST, TICKER, TRADES, VOLUME, FUTURES_INDEX, BOOK_DELTA
from cryptofeed.exchanges import (FTX, Binance, BinanceFutures, Bitfinex, Bitflyer, Bitmax, Bitmex, Bitstamp, Bittrex, Coinbase, Gateio,
                                  HitBTC, Huobi, HuobiDM, HuobiSwap, Kraken, OKCoin, OKEx, Poloniex, Bybit)


# Examples of some handlers for different updates. These currently don't do much.
# Handlers should conform to the patterns/signatures in callback.py
# Handlers can be normal methods/functions or async. The feedhandler is paused
# while the callbacks are being handled (unless they in turn await other functions or I/O)
# so they should be as lightweight as possible
async def ticker(feed, symbol, bid, ask, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {symbol} Bid: {bid} Ask: {ask}')


async def delta(feed, symbol, delta, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {symbol} Delta Bid Size is {len(delta[BID])} Delta Ask Size is {len(delta[ASK])}')


async def trade(feed, symbol, order_id, timestamp, side, amount, price, receipt_timestamp):
    assert isinstance(timestamp, float)
    assert isinstance(side, str)
    assert isinstance(amount, Decimal)
    assert isinstance(price, Decimal)
    print(f"Timestamp: {timestamp} Cryptofeed Receipt: {receipt_timestamp} Feed: {feed} Pair: {symbol} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, symbol, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Cryptofeed Receipt: {receipt_timestamp} Feed: {feed} Pair: {symbol} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


async def funding(**kwargs):
    print(f"Funding Update for {kwargs['feed']}")
    print(kwargs)


async def oi(feed, symbol, open_interest, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {symbol} open interest: {open_interest}')


async def volume(**kwargs):
    print(f"Volume: {kwargs}")


async def futures_index(**kwargs):
    print(f"FuturesIndex: {kwargs}")


def main():
    config = {'log': {'filename': 'demo.log', 'level': 'INFO'}}
    # the config will be automatically passed into any exchanges set up by string. Instantiated exchange objects would need to pass the config in manually.
    f = FeedHandler(config=config)
    # Note: EXX is extremely unreliable - sometimes a connection can take many many retries
    # from cryptofeed.exchanges import EXX
    # f.add_feed(EXX(symbols=['BTC-USDT'], channels=[L2_BOOK, TRADES], callbacks={L2_BOOK: BookCallback(book), TRADES: TradeCallback(trade)}))
    f.add_feed(Gateio(symbols=['BTC-USDT', 'ETH-USDT'], channels=[TRADES, L2_BOOK], callbacks={TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))
    pairs = list(binance_symbols().keys())
    f.add_feed(Binance(symbols=pairs, channels=[TRADES], callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(COINBASE, symbols=['BTC-USD'], channels=[TICKER], callbacks={TICKER: TickerCallback(ticker)})
    f.add_feed(Coinbase(symbols=['BTC-USD'], channels=[TRADES], callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(Coinbase(subscription={L2_BOOK: ['BTC-USD', 'ETH-USD'], TRADES: ['ETH-USD']}, callbacks={TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))
    f.add_feed(Coinbase(subscription={L3_BOOK: ['LTC-USD']}, callbacks={L3_BOOK: BookCallback(book)}))
    f.add_feed(Bitfinex(symbols=['BTC-USDT'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))
    f.add_feed(Bitfinex(symbols=['BTC'], channels=[FUNDING], callbacks={FUNDING: FundingCallback(funding)}))
    f.add_feed(Poloniex(symbols=['BTC-USDT', 'BTC-USDC'], channels=[TICKER, TRADES, VOLUME], callbacks={VOLUME: volume, TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade)}))
    f.add_feed(Poloniex(subscription={TRADES: ['DOGE-BTC', 'ETH-BTC'], TICKER: ['ETH-BTC'], L2_BOOK: ['LTC-BTC']}, callbacks={TRADES: TradeCallback(trade), TICKER: TickerCallback(ticker), L2_BOOK: BookCallback(book)}))
    f.add_feed(GEMINI, subscription={L2_BOOK: ['BTC-USD', 'ETH-USD'], TRADES: ['ETH-USD', 'BTC-USD']}, callbacks={TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)})
    f.add_feed(HitBTC(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(HitBTC(channels=[L2_BOOK], symbols=['BTC-USD'], callbacks={L2_BOOK: BookCallback(book)}))
    f.add_feed(Bitstamp(channels=[L2_BOOK, TRADES], symbols=['BTC-USD'], callbacks={L2_BOOK: BookCallback(book), TRADES: TradeCallback(trade)}))
    bitmex_symbols = Bitmex.info()['symbols']
    f.add_feed(Bitmex(channels=[OPEN_INTEREST], symbols=['XBTUSD'], callbacks={OPEN_INTEREST: oi}))
    f.add_feed(Bitmex(channels=[TRADES], symbols=bitmex_symbols, callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(Bitmex(symbols=['XBTUSD'], channels=[FUNDING, TRADES], callbacks={FUNDING: FundingCallback(funding), TRADES: TradeCallback(trade)}))
    f.add_feed(Bitmex(symbols=['XBTUSD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))
    f.add_feed(Kraken(checksum_validation=True, subscription={L2_BOOK: ['BTC-USD'], TRADES: ['BTC-USD'], TICKER: ['ETH-USD']}, callbacks={L2_BOOK: book, TRADES: TradeCallback(trade), TICKER: TickerCallback(ticker)}))
    sub = {TRADES: ['BTC-USDT', 'ETH-USDT'], L2_BOOK: ['BTC-USDT']}
    f.add_feed(Huobi(subscription=sub, callbacks={TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))
    sub = {L2_BOOK: ['BTC_CQ', 'BTC_NQ']}
    f.add_feed(HuobiDM(subscription=sub, callbacks={TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))
    pairs = ['BTC-USD', 'ETH-USD', 'EOS-USD', 'BCH-USD', 'BSV-USD', 'LTC-USD']
    f.add_feed(HuobiSwap(symbols=pairs, channels=[TRADES, L2_BOOK, FUNDING], callbacks={FUNDING: funding, TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))
    f.add_feed(OKCoin(symbols=['BTC-USD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))
    f.add_feed(OKEx(symbols=['BTC-USDT'], channels=[TRADES], callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(Bittrex(subscription={TRADES: ['BTC-USD'], TICKER: ['ETH-USD'], L2_BOOK: ['BTC-USDT']}, callbacks={L2_BOOK: BookCallback(book), TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade)}))
    f.add_feed(FTX(symbols=['ADA-PERP', 'ALGO-PERP', 'ALT-PERP', 'ATOM-PERP', 'BCH-PERP', 'BNB-PERP', 'BSV-PERP', 'BTC-PERP', 'BTMX-PERP', 'DOGE-PERP', 'DRGN-PERP', 'EOS-PERP', 'ETC-PERP'], channels=[TICKER], callbacks={TICKER: ticker, TRADES: TradeCallback(trade)}))
    f.add_feed(Bybit(symbols=['BTC-USDT', 'BTC-USD'], channels=[FUTURES_INDEX], callbacks={OPEN_INTEREST: OpenInterestCallback(oi), FUTURES_INDEX: FuturesIndexCallback(futures_index)}))
    f.add_feed(Bybit(symbols=['BTC-USDT', 'BTC-USD'], channels=[L2_BOOK, TRADES], callbacks={TRADES: trade, L2_BOOK: book}))
    f.add_feed(BLOCKCHAIN, symbols=['BTC-USD', 'ETH-USD'], channels=[L2_BOOK, TRADES], callbacks={L2_BOOK: BookCallback(book), TRADES: trade})
    f.add_feed(Bitmax(symbols=['XRP-USDT', 'BTC-USDT'], channels=[L2_BOOK], callbacks={TRADES: trade, L2_BOOK: book}))
    f.add_feed(Bitflyer(symbols=['BTC-JPY'], channels=[L2_BOOK, TRADES, TICKER], callbacks={L2_BOOK: book, BOOK_DELTA: delta, TICKER: ticker, TRADES: trade}))
    f.add_feed(BinanceFutures(symbols=['BTC-USDT'], channels=[TICKER], callbacks={TICKER: ticker}))

    f.run()


if __name__ == '__main__':
    main()
