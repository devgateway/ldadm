import logging

from ldap3.core.exceptions import LDAPEntryAlreadyExistsResult, LDAPKeyError, \
        LDAPAttributeOrValueExistsResult, LDAPNotAllowedOnNotLeafResult

from .command import Command
from .collections import UnitMapping, UserMapping, MissingObjects
from .config import cfg
from .objects import Unit
from .parsers import multi_user, single_unit, multi_unit

log = logging.getLogger(__name__)

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

    def _get_unit(self, unit_name):
        units = UnitMapping(base = __class__.__base, limit = [unit_name])

        try:
            unit_list = [u for u in units]
            return unit_list[0]
        except MissingObjects as err:
            raise RuntimeError("Unit %s not found" % unit_name) from err

    def on_unit_list(self):
        for unit in UnitMapping():
            print(unit)

    def on_unit_show(self):
        unit_name = self._args.unit
        sub_tree = self._args.full

        unit = self._get_unit(unit_name)
        unit_dn = unit.entry_dn

        users = UserMapping(base = unit_dn, sub_tree = sub_tree)
        for uid in users.keys():
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
