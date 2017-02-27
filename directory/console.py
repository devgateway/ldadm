from functools import reduce
from datetime import datetime

def pretty_print(entry):
    def output(k, v):
        try:
            s = v.decode("utf-8")
        except AttributeError:
            s = str(v)

        print(formatter.format(k, s))

    attrs = entry["attributes"]
    longest = reduce(lambda x, y: x if len(x) > len(y) else y, attrs)
    width = len(longest) + 1
    formatter = "{:%is} {:s}" % width

    for key in sorted(attrs):
        values = attrs[key]

        if type(values) is list:
            first_value = values.pop(0)
            output(key + ":", first_value)
            for value in values:
                output("", value)

        elif type(values) is datetime:
            output(key + ":", values.strftime("%c"))

        else:
            output(key + ":", values)

    print()
