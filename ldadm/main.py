#!/usr/bin/python3
import logging, sys, os, argparse, inspect
from importlib import import_module

from .command import Command

log = None

def _set_log_level():
    valid_levels = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
    try:
        env_level = os.environ["LOG_LEVEL"]
        valid_levels.remove(env_level)
        level = getattr(logging, env_level)
    except KeyError:
        level = logging.WARNING
    except ValueError:
        msg = "Expected log level: %s, got: %s. Using default level WARNING." \
                % ("|".join(valid_levels), env_level)
        print(msg, file = sys.stderr)
        level = logging.WARNING

    logging.basicConfig(level = level)
    global log
    log = logging.getLogger(__name__)

def main():
    _set_log_level()

    ap = argparse.ArgumentParser(description = "Manage LDAP accounts")

    subcommands = ap.add_subparsers(description = "Objects to manage", dest = "subcommand")
    subcommands.required = True

    command_modules = ["user", "unit", "project"]
    for module_name in command_modules:
        module = import_module("." + module_name, "ldadm")
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if cls is not Command and issubclass(cls, Command):
                cls.add_subparser(subcommands)

    args = ap.parse_args()

    log.debug("Invoking %s.%s" % (args._class.__name__, args._event))
    try:
        command_instance = args._class(args)
        handler = getattr(command_instance, args._event)
        handler()
    except Exception as e:
        if log.isEnabledFor(logging.DEBUG):
            raise RuntimeError("Daisy… Daisy…") from e
        else:
            sys.exit(str(e))

if __name__ == "__main__":
    main()
