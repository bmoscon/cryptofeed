#!/bin/bash

if [[ $1 = -h ]] || [[ $1 = --help ]]
then
    echo '
This script uses the tool isort to reformat the import sections
isort = sorts import definitions alphabetically and removes the unused ones

Usage:

    ./reformat-import-sections.sh [directory] [file.py] [...]

Without argument, this script reformats all Python files in the Git repository.

isort can be configured in many ways.
This script uses the isort configuration compatible with the tool black.
See https://github.com/psf/black/blob/master/docs/compatible_configs.md#isort

isort requires the Cryptofeed dependencies to be installed
This script assumes you use Pipenv to manage the Cryptofeed dependencies.
If you do not want to use Pipenv, then install isort (use "pip install isort" for example)
and remove the leading "python3 -m pipenv run" in the last command line of this script.
'
    exit
fi

set -e  # Stop this script when an error occurs
set -x  # Print command line

# Go to sub-directory because isort requires to distinguish external and internal dependencies
cd "$( dirname "${0}" )"/..

# isort uses settings from file pyproject.toml
python3 -m pipenv run python3 -m isort --jobs 8 "${@:-.}"