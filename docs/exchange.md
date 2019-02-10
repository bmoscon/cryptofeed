# Adding a new exchange

Perhaps the best way to understand the workings of the library is to walk through the addition of a new exchange. For this example, we'll 
add support for the exchange [Huobi](https://huobi.readme.io/docs/ws-api-reference). The exchange supports websocket data, so we'll 
add support for these endopoints.


### Adding a new Feed class
The first step is to define a new class, with the Feed class as the parent. By convention new feeds go into new modules, so the 
class definition will go in the `huobi` module within `cryptofeed`. 

```python
import logging

from cryptofeed.feed import Feed
from cryptofeed.defines import HUOBI


LOG = logging.getLogger('feedhandler')


class Huobi(Feed):
    id = HUOBI

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://api.huobi.pro/hbus/ws', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.__reset()

    def __reset(self):
        pass
    
    async def subscribe(self, websocket):
        self.__reset()

```

We've basically just extended Feed, populated the websocket address in the parent's constructor call, and defined the `__reset` and `subscribe` methods; we may or may not need `__reset` (more on this later). `subscribe` is called every time a connection is made to the exchange - typically just when the feedhandler starts, and again if the connection is interrupted and has to be reestablished. You might notice that `HUOBI` is being imported from `defines`, so we'll need to add that as well:

```python
HUOBI = 'HUOBI'
```

Again by convention the exchange names in `defines.py` are all uppercase.

### Subscribing
Cryptofeed accepts standarized names for data channels/feeds. The `Feed` parent class will convert these to the exchange specific versions for use when subscribing. Per the exchange docs, each subscription to the various data channels must be made with a new subscription message, so for this exchange we can subscribe like so:


```python
async def subscribe(self, websocket):
        self.websocket = websocket
        self.__reset()
        client_id = 0
        for chan in self.channels:
            for pair in self.pairs:
                client_id += 1
                await websocket.send(json.dumps(
                    {
                        "sub": "market.{}.{}".format(pair, chan),
                        "id": client_id
                    }
                ))
```
We also save the websocket connection to a private data member of the class so we can use it in the message handler to respond to pings (more on this later, this is specific to this exchange).
This also mean we'll need to add support for the various channel mappings in `standards.py`, add support for the pair mappings in `pairs.py` and add the exchange import to `exchanges.py`. 


* `standards.py`
    - ```python
        _feed_to_exchange_map = {
            ...
            TRADES: {
                ...
                HUOBI: 'trade.detail'
            },
        ```

* `pairs.py`
    - Per the documentation we can get a list of symbols from their REST api via `GET /v1/common/symbols`
    - ```python
      def huobi_pairs():
            r = requests.get('https://api.huobi.com/v1/common/symbols').json()
            return {'{}-{}'.format(e['base-currency'].upper(), e['quote-currency'].upper()) : '{}{}'.format(e['base-currency'], e['quote-currency']) for e in r['data']}


      _exchange_function_map = {
           ...
           HUOBI: huobi_pairs
        }
      ```
* `exchanges.py`
    - ```python
      from cryptofeed.huobi.huobi import Huobi
      ```

### Message Handler
Now that we can subscribe to trades, we can add the message handler (which is called by the feedhandler when messages are received on ther websocket). Huobi's documentation informs us that messages sent via websocket are compressed, so we'll need to make sure we uncompress them before handling them. It also informs us that we'll need to respond to pings or be disconnected. Most websocket libraries will do this automatically, but they cannot intepret a ping correctly if the messages are compressed so we'll need to handle pings automatically. We also can see from the documentation that the feed and pair are sent in the update so we'll need to parse those out to properly handle the message. 


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
            await self.callbacks[TRADES](
                feed=self.id,
                pair=pair_exchange_to_std(msg['ch'].split('.')[1]),
                order_id=trade['id'],
                side=BUY if trade['direction'] == 'buy' else SELL,
                amount=Decimal(trade['amount']),
                price=Decimal(trade['price']),
                timestamp=trade['ts']
            )

    async def message_handler(self, msg):
        # unzip message
        msg = zlib.decompress(msg, 16+zlib.MAX_WBITS)
        msg = json.loads(msg, parse_float=Decimal)
        
        # Huobi sends a ping evert 5 seconds and will disconnect us if we do not respond to it
        if 'ping' in msg:
            await self.websocket.send(json.dumps({'pong': msg['ping']}))
        elif 'status' in msg and msg['status'] == 'ok':
            return
        elif 'ch' in msg:
            if 'trade' in msg['ch']:
                await self._trade(msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)
```

The actual trade handler, `_trade`, simply parses out the relevant data and invokes the callback to deliver the update to the client. 

### Order Book Support

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
          pair = pair_exchange_to_std(msg['ch'].split('.')[1])
          data = msg['tick']
          self.l2_book[pair] = {
              BID: sd({
                  Decimal(price): Decimal(amount)
                  for price, amount in data['bids']
              }),
              ASK: sd({
                  Decimal(price): Decimal(amount)
                  for price, amount in data['asks']
              })
          }

          await self.book_callback(pair, L2_BOOK, False, False, msg['ts'])
    ```
   
According to the docs, for the book updates, the entire book is sent each time, so we just need to process the message in its entirety and call the `book_callback` method, defined in the parent `Feed` class. Its designed to handle the myriad of ways an update might take place, many of which Huobi does not support. Some exchanges supply only incremental updates (also called deltas), meaning a client can subscribe to a book delta, instead of getting the entire book each time. Huobi does not support this, so there is no delta processing to handle, but by convention the same method is used to process the book update. 
