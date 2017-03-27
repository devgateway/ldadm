import logging, sys

import ldap3
from ldap3 import Connection
from ldap3.utils.dn import safe_rdn
from ldap3.utils.log import set_library_log_detail_level, PROTOCOL

from .config import cfg

log = logging.getLogger(__name__)

class Command:
    def __init__(self, args):
        self._args = args
        self._conn = self._connect()

    def _connect(self):
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

    def _args_or_stdin(self, argname):
        args = getattr(self._args, argname)
        if args:
            if not sys.__stdin__.isatty():
                log.warning("Standard input ignored, because arguments are present")
            if hasattr(args[0], "read"):
                with args[0] as file_object:
                    for line in file_object:
                        yield line[:-1] # in text mode linesep is always "\n"
            else:
                for arg in args:
                    yield arg
        else:
            with sys.__stdin__ as file_object:
                for line in file_object:
                    yield line[:-1] # in text mode linesep is always "\n"
