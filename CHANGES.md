## Changelog

### 1.9.1
  * Bugfix: Fix inverted Poloniex symbols
  * Feature: simplify and cleanup parts of Poloniex
  * Feature: add `symbols` class method to all exchanges to get list of supported trading pairs
  * Feature: Clean up internal class attributes in Feed class
  * Feature: Add graceful stop and shutdown methods for Feeds
  * Feature: Add ledger endpoint to Kraken Rest module, add ability to optionally filter by symbol, or all symbols, for historical trades
  * Docs: Update documentation regarding adding a new exchange to cryptofeed
  * Bugfix: Reset delay after connection is successful
  * Feature: yapic.json parses strings to datetimes automatically, no longer need to rely on Pandas for datetime parsing
  * Bugfix: #491 - dictionary resized during iteration in ByBit
  * Bugfix: #494 - added status argument to liquidations callback
  * Bugfix: #399 - book delta issue with Kucoin and Gateio
  * Feature: Binance Delivery candle support
  * Feature: Binance US candle support
  * Feature: Kraken Candle support
  * Update: Remove deprecated channel mapping from Kraken, use channel name from message instead
  * Bugfix: change Kraken Futures to use the standard symbol to be consistent with the rest of the library

### 1.9.0 (2021-04-25)
  * Bugfix: Fix Binance subscriptions when subscribing to more than one candle
  * Feature: Remove support for Influx versions prior to 2.0
  * Feature: Add stop method to HTTP Backends to gracefully drain queue and write pending data on shutdown
  * Feature: Revamp InfluxDB code. Drop support for storing floating point as str, store book data as json blob
  * Bugfix: Remove unused get_instrument calls in Deribit and Kraken Futures
  * Feature: Revamp symbol generation and exchange info for Deribit and Kraken Futures
  * Bugfix: Fix issue using AsyncFile callback to store raw data
  * Testing: Add exchange tests for Deribit and Binance
  * Bugfix: Fix symbol issue in Bitmex when initializing the orderbook
  * Bugfix: Fix various issues with FTX, OKCOIN/OKEX and Huobi symbol generation
  * Testing: Overhaul exchange tests, all exchanges are now tested with real data. Fixed various bugs as a result of this testing. Revamped AsyncFileCallback.
             Added new tool to generate test data for testing.
  * Bugfix: Improve connection cleanup in AsyncConnection object
  * Feature: Add support for user defined exception handling in FeedHandler
  * Bugfix: Fix redis backends that can't handle None
  * Bugfix: Connection exceptions being ignored in Feedhandler
  * Bugfix: Binance address generation correction
  * Bugfix: OKEX symbol generation incorrect + validate symbols used for channels that dont support all types
  * Breaking Change: Large rewrite of Feedhandler, Connection, and Feed. Many timeout related options moved from feedhandler to Feed. Symbol specific code
                     moved to exchange class. Rewrite of raw data collection.
  * Feature: Candle support for Huobi
  * Feature: Allow user to specify Postgres port in Postgres backends
  * Bugfix: Report base volume, not quote volume in Huobi candles
  * Feature: Support for the KuCoin exchange

### 1.8.2 (2020-04-02)
  * Update to use alpha release of aioredis 2.0. Allows building of wheels again

### 1.8.1 (2020-04-01)
  * Bugfix: Add manifest file for source dist

