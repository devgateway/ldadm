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
    def output(k, v):
        try:
            s = v.decode("utf-8")
        except AttributeError:
            s = str(v)

        print(formatter.format(k, s))

    attrs = entry["attributes"]
    width = len( functools.reduce(longest_str, attrs) ) + 1
    formatter = "{:%is} {:s}" % width

    for key in sorted(attrs):
        values = attrs[key]
        if type(values) is list:
            first_value = values.pop(0)
            output(key + ":", first_value)
            for value in values:
                output("", value)

        else:
            output(key + ":", values)

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

    def _move_entry(self, dn, new_superior):
        rdn = "+".join( ldap3.utils.dn.safe_rdn(dn) )
        logging.debug("Moving %s to %s, keeping RDN %s" % (dn, new_superior, rdn))
        self._ldap.modify_dn(
                dn = dn,
                relative_dn = rdn,
                new_superior = new_superior)

    def _rename_entry(self, dn, attr, new_val):
        rdns = ldap3.utils.dn.safe_rdn(dn, decompose = True)
        new_rdns = []
        for rdn in rdns:
            if rdn[0] == attr:
                new_rdns.append( (rdn[0], new_val) )
            else:
                new_rdns.append(rdn)

        new_rdn = "+".join(new_rdns)
        logging.debug("Renaming %s to RDN %s" % (dn, new_rdn))
        self._ldap.modify_dn(dn = dn, relative_dn = new_rdn)

    def _delete_entry(self, dn):
        logging.debug("Deleting %s" % dn)
        self._ldap.delete(dn)

class UserCommand(Command):
    def _search_users(self, filt):
        user = self._cfg.user
        if self._args.suspended:
            base = self._cfg.suspended.base
        else:
            base = user.base

        logging.debug("Search '%s' in '%s' scope %s" % (filt, base, user.scope))
        entries = self._ldap.extend.standard.paged_search(
                search_base = base,
                search_filter = filt,
                search_scope = scope(user.scope),
                attributes = user.uid.attr)
        for entry in entries:
            print(entry["attributes"][user.uid.attr][0])

    def _get_single_entry(self, username, active = True, attrs = None):
        user = self._cfg.user
        filt = "(%s=%s)" % (user.uid.attr, username)
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
        self._search_users("(%s=*)" % self._cfg.user.uid.attr)

    def search(self):
        self._search_users(self._args.filter)

    def show(self):
        for username in self._args_or_stdin("username"):
            try:
                entry = self._get_single_entry(username, attrs = ldap3.ALL_ATTRIBUTES)
                pretty_print(entry)
            except NotFound as err:
                pass

    def suspend(self):
        for username in self._args_or_stdin("username"):
            dn = self._get_single_entry(username)["dn"]
            self._move_entry(dn, self._cfg.suspended.base)

    def restore(self):
        for username in self._args_or_stdin("username"):
            dn = self._get_single_entry(username, active = False)["dn"]
            self._move_entry(dn, self._cfg.user.base)

    def delete(self):
        for username in self._args_or_stdin("username"):
            dn = self._get_single_entry(username, active = False)["dn"]
            self._delete_entry(dn)

#    def add(self):
#    def rename(self):
#    def list_keys(self):
    def add_key(self):
        pass
#    def delete_key(self):
