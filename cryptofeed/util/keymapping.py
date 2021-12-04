from typing import Dict

class Payload:
    '''
    class which takes a dictionary as input, the values of which corrospond to a payload's specific item.
    
    this class allows for easy dynamic manipulation of a payload where successive requests with updated
    payload's are required. An example is when we wish to get historical trades on binance.
    
    for this example we may intiate a payload as such:
    
    import time
    trades_payload = Payload({
        SYMBOL : {'symbol' : 'BTC-USDT},
        START  : {'startTime' : time.time()-60*60*3}, # 3 hours in the past
        END    : {'endTime' : time.time()},
        
    })
    
    The binance docs specify that the END may not exceed 1 hour beyond the START. 
    In this case, when we pool data with successive calls, we most curtail the END
    to not overexceed 1 hour and increment the START by 1 hour. This can be easily done 
    by utilizing the __get_item__ and __set_item__ dunbar methods, as such:
    
    while True:
        trade_payload[START] = trade_payload[START] + 60*60 # increment by 1 hour
        trade_payload[END] = trade_payload[START] + 60*60 # make sure END is, at max, only 1 hour ahead
        requests.get(url=url data=trade_payload())
        
        # Data manipulation 
     
    
    
    As can be seen the the payload itself is returned by utilizing the __call__ dunbar method 
    (i.e. my_payload() will supply the actual payload)
    
    payload items may be deleted using del trade_payload[Key]
    
    payload values can be updated by my_payload[key] = some value
        ->  note: if the value supplied is of type dict the key will be overwritten
            or newly created with the value being the supplied dict as the payload item   
    '''
    
    def __init__(self, data_dict : Dict[str, dict]):
        self.payload = data_dict
        
    def __getitem__(self, key):
        return self.payload[key]
    
    def __setitem__(self, key, value):
        if isinstance(value, dict):
            self.payload[key] = value
        elif key in self.payload.keys():
            load = dict() 
            for k in reversed(self.payload[key]):
                load  = {k : load} if load else {k : value}
            self.payload[key].update(load)
        else:
            raise KeyError
    
    def __call__(self):
        payload = dict()
        for load in self.payload.values():
            payload.update(load) 
        return payload