### 1.8.0 (2020-04-01)
  * Bugfix: Init uvloop earlier so backends that use loop will not fail
  * Docs: Remove FAQ, added performance doc section
  * Bugfix: #404 - Use AsyncConnection object for Binance OI
  * Feature: Rework how raw data is stored (when enabled). REST data can now be captured
  * Feature: New feedhandler method, `add_feed_running` allows user to add feed to running instance of a feedhandler
  * Feature: create_db defaults to False on InfluxDB backends
  * Feature: Normalize Bitmex Symbols
  * Update: Remove extraneous methods in feed objects used to query symbol information
  * Feature: Use realtime ticker for Binance
  * Bugfix: Bitmex symbols not being normalized correctly
  * Bugfix: Fix GCP PubSub backend
  * Bugfix: Fix historical data REST api for Bitmex
  * Feature: Use separate tasks (fed by async queue) for backend writing. Redis now uses this method
  * Bugfix: Allow user specified max depths on Kraken
  * Feature: Add backend queue support to ZMQ backend
  * Feature: Add backend queue support to Socket backends
  * Feature: Add VictoriaMetrics support via backend
  * Feature: Add backend queue support to influx and elastic
  * Feature: Candle support
  * Bugfix: Ignore untradeable symbols in Binance symbol generation
  * Feature: Add backend support for queues in Postgres. Rework postgres backend and supply example SQL file to create tables for demo
  * Bugfix: Fix ByBit symbol generation
  * Feature: Authenticated channel support for OKEX/OKCOIN
  * Update: Poloniex changed signaure of ticker data
  * Feature: Candles for Binance Futures
  * Feature: Premium Index Candle support for Binance Futures
  * Feature: Update Gateio to use new v4 websocket api. Adds support for candles 


### 1.7.0 (2021-02-15)
  * Feature: Use UVLoop if installed (not available on windows)
  * Bugfix: Allow exchanges to customize their retry delays on error
  * Feature: New demo code showing user loop management
  * Feature: Handle more signals for graceful shutdown
  * Bugfix: BinanceFutures message format change
  * Feature: Missing sequence number on Coinbase will not reset all data streams, just the affected pair
  * Feature: Use timestamp from exchange for L2 book data from Coinbase
  * Bugfix: Blockchain exchange had incorrect timestamps, and incorrect log lines
  * Bugfix: Wrong datatype in BackendFuturesIndexCallback
  * Bugfix: Fix bad postgres callback for open_interest and futures_index
  * Feature: Signal handler installation now optional, can be done separately. This will allow the feedhandler to be run from child threads/loops
  * Bugfix: Fix binance delivery book ticker (message format change)
  * Breaking change: Feed object `config` renamed `subscription`
  * Feature: Configuration passed from feedhandler to exchanges
  * Breaking change: Most use of `pair` and `pairs` changed to `symbol` and `symbols` to be more consistent with actual usage. pairs.py renamed to symbols.py
  * Feature: Allow configuring the API KEY ID from Config or from environment variable
  * Bugfix: Collisions in normalized CoinGecko symbols (this adds about 700 new symbols)
  * Feature: Add candles function to coinbase
  * Feature: Explain when Cryptofeed crashes during pairs retrieval
  * Bugfix: BINANCE_DELIVERY Ticker use msg_type='bookTicker' as for the other BINANCE markets
  * Feature: Support Bitmex authentication using personal API key and secret
  * Feature: Print the origin of the configuration (filename, dict) for better developer experience
  * Bugfix: Add guard against non-supported asyncio add_signal_handler() on windows platforms
  * Feature: Simplify source code by standardization iterations over channels and symbols
  * Bugfix: Remove remaining character "*" in book_test.py
  * Bugfix: Fix return type of the function book_flatten()
  * Feature: Shutdown multiple backends asynchronously, and close the event loop properly
  * Bugfix: Repair the Bitfinex FUNDING
  * Feature: Speedup the handling of Bitfinex messages by reducing intermediate mappings
  * Feature: Support OKEx options
  * Bugfix: Cancel the pending tasks to gracefully/properly close the ASyncIO loop
  * Feature: Support for authenticated websocket data channels

