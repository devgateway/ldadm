# Copyright 2017, Development Gateway, Inc.
# This file is part of ldadm, see COPYING.

import logging
from argparse import ArgumentParser

from ldap3.core.exceptions import LDAPEntryAlreadyExistsResult, LDAPKeyError, \
        LDAPAttributeOrValueExistsResult
from ldap3 import ALL_ATTRIBUTES, ObjectDef

from .command import Command
from .abstract import MissingObjects, LdapObjectMapping, LdapObject
from .config import cfg
from .user import single_user, multi_user, UserMapping
from .unit import UnitMapping, single_unit, multi_unit
from .console import pretty_print
from .connection import ldap

log = logging.getLogger(__name__)

single_server = ArgumentParser(add_help = False)
single_server.add_argument("server",
        metavar = "SERVER",
        help = "Server name")

multi_server = ArgumentParser(add_help = False)
multi_server.add_argument("server",
        metavar = "SERVER_NAME",
        nargs = "*",
        help = "One or more server names. If omitted, read from stdin.")

class Server(LdapObject):
    _config_node = cfg.server
    _object_class = cfg.server.objectclass
    _object_def = ObjectDef(object_class = _object_class, schema = ldap)

class ServerMapping(LdapObjectMapping):
    _name = "Servers"
    _attribute = cfg.server.attr.id
    _object_def = Server._object_def
    _base = cfg.server.base

    @staticmethod
    def get_dn(names):
        mapping = __class__(base = cfg.server.base)
        try:
            return __class__._get_dn(names, mapping)
        except MissingObjects as err:
            msg = "Unknown servers: " + ", ".join(err.items)
            raise RuntimeError(msg) from err

class ServerCommand(Command):
    __base = cfg.server.base
    parser_name = "server"
    parser_args = {
        "kwargs": {
            "help": "Servers"
        },
        "subparsers_title": "Server command",
        "subparsers": {
            "list": {
                "kwargs": {
                    "help": "List all servers"
                }
            },
            "show": {
                "kwargs": {
                    "parents": [multi_server],
                    "aliases": ["info"],
                    "help": "List server attributes"
                }
            },
            "add": {
                "kwargs": {
                    "aliases": ["create"],
                    "help": "Add a server"
                },
                "arguments": {
                    "--defaults": {
                        "dest": "defaults",
                        "metavar": "SERVER",
                        "nargs": 1,
                        "help": "Suggest defaults from an existing server"
                    }
                }
            },
            "delete": {
                "kwargs": {
                    "parents": [multi_server],
                    "aliases": ["remove"],
                    "help": "Delete servers"
                }
            },
            "unit": {
                "kwargs": {
                    "help": "Server units"
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
                            "help": "List servers in the unit"
                        },
                        "arguments": {
                            "--full": {
                                "action": "store_true",
                                "help": "List servers in nested units, too"
                            }
                        }
                    },
                    "add": {
                        "kwargs": {
                            "aliases": ["create"],
                            "help": "Add a server unit"
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
                            "help": "Delete an server unit (category)"
                        }
                    },
                    "assign": {
                        "kwargs": {
                            "parents": [single_unit, multi_server],
                            "help": "Move servers to the unit (category)"
                        }
                    }
                }
            }
        }
    }

    def on_server_list(self):
        servers = ServerMapping()
        for name in servers:
            print(name)
