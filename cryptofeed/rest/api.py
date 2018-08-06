import yaml


class API:
    ID = 'NotImplemented'

    def __init__(self, config):
        self.key_id, self.key_secret = None, None
        if not config:
            config = "config.yaml"
        
        try:
            with open(config, 'r') as fp:
                data = yaml.load(fp)
                self.key_id = data[self.ID]['key_id']
                self.key_secret = data[self.ID]['key_secret']
        except:
            pass