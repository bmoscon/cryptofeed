# Cryptocurrency Exchange Feed Handler
[![License](https://img.shields.io/badge/license-XFree86-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.7+-green.svg)
[![Build Status](https://travis-ci.org/bmoscon/cryptofeed.svg?branch=master)](https://travis-ci.org/bmoscon/cryptofeed)
[![PyPi](https://img.shields.io/badge/PyPi-cryptofeed-brightgreen.svg)](https://pypi.python.org/pypi/cryptofeed)
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/efa4e0d6e10b41d0b51454d08f7b33b1)](https://www.codacy.com/app/bmoscon/cryptofeed?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=bmoscon/cryptofeed&amp;utm_campaign=Badge_Grade)

Handles multiple cryptocurrency exchange data feeds and returns normalized and standardized results to client registered callbacks for events like trades, book updates, ticker updates, etc. Utilizes websockets when possible, but can also poll data via REST endpoints if a websocket is not provided.

## Installation

    pip install cryptofeed

or a safer installation:

    python3 -m pip install --user --upgrade cryptofeed

To install Cryptofeed along with all its optional dependencies in one bundle:

    pip install cryptofeed[all]

See more options, explanations and Pipenv usage in [INSTALL.md](https://github.com/bmoscon/cryptofeed/blob/master/INSTALL.md).


## Examples

Please see the [examples](https://github.com/bmoscon/cryptofeed/tree/master/examples) for more code samples and the [documentation](https://github.com/bmoscon/cryptofeed/blob/master/docs/README.md) for more information about the library usage. The [FAQ](https://github.com/bmoscon/cryptofeed/tree/master/FAQ.md) contains a few oddities/gotchas as well as answers to common questions.


```python
from cryptofeed import FeedHandler

fh = FeedHandler()

# ticker, trade, and book are user defined functions that
# will be called when ticker, trade and book updates are received
ticker_cb = {TICKER: TickerCallback(ticker)}
trade_cb = {TRADES: TradeCallback(trade)}
gemini_cb = {TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}


fh.add_feed(Coinbase(pairs=['BTC-USD'], channels=[TICKER], callbacks=ticker_cb))
fh.add_feed(Bitfinex(pairs=['BTC-USD'], channels=[TICKER], callbacks=ticker_cb))
fh.add_feed(Poloniex(pairs=['BTC-USDT'], channels=[TRADES], callbacks=trade_cb))
fh.add_feed(Gemini(pairs=['BTC-USD', 'ETH-USD'], channels=[TRADES, L2_BOOK], callbacks=gemini_cb))

fh.run()
```

To see an example of an application using cryptofeed to aggregate and store cryptocurrency data to a database, please look at [Cryptostore](https://github.com/bmoscon/cryptostore).

## Supported exchanges

* [Bitcoin.com](https://www.bitcoin.com/)
* [Bitfinex](https://bitfinex.com)
* [BitMax](https://bitmax.io/) (BTMX)
* [Bitstamp](https://www.bitstamp.net/)
* [Bittrex](https://global.bittrex.com/)
* [Blockchain.com](https://www.blockchain.com/)
* [Bybit](https://www.bybit.com/)
* [Binance](https://www.binance.com/en)
* [Binance Delivery](https://binance-docs.github.io/apidocs/delivery/en/)
* [Binance Futures](https://www.binance.com/en/futures)
* [Binance US](https://www.binance.us/en)
* [BitMEX](https://www.bitmex.com/)
* [Coinbase](https://www.coinbase.com/) (GDAX)
* [Deribit](https://www.deribit.com/)
* [EXX](https://www.exx.com/)
* [FTX](https://ftx.com/)
* [FTX US](https://ftx.us/)
* [Gate.io](https://www.gate.io/)
* [Gemini](https://gemini.com/)
* [HitBTC](https://hitbtc.com/)
* [Huobi](https://www.hbg.com/)
* [Huobi DM](https://www.huobi.com/en-us/markets/hb_dm/)
* Huobi Swap
* [Kraken](https://www.kraken.com/)
* [Kraken Futures](https://futures.kraken.com/)
* [OKCoin](http://okcoin.com/)
* [OKEx](https://www.okex.com/)
* [Poloniex](https://www.poloniex.com/)
* [ProBit](https://www.probit.com/)
* [Upbit](https://sg.upbit.com/home)

## National Best Bid/Offer (NBBO)

Cryptofeed also provides a synthetic NBBO (National Best Bid/Offer) feed that aggregates the best bids and asks from the user specified feeds.

```python
from cryptofeed.feedhandler import FeedHandler
from cryptofeed.exchanges import Coinbase, Bitfinex, HitBTC


def nbbo_ticker(pair, bid, ask, bid_feed, ask_feed):
    print('Pair: {} Bid: {} Bid Feed: {} Ask: {} Ask Feed: {}'.format(pair,
                                                                      bid,
                                                                      bid_feed,
                                                                      ask,
                                                                      ask_feed))


fh = FeedHandler()
fh.add_nbbo([Coinbase, Bitfinex, HitBTC], ['BTC-USD'], nbbo_ticker)
fh.run()
```

## Supported Channels

Cryptofeed supports the following channels:

* L2_BOOK - Price aggregated sizes. Some exchanges provide the entire depth, some provide a subset.
* L3_BOOK - Price aggregated orders. Like the L2 book, some exchanges may only provide partial depth.
* TRADES - Note this reports the taker's side, even for exchanges that report the maker side
* TICKER
* VOLUME
* FUNDING
* BOOK_DELTA - Subscribed to with L2 or L3 books, receive book deltas rather than the entire book on updates. Full updates will be periodically sent on the L2 or L3 channel. If BOOK_DELTA is enabled, only L2 or L3 book can be enabled, not both. To receive both create two `feedhandler` objects. Not all exchanges are supported, as some exchanges send complete books on every update.
* OPEN_INTEREST - Open interest data

## Backends

Cryptofeed supports `backend` callbacks that will write directly to storage or other interfaces

Supported Backends:
* Redis (Streams and Sorted Sets)
* [Arctic](https://github.com/manahl/arctic)
* ZeroMQ
* UDP Sockets
* TCP Sockets
* Unix Domain Sockets
* [InfluxDB](https://github.com/influxdata/influxdb) (v1 and v2)
* MongoDB
* Kafka
* Elastic Search
* RabbitMQ
* PostgreSQL


## Rest API

Cryptofeed supports some REST interfaces for retrieving historical data and placing orders. See the [rest](https://github.com/bmoscon/cryptofeed/tree/master/cryptofeed/rest) package.


## Planned Work

### Future Feeds
* CEX
* BTCC
* Many more...

### REST
Continue to build out rest endpoints and standardize exchange interfaces and data

### Additional Callback Methods / Backends
* Pulsar
* More ZMQ improvements/options

## Contributing
Issues and PRs are welcomed. If you'd like to discuss ongoing development please join the [slack](https://join.slack.com/t/cryptofeed-dev/shared_invite/enQtNjY4ODIwODA1MzQ3LTIzMzY3Y2YxMGVhNmQ4YzFhYTc3ODU1MjQ5MDdmY2QyZjdhMGU5ZDFhZDlmMmYzOTUzOTdkYTZiOGUwNGIzYTk)

This wouldn't have been possible without the help of many [contributors](AUTHORS.md)! I owe them and all other contribtors my thanks!
