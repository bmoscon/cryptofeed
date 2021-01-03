'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import sys

from yapic import json


def main(filename):
    with open(filename, 'r') as fp:
        counter = 0
        for line in fp.readlines():
            timestamp, line = line.split(":", 1)
            try:
                _ = json.loads(line)
            except Exception:
                print(f"Failed on line {counter}: ")
                print(line)
                raise
            counter += 1
        print(f"Successfully verified {counter} updates")


if __name__ == '__main__':
    main(sys.argv[1])
