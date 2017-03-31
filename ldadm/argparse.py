import argparse, logging

log = logging.getLogger(__name__)

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

# concrete parsers, more readable than a ton of statements
_parsers = {
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
            "passwd": {
                "kwargs": {
                    "help": "Reset user password"
                },
                "arguments": {
                    "username": {
                        "metavar": "USERNAME",
                        "help": "User ID"
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
                },
                "arguments": {
                    "--full": {
                        "action": "store_true",
                        "help": "List members in nested units, too"
                    }
                }
            },
            "add": {
                "kwargs": {
                    "aliases": ["create"],
                    "help": "Add an organizational unit"
                },
                "arguments": {
                    "--parent": {
                        "metavar": "PARENT_UNIT",
                        "help": "Create nested in this unit"
                    }
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

def get_args():
    def gen_parser(parent, parser_name, options):
        if "kwargs" in options:
            kwargs = options["kwargs"]
        else:
            kwargs = {}

        log.debug("add_parser %s" % parser_name)
        parser = parent.add_parser(parser_name, **kwargs)

        if "defaults" in options:
            for key, value in options["defaults"].items():
                log.debug("%s.set_defaults %s = %s" % (parser_name, key, value) )
                kwargs = {key: value}
                parser.set_defaults(**kwargs)

        parser.set_defaults(_event = "on_" + parser_name)

        if "arguments" in options:
            for arg, kwargs in options["arguments"].items():
                log.debug("%s.add_argument %s" % (parser_name, arg))
                parser.add_argument(arg, **kwargs)

        if "subparsers" in options:
            title = options["subparsers_title"]
            subparsers = parser.add_subparsers(title = title)
            for subparser_name, subparser_opts in options["subparsers"].items():
                log.debug("%s.add_subparser %s" % (parser_name, subparser_name))
                gen_parser(subparsers, subparser_name, subparser_opts)

    ap = argparse.ArgumentParser(description = "Manage LDAP accounts")

    subcommands = ap.add_subparsers(description = "Objects to manage", dest = "subcommand")
    subcommands.required = True

    for name, options in _parsers.items():
        gen_parser(subcommands, name, options)

    args = ap.parse_args()
    return args
