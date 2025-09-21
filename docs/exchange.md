# Exchange Integration Roadmap

Cryptofeed is cleaning up legacy connectors and focusing engineering effort on
modern venues with reliable APIs. The immediate targets for 2025Q4 are:

- **Backpack** – spot and perpetual derivatives with high-frequency WebSocket
  channels (`wss://api.backpack.exchange/stream`) plus REST order entry and
  account webhooks. Public docs cover depth snapshots, incremental trades, and
  private order execution streams suitable for latency-sensitive trading.citeturn0search0
- **Hyperliquid** – on-chain perpetual venue with a unified WebSocket gateway
  for order book updates, vault statistics, and the protocol’s funding feed.
  REST endpoints expose historical candles, open interest, and account
  signature flows required for authenticated data.citeturn0search1

Implementation checklist for these connectors:

1. Map normalized channel names (TRADES, L2_BOOK, FUNDING) to the provider’s
   topic schema and document any authentication signature requirements.
2. Provide depth snapshot bootstrapping plus delta replay logic aligned with
   the exchange sequencing guarantees.
3. Capture exchange-specific metadata (e.g., Backpack’s `sequence` field or
   Hyperliquid’s `crossSequence`) so downstream storage backends can reason
   about ordering.

Contributors interested in these venues can find acceptance criteria and
tracking issues in this document. The historical walkthrough below (based on
Huobi) is retained for reference, but new connectors should follow the roadmap
above and prefer the latest standards helpers.

### ccxt / ccxt.pro integration

