from config import *
from define import *
import pymongo

client=pymongo.MongoClient(DB_URI)
for item in EXCHANGE:
    db=client[item]
    for i in range(len(PAIR[item])+1):
        col=db[PAIR[item][i]+'_'+ORDERBOOK+'_'+TS[item][0]]
        col.update_many({}, {'$set':{'mid_price':}})


