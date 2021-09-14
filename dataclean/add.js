db = db.getSiblingDB('huobidm') 

db.BTC200925_orderbook_1597690287.update({},[{"$set": {"mid_price": {$divide:[{$add:[{$arrayElemAt:["$ask_price",0]}, {$arrayElemAt:["$bid_price",0]}]},2]}}}])

db.ETH200925_orderbook_1597690287.update({},[{"$set": {"mid_price": {$divide:[{$add:[{$arrayElemAt:["$ask_price",0]}, {$arrayElemAt:["$bid_price",0]}]},2]}}}])

db = db.getSiblingDB('bitmex') 

db.XBTUSD_orderbook_1597690287.update({},[{"$set": {"mid_price": {$divide:[{$add:[{$arrayElemAt:["$ask_price",0]}, {$arrayElemAt:["$bid_price",0]}]},2]}}}])

db.ETHUSD_orderbook_1597690287.update({},[{"$set": {"mid_price": {$divide:[{$add:[{$arrayElemAt:["$ask_price",0]}, {$arrayElemAt:["$bid_price",0]}]},2]}}}])

db.XBTUSD_fullbook_1597690287.update({},[{"$set": {"mid_price": {$divide:[{$add:[{$arrayElemAt:["$ask_price",0]}, {$arrayElemAt:["$bid_price",0]}]},2]}}}])

db.ETHUSD_fullbook_1597690287.update({},[{"$set": {"mid_price": {$divide:[{$add:[{$arrayElemAt:["$ask_price",0]}, {$arrayElemAt:["$bid_price",0]}]},2]}}}])