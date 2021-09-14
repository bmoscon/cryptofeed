'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os

import yaml


_default_config = {'uvloop': True, 'log': {'filename': 'feedhandler.log', 'level': 'WARNING'}}


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

    def __repr__(self) -> str:
        return super().__repr__()

    __setattr__ = __setitem__


class Config:
    def __init__(self, config=None):
        self.config = AttrDict(_default_config)
        self.log_msg = ""

        if isinstance(config, str):
            if config and os.path.exists(config):
                with open(config) as fp:
                    self.config = AttrDict(yaml.safe_load(fp))
                    self.log_msg = f'Config: use file={config!r} containing the following main keys: {", ".join(self.config.keys())}'
            else:
                self.log_msg = f'Config: no file={config!r} => default config.'
        elif isinstance(config, dict):
            self.config = AttrDict(config)
            self.log_msg = f'Config: use dict containing the following main keys: {", ".join(self.config.keys())}'
        elif isinstance(config, Config):
            self.config = AttrDict(config.config)
            self.log_msg = f'Config: using Config containing the following main keys: {", ".join(self.config.keys())}'
        elif os.environ.get('CRYPTOFEED_CONFIG') and os.path.exists(os.environ.get('CRYPTOFEED_CONFIG')):
            config = os.environ.get('CRYPTOFEED_CONFIG')
            with open(config) as fp:
                self.config = AttrDict(yaml.safe_load(fp))
                self.log_msg = f'Config: use file={config!r} from CRYPTOFEED_CONFIG containing the following main keys: {", ".join(self.config.keys())}'
        else:
            self.log_msg = f'Config: Only accept str and dict but got {type(config)!r} => default config.'

    def __bool__(self):
        return self.config != {}

    def __getattr__(self, attr):
        return self.config[attr]

    def __getitem__(self, key):
        return self.config[key]

    def __contains__(self, item):
        return item in self.config

    def __repr__(self) -> str:
        return self.config.__repr__()
