
## Performance Considerations

Cryptofeed uses asyncio to optimize performance in a single threaded environment. Asyncio is able to "multitask" while tasks are blocked on I/O operations. While reading data from an exchange (or waiting to read data), and while writing data (via the backends), other tasks can execute. CPU intensive tasks, like parsing messages, will block other operations. Each Feed object runs inside its own asyncio `task`. A few exchanges with multiple channels and multiple symbols configured should be ok on a single process, but larger scale setups will require the creation of multiple processes. Various channels will require more or less computation time (eg. book data is very high throughput). Similarly, the backends in use, or the code handling the callbacks will also influence how many exchanges you can configure in a single process. What follows is a rough guide of things to consider when using Cryptofeed.


In general, these performance considerations only apply when dealing with book data. Other data channels are low volume (relatively) and are unlikely to suffer from latency/performance issues.


* Book channels are typically very message intensive. If subscribing to book data with many symbols consider breaking those up into multiple calls to `add_feed`. Each call to `add_Feed` creates at least one new asyncio `task`.
* There is a limit to how much data can be processed on a single process. If your needs are great (book data for 100s of symbols) you will need to multiprocess.
* Enforcing a `max_depth` on a book increases processing time.
* Using deltas on exchanges that do not support it (eg. Huobi) increases processing time.
* Handling callbacks increases latency. Callbacks should be as lightweight as possible, and use asyncio if possible/applicable.
