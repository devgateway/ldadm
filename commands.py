import logging
import sys
import functools

import ldap3

import settings

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

def pretty_print(entry):
    attrs = entry["attributes"]
    width = len( functools.reduce(longest_str, attrs) ) + 1
    formatter = "{:%is} {:s}" % width

    for key in sorted(attrs):
        values = attrs[key]
        if type(values) is list:
            first_value = values.pop(0)
            print( formatter.format(key + ":", str(first_value)) )
            for value in values:
                print( formatter.format("", str(value)) )

        else:
            print( formatter.format(key + ":", str(values)) )

    print()

longest_str = lambda x, y: x if len(x) > len(y) else y

class NotFound(Exception):
    pass

class Command:
    def __init__(self, args):
        self._args = args

        self._cfg = settings.Config()
        ldap = self._cfg.ldap

        try:
            binddn = ldap.binddn
            bindpw = ldap.bindpw
        except AttributeError:
            binddn = None
            bindpw = None

        self._ldap = ldap3.Connection(
                server = ldap.uri,
                user = binddn,
                password = bindpw,
                raise_exceptions = True)
        self._ldap.bind()

    def _args_or_stdin(self, argname):
        args = getattr(self._args, argname)
        if args:
            if not sys.__stdin__.isatty():
                logging.warning("Standard input ignored, because arguments are present")
            for arg in args:
                yield arg
        else:
            with sys.__stdin__ as stdin:
                for line in stdin:
                    yield line[:-1]

class UserCommand(Command):
    def _search_users(self, filt):
        user = self._cfg.user
        logging.debug("Search '%s' in '%s' scope %s" % (filt, user.base, user.scope))
        entries = self._ldap.extend.standard.paged_search(
                search_base = user.base,
                search_filter = filt,
                search_scope = scope(user.scope),
                attributes = user.attr)
        for entry in entries:
            print(entry["attributes"][user.attr][0])

    def _get_single_entry(self, username, active = True, attrs = None):
        user = self._cfg.user
        filt = "(%s=%s)" % (user.attr, username)
        if active:
            base = user.base
        else:
            base = self._cfg.suspended.base

        logging.debug("Search '%s' in '%s' scope %s" % (filt, user.base, user.scope))
        generator = self._ldap.search(
                search_base = base,
                search_filter = filt,
                search_scope = scope(user.scope),
                attributes = attrs,
                size_limit = 1)

        if self._ldap.response:
            return self._ldap.response[0]
        else:
            msg = "User %s not found" % username
            logging.error(msg)
            raise NotFound(msg)

    def list_users(self):
        self._search_users("(%s=*)" % self._cfg.user.attr)

    def search(self):
        self._search_users(self._args.filter)

    def show(self):
        for username in self._args_or_stdin("username"):
            try:
                entry = self._get_single_entry(username, attrs = ldap3.ALL_ATTRIBUTES)
                pretty_print(entry)
            except NotFound as err:
                pass


#    def suspend(self):
#    def restore(self):
#    def delete(self):
#    def add(self):
#    def rename(self):
#    def list_keys(self):
    def add_key(self):
        pass
#    def delete_key(self):
