# Copyright 2017, Development Gateway, Inc.
# This file is part of ldadm, see COPYING.

import logging, sys, argparse
from copy import copy

log = logging.getLogger(__name__)

class Command:
    def __init__(self, args):
        self._args = args

    def _args_or_stdin(self, argname):
        args = getattr(self._args, argname)
        if args:
            if not sys.__stdin__.isatty():
                log.warning("Standard input ignored, because arguments are present")
            if hasattr(args[0], "read"):
                with args[0] as file_object:
                    for line in file_object:
                        yield line[:-1] # in text mode linesep is always "\n"
            else:
                for arg in args:
                    yield arg
        else:
            with sys.__stdin__ as file_object:
                for line in file_object:
                    yield line[:-1] # in text mode linesep is always "\n"

    @classmethod
    def add_subparser(cls, parent, full_name = []):
        if not full_name:
            full_name = [cls.parser_name]

        options = cls.parser_args
        for name in full_name[1:]:
            options = options["subparsers"][name]

        this_name = full_name[-1]

        log.debug("add_parser %s" % this_name)
        try:
            kwargs = options["kwargs"]
        except KeyError:
            kwargs = {}
        parser = parent.add_parser(this_name, **kwargs)

        event_name = "on_" + "_".join(full_name)
        parser.set_defaults(_class = cls)
        parser.set_defaults(_event = event_name)

        try:
            arguments = options["arguments"]
        except KeyError:
            arguments = {}
        for arg, kwargs in arguments.items():
            log.debug("%s.add_argument %s" % (this_name, arg))
            parser.add_argument(arg, **kwargs)

        if "subparsers" in options:
            child_name = copy(full_name)
            title = options["subparsers_title"]
            new_parent = parser.add_subparsers(title = title)
            for name in options["subparsers"]:
                log.debug("%s.add_subparser %s" % (this_name, name))
                child_name.append(name)
                cls.add_subparser(new_parent, child_name)
                child_name.pop()
