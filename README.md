# Cryptocurrency Exchange Feed Handler
[![License](https://img.shields.io/badge/license-XFree86-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.7+-green.svg)
[![Build Status](https://travis-ci.org/bmoscon/cryptofeed.svg?branch=master)](https://travis-ci.org/bmoscon/cryptofeed)
[![PyPi](https://img.shields.io/badge/PyPi-cryptofeed-brightgreen.svg)](https://pypi.python.org/pypi/cryptofeed)
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/efa4e0d6e10b41d0b51454d08f7b33b1)](https://www.codacy.com/app/bmoscon/cryptofeed?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=bmoscon/cryptofeed&amp;utm_campaign=Badge_Grade)

Handles multiple cryptocurrency exchange data feeds and returns normalized and standardized results to client registered callbacks for events like trades, book updates, ticker updates, etc. Utilizes websockets when possible, but can also poll data via REST endpoints if a websocket is not provided.

## Install

You can install and upgrade Cryptofeed using Pip:

    $ python3 -m pip install --user --upgrade aiohttp

For speeding up DNS resolving also install aiodns:

    $ python3 -m pip install --user --upgrade aiodns

You may also be interested by cchardet as a faster replacement for chardet:

    $ python3 -m pip install --user --upgrade cchardet

To install Cryptofeed along with aiodns and cchardet in one bundle:

    $ python3 -m pip install --user --upgrade cryptofeed[speedups]

To install Cryptofeed along with [Arctic](https://github.com/man-group/arctic/):

    $ python3 -m pip install --user --upgrade cryptofeed[arctic]

To install Cryptofeed and enable its Redis backend:

    $ python3 -m pip install --user --upgrade cryptofeed[redis]

To install Cryptofeed and enable its ZeroMQ  backend:

    $ python3 -m pip install --user --upgrade cryptofeed[zmq]

To install Cryptofeed and enable its RabbitMQ backend:

    $ python3 -m pip install --user --upgrade cryptofeed[zmq]

To install Cryptofeed and enable its MongoDB backend:

    $ python3 -m pip install --user --upgrade cryptofeed[mongo]

To install Cryptofeed and enable its PostgreSQL backend:

    $ python3 -m pip install --user --upgrade cryptofeed[postgres]

To install Cryptofeed and enable its Kafka backend:

    $ python3 -m pip install --user --upgrade cryptofeed[kafka]

To install Cryptofeed and enable more features: historical data retrieval and order placement (see [Rest API](#rest-api))

    $ python3 -m pip install --user --upgrade cryptofeed[rest_api]

To install Cryptofeed along with all optional dependencies and speedups:

    $ python3 -m pip install --user --upgrade cryptofeed[all]

## Example

Please see the [examples](https://github.com/bmoscon/cryptofeed/tree/master/examples) for more code samples, the [documentation](https://github.com/bmoscon/cryptofeed/blob/master/docs/README.md)  or the [FAQ](https://github.com/bmoscon/cryptofeed/tree/master/FAQ.md) for some oddities and gotchas.


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

* Binance
* Binance US
* Binance Jersey
* Binance Futures
* Bitcoin.com
* Bitfinex
* BitMax
* BitMEX
* Bitstamp
* Bittrex
* Blockchain
* Bybit
* Coinbase
* Deribit
* EXX
* FTX
* FTX US
* Gemini
* HitBTC
* Huobi
* HuobiDM
* Kraken
* Kraken Futures
* OKCoin
* OKEx
* Poloniex
* Upbit

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
* *_SWAP (L2/L3 Books, Trades, Ticker) - Swap data on supporting exchanges
* *_FUTURES (L2/L3 Books, Trades, Ticker) - Futures data on supporting exchanges
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
* [InfluxDB](https://github.com/influxdata/influxdb)
* MongoDB
* Kafka
* Elastic Search
* RabbitMQ
* Postgres


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

This wouldn't have been possible with the many [contributors](AUTHORS.md)! I owe them and all who have contributed in other ways my thanks!

## Pipenv

The Pipenv tool allows to install the project dependencies without impacting your daily Python environment.
Pipenv is based on `pip` and `virtualenv`.

### Install Pipenv

```commandline
python3 -m pip install --user --upgrade pip
python3 -m pip install --user --upgrade pipenv
```

### Install the runtime dependencies

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv install
```

### Once a week, you may update dependency versions

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv update
```

### Print the dependency graph

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv graph
```

### Uninstall the unused dependencies

Edit the `Pipfile` and comment some or all dependencies above the line `# Optional dependencies`.
After, run:

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv clean
```

### Run a script
 
In the following example, we run the `demo.py` script.

```commandline
cd your/path/to/cryptofeed
export PYTONPATH=.
python3 -m pipenv run python3 examples/demo.py 
```

### Install the dependencies required for the development

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv install --dev
```

### Unit-test the source code

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv run python3 -m pytest tests
```

Pytest is listed as a dependency in `Pipfile`.
There is also a Pytest plugin, pytest-asyncio, allowing us to write unit-tests for `asyncio` functions.

### Statically analyse the code

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv run python3 -m pylint --output-format=colorized ./cryptofeed/exchange
```

In `Pipfile`, Pylint and some plugins are listed as dependencies.

Reduce the amount of issues by disabling the minor ones with option `--disable`:

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv run python3 -m pylint --output-format=colorized --disable=C0111,C0301,C0103,R0903,R0913,R0912  ./cryptofeed/exchange
```

Analyse more folders:

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv run python3 -m pylint --output-format=colorized ./cryptofeed ./examples ./tools
```

Enable Pylint plugins with option `--load-plugins`:

```commandline
cd your/path/to/cryptofeed
export PYTONPATH=.
python3 -m pipenv run python3 -m pylint --verbose --output-format=colorized --load-plugins=pylint_topology,pylint_import_modules,pylint_google_style_guide_imports_enforcing,pylint_unittest,pylint_requests,pylint_args,string_spaces_checkers ./cryptofeed
```

When almost all issues are fixed, speed up the Pylint using option `--jobs=8`.
(this options mixes the Pylint output when there is many issues) 

### Clean the `import` sections

The following `isort` options apply the same formatting as `black` but only on the `import` sections.

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv run python3 -m isort --jobs=8 --atomic --multi-line 3 --force-grid-wrap 0 --trailing-comma --use-parentheses --apply --recursive .
```
