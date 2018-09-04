## Changelog

### 0.14.0 (2018-09-04)
  * Feature: support for writing order books directly to redis
  * Feature: ability to specify book depth for redis updates

### 0.13.3 (2018-08-31)
  * Feature: normalize bitfinex funding symbols

### 0.13.2 (2018-08-31)
  * Bugfix: fix symbol in bitfinex rest

### 0.13.1 (2018-08-31)
  * Feature: access rest endpoints via getitem / []
  * Bugfix: #31 - funding channel broke gemini
  * Feature: Book deltas for GDAX
  * Bugfix: Fix intervals on Bitmex (rest)

### 0.13.0 (2018-08-22)
  * Feature: Funding data from Bitmex on ws
  * Feature: Funding historical data via rest
  * Bugfix: Python 3.7 compatibility
  * Feature: Rest trade APIs are now generators
  * Feature: funding data on bitfinex - ws and rest

### 0.12.0 (2018-08-20)
  * Bugfix: Handle 429s in Bitmex (REST)
  * Feature: Redis backend for trades to write updates directly to redis
  * Bugfix: issue #27 - Bitmex trades missing timestamps

### 0.11.1 (2018-08-18)
  * Bitfinex and Bitmex historical trade data via REST
  * Bugfix: interval incorrect for rest time ranges
  * Bugfix: lowercase attrs in Rest interface

### 0.11.0 (2018-08-05)
  * Feature: Support for delta updates for order books
  * REST api work started

### 0.10.2
  * Bugfix: Clear data structures on reconnect in bitmex
  * Feature: Support reconnecting on more connection errors
  * Feature: Timestamp support on trade feeds
  * Feature: Connection watcher will terminate and re-open idle connections

### 0.10.1 (2018-5-11)
  * Feature: Reconnect when a connection is lost
  * Bugfix #22: Check for additional connection failures
  * Feature #4: Trade ID support
  * Feature: Account for new gemini message type

### 0.10.0 (2018-03-18)
  * Feature: Bitmex

### 0.9.2 (2018-03-13)
  * Bugfix #10: Change from float to decimal.Decimal in GDAX
  * Feature #5: use sorted dictionaries for order books
  * Feature #17: logging support
  * Bugfix: Gemini order books now work
  * Bugfix: All json floats parsed to Decimal
  * Bugfix: Fix Bitstamp pair parsing
  * Feature: Major clean up of channel, exchange, and trading pair names

### 0.9.1 (2018-01-27)
  * Bugfix #4: produce ticker from trades channel on GDAX
  * Feature: Bitstamp feed

### 0.8.0 (2018-01-07)
  * Feature: HitBTC feed
  * Feature: Poloniex Orderbook support

### 0.6.0 (2018-01-02)
  * Feature: Gemini Feed

### 0.5.0 (2018-01-02)
  * Initial release: GDAX, Poloniex, Bitfinex Support
  * Feature: NBBO support
