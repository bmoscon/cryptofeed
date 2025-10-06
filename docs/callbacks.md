## Using Callbacks

Cryptofeed is a library that uses asyncio to handle asynchronous events. When `fh.run()` is called, the main program thread of execution will block until an exception is hit or the user terminates the program (There is a slight exception to this, if `run` is called with the kwarg `start_loop=False` the feedhandler will not be started, the user can add more tasks/coroutines, and will then be responsible for starting the event loop later). Because the program is effectively blocked on the event loop, the user needs to define callbacks that will handle data from cryptofeed. Only data you register for will be delivered via these callbacks.

### Callback Types

There are two types of callbacks supported in cryptofeed, *raw* and *backend*. The raw callbacks deliver the data directly to the specified function. Backend callbacks take the data and do something else with it (typically store or send). Some examples of the backend callbacks are Redis, Postgres and TCP. You might use the Redis or Postgres callbacks to store the data, and you could use the TCP callback to send data to another application for processing.

The raw callbacks are defined [here](../cryptofeed/callback.py). They are:

* Trade
* Ticker
* Book
* Open Interest
* Funding
* Liquidation
* Candles
* Index
* L1Book (aka Top of Book)
* Order Info
* User Fills
* Transactions
* Balances

It's important to note that if your choose to use the raw callbacks and your callbacks are async functions, you do not need to use these wrappers (like is commonly shown in the example code). You can use your callback functions without wrapping them in `TradeCallback`, `TickerCallback`, etc.

Every callback has the same signature, two positional arguments, the data object and the receipt timestamp. The data object differs by data type. The data objects are defined in [types.pyx](../cryptofeed/types.pyx)


### Backends

The backends are defined [here](../cryptofeed/backends/).

#### Actively supported destinations

* Kafka
* Postgres
* QuestDB
* RabbitMQ
* Redis / Redis Streams
* TCP / UDP / UDS sockets
* VictoriaMetrics

#### Legacy / community-maintained targets

The following adapters remain in-tree for backwards compatibility but are no longer
part of the release test matrix:

* Arctic
* ElasticSearch
* GCP Pub/Sub
* InfluxDB
* MongoDB
* ZMQ

#### Upcoming storage integrations

We are actively drafting specs and proof-of-concept adapters for the next wave of
streaming and analytics backends:

- GreptimeDB – distributed, columnar time-series database with SQL/PromQL
  compatibility; ideal for storing high-cardinality trade and metrics data.citeturn0search2
- RisingWave – cloud-native streaming database that speaks PostgreSQL wire
  protocol, enabling windowed aggregations directly on order flow.citeturn0search3
- Apache Iceberg – table format for large-scale analytic lakes; plan to stream
  data into Iceberg tables via object storage writers and metadata commits.citeturn0search4
- NATS JetStream – lightweight, horizontally scalable streaming log suitable
  for fan-out distribution and durable replay workloads.citeturn0search5
- InfluxDB3 – next-generation time-series/analytics stack with SQL and Apache
  Arrow support, providing a unified write path for metrics and events.citeturn0search6

There are also a handful of wrappers defined [here](../cryptofeed/backends/aggregate.py) that can be used in conjunction with these and raw callbacks to convert data to OHLCV, throttle data, etc. 

### Performance Considerations

Do not do anything computationally intensive in your callbacks, or this will greatly impact the performance of cryptofeed. Data should be quickly processed and passed along to another process/application/etc or a backend callback should be used to forward the data elsewhere. If possible, use async libraries in your callbacks!
