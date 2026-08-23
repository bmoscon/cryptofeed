# Cryptocurrency Exchange Feed Handler
[![License](https://img.shields.io/badge/license-AGPL-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.12+-green.svg)
[![PyPi](https://img.shields.io/badge/PyPi-cryptofeed-brightgreen.svg)](https://pypi.python.org/pypi/cryptofeed)


Handles multiple cryptocurrency exchange data feeds and returns normalized and standardized results to client registered callbacks for events like trades, book updates, ticker updates, etc. Utilizes websockets when possible, but can also poll data via REST endpoints if a websocket is not provided.

## Supported exchanges

* [Bitfinex](https://bitfinex.com)
* [bitFlyer](https://bitflyer.com/)
* [Bithumb](https://en.bithumb.com/)
* [Bitstamp](https://www.bitstamp.net/)
* [Bybit](https://www.bybit.com/)
* [Binance](https://www.binance.com/en)
* [Binance Delivery](https://binance-docs.github.io/apidocs/delivery/en/)
* [Binance Futures](https://www.binance.com/en/futures)
* [Binance US](https://www.binance.us/en)
* [Bitget](https://www.bitget.com/)
* [Coinbase](https://www.coinbase.com/)
* [Crypto.com](https://www.crypto.com)
* [Deribit](https://www.deribit.com/)
* [Gate.io](https://www.gate.io/)
* [Gate.io Futures](https://www.gate.io/futures_center)
* [dYdX v4](https://dydx.trade/)
* [Gemini](https://gemini.com/)
* [Hyperliquid](https://hyperliquid.xyz/)
* [HTX](https://www.htx.com/) (formerly Huobi)
* HTX Swap (Coin-M and USDT-M)
* [Independent Reserve](https://www.independentreserve.com/) 
* [Kraken](https://www.kraken.com/)
* [MEXC](https://www.mexc.com/) (spot)
* [Kraken Futures](https://futures.kraken.com/)
* [KuCoin](https://www.kucoin.com/)
* [OKX](https://www.okx.com/)
* [Phemex](https://phemex.com/)
* [Poloniex](https://www.poloniex.com/)
* [Upbit](https://sg.upbit.com/home)


## Basic Usage

Create a FeedHandler object and add subscriptions. For the various data channels that an exchange supports, you can supply callbacks for data events, or use provided backends (described below) to handle the data for you. Start the feed handler and you're done!

```python
from cryptofeed import FeedHandler
# not all imports shown for clarity

fh = FeedHandler()

# ticker, trade and book are user defined coroutine functions, each taking the
# normalized object and the timestamp cryptofeed received the message at:
#
#     async def trade(t, receipt_timestamp):
#         print(f'{t.exchange} {t.symbol} {t.side} {t.amount} @ {t.price}')
#
# a callback must be async - wrap a synchronous one in cryptofeed.callback.ExecutorCallback
ticker_cb = {TICKER: ticker}
trade_cb = {TRADES: trade}
gemini_cb = {TRADES: trade, L2_BOOK: book}


fh.add_feed(Coinbase(symbols=['BTC-USD'], channels=[TICKER], callbacks=ticker_cb))
fh.add_feed(Bitfinex(symbols=['BTC-USD'], channels=[TICKER], callbacks=ticker_cb))
fh.add_feed(Poloniex(symbols=['BTC-USDT'], channels=[TRADES], callbacks=trade_cb))
fh.add_feed(Gemini(symbols=['BTC-USD', 'ETH-USD'], channels=[TRADES, L2_BOOK], callbacks=gemini_cb))

fh.run()
```

## National Best Bid/Offer (NBBO)

Cryptofeed also provides a synthetic NBBO (National Best Bid/Offer) feed that aggregates the best bids and asks from the user specified feeds.

```python
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase, Gemini, Kraken


async def nbbo_update(symbol, bid, bid_size, ask, ask_size, bid_feed, ask_feed):
    print(f'Pair: {symbol} Bid Price: {bid:.2f} Bid Size: {bid_size:.6f} Bid Feed: {bid_feed} Ask Price: {ask:.2f} Ask Size: {ask_size:.6f} Ask Feed: {ask_feed}')


def main():
    f = FeedHandler()
    f.add_nbbo([Coinbase, Kraken, Gemini], ['BTC-USD'], nbbo_update)
    f.run()
```

## Supported Channels

Cryptofeed supports the following public data channels from exchanges

* L1_BOOK - Top of book
* L2_BOOK - Price aggregated sizes. Some exchanges provide the entire depth, some provide a subset.
* L3_BOOK - Price aggregated orders. Like the L2 book, some exchanges may only provide partial depth.
* TRADES - Note this reports the taker's side, even for exchanges that report the maker side.
* TICKER
* FUNDING
* OPEN_INTEREST - Open interest data.
* LIQUIDATIONS
* INDEX
* CANDLES - Candlestick / K-Line data.

## Backends

Cryptofeed supports `backend` callbacks that will write directly to storage or other interfaces.

Supported Backends:
* Redis (Sorted Sets, Streams and Keys)
* ZeroMQ
* UDP Sockets
* TCP Sockets
* Unix Domain Sockets
* [InfluxDB v2](https://github.com/influxdata/influxdb)
* MongoDB
* Kafka
* PostgreSQL
* [QuestDB](https://questdb.io/)


## Installation

**Note:** cryptofeed requires Python 3.12+

Cryptofeed can be installed from PyPi. (It's recommended that you install in a virtual environment of your choosing).

    pip install cryptofeed

Cryptofeed has optional dependencies, depending on the backends used. You can install them individually, or all at once. To install Cryptofeed along with all its optional dependencies in one bundle:

    pip install cryptofeed[all]

If you wish to clone the repository and work on it (development uses [uv](https://docs.astral.sh/uv/)), run this from the root of the cloned repository:

    uv sync

Alternatively, you can install from source in editable mode with pip:

    pip install -e .


## Performance

Measured on Python 3.14.6 based on throughput over real recorded exchange traffic.

| Operation | Result |
|---|---|
| `Trade` construct / `to_dict` / `from_dict` | 102 ns / 214 ns / 277 ns |
| `Ticker` / `Candle` / `Funding` construct | 70 ns / 118 ns / 141 ns |
| Book single level update / delete / top-of-book read | 89 ns / 124 ns / 140 ns |
| Book `to_dict`, 10 / 100 levels per side | 2.4 µs / 22.2 µs |
| Checksum, Kraken / OKX format (200 levels) | 2.0 µs / 6.1 µs |
| JSON decode with `Decimal` (msgspec / stdlib fallback) | 1.39M / 0.60M msg/s |
| JSON encode to str / bytes | 4.65M / 5.25M msg/s |
| Message handler, Kraken / Bybit / KuCoin / Kraken Futures | 161k / 134k / 122k / ~100k frames/s |


## Future Work

There are a lot of planned features, new exchanges, etc planned! If you'd like to discuss ongoing development, please join the [discord](https://discord.gg/zaBYaGAYfR) or open a thread in the [discussions](https://github.com/bmoscon/cryptofeed/discussions) in GitHub.

## Contributing

Issues and PRs are welcomed!

Cryptofeed wouldn't be possible without the help of many [contributors](AUTHORS.md)! I owe them and all other contributors my thanks!

## Donations / Support

Support and donations are appreciated but not required. You can donate via [GitHub Sponsors](https://github.com/sponsors/bmoscon), or via the addresses below:

* Bitcoin: bc1qm0kxz8hqacaglku5fjhfe9a5hjnuyfwk02lsyr
* Ethereum: 0x690709FEe13eEce9E7852089BB2D53Ae5D073154
