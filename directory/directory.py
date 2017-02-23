try:
    from collections.abc import MutableMapping
except(ImportError):
    from collections import MutableMapping

import ldap3

from .config import cfg
from .ldap import ldap

class DirectoryMapping(MutableMapping):
    def __init__(self, base, attrs = None):
        self._base = base
        self._attrs = attrs

    def _getitem(self, id, attrs = None):
        ldap.search(
                search_base = self._base,
                search_filter = "(%s=%s)" % (__class__._id_attr, id),
                search_scope = __class__._scope,
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
                search_scope = self._scope,
                attributes = self._attrs)

    def __iter__(self):
        self.search( "(%s=*)" % __class__._id_attr )

    def __contains__(self, id):
        try:
            self.__getitem__(id, attrs = None)
            return True
        except IndexError:
            return False

    def __getitem__(self, id):
        self._getitem(id, attrs = self._attrs)

    def __setitem__(self, id, entry):
        dn = self._get_dn(id)
        ldap.add(dn, object_class = None, attributes = entry)

    def __delitem__(self, id):
        dn = self._get_dn(id)
        ldap.delete(dn)

    def move(self, id, dest):
        if not isinstance(dest, __class__):
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
            if rdn[0] == __class__._id_attr:
                # primary ID element
                new_rdns.append( (rdn[0], new_val) )
            else:
                new_rdns.append(rdn)
        new_rdn = "+".join(new_rdns)

        self._ldap.modify_dn(dn = dn, relative_dn = new_rdn)

    def __len__(self):
        raise NotImplementedError

class DirectoryObject:
    def __init__(self, id):
        self._id = id
        self._dn = None
        self._attrs = {}

    def __str__(self):
        return self._id