### 1.6.2 (2020-12-25)
  * Feature: Support for Coingecko aggregated data per coin, to be used with a new data channel 'profile'
  * Feature: Support for Whale Alert on-chain transaction data per coin, to be used with a new data channel 'transactions'
  * Bugfix: Reset delay and retry for rest feed
  * Feature: Add GCP Pub/Sub backend
  * Bugfix: Fix aggregated callbacks (Renko and OHLCV) when used with exchanges that support order types
  * Bugfix: Fix broken example/demo code
  * Feature: New data channel - `futures_index` - demonstrated in ByBit
  * Feature: Add stop callback when exiting loop, add stop method placeholder for base callbacks
  * Bugfix: Fix NBBO callback
  * Feature: Orderbook sequence number validation for HitBTC
  * Feature: Kraken orderbook checksum support in Kraken
  * Feature: KrakenFutures sequence number check added
  * Feature: Add optional caching to postgres backend
  * Feature: New Exchange - Binance Delivery
  * Feature: Liquidation for OKEX
  * Bugfix: Adjust ping interval on websocket connection, some exchanges require pings more frequently
  * Feature: Checksum validation for orderbooks on OKEX and OKCoin
  * Feature: Use rotating log handler
  * Bugfix: Later versions of aiokafka break kafka backend
  * Bugfix: Huobi sends empty book updates for delisted pairs
  * Bugfix: Harden channel map usage in Kraken
  * Feature: Config file support
  * Bugfix: Subscribing to all BitMEX symbols gives 400 error - message too long
  * Bugfix: Cleanup of code - fixed a few examples and resolved all outstanding flake8 issues
  * Bugfix: Fix Bitfinex pair normalization
  * Feature: Refactor connection handling. New connection design allows feeds to open multiple connections
  * Feature: Update BitMax to use the new BitMax Pro API - includes sequence number verification on books
  * Feature: Bybit - support for USDT perpetual data channels
  * Feature: Can now configure more than 25 Bitfinex pair/channel combinations
  * Feature: Support more than 200 pair/stream combinations on Binance from a single Feed
  * Feature: Support for the bitFlyer exchange
  * Feature: Update Kraken to work with very large numbers of trading pairs

### 1.6.1 (2020-11-12)
  * Feature: New kwarg for exchange feed - `snapshot_interval` - used to control number of snapshot updates sent to client
  * Feature: Support for rabbitmq message routing
  * Feature: Support for raw file playback. Will be useful for testing features and building out new test suites for cryptofeed.
  * Feature: Arctic library quota can be configured, new default is unlimited
  * Feature: New exchange: Probit
  * Bugfix: Correctly store receipt timestamp in mongo backend
  * Bugfix: FTX - set a funding rate requests limit constant (10 requests per second, 60 seconds pause between loops)
  * Bugfix: Open Interest data on FTX erroneously had timestamps set to None
  * Update: Binance Jersey shutdown - feed removed
  * Bugfix: Fixed open interest channel for Binance Delivery

### 1.6.0 (2020-09-28)
  * Feature: Validate FTX book checksums (optionally enabled)
  * Bugfix: Subscribing only to open interest on Binance futures gave connection errors
  * Feature: Authentication for Influxdb 1.x
  * Feature: Override logging defaults with environment variables (filename and log level)
  * Bugfix: For Coinbase L3 books need to ignore/drop some change updates (per docs)
  * Bugfix: Obey rate limits when using Coinbase REST API to get L3 book snapshots
  * Bugfix: Ignore auction updates from Gemini
  * Feature: Add order type (limit/market) for Kraken Trades
  * Feature: Exchange specific information available via info classmethod - contains pairs, data channels and tick size
  * Feature: Funding data supported on HuobiSwap
  * Bugfix: Fix broken mongo callbacks in backends

### 1.5.1 (2020-08-26)
  * Bugfix: #136 - Kraken Rate limiting
  * Feature: Funding data on Binance Futures
  * Bugfix: Support new Huobi tradeId field, old id field deprecated
  * Bugfix: Unclear errors when unsupported data feeds used
  * Bugfix: Handle order status messages more gracefully in Coinbase
  * Bugfix: Fix Kraken pair mappings
  * Feature: New Exchange - Gate.io
  * Feature: Remove \_SWAP, \_FUTURE channel (and callback) types - determine correct type at subscribe time based on symbol
  * Docs: Add documentation about callbacks
  * Feature: Deribit provides sequence number for book updates - check them to ensure no messages lost
  * Bugfix: Fix timestamp on Binance Futures Open Interest
  * Bugfix: Update/standardize liquidation callbacks
  * Feature: Update Upbit subscription methods based on updated docs
  * Bugfix: Ticker not working correctly on Binance Futures
  * Feature: Liquidations callbacks for backends

