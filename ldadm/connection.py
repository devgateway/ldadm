import logging

from ldap3 import Connection
from ldap3.utils.log import set_library_log_detail_level, PROTOCOL

from .config import cfg

log = logging.getLogger(__name__)

def _connect():
    try:
        binddn = cfg.ldap.binddn
        bindpw = cfg.ldap.bindpw
    except AttributeError:
        binddn = None
        bindpw = None

    if log.isEnabledFor(logging.DEBUG):
        set_library_log_detail_level(PROTOCOL)

    conn = Connection(
            server = cfg.ldap.uri,
            user = binddn,
            password = bindpw,
            raise_exceptions = True)
    conn.bind()

    return conn

ldap = _connect()
