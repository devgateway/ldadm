import logging

from ldap3.core.exceptions import LDAPEntryAlreadyExistsResult, LDAPKeyError, \
        LDAPAttributeOrValueExistsResult

from .command import Command
from .collections import UnitMapping, UserMapping, MissingObjects
from .config import cfg
from .objects import Unit

log = logging.getLogger(__name__)

class UnitCommand(Command):
    __base = cfg.user.base.active

    def _get_unit(self, unit_name):
        units = UnitMapping(base = __class__.__base, limit = [unit_name])

        try:
            unit_list = [u for u in units]
            return unit_list[0]
        except MissingObjects as err:
            raise RuntimeError("Unit %s not found" % unit_name) from err

    def on_list(self):
        units = UnitMapping(base = __class__.__base)
        for name in units.keys():
            print(name)

    def on_show(self):
        unit_name = self._args.unit
        sub_tree = self._args.full

        unit = self._get_unit(unit_name)
        unit_dn = unit.entry_dn

        users = UserMapping(base = unit_dn, sub_tree = sub_tree)
        for uid in users.keys():
            print(uid)

    def on_add(self):
        parent_name = self._args.parent
        if parent_name:
            parent = self._get_unit(parent_name)
            base = parent.entry_dn
        else:
            base = __class__.__base

        unit = Unit()
        ou = unit.attrs[UnitMapping._attribute]
        subunits = UnitMapping(base = base)
        subunits[ou] = unit.attrs

        if unit.message:
            print(unit.message)
