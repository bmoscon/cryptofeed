# Cryptofeed High Level Overview

Cryptofeed is composed of the following components:

* Feedhandler
* Exchange Interfaces
* Callbacks
* Backends


### Feedhandler

The feedhandler is the main object that a user of the library will configure. It has the following methods:

* `add_feed`
* `add_nbbo`
* `run`

`add_feed`is the main method used to register an exchange with the feedhandler. You can supply an Exchange object, or a string matching the exchange's name (all uppercase). Currently if you wish to add multiple exchanges, you must call add_feed multiple times (one per exchange).

`add_nbbo` lets you compose your own NBBO data feed. It takes the arguments `feeds`, `pairs` and `callback`, which are the normal arguments you'd supply for exchange objects when supplied to the feed handler. The exchanges in the `feeds` list will subscribe to the `pairs` and NBBO updates will be supplied to the `callback` method as they are received from the exchanges.

`run` simply starts the feedhandler. The feedhandler uses asyncio, so `run` will block while the feedhandler runs.

### Exchange Interface

The exchange objects are supplied with the following arguments:

* `channels`
* `pairs`
* `config`
* `callbacks`

`channels` are the data channels for which you are interested in receiving updates. Examples are TRADES, TICKER, and L2_BOOK. Not all exchanges support all channels. `pairs` are the trading pairs. Every pair in `pairs` will subscribed to every channel in `channels`. If you wish to create a more granular subscription, use the `config` option.

The supported data channels are:

* L2_BOOK - Price aggregated sizes. Some exchanges provide the entire depth, some provide a subset.
* L3_BOOK - Price aggregated orders. Like the L2 book, some exchanges may only provide partial depth.
* TRADES - Note this reports the taker's side, even for exchanges that report the maker side
* TICKER - Traditional ticker updates
* VOLUME - Volume information (Poloniex only currently)
* FUNDING - Exchange specific funding data / updates
* BOOK_DELTA - Subscribed to with L2 or L3 books, receive book deltas rather than the entire book on updates. Full updates will be periodically sent on the L2 or L3 channel. If BOOK_DELTA is enabled, only L2 or L3 book can be enabled, not both. To received both create two `feedhandler` objects. Not all exchanges support, as some exchanges send complete books on every update.


Trading pairs follow the following scheme BASE-QUOTE. As an example, Bitcoin denominated by US Dollars would be BTC-USD. Many exchanges do not internally use this format, but cryptofeed handles trading pair normalization and all pairs should be subscribed to in this format and will be reported in this format. 

If you use `channels` and `pairs` you cannot use `config`, likewise if `config` is supplied you cannot use `channels` and `pairs`. `config` is supplied in a dictionary format, in the following manner: {CHANNEL: [trading pairs], ... }. As an example:

```python
{TRADES: ['BTC-USD', 'BTC-USDT', 'ETH-USD'], L2_BOOK: ['BTC-USD']}
```

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


async def ticker(feed, pair, bid, ask):
    print(f'Feed: {feed} Pair: {pair} Bid: {bid} Ask: {ask}')


async def trade(feed, pair, order_id, timestamp, side, amount, price):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


def main():
    f = FeedHandler()
    f.add_feed(Coinbase(pairs=['BTC-USD'], channels=[TRADES, TICKER], callbacks={TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade)}))
  
    f.run()


if __name__ == '__main__':
    main()
```

more complicated examples, including the use of backends, can be found [here](../examples)
