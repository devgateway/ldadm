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
    logging.debug(formatter)

    for (key, values) in attrs.items():
        first_value = values.pop(0)
        print( formatter.format(key + ":", str(first_value)) )
        for value in values:
            print( formatter.format("", str(value)) )

    print()

longest_str = lambda x, y: x if len(x) > len(y) else y

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
    def list_users(self):
        user = self._cfg.user
        generator = self._ldap.extend.standard.paged_search(
                search_base = user.base,
                search_filter = user.filter,
                search_scope = scope(user.scope),
                attributes = [user.attr])
        for entry in generator:
            print(entry["attributes"][user.attr][0])

    def search(self):
        user = self._cfg.user
        filt = self._args.filter
        generator = self._ldap.extend.standard.paged_search(
                search_base = user.base,
                search_filter = filt,
                search_scope = scope(user.scope),
                attributes = [user.attr])
        for entry in generator:
            print(entry["attributes"][user.attr][0])

    def show(self):
        for username in self._args_or_stdin("username"):
            user = self._cfg.user
            filt = "(%s=%s)" % (user.attr, username)

            generator = self._ldap.extend.standard.paged_search(
                    search_base = user.base,
                    search_filter = filt,
                    search_scope = scope(user.scope),
                    attributes = ldap3.ALL_ATTRIBUTES)

            for entry in generator:
                pretty_print(entry)

#    def suspend(self):
#    def restore(self):
#    def delete(self):
#    def add(self):
#    def rename(self):
#    def list_keys(self):
    def add_key(self):
        pass
#    def delete_key(self):
