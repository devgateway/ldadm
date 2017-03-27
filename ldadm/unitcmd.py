import logging

from ldap3.core.exceptions import LDAPEntryAlreadyExistsResult, LDAPKeyError
from ldap3.core.exceptions import LDAPAttributeOrValueExistsResult
from ldap3.utils.dn import escape_attribute_value, safe_dn

from .command import Command
from .collections import UnitMapping
from .config import cfg

log = logging.getLogger(__name__)

class UnitCommand(Command):
    __base = cfg.user.base.active

    def on_list(self):
        units = UnitMapping(base = __class__.__base)
        for name in units.keys():
            print(name)
