# FAQ and Oddities

* Why does BitMEX/Deribit not have normalized symbols / I noticed BitMEX uses XBTUSD whereas other exchanges use BTC-USD - why the difference?
  - BitMEX (and Deribit) offers futures contracts, swaps and other derivative products that are bought and sold in bitcoin, which differs from other exchanges where cryptocurrencies like bitcoin are bought in other currencies like dollars (or other cryptocurrencies). For this reason, most their symbols have no analogues on other exchanges. More information [here](https://www.bitmex.com/app/perpetualContractsGuide).

* How fast is cryptofeed/Other performance related questions/etc
  - Cryptofeed uses asyncio for concurrency. Each Feed object runs inside its own coroutine. Most of the "time" spent handling the messages from the exchanges is in the form of blocking I/O, so asyncio is very performant for this scenario. This means that everything is running in a single process/thread. A few exchanges with multiple channels and multiple symbols configured should be ok on a single process, but larger scale setups will require the creation of multiple processes. Various channels will require more or less computation time (eg. book data is very high throughput). Similarly, the backends in use, or the code handling the callbacks will also influence how many exchanges you can configure in a single process.
