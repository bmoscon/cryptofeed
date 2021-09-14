from config import *
from define import *
import pymongo

client=pymongo.MongoClient(DB_URI)
db=client[HUOBIDM]
for i in range(len(PAIR[HUOBIDM])+1):
    col=db[PAIR[HUOBIDM][i]+'_'+TRADES+'_'+TS[HUOBIDM][0]]
    col.update_many({}, {'$unset':{'tick_direction':''}})
    col=db[PAIR[HUOBIDM][i]+'_'+ORDERBOOK+'_'+TS[HUOBIDM][0]]
    print(i)
    col.update_many({}, {'$unset':{'timestamp':''}})
client.close()