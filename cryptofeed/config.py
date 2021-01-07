'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os

import yaml


_default_config = {'log': {'filename': 'feedhandler.log', 'level': 'WARNING'}}


class AttrDict(dict):
    def __init__(self, d=None):
        super().__init__()
        if d:
            for k, v in d.items():
                self.__setitem__(k, v)

    def __setitem__(self, key, value):
        if isinstance(value, dict):
            value = AttrDict(value)
        super().__setitem__(key, value)

    def __getattr__(self, item):
        return self.__getitem__(item)

    def __missing__(self, key):
        return AttrDict()

    __setattr__ = __setitem__


class Config:
    def __init__(self, config=None):
        if isinstance(config, str):
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
            if config and os.path.exists(config):
                config_file = config
            elif os.environ.get('CRYPTOFEED_CONFIG'):
                config_file = os.environ.get('CRYPTOFEED_CONFIG')

            if os.path.exists(config_file):
                with open(config_file) as fp:
                    self.config = AttrDict(yaml.safe_load(fp))
        elif isinstance(config, dict):
            self.config = AttrDict(config)
        else:
            self.config = AttrDict(_default_config)

    def __bool__(self):
        return self.config != {}

    def __getattr__(self, attr):
        return self.config[attr]

    def __getitem__(self, key):
        return self.config[key]

    def __contains__(self, item):
        return item in self.config
