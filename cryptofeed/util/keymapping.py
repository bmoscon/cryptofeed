import json
from typing import Any, Callable

class access_route(list):
        def __init__(self, *args, **kwargs):
            super(access_route, self).__init__(args)
            
        ''' 
        Inherits all functionality of a standard phython list. Is used to differentiate from other sequence objects, 
        i.e. a Keymap will not extract data with other types as values! Therefore if a value in the Keymap is not of type access_route 
        we can assume that the value supplied is predefinded. Also increases readability of code.
        '''

class Keymap:
    '''
    Class which takes a dictionary who's values point to a sequence of type access_route. 
    The access_route can map information from a corrosponding dictionary to the supplied keys.
        
    The practical usage for which this class was created is to unify data from differing json_response formats. 
    
    For example: if we know the structure of two differing json responses for the price data of a particular stock
    on two different exchanges we can create a keymap for each exchange to extract the data in a unified manner.

        Code_example:
        
        StockExchange_1_keymap = Keymap({'ask' : access_route('request', 'price'), 'bid' : access_route('offer', 'price')})
        StockExchange_2_keymap = Keymap({'ask' : access_route('ask', 'value' ), 'bid' : access_route('bid', 'value')}) 
        
        # Call to corrosponding APIs
        
        print(json_response_stock_exchange_1) -> {'request' : {'price' : 12.14}, 'offer' : {'price' : 12:10}}
        print(json_response_stock_exchange_2) -> {'ask' : {'value' : 12.13}, 'bid' : {'value' : 12.11}}
        
        #extract unified response
        
        print(StockExchange_1_keymap(json_response_stock_exchange_1)) -> {'ask' : 12.14, 'bid' :  12.10}
        print(StockExchange_2_keymap(json_response_stock_exchange_2)) -> {'ask' : 12.13, 'bid' :  12.11}
    
    How sequences in an access_route are employed:
       
        ints and str:
            these work as simple indices or keys for dictionaries / lists.

        list and slice notation:
            The keymap is able to utilize slices, as well as list of indices, to extract data from a json response, 
            this works by applying all further keys to each individual element extracted by the slice / list of indices notation. 
            the data returned will hence be a list of values.
            
        Callables:
            A callable may be supplied to the keymap, this callable will be applied to each element in the keymap
            at the specfied location. A practical example would be to supply a function to manipulate the final value, 
            such as converting millisecond timestamps to timestamps in seconds, or rectifying inverted booleans. 

    Concerning Values that are not of type access_route:
    
        if values are not of type access route, the given value is returned, see comment @ access_route for more info. 
        
    Considerations for Future:
        1) Currently a keymap can extract required values from differing json_responses, despite this only a single key 
        may be mapped to a single value or list of values. Allowing the keymap to restructure data into nested dicts would 
        cut reliance on post_processing techniques currently employed to fully standarize a json response.
        
        2) The Keymap always retrives values packed in lists, which need post_processing attention. 
        Ideally Keymaps should be able to extract standalone types as they are. 
    '''
    
    allowed_types = (int, str, list, slice, Callable)
    
    def __init__(self, keymap : dict[Any:access_route]) -> None:
        self.keymap = keymap
        self.data = None
    
    def retrive_apriori_data(self):
        return {k : v for k, v in self.keymap.items() if not isinstance(v, access_route)}
    
    def __call__(self, data_dict):
        if isinstance(data_dict, (dict, list)):
            self.data = data_dict
        else:
            self.data = json.loads(data_dict) 
        return {key : [*self[key]] for key in self.keymap.keys()}
    
    def __getitem__(self, key):
        if isinstance(self.keymap[key], access_route):
            
            def inner(value, depth):
            
                if depth == len(self.keymap[key]):
                    yield value
                elif isinstance(self.keymap[key][depth], (int, str)):
                    yield from inner(value[self.keymap[key][depth]], depth+1)
                elif isinstance(self.keymap[key][depth], (slice, list)):
                    if isinstance(value, dict):
                        value = list(value.values())
                    if isinstance(self.keymap[key][depth], slice):
                        for val in value[self.keymap[key][depth]]:
                            yield from inner(val, depth+1)
                    else:
                        for i in self.keymap[key][depth]:
                            yield from inner(value[i], depth+1)
                elif isinstance(self.keymap[key][depth], Callable):
                    yield from inner(self.keymap[key][depth](value), depth+1) 
            
            yield from inner(self.data, 0)
        
        else:
            yield self.keymap[key]