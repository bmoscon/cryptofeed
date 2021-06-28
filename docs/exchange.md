# Adding a new exchange

<br><br>

Perhaps the best way to understand the workings of the library is to walk through the addition of a new exchange. For this example, we'll
add support for the exchange [Huobi](https://huobi.readme.io/docs/ws-api-reference). The exchange supports websocket data, so we'll
add support for these endpoints.


## Adding a new Feed class
The first step is to define a new class, with the `Feed` class as the parent. By convention new feeds go into new modules, so the
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
This also mean we'll need to add support for the various channel mappings in `standards.py`, add support for the symbol mappings in the classmethod `_parse_symbol_data` and add the exchange import to `exchanges.py`.


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
      from cryptofeed.exchange.huobi import Huobi
      ```
    - An entry is also needed in the `EXCHANGE_MAP` to map the string `'HUOBI'` to the class `Huobi`.

## Message Handler
Now that we can subscribe to trades, we can add the message handler (which is called by the `ConnectionHandler` when messages are received on a websocket). Huobi's documentation informs us that messages sent via websocket are compressed, so we'll need to make sure we uncompress them before handling them. It also informs us that we'll need to respond to pings or be disconnected. Most websocket libraries will do this automatically, but they cannot interpret a ping correctly if the messages are compressed so we'll need to handle pings automatically. We also can see from the documentation that the feed and symbol are sent in the update so we'll need to parse those out to properly handle the message. The `message_handler` is provided with a copy of the websocket connection, `conn`, so we can use this to respond to pings.


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

Finally we'll add support for order books. There are other data feeds we could support (like `TICKER`) but for the purposes of this walk through, trades are order book are sufficient to illustrate the process for adding a new exchange.

Like we did with for the trades channel, we'll need to add a handler for the book data in the message handler, and add support for the subscription message in `standards.py`.


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
          self.l2_book[symbol] = {
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

According to the docs, for the book updates, the entire book is sent each time, so we just need to process the message in its entirety and call the `book_callback` method, defined in the parent `Feed` class. Its designed to handle the myriad of ways an update might take place, many of which Huobi does not support. Some exchanges supply only incremental updates (also called deltas), meaning a client can subscribe to a book delta, instead of getting the entire book each time. Huobi does not support this, so there is no delta processing to handle, but by convention the same method is used to process the book update.
