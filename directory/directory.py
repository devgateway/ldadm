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

class DirectoryObject:
    def __init__(self, id):
        self._id = id
        self._dn = None
        self._attrs = {}

    def __str__(self):
        return self._id
