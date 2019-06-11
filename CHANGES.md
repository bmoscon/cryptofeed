## Changelog

### 0.24.0
  * Bugfix: Book Delta Conversion issue in backends
  * Bugfix: Tweak BitMEX rest api to handle more errors more gracefully
  * Feature: Deribit Exchange support
  * Feature: Instrument channel
  * Bugfix: support Kraken websocket API changes
  * Bugfix: correct USDT symbol mappings for Bitfinex

### 0.23.0 (2019-06-03)
  * Feature: Book delta support for InfluxDB
  * Feature: Swaps on OkEX

### 0.22.2 (2019-05-23)
  * Bugfix: Fix tagging issue in InfluxDB
  * Bugfix: Fix book updates in InfluxDB
  * Feature: Book delta support in Redis backends
  * Feature: Book delta support in Kafka backend

### 0.22.1 (2019-05-19)
  * Feature: Cleanup callback code
  * Feature: Poloniex subscription now behaves like other exchanges
  * Feature: Kafka Backend

### 0.22.0 (2019-05-04)
  * Bugfix: Timestamp normalization for backends were losing subsecond fidelity
  * Feature: All exchanges report timestamps in floating point unix time
  * Bugfix: Implement change in OkEx's trading pair endpoint for pair generation

### 0.21.1 (2019-04-28)
  * Feature: Config support for Coinbene, Binance, EXX, BitMEX, Bitfinex, Bitstamp, HitBTC
  * Feature: Complete clean up of public REST endpoints
  * Feature: Improved book delta example
  * Feature: Bitstamp Websocket V2 - L3 books now supported
  * Bugfix: Incorrect book building in Kraken

### 0.21.0 (2019-04-07)
  * Bugfix: Coinbase L3 Book would get in cycle of reconnecting due to missing sequence numbers
  * Feature: Kraken L2 Book Deltas
  * Feature: Book deltas streamlined and retain ordering
  * Feature: OKCoin exchange support
  * Feature: OKEx exchange support
  * Feature: Coinbene exchange support
  * Feature: Support Huobi Global and Huobi USA

### 0.20.2 (2019-03-19)
  * Bugfix: Kraken REST api using wrong symbol for trades
  * Feature: Complete work on standardizing Bitfinex rest API
  * Bugfix: Allow index symbols on Bitmex

### 0.20.1 (2019-02-16)
  * Feature: Trades sides are now labeled as Buy / Sell instead of Bid / Ask.
  * Feature: Support for the Huobi exchange
  * Bugfix: Change how exchange pairs are mapped for REST module - only map exchanges that are used
  * Bugfix #67: Ensure all trades report the taker's side

### 0.20.0 (2019-02-04)
  * Feature #57: Write updates directly to MongoDB via new backend support
  * Feature #56: Experimental support for fine grained configuration per exchange
  * Feature #58: Support Kraken websocket API
  * Feature: Only generate trading pair conversions for configured exchanges
  * Feature: Historical trade data on REST api for Kraken

### 0.19.2 (2019-01-21)
  * Feature #55: OHLCV aggregation method in backends plus support for user defined aggregators
  * Feature: EXX exchange support

### 0.19.1 (2019-01-11)
  * Bugfix: Poloniex logging had bug that prevented reconnect on missing sequence number

### 0.19.0 (2019-01-10)
  * Feature #50: Support multiple streams per websocket connection on Binance
  * Bugfix #51: Fix pairs on streams in Binance

### 0.18.0 (2018-12-15)
  * Feature: InfluxDB support via backend
  * Feature: Aggregation backend wrappers
  * Bugfix: BookDelta callback no longer needs to be an instance of BookUpdateCallback
  * Bugfix: REST module was creating duplicate log handlers
  * Bugfix: Bitfinex REST now properly handles cases when there are more than 1000 updates for a single tick

### 0.17.4 (2018-11-17)
  * Readme change for long description rendering issue

### 0.17.3 (2018-11-17)
  * Feature #41: Rework trading pairs to generate them dynamically (as opposed to hard coded)
  * Feature: When book depth configured Redis, ZMQ and UDP backends only report book changes when changed occurred in 
             depth window
  * Feature: TCP socket backend support
  * Feature: UDS backend support

### 0.17.2 (2018-11-03)
  * Bugfix #45: Bitstamp prices and sizes in L2 book are string, not decimal.Decimal
  * Feature: Binance support

### 0.17.1 (2018-10-19)
  * Bugfix #43: Coinbase L2 book used "0" rather than 0 for comparisons against decimal.Decimal
  * Feature: REST feed market data supported via normal subscription methods
  * Feature: Kraken support
  * Bugfix: Bitfinex book timestamps match expected bitfinex timestamps (in ms)

### 0.17.0 (2018-10-13)
  * Feature: Timestamps for orderbooks and book deltas
  * Feature #40: NBBO now uses best bid/ask from L2 books
  * Feature #28: GDAX now renamed Coinbase and uses coinbase endpoints
  * Feature: ZeroMQ backend. Write updates directly to zmq connection
  * Feature: UDP Socket backend. Write updates directy to UDP socket

### 0.16.0 (2018-10-4)
  * Feature: L2 books are now all price aggregted amounts, L3 books are price aggregated orders
  * Book deltas supported on all feeds
  * Bugfix: Fix NBBO feed

### 0.15.0 (2018-09-29)
  * Feature: GDAX/Coinbase rest support - trades, order status, etc
  * Feature: Arctic backend, supports writing to arctic directly on trade/funding updates
  * Bugfix: #36 Update poloniex to use new trading pairs and handle sequence numbers
  * Bugfix: Improve Bitfinex orderbooks and handle sequence numbers
  * Bugfix: GDAX and Bitmex orderbook and logging improvements

### 0.14.1 (2018-09-14)
  * Added some docstrings
  * Feature: Add exchanges by name to feedhandler. Easier to instantiate a feedhandler from config
  * Logging improvements
  * Bugfix: non-gathered futures were suppressing exceptions when multiple feeds are configured. Changed to tasks 
  * Redis backend uses a connection pool

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
