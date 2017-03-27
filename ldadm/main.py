#!/usr/bin/python3
import argparse, logging, sys, importlib

log_levels = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG
}

ap = argparse.ArgumentParser(description = "Manage LDAP accounts")

ap.add_argument("--loglevel",
        dest = "log_level",
        default = "WARNING",
        type = str,
        choices = log_levels.keys(),
        help = "Set logging verbosity")

subcommands = ap.add_subparsers(
        description = "Objects to manage",
        dest = "subcommand"
        )
subcommands.required = True

# Abstract parsers

single_user_parser = argparse.ArgumentParser(add_help = False)
single_user_parser.add_argument("username",
        metavar = "USER_NAME",
        help = "User ID")

multi_user_parser = argparse.ArgumentParser(add_help = False)
multi_user_parser.add_argument("username",
        metavar = "USER_NAME",
        nargs = "*",
        help = "One or more UIDs. If omitted, read from stdin.")

only_suspended = argparse.ArgumentParser(add_help = False)
only_suspended.add_argument("--suspended",
        action = "store_true",
        help = "Only include suspended users")

single_unit_parser = argparse.ArgumentParser(add_help = False)
single_unit_parser.add_argument("unit",
        metavar = "UNIT",
        help = "Unit name")

multi_unit_parser = argparse.ArgumentParser(add_help = False)
multi_unit_parser.add_argument("unit",
        metavar = "UNIT_NAME",
        nargs = "*",
        help = "One or more unit names. If omitted, read from stdin.")

parsers = {
    "user": {
        "help": "User accounts",
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
                    "parents": [multi_user_parser, only_suspended],
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
                    "parents": [multi_user_parser],
                    "help": "Make accounts inactive"
                }
            },
            "restore": {
                "kwargs": {
                    "aliases": ["unlock", "unban", "enable"],
                    "parents": [multi_user_parser],
                    "help": "Re-activate accounts"
                }
            },
            "delete": {
                "kwargs": {
                    "aliases": ["remove"],
                    "parents": [multi_user_parser],
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
                            "parents": [single_user_parser],
                            "help": "List public keys for a user"
                        }
                    },
                    "add": {
                        "kwargs": {
                            "aliases": ["create"],
                            "parents": [single_user_parser],
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
                            "parents": [single_user_parser],
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
        "help": "Organizational units",
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
                    "parents": [single_unit_parser],
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
                    "parents": [multi_unit_parser],
                    "aliases": ["remove"],
                    "help": "Delete an organizational unit"
                }
            },
            "assign": {
                "kwargs": {
                    "parents": [single_unit_parser, multi_user_parser],
                    "help": "Move users to the organizational unit"
                }
            }
        }
    },
    "list": {
        "help": "Mailing lists",
        "defaults": {
            "_class": "ListCommand",
            "_module": "listcmd"
        },
    }
}


args = ap.parse_args()

log_level = log_levels[args.log_level]
logging.basicConfig(level = log_level)

def main():
    logging.debug("Invoking %s.%s" % (args._class, args._event))

    try:
        commands = importlib.import_module("." + args._module, "ldadm")
        command_instance = getattr(commands, args._class)(args)
        handler = getattr(command_instance, "on_" + args._event)
        handler()
    except Exception as e:
        if log_level == logging.DEBUG:
            raise RuntimeError("Daisy… Daisy…") from e
        else:
            sys.exit(str(e))

if __name__ == "__main__":
    main()
