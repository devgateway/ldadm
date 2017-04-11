import logging
from argparse import ArgumentParser

from ldap3 import ObjectDef
from ldap3.core.exceptions import LDAPEntryAlreadyExistsResult, LDAPKeyError, \
        LDAPAttributeOrValueExistsResult, LDAPNotAllowedOnNotLeafResult

from .command import Command
from .abstract import LdapObjectMapping, LdapObject
from .config import cfg, ConfigAttrError
from .user import UserMapping, multi_user
from .connection import ldap

log = logging.getLogger(__name__)

single_unit = ArgumentParser(add_help = False)
single_unit.add_argument("unit",
        metavar = "UNIT",
        help = "Unit name")

multi_unit = ArgumentParser(add_help = False)
multi_unit.add_argument("unit",
        metavar = "UNIT_NAME",
        nargs = "*",
        help = "One or more unit names. If omitted, read from stdin.")

class Unit(LdapObject):
    try:
        _config_node = cfg.unit
    except ConfigAttrError:
        _config_node = None

    _object_class = "organizationalUnit"
    # Load attribute definitions by ObjectClass
    _object_def = ObjectDef(object_class = _object_class, schema = ldap)

class UnitMapping(LdapObjectMapping):
    _name = "Units"
    _attribute = "organizationalUnitName"
    _object_def = Unit._object_def
    _base = cfg.user.base.active

class UnitCommand(Command):
    __base = cfg.user.base.active
    parser_name = "unit"
    parser_args = {
        "kwargs": {
            "help": "Organizational units"
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
    }

    def on_unit_list(self):
        for unit in UnitMapping():
            print(unit)

    def on_unit_show(self):
        unit_name = self._args.unit
        sub_tree = self._args.full

        unit = UnitMapping()[unit_name]
        users = UserMapping(base = unit.entry_dn, sub_tree = sub_tree)

        for uid in users:
            print(uid)

    def on_unit_add(self):
        unit = Unit()
        ou = unit.attrs[UnitMapping._attribute]

        parent_name = self._args.parent
        if parent_name:
            parent = UnitMapping()[parent_name]
            base = parent.entry_dn
        else:
            base = None

        subunits = UnitMapping(base = base)
        subunits[ou] = unit.attrs

        if unit.message:
            print(unit.message)

    def on_unit_delete(self):
        unit_names = list(self._args_or_stdin("unit"))
        if not unit_names:
            return

        units = UnitMapping().select(unit_names)
        try:
            units.delete()
        except LDAPNotAllowedOnNotLeafResult as err:
            raise RuntimeError("One or more units not empty") from err

    def on_unit_assign(self):
        unit = UnitMapping()[self._args.unit]

        users = UserMapping(base = UnitMapping._base)
        users.select(self._args_or_stdin("username"))
        users.move(unit.entry_dn)