### 1.5.0 (2020-07-31)
  * Feature: New Exchange - FTX US
  * Feature: Add funding data to rest library
  * Bugfix: DSX updated their API, websocket no longer supported. Removing DSX
  * Feature: Websocket client now uses unbounded message queue
  * Feature: Support for HuobiDM next quarter contracts
  * Bugfix: Fix datetime fields in elasticsearch
  * Feature: BinanceFutures: support ticker, open interest and Liquidation, FTX: support open interest and liquidations, Deribit: liquidations support
  * Bugfix: Fix receipt timestamps in Postgres backend
  * Bugfix: Huobi Swap Init

### 1.4.1 (2020-05-22)
  * Feature: Support for disabling timeouts on feeds
  * Bugfix: #224 Ignore newly added trading pairs in Poloniex while running
  * Feature: New exchange, DSX
  * Bugfix: Bybit updated their API, websocket subscription to L2 book data needed to be updated
  * Bugfix: Deribit subscription condensed into a single message to avoid issues with rate limit
  * Bugfix: Funding interval for bitmex not converted to integer
  * Bugfix: HuobiSwap missing from feedhandler
  * Feature: Optional flag on Feed to enable check for crossed books
  * Feature: Blockchain Exchange

### 1.3.1 (2020-03-17)
  * Feature: Add missing update detection to orderbooks in Binance
  * Feature: REST support for FTX
  * Feature: Added new field, receipt timestamp, to all callbacks. This contains the time the message was received by cryptofeed.
  * Feature: Upbit Exchange Support

### 1.3.0 (2020-02-11)
  * Bugfix: Enabling multiple symbols on Bitmex with deltas and max depth configured could cause crashes.
  * Bugfix: Default open interest callback missing
  * Change: Mongo backend stores book data in BSON
  * Feature: Open Interest callbacks added to all backends
  * Change: Instrument removed in favor of open interest
  * Bugfix: Huobi feedhandlers not properly setting forced indicator for book updates, breaking deltas
  * Bugfix: Some Kraken futures funding fields not always populated
  * Feature: Open interest updates for Kraken futures
  * Feature: Open interest updates for Deribit
  * Bugfix: FTX ticker can have Nones for bid/ask
  * Feature: InfluxDB 2.0 support
  * Bugfix: Deribit funding only available on perpetuals
  * Feature: Enable deltas (with out max depth) on exchanges that do not support them

### 1.2.0 (2020-01-18)
  * Feature: New exchange: Binance Futures
  * Feature: New Exchange: Binance Jersey
  * Feature: Funding data on Kraken Futures
  * Feature: User defined pair separator (default still -)
  * Feature: Postgres backend
  * Feature: Deribit Funding
  * Bugfix: Deribit subscriptions using config subscribed to symbols incorrectly
  * Bugfix: Some RabbitMQ messages were missing symbol and exchange data
  * Feature: Open interest data for OKEX swaps

### 1.1.0 (2019-11-14)
  * Feature: User enabled logging of exchange messages on error
  * Refactor: Overhaul of backends - new base classes and simplified code
  * Bugfix: Handle i messages from poloniex more correctly
  * Bugfix: Report bittrex errors correctly
  * Feature: New exchange: Bitcoin.com
  * Feature: New exchange: BinanceUS
  * Feature: New exchange: Bitmax
  * Feature: Ability to store raw messages from exchanges

### 1.0.1 (2019-09-30)
  * Feature: Backfill Bitmex historical trade data from S3 Bucket
  * Feature: RabbitMQ backend
  * Feature: Custom Depth and deltas for all L2 book updates
  * Feature: Support new 100ms book diff channel on Binance
  * Feature: Bittrex exchange support
  * Feature: Ticker support in Redis and Kafka Backends
  * Feature: Ticker callbacks require/contain timestamp
  * Feature: Renko Aggregation
  * Bugfix: Max Depth without deltas should only send updates when book changes
  * Bugfix: Update count and previous book now associated with pair

