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

    def on_server_show(self):
        servers = ServerMapping(attrs = ALL_ATTRIBUTES)
        servers.select(self._args_or_stdin("server"))
        for entry in servers.values():
            pretty_print(entry)

    def on_server_add(self):
        attr_name = ServerMapping._attribute
        servers = ServerMapping(attrs = ALL_ATTRIBUTES)

        # Get default values from a reference object
        if self._args.defaults:
            source_obj = servers[self._args.defaults]
        else:
            source_obj = None

        server = Server(reference_object = source_obj)
        id = server.attrs[attr_name]
        servers[id] = server.attrs

        if server.message:
            print(server.message)

    def on_server_delete(self):
        server_names = list(self._args_or_stdin("server"))
        if server_names:
            servers = ServerMapping()
            servers.select(server_names).delete()

    def on_server_unit_list(self):
        units = UnitMapping(cfg.server.base)
        for unit in units:
            print(unit)

    def on_server_unit_show(self):
        units = UnitMapping(cfg.server.base)
        base = units[self._args.unit].entry_dn

        servers = ServerMapping(base = base, sub_tree = self._args.full)
        for uid in servers:
            print(uid)

    def on_server_unit_add(self):
        units = UnitMapping(cfg.server.base)
        units.add(parent_name = self._args.parent)

    def on_server_unit_delete(self):
        unit_names = list(self._args_or_stdin("unit"))
        if unit_names:
            units = UnitMapping(cfg.server.base).select(unit_names)
            try:
                units.delete()
            except LDAPNotAllowedOnNotLeafResult as err:
                raise RuntimeError("One or more units not empty") from err

    def on_server_unit_assign(self):
        base = cfg.server.base
        units = UnitMapping(base)
        unit = units[self._args.unit]

        servers = ServerMapping(base = base)
        servers.select(self._args_or_stdin("server"))
        servers.move(unit.entry_dn)
