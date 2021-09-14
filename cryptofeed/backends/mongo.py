
'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com
'''

import bson
import motor.motor_tornado


from cryptofeed.backends.backend import BackendBookCallback, BackendCallback

from config import ORDERBOOK_DEPTH
from numpy import isnan, NaN




class MongoCallback:
    def __init__(self, db, uri='mongodb://127.0.0.1:27017', key=None, numeric_type=float, **kwargs):
        self.conn = motor.motor_tornado.MotorClient(uri)
        self.db = self.conn[db]
        self.numeric_type = numeric_type
        self.collection = key if key else self.default_key
        self.gap=0.1
        self.just={}
        self.origin=self.collection.split('_')[-1]
        self.lastob={}
        self.lastloc={}
        self.start={}

    async def write(self, data: dict):
        if 'delta' in data:
            d = {'exchange': data['exchange'], 'symbol': data['symbol'], 'timestamp': data['timestamp'], 'receipt_timestamp': data['receipt_timestamp'], 'delta': data['delta'], 'bid': bson.BSON.encode(data['bid']), 'ask': bson.BSON.encode(data['ask'])}
            await self.db[self.collection].insert_one(d)
        else:
            await self.db[self.collection].insert_one(data)


class TradeMongo(MongoCallback, BackendCallback):
    default_key = 'trades'

    async def write(self, pair: str, timestamp: float, receipt_timestamp: float, data: dict):
        loc = {'_id': timestamp}
        d = {'_id': timestamp, 'receipt_timestamp': receipt_timestamp, 'size': data['amount'], 'price': data['price'], 'side': True if data['side'] == "sell" else False}
        if 'tick_direction' in data.keys() and data['side'] != data['tick_direction']:
            d['tick_direction'] = data['tick_direction'], 
        await self.db[pair + '_' + self.collection].update_one(loc, {'$set': d}, upsert = True)


class FundingMongo(MongoCallback, BackendCallback):
    default_key = 'funding'


class BookMongo(MongoCallback, BackendBookCallback):
#Orderbook in dictionary form. Look up BackendBookCallback (in backend.py) for more information.
    default_key = 'book'
    async def write(self, pair: str, timestamp: float, receipt_timestamp: float, data: dict):
        loc = {'_id': timestamp}
        insert = {'receipt_timestamp': receipt_timestamp}
        price = {'ask': [], 'bid': []}
        size = {'ask': [], 'bid': []}
        name = {'ask':['ask_price', 'ask_size'], 'bid': ['bid_price', 'bid_size']}
        for side in ['bid', 'ask']:
            if len(data[side]) != 0:
                depth = min(len(data[side]), ORDERBOOK_DEPTH)
                for d in list(data[side].keys())[0:depth]:
                    price[side].append(float(d))
                    if data[side][d] is not None:
                        size[side].append(data[side][d])
                    else:
                        size[side].append(0)
                insert[name[side][0]] = price[side] 
                insert[name[side][1]] = size[side]
        insert['mid_price'] = (price['ask'][0]+price['bid'][0])/2
        if isnan(data['timestamp']):
            insert['timestamp'] = NaN
            await self.db[pair + '_' + self.collection].insert_one(insert)
        else:
            await self.db[pair + '_' + self.collection].update_one(loc, {'$set': insert}, upsert = True)



class BookDeltaMongo(MongoCallback, BackendBookCallback):
    default_key = 'bookdelta'
    async def write(self, pair:str, timestamp: float, receipt_timestamp: float, forced:bool, book: dict, delta: dict):
        self.gap=3600
        loc = {'_id': timestamp}
        insert = {'_id': timestamp, 'receipt_timestamp': receipt_timestamp}
        if forced or (timestamp//self.gap-self.just[pair]>0.5):
        # save snapshot
            insert1=insert.copy()
            price = {'ask': [], 'bid': []}
            size = {'ask': [], 'bid': []}
            name = {'ask':['ask_price', 'ask_size'], 'bid': ['bid_price', 'bid_size']}
            for side in ['bid', 'ask']:
                if len(book[side]) != 0:
                    price[side]=[float(i) for i in list(book[side].keys())]
                    size[side]=[0 if i is None else float(i)  for i in list(book[side].values())]
                insert1[name[side][0]] = price[side] 
                insert1[name[side][1]] = size[side]
            insert1['mid_price'] = (price['ask'][0]+price['bid'][0])/2
            self.just[pair]=(timestamp+ 0.0001)//self.gap
            await self.db[pair + '_' + 'FB1hsnapshot_'+self.origin].update_one(loc, {'$set': insert1}, upsert = True)    
        if delta is not None:
            price = {'ask': [], 'bid': []}
            size = {'ask': [], 'bid': []}
            name = {'ask':['ask_price', 'ask_size'], 'bid': ['bid_price', 'bid_size']}
            for side in ['bid', 'ask']:
                if len(delta[side]) != 0:
                    price[side]=list(delta[side].keys())
                    size[side]=[0 if i is None else i  for i in list(delta[side].values())]
                insert[name[side][0]] = price[side] 
                insert[name[side][1]] = size[side]
            await self.db[pair + '_' + self.collection].update_one(loc, {'$set': insert}, upsert = True)
   

class TickerMongo(MongoCallback, BackendCallback):
    default_key = 'ticker'
    async def write(self, pair: str, timestamp: float, receipt_timestamp: float, data: dict):
        loc = {'_id': timestamp}
        d = {
            '_id': timestamp,
            'receipt_timestamp': receipt_timestamp,
            'bid': data['bid'],  
            'bid_size': data['bid_size'],
            'ask': data['ask'],
            'ask_size': data['ask_size'],
            'mid_price': (float(data['bid']) + float(data['ask'])) / 2
        }
        await self.db[pair + '_' + self.collection].update_one(loc, {'$set': d}, upsert =True)


class OpenInterestMongo(MongoCallback, BackendCallback):
    default_key = 'open_interest'


class LiquidationsMongo(MongoCallback, BackendCallback):
    default_key = 'liquidations'


    
class OrderbookMongo(MongoCallback,BackendBookCallback):
    default_key = 'orderbook'
    async def write(self, pair: str, timestamp: float, receipt_timestamp: float, data: dict):
        loc = {'_id': timestamp}
        insert = {'_id': timestamp, 'receipt_timestamp': receipt_timestamp}
        price = {'ask': [], 'bid': []}
        size = {'ask': [], 'bid': []}
        name = {'ask':['ask_price', 'ask_size'], 'bid': ['bid_price', 'bid_size']}
        for side in ['bid', 'ask']:
            if len(data[side]) != 0:
                for d in data[side]:
                    price[side].append(float(d[0]))
                    if d[1] is not None:
                        size[side].append(d[1])
                    else:
                        size[side].append(0)
                insert[name[side][0]] = price[side] 
                insert[name[side][1]] = size[side]
        insert['mid_price'] = (price['ask'][0]+price['bid'][0])/2

        if  pair in self.start:
            if timestamp//self.gap-self.just[pair] >0.5 :
                self.lastob[pair]['receipt_timestamp']=round((self.just[pair]+1)*self.gap,1)
                self.just[pair]=(timestamp+ 0.00001)//self.gap

                await self.db[pair + '_' + 'OBsnapshot_'+self.origin].update_one(self.lastloc[pair], {'$set': self.lastob[pair]}, upsert = True)
        else:
            self.start[pair]=True
            self.just[pair]=(timestamp+ 0.00001)//self.gap
        
        self.lastob[pair]=insert
        self.lastloc[pair]=loc

        await self.db[pair + '_' + self.collection].update_one(loc, {'$set': insert}, upsert = True)


class CandlesMongo(MongoCallback, BackendCallback):
    default_key = 'candles'
