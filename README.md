# Cryptocurrency Exchange Feed Handler
[![License](https://img.shields.io/badge/license-XFree86-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.7+-green.svg)
[![Build Status](https://travis-ci.com/bmoscon/cryptofeed.svg?branch=master)](https://travis-ci.com/bmoscon/cryptofeed)
[![PyPi](https://img.shields.io/badge/PyPi-cryptofeed-brightgreen.svg)](https://pypi.python.org/pypi/cryptofeed)
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/efa4e0d6e10b41d0b51454d08f7b33b1)](https://www.codacy.com/app/bmoscon/cryptofeed?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=bmoscon/cryptofeed&amp;utm_campaign=Badge_Grade)

Handles multiple cryptocurrency exchange data feeds and returns normalized and standardized results to client registered callbacks for events like trades, book updates, ticker updates, etc. Utilizes websockets when possible, but can also poll data via REST endpoints if a websocket is not provided.

## Supported exchanges

* [Bitcoin.com](https://www.bitcoin.com/)
* [Bitfinex](https://bitfinex.com)
* [bitFlyer](https://bitflyer.com/)
* [Bithumb](https://en.bithumb.com/)
* [BitMax](https://bitmax.io/)
* [Bitstamp](https://www.bitstamp.net/)
* [Bittrex](https://global.bittrex.com/)
* [Blockchain.com](https://www.blockchain.com/)
* [Bybit](https://www.bybit.com/)
* [Binance](https://www.binance.com/en)
* [Binance Delivery](https://binance-docs.github.io/apidocs/delivery/en/)
* [Binance Futures](https://www.binance.com/en/futures)
* [Binance US](https://www.binance.us/en)
* [BitMEX](https://www.bitmex.com/)
* [Coinbase](https://www.coinbase.com/)
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
* [KuCoin](https://www.kucoin.com/)
* [OKCoin](http://okcoin.com/)
* [OKEx](https://www.okex.com/)
* [Poloniex](https://www.poloniex.com/)
* [ProBit](https://www.probit.com/)
* [Upbit](https://sg.upbit.com/home)

## Supported aggregated crypto data providers

* [Coingecko](https://www.coingecko.com/en)


## Basic Usage

Create a FeedHandler object and add subscriptions. For the various data channels that an exchange supports, you can supply callbacks for data events, or use provided backends (described below) to handle the data for you. Start the feed handler and you're done!

```python
from cryptofeed import FeedHandler
# not all imports shown for clarity

fh = FeedHandler()

# ticker, trade, and book are user defined functions that
# will be called when ticker, trade and book updates are received
ticker_cb = {TICKER: TickerCallback(ticker)}
trade_cb = {TRADES: TradeCallback(trade)}
gemini_cb = {TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}


fh.add_feed(Coinbase(symbols=['BTC-USD'], channels=[TICKER], callbacks=ticker_cb))
fh.add_feed(Bitfinex(symbols=['BTC-USD'], channels=[TICKER], callbacks=ticker_cb))
fh.add_feed(Poloniex(symbols=['BTC-USDT'], channels=[TRADES], callbacks=trade_cb))
fh.add_feed(Gemini(symbols=['BTC-USD', 'ETH-USD'], channels=[TRADES, L2_BOOK], callbacks=gemini_cb))

fh.run()
```

Please see the [examples](https://github.com/bmoscon/cryptofeed/tree/master/examples) for more code samples and the [documentation](https://github.com/bmoscon/cryptofeed/blob/master/docs/README.md) for more information about the library usage.


To see an example of an application using cryptofeed to aggregate and store cryptocurrency data to a database, please look at [Cryptostore](https://github.com/bmoscon/cryptostore).


## National Best Bid/Offer (NBBO)

Cryptofeed also provides a synthetic [NBBO](examples/demo_nbbo.py) (National Best Bid/Offer) feed that aggregates the best bids and asks from the user specified feeds.

```python
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase, Gemini, Kraken


def nbbo_update(symbol, bid, bid_size, ask, ask_size, bid_feed, ask_feed):
    print(f'Pair: {symbol} Bid Price: {bid:.2f} Bid Size: {bid_size:.6f} Bid Feed: {bid_feed} Ask Price: {ask:.2f} Ask Size: {ask_size:.6f} Ask Feed: {ask_feed}')


def main():
    f = FeedHandler()
    f.add_nbbo([Coinbase, Kraken, Gemini], ['BTC-USD'], nbbo_update)
    f.run()
```

## Supported Channels

Cryptofeed supports the following channels from exchanges:

### Market Data Channels (Public)

* L2_BOOK - Price aggregated sizes. Some exchanges provide the entire depth, some provide a subset.
* L3_BOOK - Price aggregated orders. Like the L2 book, some exchanges may only provide partial depth.
* TRADES - Note this reports the taker's side, even for exchanges that report the maker side.
* TICKER
* FUNDING
* BOOK_DELTA - Subscribed to with L2 or L3 books, receive book deltas rather than the entire book on updates. Full updates will be periodically sent on the L2 or L3 channel. If BOOK_DELTA is enabled, only L2 or L3 book can be enabled, not both. To receive both create two `feedhandler` objects. Not all exchanges are supported, as some exchanges send complete books on every update.
* OPEN_INTEREST - Open interest data.
* LIQUIDATIONS
* FUTURES_INDEX
* CANDLES - Candlestick / K-Line data.

Aggregated data from provider is available in channel:

* MARKET_INFO - current aggregated price, market cap, volume (in USD, BTC or ETH currency), total and circulating supply,
 as well as community data (twitter, reddit, facebook...) and scores (coingecko, developer, community...)

### Authenticated Data Channels

* ORDER_INFO - Order status updates


## Backends

Cryptofeed supports `backend` callbacks that will write directly to storage or other interfaces

Supported Backends:
* Redis (Streams and Sorted Sets)
* [Arctic](https://github.com/manahl/arctic)
* ZeroMQ
* UDP Sockets
* TCP Sockets
* Unix Domain Sockets
* [InfluxDB 2](https://github.com/influxdata/influxdb)
* MongoDB
* Kafka
* Elastic Search
* RabbitMQ
* PostgreSQL
* GCP Pub/Sub
* [VictoriaMetrics](https://github.com/VictoriaMetrics/VictoriaMetrics)


## Installation

**Note:** cryptofeed requires Python 3.7+

Cryptofeed can be installed from PyPi. (It's recommended that you install in a virtual environment of your choosing).

    pip install cryptofeed

Cryptofeed has optional dependencies, depending on the backends used. You can install them individually, or all at once. To install Cryptofeed along with all its optional dependencies in one bundle:

    pip install cryptofeed[all]

If you wish to clone the repository and install from source, run this command from the root of the cloned repository

    python setup.py install

Alternatively, you can install in 'edit' mode (also called development mode):

    python setup.py develop

See more options, explanations and Pipenv usage in [INSTALL.md](https://github.com/bmoscon/cryptofeed/blob/master/INSTALL.md).



## Rest API

Cryptofeed supports some REST interfaces for retrieving historical data and placing orders. See the [rest](https://github.com/bmoscon/cryptofeed/tree/master/cryptofeed/rest) package.


## Future Work

There are a lot of planned features, new exchanges, etc planned! If you'd like to discuss ongoing development please join the [slack](https://join.slack.com/t/cryptofeed-dev/shared_invite/enQtNjY4ODIwODA1MzQ3LTIzMzY3Y2YxMGVhNmQ4YzFhYTc3ODU1MjQ5MDdmY2QyZjdhMGU5ZDFhZDlmMmYzOTUzOTdkYTZiOGUwNGIzYTk) or open a thread in the [discussions](https://github.com/bmoscon/cryptofeed/discussions) in GitHub.

## Contributing

Issues and PRs are welcomed!

Cryptofeed wouldn't be possible without the help of many [contributors](AUTHORS.md)! I owe them and all other contributors my thanks!
