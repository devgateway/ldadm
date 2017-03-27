import logging

from ldap3 import ALL_ATTRIBUTES, ObjectDef, Reader, Writer
from ldap3.core.exceptions import LDAPEntryAlreadyExistsResult, LDAPKeyError
from ldap3.core.exceptions import LDAPAttributeOrValueExistsResult
from ldap3.utils.dn import escape_attribute_value, safe_dn

from .command import Command

log = logging.getLogger(__name__)

class UnitCommand(Command):
    __attr = "organizationalUnitName"

    def __init__(self, args):
        super().__init__(args)

        object_class = ["organizationalUnit"]
        self.__unit = ObjectDef(
                object_class = object_class,
                schema = self._conn)

    def on_list(self):
        base = self._cfg.user.base.active

        reader = Reader(
                connection = self._conn,
                base = base,
                query = None,
                object_def = self.__unit,
                sub_tree = True)
        units = reader.search_paged(
                paged_size = self._cfg.ldap.paged_search_size,
                attributes = self.__attr)

        for unit in units:
            print(unit[self.__attr])
