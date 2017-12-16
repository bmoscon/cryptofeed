import json
import asyncio
import websockets


sub = {
    "type": "subscribe",
    "product_ids": [
        "ETH-USD",
        "BTC-USD"
    ],
    "channels": [
        "ticker"
    ]
}

async def main():
    async with websockets.connect('wss://ws-feed.gdax.com') as websocket:
        await websocket.send(json.dumps(sub))
        await consumer_handler(websocket)

async def consumer_handler(websocket):
    async for message in websocket:
        print(message)
        print("\n\n")


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
