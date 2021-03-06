# Copyright 2017, Development Gateway, Inc.
# This file is part of ldadm, see COPYING.

from functools import reduce
from datetime import datetime
import sys

def pretty_print(entry):
    def output(k, v):
        try:
            s = v.decode("utf-8")
        except AttributeError:
            s = str(v)

        print(formatter.format(k, s))

    attrs = entry.entry_attributes
    longest = reduce(lambda x, y: x if len(x) > len(y) else y, attrs)
    width = len(longest) + 1
    formatter = "{:%is} {:s}" % width

    for key in sorted(attrs):
        value = entry[key].value

        if type(value) is list:
            first_value = value.pop(0)
            output(key + ":", first_value)
            for elem in value:
                output("", elem)

        elif type(value) is datetime:
            output(key + ":", value.strftime("%c"))

        else:
            output(key + ":", value)

    print()

def input_stderr(prompt = None):
    if prompt:
        sys.stderr.write(prompt)
        sys.stderr.flush()
    return sys.stdin.readline()[:-1]
