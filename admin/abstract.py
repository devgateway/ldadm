try:
    from collections.abc import MutableMapping
except(ImportError):
    from collections import MutableMapping

import ldap3

class DirectoryMapping(MutableMapping):
    def __init__(self):

class Directory:
    """Singleton"""

    class _inner:
        pass

    __instance = None

    def __init__(self):
        if not __class__.__instance:
            __class__.__instance = __class__._inner()

