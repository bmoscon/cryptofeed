'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal

from cryptofeed import FeedHandler
from cryptofeed.defines import CANDLES, BID, ASK, BLOCKCHAIN, FUNDING, GEMINI, L2_BOOK, L3_BOOK, LIQUIDATIONS, OPEN_INTEREST, PERPETUAL, TICKER, TRADES, INDEX
from cryptofeed.exchanges import (FTX, Binance, BinanceUS, BinanceFutures, Bitfinex, Bitflyer, AscendEX, Bitmex, Bitstamp, Bittrex, Coinbase, Gateio,
                                  HitBTC, Huobi, HuobiDM, HuobiSwap, Kraken, OKCoin, OKEx, Poloniex, Bybit, KuCoin, Bequant, Upbit, Probit)
from cryptofeed.exchanges.kraken_futures import KrakenFutures
from cryptofeed.exchanges.blockchain import Blockchain
from cryptofeed.exchanges.bithumb import Bithumb
from cryptofeed.symbols import Symbol
from cryptofeed.exchanges.phemex import Phemex
from cryptofeed.exchanges.dydx import dYdX
from cryptofeed.exchanges.deribit import Deribit


# Examples of some handlers for different updates. These currently don't do much.
# Handlers should conform to the patterns/signatures in callback.py
# Handlers can be normal methods/functions or async. The feedhandler is paused
# while the callbacks are being handled (unless they in turn await other functions or I/O)
# so they should be as lightweight as possible
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


async def funding(f, receipt_timestamp):
    print(f"Funding update received at {receipt_timestamp}: {f}")


async def oi(update, receipt_timestamp):
    print(f"Open Interest update received at {receipt_timestamp}: {update}")


async def index(i, receipt_timestamp):
    print(f"Index received at {receipt_timestamp}: {i}")


async def candle_callback(c, receipt_timestamp):
    print(f"Candle received at {receipt_timestamp}: {c}")


async def liquidations(liquidation, receipt_timestamp):
    print(f"Liquidation received at {receipt_timestamp}: {liquidation}")


