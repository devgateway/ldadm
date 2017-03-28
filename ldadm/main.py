#!/usr/bin/python3
import logging, sys, importlib, os

from .argparse import get_args

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

    args = get_args()

    log.debug("Invoking %s.%s" % (args._class, args._event))
    try:
        commands = importlib.import_module("." + args._module, "ldadm")
        command_instance = getattr(commands, args._class)(args)
        handler = getattr(command_instance, args._event)
        handler()
    except Exception as e:
        if log.isEnabledFor(logging.DEBUG):
            raise RuntimeError("Daisy… Daisy…") from e
        else:
            sys.exit(str(e))

if __name__ == "__main__":
    main()
