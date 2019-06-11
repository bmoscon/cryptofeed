'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.callback import TickerCallback, TradeCallback, BookCallback, FundingCallback, InstrumentCallback
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Bitmex, Coinbase, Bitfinex, Poloniex, Gemini, HitBTC, Bitstamp, Kraken, Binance, EXX, Huobi, HuobiUS, OKCoin, OKEx, Coinbene
from cryptofeed.defines import L3_BOOK, L2_BOOK, BID, ASK, TRADES, TICKER, FUNDING, COINBASE, INSTRUMENT


# Examples of some handlers for different updates. These currently don't do much.
# Handlers should conform to the patterns/signatures in callback.py
# Handlers can be normal methods/functions or async. The feedhandler is paused
# while the callbacks are being handled (unless they in turn await other functions or I/O)
# so they should be as lightweight as possible
async def ticker(feed, pair, bid, ask):
    print(f'Feed: {feed} Pair: {pair} Bid: {bid} Ask: {ask}')


async def trade(feed, pair, order_id, timestamp, side, amount, price):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


async def funding(**kwargs):
    print(f"Funding Update for {kwargs['feed']}")
    print(kwargs)


async def instrument(**kwargs):
    print(f"Instrument update: {kwargs}")


def main():
    f = FeedHandler()

    # Note: EXX is extremely unreliable - sometimes a connection can take many many retries
    # f.add_feed(EXX(pairs=['BTC-USDT'], channels=[L2_BOOK, TRADES], callbacks={L2_BOOK: BookCallback(book), TRADES: TradeCallback(trade)}))
    f.add_feed(Binance(pairs=['BTC-USDT'], channels=[TRADES, TICKER, L2_BOOK], callbacks={L2_BOOK: BookCallback(book), TRADES: TradeCallback(trade), TICKER: TickerCallback(ticker)}))
    f.add_feed(COINBASE, pairs=['BTC-USD'], channels=[TICKER], callbacks={TICKER: TickerCallback(ticker)})
    f.add_feed(Coinbase(pairs=['BTC-USD'], channels=[TRADES], callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(Coinbase(pairs=['BTC-USD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))
    f.add_feed(Bitfinex(pairs=['BTC-USD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))
    f.add_feed(Poloniex(pairs=['BTC-USDT', 'BTC-USDC'], channels=[TICKER, TRADES], callbacks={TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade)}))
    f.add_feed(Poloniex(config={TRADES: ['DOGE-BTC', 'ETH-BTC'], TICKER: ['ETH-BTC'], L2_BOOK: ['LTC-BTC']}, callbacks={TRADES: TradeCallback(trade), TICKER: TickerCallback(ticker), L2_BOOK: BookCallback(book)}))
    f.add_feed(Gemini(pairs=['BTC-USD'], callbacks={L2_BOOK: BookCallback(book), TRADES: TradeCallback(trade)}))
    f.add_feed(HitBTC(channels=[TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(HitBTC(channels=[L2_BOOK], pairs=['BTC-USD'], callbacks={L2_BOOK: BookCallback(book)}))
    f.add_feed(Bitstamp(channels=[L2_BOOK, TRADES], pairs=['BTC-USD'], callbacks={L2_BOOK: BookCallback(book), TRADES: TradeCallback(trade)}))

    bitmex_symbols = Bitmex.get_active_symbols()
    f.add_feed(Bitmex(channels=[INSTRUMENT], pairs=['XBTUSD'], callbacks={INSTRUMENT: InstrumentCallback(instrument)}))
    f.add_feed(Bitmex(channels=[TRADES], pairs=bitmex_symbols, callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(Bitmex(pairs=['XBTUSD'], channels=[FUNDING, TRADES], callbacks={FUNDING: FundingCallback(funding), TRADES: TradeCallback(trade)}))

    f.add_feed(Bitfinex(pairs=['BTC'], channels=[FUNDING], callbacks={FUNDING: FundingCallback(funding)}))
    f.add_feed(Bitmex(pairs=['XBTUSD'], channels=[L3_BOOK], callbacks={L3_BOOK: BookCallback(book)}))
    f.add_feed(Kraken(config={TRADES: ['BTC-USD'], TICKER: ['ETH-USD']}, callbacks={TRADES: TradeCallback(trade), TICKER: TickerCallback(ticker)}))

    config={TRADES: ['BTC-USD', 'ETH-USD', 'BTC-USDT', 'ETH-USDT'], L2_BOOK: ['BTC-USD', 'BTC-USDT']}
    f.add_feed(HuobiUS(config=config, callbacks={TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))

    config={TRADES: ['BTC-USDT', 'ETH-USDT'], L2_BOOK: ['BTC-USDT']}
    f.add_feed(Huobi(config=config, callbacks={TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))

    f.add_feed(OKCoin(pairs=['BTC-USD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))
    f.add_feed(OKEx(pairs=['BTC-USDT'], channels=[TRADES], callbacks={TRADES: TradeCallback(trade)}))

    config = {TRADES: ['BTC-USDT'], TICKER: ['BTC-USDT']}
    f.add_feed(Coinbene(config=config, callbacks={L2_BOOK: BookCallback(book), TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade)}))
    f.add_feed(Coinbene(channels=[L2_BOOK, TRADES, TICKER], pairs=['BTC-USDT'], callbacks={L2_BOOK: BookCallback(book), TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade)}))
    f.run()


if __name__ == '__main__':
    main()
