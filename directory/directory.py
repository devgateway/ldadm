import copy
try:
    from collections.abc import MutableMapping
except(ImportError):
    from collections import MutableMapping

import ldap3

from .config import cfg
from .ldap import ldap, scope

class DirectoryMapping(MutableMapping):
    def __init__(self, base, attrs):
        self._base = base
        self._attrs = attrs

    def _getitem(self, id, attrs = None):
        ldap.search(
                search_base = self._base,
                search_filter = "(%s=%s)" % (self.__class__._id_attr, id),
                search_scope = self.__class__._scope,
                attributes = attrs,
                size_limit = 1)

        if ldap.response:
            return ldap.response[0]
        else:
            raise IndexError(id)

    def _get_dn(self, id):
        return self._getitem(id, attrs = None)["dn"]

    def search(self, filter):
        return ldap.extend.standard.paged_search(
                search_base = self._base,
                search_filter = filter,
                search_scope = self.__class__._scope,
                attributes = self._attrs)

    def __iter__(self):
        filter = "(%s=*)" % self.__class__._id_attr
        for entry in self.search(filter):
            yield entry["attributes"][self.__class__._id_attr][0]

    def __contains__(self, id):
        try:
            self.__getitem__(id)
            return True
        except IndexError:
            return False

    def __getitem__(self, id):
        return self._getitem(id, attrs = self._attrs)

    def __setitem__(self, id, entry):
        dn = self._get_dn(id)
        ldap.add(dn, object_class = None, attributes = entry)

    def __delitem__(self, id):
        dn = self._get_dn(id)
        ldap.delete(dn)

    def move(self, id, dest):
        if not isinstance(dest, self.__class__):
            raise TypeError("Can't move to different object type")

        dn = self._get_dn(id)
        rdn = "+".join( ldap3.utils.dn.safe_rdn(dn) )
        ldap.modify_dn(
                dn = dn,
                relative_dn = rdn,
                new_superior = dest._base)

    def rename(self, id, new_id):
        dn = self._get_dn(id)

        # RDN can be an array: gn=John+sn=Doe
        rdns = ldap3.utils.dn.safe_rdn(dn, decompose = True)
        new_rdns = []
        for rdn in rdns:
            if rdn[0] == self.__class__._id_attr:
                # primary ID element
                new_rdns.append( (rdn[0], new_val) )
            else:
                new_rdns.append(rdn)
        new_rdn = "+".join(new_rdns)

        self._ldap.modify_dn(dn = dn, relative_dn = new_rdn)

    def __len__(self):
        raise NotImplementedError

class UserMapping(DirectoryMapping):
    _id_attr = cfg.user.attr.uid
    _scope = scope(cfg.user.scope)

class DirectoryObject():
    def __init__(self, ref = None):
        if ref is None:
            self._dn = None
            self._attrs = {}
        elif type(ref) is dict:
            self._dn = ref["dn"]
            self._attrs = ref["attributes"]
        elif isinstance(ref, self.__class__):
            self._dn = None
            self._attrs = copy.deepcopy(peer._attrs)
            del self._attrs[self.__class__._id_attr]
        else:
            print(repr(ref))
            raise TypeError

    def __str__(self):
        return self._attrs[self.__class__._id_attr][0]

    def __repr__(self):
        return "DN: %s\nattrs: %s" % (self._dn, repr(self._attrs))

class User(DirectoryObject):
    _id_attr = cfg.user.attr.uid

class Directory():
    def active_users(self, attrs = None):
        return UserMapping(cfg.user.base.active, attrs)

    def suspended_users(self, attrs = None):
        return UserMapping(cfg.user.base.suspended, attrs)
