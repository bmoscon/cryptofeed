'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import ast
import sys
import zlib

from yapic import json


def bytes_string_to_bytes(string):
    tree = ast.parse(string)
    return tree.body[0].value.s


def main(filename):
    with open(filename, 'r') as fp:
        counter = 0
        for line in fp.readlines():
            counter += 1
            if line == "\n":
                continue
            if line.startswith("configuration"):
                continue
            start = line[:3]
            if start == 'wss':

                continue
            if start == 'htt':
                _, line = line.split(" -> ")

            _, line = line.split(": ", 1)
            if "header: " in line:
                line = line.split("header:")[0]
            try:
                if 'OKCOIN' in filename or 'OKEX' in filename:
                    if line.startswith('b\'') or line.startswith('b"'):
                        line = bytes_string_to_bytes(line)
                        line = zlib.decompress(line, -15).decode()
                elif 'HUOBI' in filename and 'ws' in filename:
                    line = bytes_string_to_bytes(line)
                    line = zlib.decompress(line, 16 + zlib.MAX_WBITS)
                elif 'UPBIT' in filename:
                    if line.startswith('b\'') or line.startswith('b"'):
                        line = line.strip()[2:-1]
                _ = json.loads(line)
            except Exception:
                print(f"Failed on line {counter}: ")
                print(line)
                raise
        print(f"Successfully verified {counter} updates")


if __name__ == '__main__':
    main(sys.argv[1])