def main():
    config = {'log': {'filename': 'demo.log', 'level': 'DEBUG'}}
    # the config will be automatically passed into any exchanges set up by string. Instantiated exchange objects would need to pass the config in manually.
    f = FeedHandler(config=config)

    f.add_feed(AscendEX(symbols=['XRP-USDT'], channels=[L2_BOOK, TRADES], callbacks={L2_BOOK: book, TRADES: trade}))
    f.add_feed(Bequant(symbols=['BTC-USDT'], channels=[L2_BOOK], callbacks={L2_BOOK: book, TRADES: trade, TICKER: ticker, CANDLES: candle_callback}))
    pairs = Binance.symbols()[:1]
    f.add_feed(Binance(symbols=pairs, channels=[L2_BOOK], callbacks={L2_BOOK: book, CANDLES: candle_callback, TRADES: trade, TICKER: ticker}))
    pairs = BinanceFutures.symbols()[:30]
    f.add_feed(BinanceFutures(symbols=pairs, channels=[OPEN_INTEREST, FUNDING, LIQUIDATIONS], callbacks={OPEN_INTEREST: oi, FUNDING: funding, LIQUIDATIONS: liquidations}))
    f.add_feed(BinanceUS(symbols=BinanceUS.symbols(), channels=[TRADES], callbacks={TRADES: trade}))
    f.add_feed(Bitfinex(symbols=['BTC-USDT'], channels=[L3_BOOK], callbacks={L3_BOOK: book, TICKER: ticker, TRADES: trade}))
    f.add_feed(Bitflyer(symbols=['BTC-JPY'], channels=[TICKER, TRADES, L2_BOOK], callbacks={L2_BOOK: book, TICKER: ticker, TRADES: trade}))
    f.add_feed(Bithumb(symbols=['BTC-KRW'], channels=[TRADES], callbacks={TRADES: trade}))
    f.add_feed(Bitmex(timeout=5000, symbols=Bitmex.symbols(), channels=[LIQUIDATIONS], callbacks={LIQUIDATIONS: liquidations, OPEN_INTEREST: oi, FUNDING: funding}))
    f.add_feed(Bitstamp(channels=[L2_BOOK, TRADES], symbols=['BTC-USD'], callbacks={L2_BOOK: book, TRADES: trade}))
    f.add_feed(Bittrex(subscription={L2_BOOK: ['BTC-USDT'], CANDLES: ['BTC-USDT', 'ETH-USDT'], TRADES: ['ETH-USDT', 'BTC-USDT'], TICKER: ['ETH-USDT']}, callbacks={CANDLES: candle_callback, L2_BOOK: book, TICKER: ticker, TRADES: trade}))
    f.add_feed(BLOCKCHAIN, subscription={L2_BOOK: ['BTC-USD'], TRADES: Blockchain.symbols()}, callbacks={L2_BOOK: book, TRADES: trade})
    f.add_feed(Bybit(symbols=['BTC-USDT-PERP', 'BTC-USD-PERP'], channels=[INDEX, FUNDING, OPEN_INTEREST], callbacks={OPEN_INTEREST: oi, INDEX: index, FUNDING: funding}))
    f.add_feed(Bybit(symbols=['BTC-USDT-PERP', 'BTC-USD-PERP'], channels=[L2_BOOK, TRADES], callbacks={TRADES: trade, L2_BOOK: book}))
    f.add_feed(Coinbase(subscription={L2_BOOK: ['BTC-USD'], TRADES: ['BTC-USD'], TICKER: ['BTC-USD']}, callbacks={TRADES: trade, L2_BOOK: book, TICKER: ticker}))
    f.add_feed(Coinbase(subscription={L3_BOOK: ['LTC-USD']}, callbacks={L3_BOOK: book}))
    f.add_feed(Deribit(symbols=['BTC-USD-PERP'], channels=[L2_BOOK, TRADES, TICKER, FUNDING, OPEN_INTEREST, LIQUIDATIONS], callbacks={TRADES: trade, L2_BOOK: book, TICKER: ticker, OPEN_INTEREST: oi, FUNDING: funding, LIQUIDATIONS: liquidations}))
    f.add_feed(dYdX(symbols=dYdX.symbols(), channels=[L2_BOOK, TRADES], callbacks={TRADES: trade, L2_BOOK: book}))
    f.add_feed(FTX(checksum_validation=True, symbols=['ALGO-USD-PERP'], channels=[TICKER, TRADES, L2_BOOK, LIQUIDATIONS, OPEN_INTEREST, FUNDING], callbacks={TICKER: ticker, TRADES: trade, OPEN_INTEREST: oi, FUNDING: funding, LIQUIDATIONS: liquidations, L2_BOOK: book}))
    f.add_feed(Gateio(symbols=['BTC-USDT', 'ETH-USDT'], channels=[L2_BOOK, CANDLES, TRADES, TICKER], callbacks={CANDLES: candle_callback, L2_BOOK: book, TRADES: trade, TICKER: ticker}))
    f.add_feed(GEMINI, subscription={L2_BOOK: ['BTC-USD', 'ETH-USD'], TRADES: ['ETH-USD', 'BTC-USD']}, callbacks={TRADES: trade, L2_BOOK: book})
    f.add_feed(HitBTC(channels=[TRADES], symbols=['BTC-USDT'], callbacks={TRADES: trade}))
    f.add_feed(Huobi(symbols=['BTC-USDT'], channels=[CANDLES, TRADES, L2_BOOK], callbacks={TRADES: trade, L2_BOOK: book, CANDLES: candle_callback}))
    f.add_feed(HuobiDM(subscription={L2_BOOK: HuobiDM.symbols()[:2], TRADES: HuobiDM.symbols()[:10]}, callbacks={TRADES: trade, L2_BOOK: book}))
    pairs = ['BTC-USD-PERP', 'ETH-USD-PERP', 'EOS-USD-PERP', 'BCH-USD-PERP', 'BSV-USD-PERP', 'LTC-USD-PERP']
    f.add_feed(HuobiSwap(symbols=pairs, channels=[TRADES, L2_BOOK, FUNDING], callbacks={FUNDING: funding, TRADES: trade, L2_BOOK: book}))
    f.add_feed(KrakenFutures(symbols=KrakenFutures.symbols(), channels=[L2_BOOK, TICKER, TRADES, OPEN_INTEREST, FUNDING], callbacks={L2_BOOK: book, FUNDING: funding, OPEN_INTEREST: oi, TRADES: trade, TICKER: ticker}))
    f.add_feed(Kraken(checksum_validation=True, subscription={L2_BOOK: ['BTC-USD'], TRADES: ['BTC-USD'], CANDLES: ['BTC-USD'], TICKER: ['ETH-USD']}, callbacks={L2_BOOK: book, CANDLES: candle_callback, TRADES: trade, TICKER: ticker}))
    f.add_feed(KuCoin(symbols=['BTC-USDT', 'ETH-USDT'], channels=[TICKER, TRADES, CANDLES], callbacks={CANDLES: candle_callback, TICKER: ticker, TRADES: trade}))
    f.add_feed(OKEx(checksum_validation=True, symbols=['BTC-USDT-PERP'], channels=[TRADES, TICKER, FUNDING, OPEN_INTEREST, LIQUIDATIONS, L2_BOOK], callbacks={L2_BOOK: book, TICKER: ticker, LIQUIDATIONS: liquidations, FUNDING: funding, OPEN_INTEREST: oi, TRADES: trade}))
    f.add_feed(OKCoin(checksum_validation=True, symbols=['BTC-USD'], channels=[TRADES, TICKER, L2_BOOK], callbacks={L2_BOOK: book, TICKER: ticker, TRADES: trade}))
    f.add_feed(Phemex(symbols=[Symbol('BTC', 'USD', type=PERPETUAL)], channels=[L2_BOOK, CANDLES, TRADES], callbacks={TRADES: trade, L2_BOOK: book, CANDLES: candle_callback}))
    f.add_feed(Poloniex(symbols=['BTC-USDT'], channels=[TICKER, TRADES], callbacks={TICKER: ticker, TRADES: trade}))
    f.add_feed(Poloniex(subscription={TRADES: ['DOGE-BTC'], L2_BOOK: ['LTC-BTC']}, callbacks={TRADES: trade, L2_BOOK: book}))
    f.add_feed(Probit(subscription={TRADES: ['BTC-USDT'], L2_BOOK: ['BTC-USDT']}, callbacks={TRADES: trade, L2_BOOK: book}))
    f.add_feed(Upbit(subscription={TRADES: ['BTC-USDT'], L2_BOOK: ['BTC-USDT']}, callbacks={TRADES: trade, L2_BOOK: book}))

    f.run()


if __name__ == '__main__':
    main()
