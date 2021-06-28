## Using Callbacks

Cryptofeed is a library that uses asyncio to handle asyncronous events. When `fh.run()` is called, the main program thread of execution will block until an exception is hit or the user terminates the program (There is a slight exception to this, if `run` is called with the kwarg `start_loop=False` the feedhandler will not be started, the user can add more tasks/coroutines, and will then be responsible for starting the event loop later). Because the program is effectively blocked on the event loop, the user needs to define callbacks that will handle data from cryptofeed. Only data you register for will be delivered via these callbacks.

### Callback Types

There are two types of callbacks supported in cryptofeed, *raw* and *backend*. The raw callbacks deliver the data directly to the specified function. Backend callbacks take the data and do something else with it (typically store or send). Some examples of the backend callbacks are Redis, Postgres and TCP. You might use the Redis or Postgres callbacks to store the data, and you could use the TCP callback to send data to another application for processing.

The raw callbacks are defined [here](../cryptofeed/callback.py), along with their required arguments/kwargs. They are:

* Trade
* Ticker
* Book
* Book Update
* Open Interest
* Funding
* Liquidation
* Volume

Its important to note that if your choose to use the raw callbacks, and your user defined callbacks match these function signatures *and* are async functions, you do not need to use these wrappers (like is commonly shown in the example code). You can use your callback functions without wrapping them in `TradeCallback`, `TickerCallback`, etc.


### Backends

The backends are defined [here](../cryptofeed/backends/). Currently the following are supported:

* Arctic
* ElasticSearch
* InfluxDB
* Kafka
* MongoDB
* Postgres
* RabbitMQ
* Redis
* Redis Streams
* TCP/UDP/UDS sockets
* ZMQ

There are also a handful of wrappers defined [here](../cryptofeed/backends/aggregate.py) that can be used in conjunction with these and raw callbacks to convert data to OHLCV, throttle data, etc. 

### Performance Considerations

Do not do anything computationally intensive in your callbacks or this will greatly impact the performance of cryptofeed. Data should be quickly processed and passed along to another process/application/etc or a backend callback should be used to forward the data elsewhere. 
