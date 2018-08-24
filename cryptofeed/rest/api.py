import os

import yaml


class API:
    ID = 'NotImplemented'

    def __init__(self, config):
        path = os.path.dirname(os.path.abspath(__file__))
        self.key_id, self.key_secret = None, None
        if not config:
            config = "config.yaml"

        try:
            with open(os.path.join(path, config), 'r') as fp:
                data = yaml.load(fp)
                self.key_id = data[self.ID.lower()]['key_id']
                self.key_secret = data[self.ID.lower()]['key_secret']
        except:
            pass

    def trades(self, *args, **kwargs):
        raise NotImplementedError

    def funding(self, *args, **kwargs):
        raise NotImplementedError

    def __getitem__(self, key):
        if key == 'trades':
            return self.trades
        elif key == 'funding':
            return self.funding
