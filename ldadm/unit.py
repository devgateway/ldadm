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

    def __init__(self, base, child_mapping_class):
        super().__init__(self, base = base)
        self._base = base

    def add(self, parent_name):
        unit = Unit()
        ou = unit.attrs[UnitMapping._attribute]

        if parent_name:
            parent = UnitMapping()[parent_name]
            base = parent.entry_dn
        else:
            base = self._base

        subunits = UnitMapping(base = base)
        subunits[ou] = unit.attrs

        if unit.message:
            print(unit.message)
