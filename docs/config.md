## Configuring Cryptofeed

Configuration is specified during the creation of the feedhandler object, via the `config` kwarg. It defaults to `None`. Currently, the following options exist for specifying a configuration to the feedhandler.

* Specifying nothing
  - If config is left as None, the defaults in `config.py` will be used
* Specifying a dictionary
  - A dictionary can be directly provided, as long as the keys match the expected setting options (see below under Settings).
* Specifying a path to a config file
  - A yaml file can be loaded, provided it has entries in it that match the expected settings (see below under Settings)
* An env var
  - An environment variable can be specified to point to the configuration. if `CRYPTOFEED_CONFIG` is set, the value in this env var is used as a path to a config file. It is assumed the path is an absolute path and that it also contains the file name.

The configuration will be automatically passed to exchange objects that the feed handler directly creates (feeds that are specified by string/name). Exchange objects created by the user will need to have the config passed as well (via the Feed object `config` kwarg), or the same defaulting rules mentioned above will apply.

### Settings

The following are valid settings for the configuration of Cryptofeed.


* log
  - logging settings. Valid entries are `filename` and `level` (corresponding to log filename and level).
* uvloop
  - default is True. This boolean can enable or disable uvloop support.
* exchange config. 
  - A lowercase exchange name. Valid entries here will vary by exchange, but normally will contain `key_id` and `key_secret`. For exchanges that use different, or more, secrets, those entries will be here as well.


For an example config file, see the provided [sample config](../config.yaml)

- `iggy_emit_total`, `iggy_emit_failure_total`, `iggy_emit_latency_seconds` counters/histograms exported when `prometheus_client` is installed (see `cryptofeed.backends.iggy`).
```yaml
backends:
  iggy:
    host: localhost
    port: 8090
    # or provide connection_string: iggy+tcp://user:pass@localhost:8090
    stream: cryptofeed
    topic: trades
    transport: tcp
    retry_attempts: 3
    auto_create: true
    stream_id: 1
    topic_id: 2
    partitions: 3
    replication_factor: 1
    prometheus_metrics: true  # ensure prometheus_client is installed
```
- When `auto_create` is enabled the backend will lazily call `get_stream`/`create_stream` and `get_topic`/`create_topic` before the first send, matching the Apache Iggy Python producer example. citeturn0search0turn0search4

- To forward metrics/logs to OpenTelemetry, configure `OTEL_EXPORTER_OTLP_ENDPOINT` (or your provider-specific settings) and set `export_otel: true` in the Iggy backend config (fallbacks to Prometheus/local logging when not enabled).
