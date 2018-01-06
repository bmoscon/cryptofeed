# Cryptocurrency Feed Handler
[![License](https://img.shields.io/badge/license-XFree86-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.5+-green.svg)](LICENSE)
[![Build Status](https://travis-ci.org/bmoscon/cryptofeed.svg?branch=master)](https://travis-ci.org/bmoscon/cryptofeed)
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/efa4e0d6e10b41d0b51454d08f7b33b1)](https://www.codacy.com/app/bmoscon/cryptofeed?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=bmoscon/cryptofeed&amp;utm_campaign=Badge_Grade)

Handles multiple feeds and return normalized and standardized results across exchanges to client registered callbacks for events like trades, book updates, ticker updates, etc.


```python
from cryptofeed import FeedHandler

fh = FeedHandler()

# ticker, trade, and book are user defined functions that
# will be called when ticker, trade and book updates are received
ticker_cb = {'ticker': TickerCallback(ticker)}
trade_cb = {'trades': TradeCallback(trade)}
gemini_cb = {'trades': TradeCallback(trade), 'book': BookCallback(book)}


fh.add_feed(GDAX(pairs=['BTC-USD'], channels=['ticker'], callbacks=ticker_cb)
fh.add_feed(Bitfinex(pairs=['BTC-USD'], channels=['ticker'], callbacks=ticker_cb)
fh.add_feed(Poloniex(channels=['USDT_BTC'], callbacks=trade_cb))
fh.add_feed(Gemini(pairs=['BTC-USD'], callbacks=gemini_cb)

fh.run()
```

Supports the following exchanges:
* Bitfinex
* GDAX
* Poloniex
* Gemini
* HitBTC

Also provides a synthetic NBBO (National Best Bid/Offer) feed that aggregates the best bids and asks from the user specified feeds.

```python
from cryptofeed.feedhandler import FeedHandler
from cryptofeed import GDAX, Bitfinex, HitBTC


def nbbo_ticker(pair, bid, ask, bid_feed, ask_feed):
    print('Pair: {} Bid: {} Bid Feed: {} Ask: {} Ask Feed: {}'.format(pair,
                                                                      bid,
                                                                      bid_feed,
                                                                      ask,
                                                                      ask_feed))


fh = FeedHandler()
fh.add_nbbo([GDAX, Bitfinex, HitBTC], ['BTC-USD'], nbbo_ticker)
fh.run()
```
