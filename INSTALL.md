# Cryptofeed installation
 
The Cryptofeed library is intended for use by Python developers.

Several ways to get/use Cryptofeed:

* Pip - `pip install cryptofeed`
* Git - `git clone https://github.com/bmoscon/cryptofeed`
* Zipped source code - Download [github.com/bmoscon/cryptofeed/archive/master.zip](https://github.com/bmoscon/cryptofeed/archive/master.zip)
* Pipenv

In the following chapters you will find further details
on the use of Pip and Pipenv.


## Installation with Pip

The safe way to install and upgrade the Cryptofeed library:

    python3 -m pip install --user --upgrade cryptofeed

Cryptofeed supports many backends as Redis, ZeroMQ, RabbitMQ, MongoDB, PostgreSQL, Google Cloud and much more...
Cryptofeed is usually used with few backends (one or two) and installing the dependencies of all backends is not required. 
Thus, to minimize the number of dependencies, the backend dependencies are optional, but easy to install.

See the file [`setup.py`](https://github.com/bmoscon/cryptofeed/blob/master/setup.py#L60)
for the exhaustive list of these *extra* dependencies.

* Install all optional dependencies  
  To install Cryptofeed along with all optional dependencies in one bundle:

         python3 -m pip install --user --upgrade cryptofeed[all]

* Arctic backend  
  To install Cryptofeed along with [Arctic](https://github.com/man-group/arctic/) in one bundle:

         python3 -m pip install --user --upgrade cryptofeed[arctic]

* Google Cloud Pub / Sub backend

         python3 -m pip install --user --upgrade cryptofeed[gcp_pubsub]

* Kafka backend

         python3 -m pip install --user --upgrade cryptofeed[kafka]

* MongoDB backend

         python3 -m pip install --user --upgrade cryptofeed[mongo]

* PostgreSQL backend

         python3 -m pip install --user --upgrade cryptofeed[postgres]

* RabbitMQ backend

         python3 -m pip install --user --upgrade cryptofeed[rabbit]

* Redis backend

          python3 -m pip install --user --upgrade cryptofeed[redis]

* ZeroMQ backend

         python3 -m pip install --user --upgrade cryptofeed[zmq]


## Installation with Pipenv

The tool Pipenv allows the installation of
the Cryptofeed library and its dependencies
without affecting your daily Python environment.
Pipenv is based on `pip` and `virtualenv`.

### Install Pipenv

On an Operating System (OS) released more than 2 years ago,
installing the latest versions of Pip and Pipenv is recommended to fix issues and to enable new features.
However, Python packages installed by the system should not be altered.
Thus, we recommend installing Python packages in the user Python environment
to limit conflicts with the operating system:

    python3 -m pip install --user --upgrade pip
    python3 -m pip install --user --upgrade pipenv

### Install the runtime dependencies

Once you have cloned/downloaded the Cryptofeed source code,
you can install the dependencies within a Python virtual environment:

    cd your/path/to/cryptofeed
    python3 -m pipenv install

### Test Cryptofeed installation

The environment variable `PYTHONPATH` is required
because the `Pipefile` does locate the Cryptofeed library:

    cd your/path/to/cryptofeed
    PYTHONPATH=. python3 -m pipenv run python3 examples/demo.py

or you can enter the sub-shell of the Python virtual environment:

    export PYTHONPATH=your/path/to/cryptofeed
    ...
    cd your/path/to/cryptofeed
    python3 -m pipenv shell
    python examples/demo.py
    ...
    exit      # or [Ctrl] + [D]
 
Note: Remember that you are in the sub-shell of the virtual environment. <br>
To leave this sub-shell, use the command `exit`
or the keyboard shortcut **<kdb>Ctrl</kdb>** + **<kdb>D</kdb>**.


### Uninstall the unused dependencies

The default `Pipfile` is configured to install all optional dependencies.
Please, edit the `Pipfile` to comment the optional dependencies you do not need.
See the dependencies listed above the line `# Optional dependencies`.

To uninstall a dependency, comment it (insert "`#`" in the beginning of the line)
and run the following command lines:

    cd your/path/to/cryptofeed
    python3 -m pipenv clean

### Update dependencies

Check for security vulnerabilities and new dependency versions once a week:

    cd your/path/to/cryptofeed
    python3 -m pipenv check

Upgrade the dependency versions:

    cd your/path/to/cryptofeed
    python3 -m pipenv update

Follow the version change:

    git diff Pipfile.lock

Print the entire dependency tree:

    python3 -m pipenv graph

### Install the dev. dependencies

The `[dev-packages]` section (of the `Pipfile`) lists
the Python packages used for the Cryptofeed development.

    cd your/path/to/cryptofeed
    python3 -m pipenv install --dev

### Unit test

Pytest is listed in the `[dev-packages]` section with
`pytest-asyncio`, a Pytest plugin allowing
writing unit tests for `asyncio` functions.

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


### Alternative Pipfile

To avoid setting the `PYTHONPATH` environment variable, use a different `Pipfile`:

    cd your/path/to/cryptofeed
    rm Pipfile Pipfile.lock
    python3 -m pip install -e cryptofeed

The resulted `Pipfile` is similar to:

```toml
[[source]]
url = "https://pypi.org/simple"
verify_ssl = true
name = "pypi"

[packages]
cryptofeed = {editable = true, path = "."}
```

## Contribute

If you have a problem with the installation/hacking of Cryptofeed,
you are welcome to:
* open a new issue: https://github.com/bmoscon/cryptofeed/issues/
* join us on Slack: [cryptofeed-dev.slack.com](https://join.slack.com/t/cryptofeed-dev/shared_invite/enQtNjY4ODIwODA1MzQ3LTIzMzY3Y2YxMGVhNmQ4YzFhYTc3ODU1MjQ5MDdmY2QyZjdhMGU5ZDFhZDlmMmYzOTUzOTdkYTZiOGUwNGIzYTk)
* or on GitHub Discussion: https://github.com/bmoscon/cryptofeed/discussions

Your Pull Requests are also welcome, even for minor changes.
