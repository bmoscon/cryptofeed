'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os

import yaml


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
        try:
            return self.__getitem__(item)
        except KeyError:
            raise AttributeError(item)

    __setattr__ = __setitem__


class Config:
    def __init__(self, file_name=None):
        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
        if file_name and os.path.exists(file_name):
            config_file = file_name
        elif os.environ.get('CRYPTOFEED_CONFIG'):
            config_file = os.environ.get('CRYPTOFEED_CONFIG')

        if os.path.exists(config_file):
            with open(config_file) as fp:
                self.config = AttrDict(yaml.safe_load(fp))
        else:
            self.config = AttrDict()

    def __bool__(self):
        return self.config != {}

    def __getattr__(self, attr):
        return self.config[attr]

    def __contains__(self, item):
        return item in self.config
