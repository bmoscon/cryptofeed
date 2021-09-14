## Configuring Cryptofeed

Configuration is specified during the creation of the feedhandler object, via the `config` kwarg. It defaults to `None`. Currently the following options exist for specifying a configuration to the feedhandler.

* Specifying nothing
  - If config is left as None, the defaults in `config.py` will be used
* Specifying a dictionary
  - A dictionary can be directly provided, as long as the keys match the expected setting options (see below under Settings).
* Specifying a path to a config file
  - A yaml file can be loaded, provided it has entries in it that match the expected settings (see below under Settings)
* An env var
  - An environment variable can be specified to point to the configuration. if `CRYPTOFEED_CONFIG` is set, the value in this env var is used as a path to a config file. It is assumed the path is an absolute path and that it also contains the file name.

The configuration will be automatically passed to exchange objects that the feed handler directly creates (feeds that are specified by string/name). Exchange objects created by the user will need to have the config passed as well (via the Feed object `config` kwarg), or the same defaulting rules mentioned above will apply

### Settings

The following are valid settings for the configuration of Cryptofeed.


* log
  - logging settings. Valid entries are `filename` and `level` (corresponding to log filename and level).
* uvloop
  - default is True. This boolean can enable or disable uvloop support.
* exchange config. 
  - A lowercase exchange name. Valid entries here will vary by exchange, but normally will contain `key_id` and `key_secret`. For exchanges that use different, or more, secrets, those entries will be here as well.


For an example config file, see the provided [sample config](../config.yaml)
