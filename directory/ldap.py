import logging

import ldap3

from .config import cfg

log = logging.getLogger()

def scope(scope_str):
    scopes = {
            "base": ldap3.BASE,
            "one": ldap3.LEVEL,
            "sub": ldap3.SUBTREE
            }
    try:
        return scopes[scope_str.lower()]
    except KeyError as key:
        msg = "Scope must be %s, not '%s'" % ("|".join(scopes), scope_str)
        raise ValueError(msg) from key

def _get_ldap():
    try:
        binddn = cfg.ldap.binddn
        bindpw = cfg.ldap.bindpw
    except AttributeError:
        binddn = None
        bindpw = None

    if log.isEnabledFor(logging.DEBUG):
        ldap3.utils.log.set_library_log_detail_level(ldap3.utils.log.PROTOCOL)

    conn = ldap3.Connection(
            server = cfg.ldap.uri,
            user = binddn,
            password = bindpw,
            raise_exceptions = True)
    conn.bind()

    return conn

ldap = _get_ldap()