### 1.0.0 (2019-08-18)
  * Bugfix #113: Fix remaining exchanges who are not reporting timestamps correctly
  * Feature: Generated timestamps now based on message receipt by feedhandler
  * Feature: Multi-callback support
  * Feature: Rework ZMQ using pub/sub with topics
  * Feature: FTX Exchange
  * Feature: Gemini subscriptions now work like all other exchanges
  * Feature: Use unique id for each feed (as opposed to feed id/name)
  * Bugfix: fix Poloniex historical trade timestamps
  * Bugfix: Bitmex L2 channel incorrectly classified
  * Feature: Kraken Futures
  * Feature: Redis backend supports UDS
  * Feature: Binance full book (L2) with deltas
  * Feature: Allow user to start event loop themselves (potentially scheduling other tasks before/after).

### 0.25.0 (2019-07-06)
  * Feature: Rest Endpoints for Historical Deribit data
  * Feature: Specify numeric datatype for InfluxDB
  * Bugfix: Greatly improve performance of book writes for InfluxDB
  * Feature: Bybit exchange support
  * Bugfix: Deribit now returning floats in decimal.Decimal
  * Feature: Elastic Search backend

### 0.24.0 (2019-06-19)
  * Bugfix: Book Delta Conversion issue in backends
  * Bugfix: Tweak BitMEX rest API to handle more errors more gracefully
  * Feature: Deribit Exchange support
  * Feature: Instrument channel
  * Bugfix: support Kraken websocket API changes
  * Bugfix: correct USDT symbol mappings for Bitfinex
  * Bugfix: Fixed mongo book backend
  * Feature: Book delta support for mongo, sockets, ZMQ

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
  * Bugfix: Kraken REST API using wrong symbol for trades
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
  * Feature: Historical trade data on REST API for Kraken

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
  * README change for long description rendering issue

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
  * Bugfix: Bitfinex book timestamps match expected Bitfinex timestamps (in ms)

### 0.17.0 (2018-10-13)
  * Feature: Timestamps for orderbooks and book deltas
  * Feature #40: NBBO now uses best bid/ask from L2 books
  * Feature #28: GDAX now renamed Coinbase and uses Coinbase endpoints
  * Feature: ZeroMQ backend. Write updates directly to ZMQ connection
  * Feature: UDP Socket backend. Write updates directly to UDP socket

### 0.16.0 (2018-10-4)
  * Feature: L2 books are now all price aggregated amounts, L3 books are price aggregated orders
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
  * Feature: support for writing order books directly to Redis
  * Feature: ability to specify book depth for Redis updates

### 0.13.3 (2018-08-31)
  * Feature: normalize Bitfinex funding symbols

### 0.13.2 (2018-08-31)
  * Bugfix: fix symbol in Bitfinex rest

### 0.13.1 (2018-08-31)
  * Feature: access rest endpoints via getitem / []
  * Bugfix: #31 - funding channel broke Gemini
  * Feature: Book deltas for GDAX
  * Bugfix: Fix intervals on Bitmex (rest)

### 0.13.0 (2018-08-22)
  * Feature: Funding data from Bitmex on ws
  * Feature: Funding historical data via rest
  * Bugfix: Python 3.7 compatibility
  * Feature: Rest trade APIs are now generators
  * Feature: funding data on Bitfinex - ws and rest

### 0.12.0 (2018-08-20)
  * Bugfix: Handle 429s in Bitmex (REST)
  * Feature: Redis backend for trades to write updates directly to Redis
  * Bugfix: issue #27 - Bitmex trades missing timestamps

### 0.11.1 (2018-08-18)
  * Bitfinex and Bitmex historical trade data via REST
  * Bugfix: interval incorrect for rest time ranges
  * Bugfix: lowercase attrs in Rest interface

### 0.11.0 (2018-08-05)
  * Feature: Support for delta updates for order books
  * REST API work started

### 0.10.2
  * Bugfix: Clear data structures on reconnect in bitmex
  * Feature: Support reconnecting on more connection errors
  * Feature: Timestamp support on trade feeds
  * Feature: Connection watcher will terminate and re-open idle connections

### 0.10.1 (2018-5-11)
  * Feature: Reconnect when a connection is lost
  * Bugfix #22: Check for additional connection failures
  * Feature #4: Trade ID support
  * Feature: Account for new Gemini message type

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
