import json
import asyncio
import websockets
from collections import deque


sub = {
    "type": "subscribe",
    "product_ids": [
        #"ETH-USD",
        "BTC-USD"
    ],
    "channels": [
        #"level2",
        #"ticker",
        "full"
    ]
}

handlers = {}
seq_window = 10
seq = deque([], seq_window)


def register_handler(msg_type, callback):
    handlers[msg_type] = callback

def ticker_handler(message):
    print(message['sequence'])

def full_handler(message):
    if 'sequence' in message:
        print(message['sequence'])


def check_sequence(msg):
    seq.append(msg['sequence'])
    if len(seq) == 10:
        expected = seq[0] + seq_window - 1
        if expected == seq[-1]:
            print('none missing')
        else:
            print('missing')
            print(seq)
        last = seq[-1]
        seq.clear()
        seq.append(last)

async def main():
    async with websockets.connect('wss://ws-feed.gdax.com') as websocket:
        await websocket.send(json.dumps(sub))
        await consumer_handler(websocket)

async def consumer_handler(websocket):
    async for message in websocket:
        msg = json.loads(message)
        if 'sequence' in msg:
            check_sequence(msg)
        #print(msg)
        #if msg['type'] in handlers:
        #    handlers[msg['type']](msg)
        handlers['full'](msg)

if __name__ == '__main__':
    register_handler('ticker', ticker_handler)
    register_handler('full', full_handler)
    asyncio.get_event_loop().run_until_complete(main())
