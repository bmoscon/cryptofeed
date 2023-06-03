'''
Copyright (C) 2017-2023 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import sys
import glob
import os


def on(exchange_filter):
    for file in glob.glob(os.getcwd() + "/../cryptofeed/**/*.py", recursive=True):
        if 'performance_metrics' in file or 'perf.py' in file or exchange_filter not in file:
            continue
        data = None
        with open(file, 'r') as fp:
            data = fp.read()
        if "# PERF" in data:
            data = data.replace("# PERF ", "")
            with open(file, 'w') as fp:
                fp.write("from cryptofeed.util.perf import *\n")
                fp.write(data)


def off(exchange_filter):
    for file in glob.glob(os.getcwd() + "/../cryptofeed/**/*.py", recursive=True):
        if 'performance_metrics' in file or 'perf.py' in file or exchange_filter not in file:
            continue
        data = None
        with open(file, 'r') as fp:
            data = fp.read()
        if "perf_" in data:
            data = data.replace("perf_", "# PERF perf_")
            data = data.replace("from cryptofeed.util.perf import *\n", "")
            with open(file, 'w') as fp:
                fp.write(data)


def main():
    exchange_filter = sys.argv[2] if len(sys.argv) > 1 else None
    if sys.argv[1] == 'on':
        on(exchange_filter)
    else:
        off(exchange_filter)


if __name__ == '__main__':
    main()
