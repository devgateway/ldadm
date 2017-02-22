try:
    from collections.abc import MutableMapping
except(ImportError):
    from collections import MutableMapping

import ldap3

from .config import cfg
from .ldap import ldap

class DirectoryMapping(MutableMapping):
    def __init__(self, attrs = None):
        self._attrs = attrs

    def _getitem(self, id, attrs = None):
        ldap.search(
                search_base = __class__._base,
                search_filter = "(%s=%s)" % (__class__._id_attr, id),
                search_scope = __class__._scope,
                attributes = attrs,
                size_limit = 1)

        if ldap.response:
            return ldap.response[0]
        else:
            raise IndexError(id)

    def _get_dn(self, id):
        return self._getitem(id, attrs = None)["dn"]

    def search(self, filter):
        return ldap.extend.standard.paged_search(
                search_base = __class__._base,
                search_filter = filter,
                search_scope = self._scope,
                attributes = self._attrs)

    def __contains__(self, id):
        try:
            self.__getitem__(id, attrs = None)
            return True
        except IndexError:
            return False

    def __getitem__(self, id):
        self._getitem(id, attrs = self._attrs)

class DirectoryObject:
    def __init__(self, id):
        self._id = id
        self._dn = None
        self._attrs = {}

    def __str__(self):
        return self._id
