# Cryptofeed installation
 
The Cryptofeed library is intended to be used by Python developers.

Multiple ways to get and use Cryptofeed:

* using Pip, such as `pip install cryptofeed`
* using Git, such as `git clone https://github.com/bmoscon/cryptofeed`
* source code in a ZIP archive: https://github.com/bmoscon/cryptofeed/archive/master.zip
* using Pipenv

The following chapters provide more details
about Pip and Pipenv usage, in a pedagogical way.


## Installing using Pip

The recommended way to install or upgrade the Cryptofeed library:

    python3 -m pip install --user --upgrade cryptofeed

In order to minimize the amount of dependencies to download,
the dependencies required by the Rest API and
the Cryptofeed backends are optional, but easy to install.

See the file [`setup.py`](https://github.com/bmoscon/cryptofeed/blob/master/setup.py#L60)
for the exhaustive list of the extra dependencies.

### Install all optional dependencies

To install Cryptofeed along with all optional dependencies in one bundle:

    python3 -m pip install --user --upgrade cryptofeed[all]

### Rest API

The *Rest API* feature of Cryptofeed
allows to retrieve historical market data
and to place order. See also the chaptper
[Rest API](https://github.com/bmoscon/cryptofeed/blob/master/README.md#rest-api))
in the main README.md for more details.

    python3 -m pip install --user --upgrade cryptofeed[rest_api]

### Arctic backend

To install Cryptofeed along with
[Arctic](https://github.com/man-group/arctic/) in one bundle:

    python3 -m pip install --user --upgrade cryptofeed[arctic]

### Redis backend

    python3 -m pip install --user --upgrade cryptofeed[redis]

### ZeroMQ backend

    python3 -m pip install --user --upgrade cryptofeed[zmq]

### RabbitMQ backend

    python3 -m pip install --user --upgrade cryptofeed[zmq]

### MongoDB backend

    python3 -m pip install --user --upgrade cryptofeed[mongo]

### PostgreSQL backend

    python3 -m pip install --user --upgrade cryptofeed[postgres]

### Kafka backend

    python3 -m pip install --user --upgrade cryptofeed[kafka]


## Pipenv

The Pipenv tool allows to install Cryptofeed and its dependencies
without impacting your daily Python environment.
Pipenv is based on `pip` and `virtualenv`.

### Install Pipenv

The Cryptofeed team recommends to install the latest Pip and Pipenv versions
on the user Python environment to limit conflicts with the Operating System:

```commandline
python3 -m pip install --user --upgrade pip
python3 -m pip install --user --upgrade pipenv
```

### Install the runtime dependencies

Once you get the Cryptofeed source code,
you can install the dependencies
within a dedicated Python virtual environment
using the following command line:

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv install
```

Attention: the default `Pipfile` is configured to install
all dependencies. You edit the `Pipfile` before installing
all optional dependencies.

### Uninstall the unused dependencies

Edit the `Pipfile` and comment some (or all)
dependencies above the line `# Optional dependencies`.

After, run:

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv clean
```

You may also copy and hack this `Pipfile` within you own project.
The `Pipfile` content is in the public domain.

Attention: See the [LICENSE](https://github.com/bmoscon/cryptofeed/blob/master/LICENSE) for the rest of the Cryptofeed files.

### Update dependencies

Once a week, you may update the dependency versions.

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv update
```

### Dependency graph

You can also check the whole dependency tree.

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv graph
```

### Run a script
 
In the following example, we run the `demo.py` script.

```commandline
cd your/path/to/cryptofeed
PYTONPATH=. python3 -m pipenv run python3 examples/demo.py
```

To use shorter command lines,
you may prefer to enter in the
Python virtual environment sub-shell:

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv shell
export PYTONPATH=$PWD
cd path/to/your/awesome/project
python your-awesome-script.py
[...]
exit    # or [Ctrl] + [D]
```
 
Do not forget you are in a virtual environment sub-shell. <br>
To exit this sub-shell: use the command `exit`
or the keyboard shortcut **<kdb>Ctrl</kdb>** + **<kdb>D</kdb>**.


### Install the development dependencies

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv install --dev
```

### Unit-test

Pytest is listed as a dependency in `Pipfile`.
There is also a Pytest plugin, pytest-asyncio,
allowing us to write unit-tests for `asyncio` functions.

Once the the development dependencies are installed,
you run the unit-tests in two ways.

One way is to use a long python command line:

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv run python3 -m pytest tests
```

The second way is to activate the Python virtual environment
within a dedicated shell:

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv shell
pytest
[...]
exit   # or [Ctrl] + [D]
```


### Static-Analysis

The development dependencies in `Pipfile`
include Pylint and many Pylint plugins for a relevant static-analysis.

Therefore you can detect potential bugs and error-prone coding style.

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv run python3 -m pylint --output-format=colorized ./cryptofeed/exchange
```

You may want to reduce the amount of issues by disabling the minor ones with option `--disable`:

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv run python3 -m pylint --output-format=colorized --disable=C0111,C0301,C0103,R0903,R0913,R0912  ./cryptofeed/exchange
```

Analyze more folders:

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv run python3 -m pylint --output-format=colorized ./cryptofeed ./examples ./tools
```

Enable the Pylint plugins with option `--load-plugins`:

```commandline
cd your/path/to/cryptofeed
export PYTONPATH=.
python3 -m pipenv run python3 -m pylint --verbose --output-format=colorized --load-plugins=pylint_topology,pylint_import_modules,pylint_google_style_guide_imports_enforcing,pylint_unittest,pylint_requests,pylint_args,string_spaces_checkers ./cryptofeed
```

When almost all issues are fixed, speed up the Pylint using option `--jobs=8`.
However, when there is many issues, this options mixes the Pylint output.

### Optimize the `import` sections

One more thing: the `Pipfile` also provides the [`isort`](https://timothycrosley.github.io/isort/) tool.

The following `isort` options apply the same formatting as `black` but only on the `import` sections:

```commandline
cd your/path/to/cryptofeed
python3 -m pipenv run python3 -m isort --jobs=8 --atomic --multi-line 3 --force-grid-wrap 0 --trailing-comma --use-parentheses --apply --recursive .
```

## Support / Contribute

If you have an issue installing / hacking Cryptofeed, please feel free to open a new issue: <br>
https://github.com/bmoscon/cryptofeed/issues/

Pull Requests are also welcome, even for minor changes.
