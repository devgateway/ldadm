import logging, sys

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
