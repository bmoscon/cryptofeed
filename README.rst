Cryptocurrency Exchange Feed Handler
====================================

|License| |Python| |Build Status| |Codacy Badge| |PyPi|

Handles multiple feeds and returns normalized and standardized results
across exchanges to client registered callbacks for events like trades,
book updates, ticker updates, etc.

Please see the `examples`_ for more code samples.

.. code:: python

   from cryptofeed import FeedHandler

   fh = FeedHandler()

   # ticker, trade, and book are user defined functions that
   # will be called when ticker, trade and book updates are received
   ticker_cb = {TICKER: TickerCallback(ticker)}
   trade_cb = {TRADES: TradeCallback(trade)}
   gemini_cb = {TRADES: TradeCallback(trade), L3_BOOK: BookCallback(book)}


   fh.add_feed(Coinbase(pairs=['BTC-USD'], channels=[TICKER], callbacks=ticker_cb)
   fh.add_feed(Bitfinex(pairs=['BTC-USD'], channels=[TICKER], callbacks=ticker_cb)
   fh.add_feed(Poloniex(channels=['USDT-BTC'], callbacks=trade_cb))
   fh.add_feed(Gemini(pairs=['BTC-USD'], callbacks=gemini_cb)

   fh.run()

Supports the following exchanges:

-  Bitfinex
-  Coinbase
-  Poloniex
-  Gemini
-  HitBTC
-  Bitstamp
-  BitMEX
-  Kraken
-  Binance

Also provides a synthetic NBBO (National Best Bid/Offer) feed that
aggregates the best bids and asks from the user specified feeds.

.. code:: python

   from cryptofeed.feedhandler import FeedHandler
   from cryptofeed import Coinbase, Bitfinex, HitBTC


   def nbbo_ticker(pair, bid, ask, bid_feed, ask_feed):
       print('Pair: {} Bid: {} Bid Feed: {} Ask: {} Ask Feed: {}'.format(pair,
                                                                         bid,
                                                                         bid_feed,
                                                                         ask,
                                                                         ask_feed))


   fh = FeedHandler()
   fh.add_nbbo([Coinbase, Bitfinex, HitBTC], ['BTC-USD'], nbbo_ticker)
   fh.run()

Supported Channels
------------------

Cryptofeed supports the following channels:

-  L2_BOOK - Price aggregated sizes. Some exchanges provide the entire
   depth, some provide a subset.
-  L3_BOOK - Price aggregated orders. Like the L2 book, some exchanges
   may only provide partial depth.
-  TRADES
-  TICKER
-  VOLUME
-  FUNDING
-  BOOK_DELTA - Subscribed to with L2 or L3 books, receive book deltas
   rather than the entire book on updates. Full updates will be
   periodically sent on the L2 or L3 channel. If BOOK_DELTA is enabled,
   only L2 or L3 book can be en

.. _examples: /examples

.. |License| image:: https://img.shields.io/badge/license-XFree86-blue.svg
   :target: LICENSE
.. |Python| image:: https://img.shields.io/badge/Python-3.6+-green.svg
.. |Build Status| image:: https://travis-ci.org/bmoscon/cryptofeed.svg?branch=master
   :target: https://travis-ci.org/bmoscon/cryptofeed
.. |Codacy Badge| image:: https://api.codacy.com/project/badge/Grade/efa4e0d6e10b41d0b51454d08f7b33b1
   :target: https://www.codacy.com/app/bmoscon/cryptofeed?utm_source=github.com&utm_medium=referral&utm_content=bmoscon/cryptofeed&utm_campaign=Badge_Grade
.. |PyPi| image:: https://img.shields.io/badge/PyPi-cryptofeed-brightgreen.svg
   :target: https://pypi.python.org/pypi/cryptofeed
