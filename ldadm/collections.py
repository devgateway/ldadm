import copy, logging
try:
    from collections.abc import MutableMapping
except(ImportError):
    from collections import MutableMapping

from ldap3.utils.dn import escape_attribute_value, safe_dn
from ldap3 import ALL_ATTRIBUTES, ObjectDef, Reader, Writer

from .config import cfg

log = logging.getLogger(__name__)

class MissingObjects(Exception):
    def __init__(self, items):
        self.items = items

    def __str__(self):
        return "Objects not found: " + ", ".join(self.items)

class LdapObjectMapping(MutableMapping):
    _attribute = None

    def __init__(self, connection, base, object_def, limit = None, attrs = None):
        if not self.__class__._attribute:
            raise ValueError("Primary attribute must be defined")

        self._conn = connection
        self._base = base
        self._attrs = attrs
        self._object_def = object_def
        self.__queue = []

        if not limit:
            self._default_query = None
        elif type(limit) is str:
            self._default_query = limit
        else:
            try:
                self._default_query = self._build_query(ids)
            except TypeError as err:
                raise TypeError("limit must be a string or list of IDs") from err

    @staticmethod
    def _build_query(ids):
        return "%s: %s" % ( __class__._attribute, ";".join(list(ids)) )

    @staticmethod
    def _make_rdn(entry, new_val):
        attr = __class__._attribute
        # RDN can be an array: gn=John+sn=Doe
        old_rdn = safe_rdn(entry.entry_dn, decompose = True)
        new_rdn = []
        for key_val in old_rdn:
            if key_val[0] == attr:
                # primary ID element
                new_rdn.append( (key_val[0], new_val) )
            else:
                new_rdn.append(key_val)

        return "+".join( map(lambda key_val: "%s=%s" % key_val, new_rdn) )

    def _get_reader(self, ids = None):
        if ids:
            query = self._build_query(ids)
        else:
            query = self._default_query

        return Reader(
                connection = self._conn,
                base = self._base,
                query = query,
                object_def = self._object_def,
                sub_tree = True)

    def _get_writer(self, ids = None):
        attrs = self.__class__._attribute
        reader = self._get_reader(ids)
        reader.search(attrs)
        return Writer.from_cursor(reader)

    def _make_dn(self, attrs):
        attr = self.__class__._attribute
        key = attrs[attr]
        rdn = "=".join( [attr, escape_attribute_value(key)] )
        return safe_dn( [rdn, self._base] )

    def _get_dn(self, id):
        return self._getitem(id, attrs = None)["dn"]

    def __iter__(self):
        for value in self.values():
            yield value

    def values(self):
        reader = self._get_reader()
        results = reader.search_paged(
                paged_size = cfg.ldap.paged_search_size,
                attributes = self._attrs)
        for entry in results:
            yield entry

    def keys(self):
        attr = self.__class__._attribute
        reader = self._get_reader()
        results = reader.search_paged(
                paged_size = cfg.ldap.paged_search_size,
                attributes = attr)
        for entry in results:
            yield entry[attr].value

    def __contains__(self, id):
        raise NotImplementedError

    def __getitem__(self, id):
        raise NotImplementedError

    def __setitem__(self, id, attrs):
        # Create a new virtual object
        writer = self._get_writer([id])
        dn = self._make_dn(attrs)
        entry = writer.new(dn)

        # Set object properties from ciDict
        for key in attrs:
            setattr(entry, key, attrs[key])

        # Write the object to LDAP
        entry.entry_commit_changes(refresh = False)

    def __delitem__(self, id):
        self.__queue.append(id)

    def commit_delete(self):
        attr = self.__class__._attribute
        writer = self._get_writer(self.__queue)

        for entry in writer:
            key = entry[attr].value
            entry.entry_delete()
            self.__queue.remove(key)

        writer.commit()

        if self.__queue:
            raise MissingObjects(self.__queue)

    def move_all(self, dest):
        writer = self._get_writer()

        for entry in writer:
            entry.entry_move(dest._base)

        writer.commit(refresh = False)

    def rename(self, id, new_id):
        writer = self._get_writer([id])
        entry = writer.entries[0]
        rdn = self._make_rdn(entry, new_id)
        writer.entry_rename(rdn)
        writer.entry_commit_changes(refresh = False)

    def __len__(self):
        raise NotImplementedError

class UserMapping(LdapObjectMapping):
    _attribute = cfg.user.attr.uid