To broaden data coverage for long-tail venues, we are drafting an adapter that
wraps [`ccxt`](https://github.com/ccxt/ccxt) for REST polling and
[`ccxt.pro`](https://github.com/ccxt/ccxt.pro) for WebSocket streaming. The goal
is to expose a generic `CcxtFeed` that translates Cryptofeed’s normalized
channels into ccxt market calls while respecting our engineering principles:

1. **SOLID/KISS** – isolate ccxt-specific concerns inside a thin transport
   layer so existing callbacks/backends remain unchanged.
2. **DRY** – reuse ccxt’s market metadata to seed symbol maps, throttling, and
   authentication flows.
3. **YAGNI** – start with trades and L2 book snapshots before adding more exotic
   channels.

We expect this adapter to unlock coverage for exchanges like Backpack (until a
native connector lands), smaller spot brokers, and regional venues. Contributors
interested in the ccxt path should coordinate in `docs/exchange.md` to avoid
duplication.

#### Example: Binance via ccxt/ccxt.pro

```python
import asyncio
import ccxt.async_support as ccxt_async
import ccxt.pro as ccxt_pro

async def snapshot(symbol: str = "BTC/USDT") -> dict:
    client = ccxt_async.binance()
    try:
        await client.load_markets()
        return await client.fetch_order_book(symbol, limit=5)
    finally:
        await client.close()

async def stream_trades(symbol: str = "BTC/USDT") -> list:
    exchange = ccxt_pro.binance()
    try:
        return await exchange.watch_trades(symbol)
    finally:
        await exchange.close()

async def main():
    book = await snapshot()
    trades = await stream_trades()
    print("top bid", book["bids"][0], "last trade", trades[-1])

asyncio.run(main())
```

Architectural notes:

- Wrap the async REST client in a thin adapter that exposes the snapshot API
  expected by `Feed._reset` when bootstrapping order books.
- Use ccxt.pro streams to bridge into Cryptofeed’s polling loop; map incoming
  trades/order books into normalized dataclasses before dispatching to
  callbacks.
- ccxt relies on exchange REST endpoints for market metadata and may enforce
  *regional restrictions*. During testing the public Binance endpoint returned
  `ExchangeNotAvailable` (HTTP 451) when accessed from a restricted IP. The
  adapter should surface such errors clearly and allow users to route through
  permitted endpoints (e.g., Binance US). We were unable to capture a live
  snapshot because of this restriction.

### MVP specification for `CcxtFeed`

The MVP targets Binance because ccxt/ccxt.pro expose both REST order books and
streaming trades for it. Once stable, the adapter can be extended to other
venues supported by ccxt.

#### Goals

1. Provide a drop-in `CcxtFeed` that follows the existing `Feed` interface and
   emits normalized trades and L2 snapshots/deltas via existing callbacks.
2. Reuse ccxt metadata to populate symbol maps, precision, throttling limits,
   and authentication requirements.
3. Keep the implementation SOLID/KISS by isolating third-party dependencies in
   a transport/adaptor layer while reusing Cryptofeed’s queueing, metrics, and
   backpressure infrastructure.

#### Scope

- **In scope:**
  - Public market data (`TRADES`, `L2_BOOK`) for `BTC/USDT` and `ETH/USDT`.
  - REST snapshot bootstrapping (`fetch_order_book`) with snapshot interval
    controls to limit rate usage.
  - WebSocket streaming through `watch_trades` and `watch_order_book`.
  - Optional REST polling fallback when WebSocket faces region restrictions.
- **Out of scope (for MVP):**
  - Authenticated/user data, derivatives account channels.
  - Market-level funding/interest feeds (can piggyback on Hyperliquid work).
  - Resilience to exchange-specific quirks beyond retry/backoff wrappers.

#### Architecture

```
CcxtFeed
 ├─ CcxtMetadataCache  -> wraps ccxt.binance().load_markets()
 ├─ CcxtRestTransport  -> ccxt.async_support.binance()
 │     • fetch_order_book() → L2 snapshot
 └─ CcxtWsTransport    -> ccxt.pro.binance()
       • watch_trades(), watch_order_book()
```

- The feed schedules periodic snapshots via `CcxtRestTransport` and forwards
  data through `CcxtEmitter` in the same way native connectors call `_emit`.
- `CcxtWsTransport` pushes updates into the existing `BackendQueue` so metrics
  and retry logic are reused verbatim.
- Both transports must translate ccxt symbols (`BTC/USDT`) to the normalized
  form (`BTC-USDT`) using `ccxt.safe_symbol` and metadata caches.

#### Configuration

```yaml
exchanges:
  ccxt_binance:
    class: CcxtFeed
    exchange: binance
    symbols: ["BTC-USDT", "ETH-USDT"]
    channels: [TRADES, L2_BOOK]
    snapshot_interval: 30  # seconds between REST bootstraps
    websocket: true        # disable when region blocked
    rest_only: false
```

#### Error handling & throttling

- Handle `ExchangeNotAvailable`/HTTP 451 by surfacing actionable error messages
  and allowing configuration of alternative endpoints (e.g., `binanceus`).
- Respect ccxt’s `rateLimit` metadata and backoff when encountering 429/418.
- Provide a toggle to fall back to REST polling when WebSocket fails repeatedly
  (useful for region-blocked deployments).

#### Testing strategy

1. **Unit tests** – mock ccxt transports to ensure symbol mapping, queue
   integration, and error surfacing behave identically to native connectors.
2. **Integration smoke** – run against Binance (or Binance US) from an allowed
   region; verify trades and L2 books populate callbacks/backends.
3. **Regression harness** – add ccxt-based feed to the docker-compose
   integration to ensure future changes don’t break the adapter when ccxt
   updates.

#### Rollout

1. Land the MVP behind a feature flag (`use_ccxt=True`) so existing deployments
   are unaffected.
2. Gather feedback from users needing long-tail markets; extend coverage to
   other ccxt exchanges in priority order.
3. Once multiple venues are verified, document best practices (e.g., handling
   API keys, region-specific hosts) and promote the adapter to the “active” list
   in the README.


# Adding a new exchange (legacy Huobi walkthrough)

<br><br>

Perhaps the best way to understand the workings of the library is to walk through the addition of a new exchange. For this example, we'll
add support for the exchange [Huobi](https://huobi.readme.io/docs/ws-api-reference). The exchange supports websocket data, so we'll
add support for these endpoints.


## Adding a new Feed class
The first step is to define a new class, with the `Feed` class as the parent. By convention, new feeds go into new modules, so the
class definition will go in the `huobi` module within `cryptofeed.exchange`.

```python
import logging

from cryptofeed.feed import Feed
from cryptofeed.defines import HUOBI


LOG = logging.getLogger('feedhandler')


class Huobi(Feed):
    id = HUOBI

    def __init__(self, **kwargs):
        super().__init__('wss://api.huobi.pro/hbus/ws', **kwargs)
        self.__reset()

    def __reset(self):
        pass

    async def subscribe(self, websocket):
        self.__reset()
```

We've basically just extended `Feed`, populated the websocket address in the parent's constructor call, and defined the `__reset` and `subscribe` methods; we may or may not need `__reset` (more on this later). `subscribe` is called every time a connection is made to the exchange - typically just when the feedhandler starts, and again if the connection is interrupted and has to be reestablished. You might notice that `HUOBI` is being imported from `defines`, so we'll need to add that as well:

```python
HUOBI = 'HUOBI'
```

Again by convention the exchange names in `defines.py` are all uppercase.

## Subscribing
Cryptofeed accepts standardized names for data channels/feeds. The `Feed` parent class will convert these to the exchange specific versions for use when subscribing. Per the exchange docs, each subscription to the various data channels must be made with a new subscription message, so for this exchange we can subscribe like so:

```python
async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        client_id = 0
        for chan, symbols in self.subscription.items():
            for symbol in symbols:
                client_id += 1
                await conn.write(json.dumps(
                    {
                        "sub": f"market.{symbol}.{chan}",
                        "id": client_id
                    }
                ))
```
When a client specifies a `Feed` object, they provide channels and symbols, or use a subscription dictionary. These are saved internally in the class as `self.subscription`. The keys to the dictionary are data channels, and the value for each channel is a list of symbols. The user specifies these values as the cryptofeed defined normalizations, and the `Feed` constructor converts them in place to the exchange specific values.
This also means we'll need to add support for the various channel mappings in `standards.py`, add support for the symbol mappings in the classmethod `_parse_symbol_data` and add the exchange import to `exchanges.py`.


* `standards.py`
    - ```python
        _feed_to_exchange_map = {
            ...
            TRADES: {
                ...
                HUOBI: 'trade.detail'
            },
        ```

* the symbol mapping
    - Per the documentation we can get a list of symbols from their REST api via `GET /v1/common/symbols`
    - We need to define a class variable, `symbol_endpoint` and set it to the API endpoint
      ```python
      `symbol_endpoint = 'https://poloniex.com/public?command=returnTicker'
      ```
      
      We can then define the parser. The feed class will handle calling the API and will call this class method with the data from the REST endpoint.

      ```python
         @classmethod
         def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
            ret = {}
            for e in data['data']:
                if e['state'] == 'offline':
                    continue
                normalized = f"{e['base-currency'].upper()}{symbol_separator}{e['quote-currency'].upper()}"
                symbol = f"{e['base-currency']}{e['quote-currency']}"
                ret[normalized] = symbol
            return ret, {}
      ```
      The classmethod needs to return the symbol mapping as well as an info dictionary (if applicable). The info dict should have the tick size, if provided by the exchange. The symbol mapping is in the format normalized symbol -> exchange symbol 

* `exchanges.py`
    - ```python
      from cryptofeed.exchanges.huobi import Huobi
      ```
    - An entry is also needed in the `EXCHANGE_MAP` to map the string `'HUOBI'` to the class `Huobi`.

## Message Handler
Now that we can subscribe to trades, we can add the message handler (which is called by the `ConnectionHandler` when messages are received on a websocket). Huobi's documentation informs us that messages sent via websocket are compressed, so we'll need to make sure we uncompress them before handling them. It also informs us that we'll need to respond to pings or be disconnected. Most websocket libraries will do this automatically, but they cannot interpret a ping correctly if the messages are compressed, so we'll need to handle pings automatically. We also can see from the documentation that the feed and symbol are sent in the update, so we'll need to parse those out to properly handle the message. The `message_handler` is provided with a copy of the websocket connection, `conn`, so we can use this to respond to pings.


```python
async def _trade(self, msg):
        """
        {
            'ch': 'market.btcusd.trade.detail',
            'ts': 1549773923965,
            'tick': {
                'id': 100065340982,
                'ts': 1549757127140,
                'data': [{'id': '10006534098224147003732', 'amount': Decimal('0.0777'), 'price': Decimal('3669.69'), 'direction': 'buy', 'ts': 1549757127140}]}}
        """
        for trade in msg['tick']['data']:
            await self.callback(TRADES,
                feed=self.id,
                symbol=self.exchange_symbol_to_std_symbol(msg['ch'].split('.')[1]),
                order_id=trade['id'],
                side=BUY if trade['direction'] == 'buy' else SELL,
                amount=Decimal(trade['amount']),
                price=Decimal(trade['price']),
                timestamp=trade['ts']
            )

    async def message_handler(self, msg, conn, timestamp):
        # unzip message
        msg = zlib.decompress(msg, 16+zlib.MAX_WBITS)
        msg = json.loads(msg, parse_float=Decimal)

        # Huobi sends a ping evert 5 seconds and will disconnect us if we do not respond to it
        if 'ping' in msg:
            await conn.write(json.dumps({'pong': msg['ping']}))
        elif 'status' in msg and msg['status'] == 'ok':
            return
        elif 'ch' in msg:
            if 'trade' in msg['ch']:
                await self._trade(msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)
```

The actual trade handler, `_trade`, simply parses out the relevant data and invokes the callback to deliver the update to the client.

## Order Book Support

Finally, we'll add support for order books. There are other data feeds we could support (like `TICKER`) but for the purposes of this walk through, trades are order book are sufficient to illustrate the process for adding a new exchange.

Like we did with the trades channel, we'll need to add a handler for the book data in the message handler, and add support for the subscription message in `standards.py`.


* `standards.py`
  - ```python
      _feed_to_exchange_map = {
        L2_BOOK: {
            ...
            HUOBI: 'depth.step0'
    ```
* `huobi.py`
  - `message_handler`
  - ```python
      elif 'ch' in msg:
          ....
          elif 'depth' in msg['ch']:
              await self._book(msg)
    ```
  - `_book`
  - ```python
      async def _book(self, msg):
          symbol = self.exchange_symbol_to_std_symbol(msg['ch'].split('.')[1])
          data = msg['tick']
          self._l2_book[symbol] = {
              BID: sd({
                  Decimal(price): Decimal(amount)
                  for price, amount in data['bids']
              }),
              ASK: sd({
                  Decimal(price): Decimal(amount)
                  for price, amount in data['asks']
              })
          }

          await self.book_callback(symbol, L2_BOOK, False, False, msg['ts'])
    ```

According to the docs, for the book updates, the entire book is sent each time, so we just need to process the message in its entirety and call the `book_callback` method, defined in the parent `Feed` class. It's designed to handle the myriad of ways an update might take place, many of which Huobi does not support. Some exchanges supply only incremental updates (also called deltas), meaning a client can subscribe to a book delta, instead of getting the entire book each time. Huobi does not support this, so there is no delta processing to handle, but by convention the same method is used to process the book update.
