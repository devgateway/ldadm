try:
    from collections.abc import MutableMapping
except(ImportError):
    from collections import MutableMapping

import ldap3

from .config import cfg
from .ldap import ldap
