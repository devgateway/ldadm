#!/usr/bin/python3
import argparse, logging, sys, importlib, os

log = None

# abstract parsers
single_user = argparse.ArgumentParser(add_help = False)
single_user.add_argument("username",
        metavar = "USER_NAME",
        help = "User ID")

multi_user = argparse.ArgumentParser(add_help = False)
multi_user.add_argument("username",
        metavar = "USER_NAME",
        nargs = "*",
        help = "One or more UIDs. If omitted, read from stdin.")

only_suspended = argparse.ArgumentParser(add_help = False)
only_suspended.add_argument("--suspended",
        action = "store_true",
        help = "Only include suspended users")

single_unit = argparse.ArgumentParser(add_help = False)
single_unit.add_argument("unit",
        metavar = "UNIT",
        help = "Unit name")

multi_unit = argparse.ArgumentParser(add_help = False)
multi_unit.add_argument("unit",
        metavar = "UNIT_NAME",
        nargs = "*",
        help = "One or more unit names. If omitted, read from stdin.")

# concrete parsers
parsers = {
    "user": {
        "kwargs": {
            "help": "User accounts"
        },
        "defaults": {
            "_class": "UserCommand",
            "_module": "usercmd"
        },
        "subparsers_title": "User command",
        "subparsers": {
            "list": {
                "kwargs": {
                    "parents": [only_suspended],
                    "help": "List all active or suspended users"
                },
            },
            "search": {
                "kwargs": {
                    "parents": [only_suspended],
                    "help": "Search users with LDAP filter"
                },
                "arguments": {
                    "filter": {
                        "metavar": "LDAP_FILTER",
                        "help": "Search filter"
                    }
                }
            },
            "show": {
                "kwargs": {
                    "aliases": ["info"],
                    "parents": [multi_user, only_suspended],
                    "help": "Show details for accounts"
                },
                "arguments": {
                    "--full": {
                        "action": "store_true",
                        "help": "Also show operational attributes"
                    }
                }
            },
            "suspend": {
                "kwargs": {
                    "aliases": ["lock", "ban", "disable"],
                    "parents": [multi_user],
                    "help": "Make accounts inactive"
                }
            },
            "restore": {
                "kwargs": {
                    "aliases": ["unlock", "unban", "enable"],
                    "parents": [multi_user],
                    "help": "Re-activate accounts"
                }
            },
            "delete": {
                "kwargs": {
                    "aliases": ["remove"],
                    "parents": [multi_user],
                    "help": "Irreversibly destroy suspended accounts"
                }
            },
            "add": {
                "kwargs": {
                    "aliases": ["create"],
                    "help": "Add a new account"
                },
                "arguments": {
                    "--defaults": {
                        "dest": "defaults",
                        "metavar": "USER_NAME",
                        "nargs": 1,
                        "help": "Suggest defaults from an existing user"
                    }
                }
            },
            "rename": {
                "kwargs": {
                    "help": "Change account UID"
                },
                "arguments": {
                    "oldname": {
                        "metavar": "OLD_NAME",
                        "help": "Old UID"
                    },
                    "newname": {
                        "metavar": "NEW_NAME",
                        "help": "New UID"
                    }
                }
            },
            "key": {
                "kwargs": {
                    "help": "Manipulate user SSH public key"
                },
                "subparsers_title": "Key command",
                "subparsers": {
                    "list": {
                        "kwargs": {
                            "aliases": ["show"],
                            "parents": [single_user],
                            "help": "List public keys for a user"
                        }
                    },
                    "add": {
                        "kwargs": {
                            "aliases": ["create"],
                            "parents": [single_user],
                            "help": "Add a public key to a user"
                        },
                        "arguments": {
                            "--file": {
                                "dest": "key_file",
                                "metavar": "FILE_NAME",
                                "type": argparse.FileType("r"),
                                "nargs": 1,
                                "help": "Read public key from file"
                            }
                        }
                    },
                    "delete": {
                        "kwargs": {
                            "aliases": ["remove"],
                            "parents": [single_user],
                            "help": "Remove a public key from a user"
                        },
                        "arguments": {
                            "key_names": {
                                "metavar": "KEY_NAME",
                                "nargs": "*",
                                "help": "Public key MD5 modulus or comment"
                            }
                        }
                    }
                }
            }
        }
    },
    "unit": {
        "kwargs": {
            "help": "Organizational units"
        },
        "defaults": {
            "_class": "UnitCommand",
            "_module": "unitcmd"
        },
        "subparsers_title": "Unit command",
        "subparsers": {
            "list": {
                "kwargs": {
                    "help": "List all units"
                }
            },
            "show": {
                "kwargs": {
                    "parents": [single_unit],
                    "aliases": ["info"],
                    "help": "List members of the unit"
                }
            },
            "add": {
                "kwargs": {
                    "aliases": ["create"],
                    "help": "Add an organizational unit"
                }
            },
            "delete": {
                "kwargs": {
                    "parents": [multi_unit],
                    "aliases": ["remove"],
                    "help": "Delete an organizational unit"
                }
            },
            "assign": {
                "kwargs": {
                    "parents": [single_unit, multi_user],
                    "help": "Move users to the organizational unit"
                }
            }
        }
    },
    "list": {
       "kwargs": {
           "help": "Mailing lists"
       },
        "defaults": {
            "_class": "ListCommand",
            "_module": "listcmd"
        },
    }
}

