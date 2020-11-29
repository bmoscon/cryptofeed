'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal

from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, FundingCallback, TickerCallback, TradeCallback, FuturesIndexCallback, OpenInterestCallback
from cryptofeed.defines import BID, ASK, BLOCKCHAIN, COINBASE, FUNDING, GEMINI, L2_BOOK, OPEN_INTEREST, TICKER, TRADES, VOLUME, FUTURES_INDEX
from cryptofeed.exchanges import (EXX, FTX, Binance, Bitfinex, Bitmex, Bitstamp, Bittrex, Coinbase, Gateio, Gemini,
                                  HitBTC, Huobi, HuobiDM, HuobiSwap, Kraken, OKCoin, OKEx, Poloniex, Bybit)


# Examples of some handlers for different updates. These currently don't do much.
# Handlers should conform to the patterns/signatures in callback.py
# Handlers can be normal methods/functions or async. The feedhandler is paused
# while the callbacks are being handled (unless they in turn await other functions or I/O)
# so they should be as lightweight as possible
async def ticker(feed, pair, bid, ask, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Bid: {bid} Ask: {ask}')


async def trade(feed, pair, order_id, timestamp, side, amount, price, receipt_timestamp):
    assert isinstance(timestamp, float)
    assert isinstance(side, str)
    assert isinstance(amount, Decimal)
    assert isinstance(price, Decimal)
    print(f"Timestamp: {timestamp} Cryptofeed Receipt: {receipt_timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


async def funding(**kwargs):
    print(f"Funding Update for {kwargs['feed']}")
    print(kwargs)


async def oi(feed, pair, open_interest, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} open interest: {open_interest}')


async def volume(**kwargs):
    print(f"Volume: {kwargs}")


async def futures_index(**kwargs):
    print(f"FuturesIndex: {kwargs}")


def main():
    f = FeedHandler()
    # Note: EXX is extremely unreliable - sometimes a connection can take many many retries
    # f.add_feed(EXX(pairs=['BTC-USDT'], channels=[L2_BOOK, TRADES], callbacks={L2_BOOK: BookCallback(book), TRADES: TradeCallback(trade)}))
    f.add_feed(Gateio(pairs=['BTC-USDT', 'ETH-USDT'], channels=[TRADES, L2_BOOK], callbacks={TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))
    f.add_feed(Binance(pairs=['BTC-USDT'], channels=[TRADES, TICKER, L2_BOOK], callbacks={L2_BOOK: BookCallback(book), TRADES: TradeCallback(trade), TICKER: TickerCallback(ticker)}))
    f.add_feed(COINBASE, pairs=['BTC-USD'], channels=[TICKER], callbacks={TICKER: TickerCallback(ticker)})
    f.add_feed(Coinbase(pairs=['BTC-USD'], channels=[TRADES], callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(Coinbase(config={L2_BOOK: ['BTC-USD', 'ETH-USD'], TRADES: ['ETH-USD', 'BTC-USD']}, callbacks={TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))
    f.add_feed(Bitfinex(pairs=['BTC-USD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))
    f.add_feed(Poloniex(pairs=['BTC-USDT', 'BTC-USDC'], channels=[TICKER, TRADES, VOLUME], callbacks={VOLUME: volume, TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade)}))
    f.add_feed(Poloniex(config={TRADES: ['DOGE-BTC', 'ETH-BTC'], TICKER: ['ETH-BTC'], L2_BOOK: ['LTC-BTC']}, callbacks={TRADES: TradeCallback(trade), TICKER: TickerCallback(ticker), L2_BOOK: BookCallback(book)}))
    f.add_feed(GEMINI, config={L2_BOOK: ['BTC-USD', 'ETH-USD'], TRADES: ['ETH-USD', 'BTC-USD']}, callbacks={TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)})
    f.add_feed(HitBTC(channels=[TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(HitBTC(channels=[L2_BOOK], pairs=['BTC-USD'], callbacks={L2_BOOK: BookCallback(book)}))

    f.add_feed(Bitstamp(channels=[L2_BOOK, TRADES], pairs=['BTC-USD'], callbacks={L2_BOOK: BookCallback(book), TRADES: TradeCallback(trade)}))
    bitmex_symbols = Bitmex.info()['pairs']
    f.add_feed(Bitmex(channels=[OPEN_INTEREST], pairs=['XBTUSD'], callbacks={OPEN_INTEREST: oi}))
    f.add_feed(Bitmex(channels=[TRADES], pairs=bitmex_symbols, callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(Bitmex(pairs=['XBTUSD'], channels=[FUNDING, TRADES], callbacks={FUNDING: FundingCallback(funding), TRADES: TradeCallback(trade)}))

    f.add_feed(Bitfinex(pairs=['BTC'], channels=[FUNDING], callbacks={FUNDING: FundingCallback(funding)}))
    f.add_feed(Bitmex(pairs=['XBTUSD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))
    f.add_feed(Kraken(checksum_validation=True, config={L2_BOOK: ['BTC-USD'], TRADES: ['BTC-USD'], TICKER: ['ETH-USD']}, callbacks={L2_BOOK: book, TRADES: TradeCallback(trade), TICKER: TickerCallback(ticker)}))
    config = {TRADES: ['BTC-USDT', 'ETH-USDT'], L2_BOOK: ['BTC-USDT']}
    f.add_feed(Huobi(config=config, callbacks={TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))
    config = {L2_BOOK: ['BTC_CQ', 'BTC_NQ']}
    f.add_feed(HuobiDM(config=config, callbacks={TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))
    pairs = ['BTC-USD', 'ETH-USD', 'EOS-USD', 'BCH-USD', 'BSV-USD', 'LTC-USD']
    f.add_feed(HuobiSwap(pairs=pairs, channels=[TRADES, L2_BOOK, FUNDING], callbacks={FUNDING: funding, TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))
    f.add_feed(OKCoin(pairs=['BTC-USD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))
    f.add_feed(OKEx(pairs=['BTC-USDT'], channels=[TRADES], callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(Bittrex(config={TRADES: ['BTC-USD'], TICKER: ['ETH-USD'], L2_BOOK: ['BTC-USDT']}, callbacks={L2_BOOK: BookCallback(book), TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade)}))
    f.add_feed(FTX(pairs=['ADA-PERP', 'ALGO-PERP', 'ALT-PERP', 'ATOM-PERP', 'BCH-PERP', 'BNB-PERP', 'BSV-PERP', 'BTC-PERP', 'BTMX-PERP', 'DOGE-PERP', 'DRGN-PERP', 'EOS-PERP', 'ETC-PERP'], channels=[TICKER], callbacks={TICKER: ticker, TRADES: TradeCallback(trade)}))
    f.add_feed(Bybit(pairs=['BTC-USD'], channels=[FUTURES_INDEX], callbacks={OPEN_INTEREST: OpenInterestCallback(oi), FUTURES_INDEX: FuturesIndexCallback(futures_index)}))

    f.add_feed(BLOCKCHAIN, pairs=['BTC-USD', 'ETH-USD'], channels=[L2_BOOK, TRADES], callbacks={
                  L2_BOOK: BookCallback(book),
                  TRADES: trade,
              })

    f.run()


if __name__ == '__main__':
    main()
