# Cryptofeed installation
 
The Cryptofeed library is intended for use by Python developers.

You have several ways to get/use Cryptofeed:

* Pip - `pip install cryptofeed`
* Git - `git clone https://github.com/bmoscon/cryptofeed`
* Zipped source code - Download [github.com/bmoscon/cryptofeed/archive/master.zip](https://github.com/bmoscon/cryptofeed/archive/master.zip)
* Pipenv

In the following chapters you will find further details
on the use of Pip and Pipenv.


## Installation with Pip

The safe way to install or upgrade the Cryptofeed library:

    python3 -m pip install --user --upgrade cryptofeed

To minimize the number of dependencies to download,
the dependencies required by the Rest API, and
the cryptofeed backends are optional, but easy to install.

See the file [`setup.py`](https://github.com/bmoscon/cryptofeed/blob/master/setup.py#L60)
for the exhaustive list of these *extra* dependencies.

### Install all optional dependencies

You can install Cryptofeed along with all optional dependencies in one bundle:

    python3 -m pip install --user --upgrade cryptofeed[all]

### Rest API

Cryptofeed can also be used to access the *Rest API*
of some crypto-exchange to retrieve historical market data
and to place orders. See also the dedicated chapter
[Rest API](https://github.com/bmoscon/cryptofeed/blob/master/README.md#rest-api).

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

The tool Pipenv allows the installation of
the Cryptofeed library and its dependencies
without affecting your daily Python environment.
Pipenv is based on `pip` and `virtualenv`.

### Install Pipenv

You may want to install the latest versions of Pip and Pipenv
on your user Python environment to limit conflicts with the operating system:

    python3 -m pip install --user --upgrade pip
    python3 -m pip install --user --upgrade pipenv

### Install the runtime dependencies

Once you have cloned/downloaded the Cryptofeed source code,
you can install the dependencies
within a dedicated Python virtual environment
using the following command line:

    cd your/path/to/cryptofeed
    python3 -m pipenv install

Note: the default `Pipfile` is configured to install all optional dependencies.
You may edit the `Pipfile` to comment the optional dependencies you do not need.

### Uninstall the unused dependencies

Edit the `Pipfile` and comment some (or all)
dependencies above the line `# Optional dependencies`.

Then:

    cd your/path/to/cryptofeed
    python3 -m pipenv clean

You may also copy/hack that `Pipfile` within your own project.
That `Pipfile` is in the public domain to give you more freedom.

Note: See the [LICENSE](https://github.com/bmoscon/cryptofeed/blob/master/LICENSE)
for the rest of the Cryptofeed files.

### Update dependencies

You can update the dependency versions once a week:

    cd your/path/to/cryptofeed
    python3 -m pipenv update

### Dependency graph

You can also check the entire dependency tree:

    cd your/path/to/cryptofeed
    python3 -m pipenv graph

### Run a script
 
In the following example we execute the script `demo.py`:

    cd your/path/to/cryptofeed
    PYTONPATH=. python3 -m pipenv run python3 examples/demo.py

To use shorter command lines,
you may want to enter in the sub-shell of the
Python virtual environment:

    cd your/path/to/cryptofeed
    python3 -m pipenv shell
    export PYTONPATH=$PWD
    cd path/to/your/project
    python your-awesome-script.py
    [...]
    exit      # or [Ctrl] + [D]
 
Note: Remember that you are in a sub-shell of a virtual environment. <br>
To leave this sub-shell, use the command `exit`
or the keyboard shortcut **<kdb>Ctrl</kdb>** + **<kdb>D</kdb>**.


### Install the dev. dependencies

The `[dev-packages]` section (of the `Pipfile`) lists
the Python packages used for the Cryptofeed development.

    cd your/path/to/cryptofeed
    python3 -m pipenv install --dev

### Unit test

Pytest is listed in the `[dev-packages]` section with
`pytest-asyncio`, a Pytest plugin allowing
to write unit tests for `asyncio` functions.

Once the development dependencies are installed,
perform the unit tests in the way you prefer:

1. Using a long Python command line:

        cd your/path/to/cryptofeed
        python3 -m pipenv run python3 -m pytest tests

2. Entering the sub-shell of the virtual environment:

        cd your/path/to/cryptofeed
        python3 -m pipenv shell
        pytest
        [...]
        exit     # or [Ctrl] + [D]

### Static code analysis

The `[dev-packages]` section of the `Pipfile` also lists
Pylint with many plugins for relevant static code analysis.

This allows you to detect potential bugs and error-prone coding style.

    cd your/path/to/cryptofeed
    python3 -m pipenv run python3 -m pylint --output-format=colorized ./cryptofeed/exchange

You may want to reduce the number of reported issues
by disabling the minor/verbose ones with the `--disable` option:

    cd your/path/to/cryptofeed
    python3 -m pipenv run python3 -m pylint --output-format=colorized --disable=C0111,C0301,C0103,R0903,R0913,R0912 ./cryptofeed/exchange

Parse two folders containing Python files:

    cd your/path/to/cryptofeed
    python3 -m pipenv run python3 -m pylint --output-format=colorized ./cryptofeed ./examples

Activate the Pylint plugins with the option `--load-plugins`:

    cd your/path/to/cryptofeed
    export PYTONPATH=.
    python3 -m pipenv run python3 -m pylint --verbose --output-format=colorized --load-plugins=pylint_topology,pylint_import_modules,pylint_google_style_guide_imports_enforcing,pylint_unittest,pylint_requests,pylint_args,string_spaces_checkers ./cryptofeed

When almost all reported issues are fixed,
you can speed up the Pylint processing with the option `--jobs=8`.
Using this option when there are still many issues
may duplicate/mix the Pylint output.

### Optimize the `import` sections

One more thing: The `[dev-packages]` section also lists the tool
[`isort`](https://timothycrosley.github.io/isort/).

The following `isort` options apply the same formatting as `black`,
but only to the `import` sections:

    cd your/path/to/cryptofeed
    python3 -m pipenv run python3 -m isort --jobs=8 --atomic --multi-line 3 --force-grid-wrap 0 --trailing-comma --use-parentheses --apply --recursive .

## Contribute

If you have a problem with the installation/hacking of Cryptofeed,
you are welcome to open a new issue: https://github.com/bmoscon/cryptofeed/issues/
or join us on Slack: [cryptofeed-dev.slack.com](https://join.slack.com/t/cryptofeed-dev/shared_invite/enQtNjY4ODIwODA1MzQ3LTIzMzY3Y2YxMGVhNmQ4YzFhYTc3ODU1MjQ5MDdmY2QyZjdhMGU5ZDFhZDlmMmYzOTUzOTdkYTZiOGUwNGIzYTk)

Your Pull Requests are also welcome, even for minor changes.
