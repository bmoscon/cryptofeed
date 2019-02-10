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
        self.__reset()
        client_id = 0
        for chan in self.channels:
            for pair in self.pairs:
                await websocket.send(json.dumps(
                    {
                        "sub": "market.${}.{}".format(pair, chan),
                        "id": client_id
                    }
                ))
```

This does mean we'll need to add support for the various channel mappings in `standards.py`

