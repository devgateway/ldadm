import logging

import ldap3

import settings

class Command:
    def __init__(self, args):
        self._args = args

        self._cfg = settings.Config()
        cfg = self._cfg.ldap

        try:
            binddn = cfg.binddn
            bindpw = cfg.bindpw
        except AttributeError:
            binddn = None
            bindpw = None

        self._ldap = ldap3.Connection(
                server = cfg.uri,
                user = binddn,
                password = bindpw,
                raise_exceptions = True)
        self._ldap.bind()

class UserCommand(Command):
    def list_users(self):
        search = settings.LdapSearch(self._cfg.user)
        attr = self._cfg.user.attr
        generator = self._ldap.extend.standard.paged_search(
                search_base = search.base,
                search_filter = search.filter,
                search_scope = search.scope,
                attributes = [attr])
        for entry in generator:
            print(entry["attributes"][attr][0])

#    def search(self):
#    def show(self):
#    def suspend(self):
#    def restore(self):
#    def delete(self):
#    def add(self):
#    def rename(self):
#    def list_keys(self):
    def add_key(self):
        pass
#    def delete_key(self):
