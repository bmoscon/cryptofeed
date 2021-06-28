## Cryptofeed High Level Overview

Cryptofeed is composed of the following components:

* Feedhandler
* Connection Abstraction
* Connection Handler
* Exchange Interfaces
* Callbacks
* Backends


### Feedhandler

The feedhandler is the main object that a user of the library will configure. It has the following methods:

* `add_feed`
* `add_nbbo`
* `run`

`add_feed`is the main method used to register an exchange with the feedhandler. You can supply an Exchange object, or a string matching the exchange's name (all uppercase). Currently if you wish to add multiple exchanges, you must call add_feed multiple times (one per exchange).

`add_nbbo` lets you compose your own NBBO data feed. It takes the arguments `feeds`, `symbols` and `callback`, which are the normal arguments you'd supply for exchange objects when supplied to the feed handler. The exchanges in the `feeds` list will subscribe to the `symbols` and NBBO updates will be supplied to the `callback` method as they are received from the exchanges.

`run` simply starts the feedhandler. The feedhandler uses asyncio, so `run` will block while the feedhandler runs.

### Connection / Connection Handler

Cryptofeed supports various connection types with exchanges, including HTTP and websocket. These are maintained and monitored in the Connection Handler, which creates connections, handles exceptions, and restarts connections as appropriate.

### Exchange Interface

The exchange objects are supplied with the following arguments:

* `channels`
* `symbols`
* `subscription`
* `config`
* `callbacks`

`channels` are the data channels for which you are interested in receiving updates. Examples are TRADES, TICKER, and L2_BOOK. Not all exchanges support all channels. `symbols` are the trading symbols. Every symbol in `symbols` will subscribed to every channel in `channels`. If you wish to create a more granular subscription, use the `subscription` option. The `config` kwarg can be used to specify exchange specific configuration information. See the [config](config.md) doc for more information.  

The supported data channels are:

* L2_BOOK - Price aggregated sizes. Some exchanges provide the entire depth, some provide a subset.
* L3_BOOK - Price aggregated orders. Like the L2 book, some exchanges may only provide partial depth.
* TRADES - Note this reports the taker's side, even for exchanges that report the maker side
* TICKER - Traditional ticker updates
* FUNDING - Exchange specific funding data / updates
* BOOK_DELTA - Subscribed to with L2 or L3 books, receive book deltas rather than the entire book on updates. Full updates will be periodically sent on the L2 or L3 channel. If BOOK_DELTA is enabled, only L2 or L3 book can be enabled, not both. To received both create two `feedhandler` objects. Not all exchanges support, as some exchanges send complete books on every update.


Trading symbols follow the following scheme BASE-QUOTE. As an example, Bitcoin denominated by US Dollars would be BTC-USD. Many exchanges do not internally use this format, but cryptofeed handles trading symbol normalization and all symbols should be subscribed to in this format and will be reported in this format. 

If you use `channels` and `symbols` you cannot use `subscription`, likewise if `subscription` is supplied you cannot use `channels` and `symbols`. `subscription` is supplied in a dictionary format, in the following manner: {CHANNEL: [symbols], ... }. As an example:

```python
{TRADES: ['BTC-USD', 'BTC-USDT', 'ETH-USD'], L2_BOOK: ['BTC-USD']}
```

### Normalization

Cryptofeed normalizes various parts of the data - primarily timestamps and symbols, to ensure they are consistent across all exchanges. Pairs take the format BASE-QUOTE (as previously mentioned) and timestamps are all converted to seconds since the epoch (traditional UNIX timestamps), in floating point. 

### Callbacks

Callbacks are user defined functions that will be called on a data event, like when a trade update is received. Their format is specified in the `callbacks.py` file, and user defined callbacks should mirror their interface. 


### Backends

Backends are supplied callbacks that do specific things, like write updates to a database or send the update on a socket. They are simple to configure and use, but may not be as fully featured as a power user may wish. The backends live in the `backends` directory.


### Examples

Setting up a simple feedhandler. Subscribing to Coinbase

```python
from cryptofeed.callback import TickerCallback, TradeCallback, BookCallback, FundingCallback
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase
from cryptofeed.defines import TRADES, TICKER


async def ticker(feed, symbol, bid, ask, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {symbol} Bid: {bid} Ask: {ask}')


async def trade(feed, symbol, order_id, timestamp, side, amount, price, receipt_timestamp):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {symbol} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


def main():
    f = FeedHandler()
    f.add_feed(Coinbase(symbols=['BTC-USD'], channels=[TRADES, TICKER], callbacks={TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade)}))

    f.run()


if __name__ == '__main__':
    main()
```

more complicated examples, including the use of backends, can be found [here](../examples)