def _get_args():
    def _gen_parser(parent, parser_name, parser_opts):
        if "kwargs" in parser_opts:
            kwargs = parser_opts["kwargs"]
        else:
            kwargs = {}

        log.debug("With parser %s:" % parser_name)
        #log.debug("add_parser('%s', %s)" % (parser_name, repr(kwargs)))
        parser = parent.add_parser(parser_name, **kwargs)

        if "defaults" in parser_opts:
            for key, value in parser_opts["defaults"].items():
                log.debug("For parser %s, setting defaults %s = %s" % \
                        (parser_name, key, value) )
                kwargs = {key: value}
                #log.debug("%s.set_defaults(%s)" % (parser_name, repr(kwargs)))
                parser.set_defaults(**kwargs)

        if "arguments" in parser_opts:
            for arg, kwargs in parser_opts["arguments"].items():
                log.debug("To parser %s, adding argument %s" % (parser_name, arg))
                #log.debug("%s.add_argument(%s, %s)" % (parser_name, arg, repr(kwargs)))
                parser.add_argument(arg, **kwargs)

        if "subparsers" in parser_opts:
            log.debug("Generating subparsers for %s" % parser_name)
            title = parser_opts["subparsers_title"]
            #log.debug("%s.add_subparsers(title = '%s')" % (parser_name, title))
            subparsers = parser.add_subparsers(title = title)
            for subparser_name, subparser_opts in parser_opts["subparsers"].items():
                log.debug("To %s, adding subparser %s" % (parser_name, subparser_name))
                _gen_parser(subparsers, subparser_name, subparser_opts)

    ap = argparse.ArgumentParser(description = "Manage LDAP accounts")

    subcommands = ap.add_subparsers(description = "Objects to manage", dest = "subcommand")
    subcommands.required = True

    for parser_name, parser_opts in parsers.items():
        _gen_parser(subcommands, parser_name, parser_opts)

    args = ap.parse_args()
    return args

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

    args = _get_args()

    log.debug("Invoking %s.%s" % (args._class, args._event))
    try:
        commands = importlib.import_module("." + args._module, "ldadm")
        command_instance = getattr(commands, args._class)(args)
        handler = getattr(command_instance, "on_" + args._event)
        handler()
    except Exception as e:
        if log.isEnabledFor(logging.DEBUG):
            raise RuntimeError("Daisy… Daisy…") from e
        else:
            sys.exit(str(e))

if __name__ == "__main__":
    main()
