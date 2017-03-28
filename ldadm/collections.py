import copy, logging
try:
    from collections.abc import MutableMapping
except ImportError:
    from collections import MutableMapping

from ldap3.utils.dn import escape_attribute_value, safe_dn, safe_rdn
from ldap3 import ALL_ATTRIBUTES, ObjectDef, Reader, Writer

from .config import cfg
from .connection import ldap
from .objects import User, Unit

log = logging.getLogger(__name__)

class MissingObjects(Exception):
    def __init__(self, items):
        self.items = items

    def __str__(self):
        return "Objects not found: " + ", ".join(self.items)

class LdapObjectMapping(MutableMapping):
    _attribute = None

    def __init__(self, base, sub_tree = True, limit = None, attrs = None):
        if not self.__class__._attribute:
            raise ValueError("Primary attribute must be defined")

        self._base = base
        self._attrs = attrs
        self._sub_tree = sub_tree
        self.__queue = []

        if not limit:
            self._default_query = ""
        elif type(limit) is str:
            self._default_query = limit
        else:
            try:
                self._default_query = self.__class__._build_query(limit)
                self.__queue = list(limit)
            except TypeError as err:
                raise TypeError("limit must be a string or list of IDs") from err

    @classmethod
    def _build_query(cls, ids):
        return "%s: %s" % ( cls._attribute, ";".join(list(ids)) )

    @classmethod
    def _make_rdn(cls, entry, new_val):
        attr = cls._attribute
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
            query = self.__class__._build_query(ids)
            self.__queue = list(ids)
        else:
            query = self._default_query

        return Reader(
                connection = ldap,
                base = self._base,
                query = query,
                object_def = self.__class__._object_def,
                sub_tree = self._sub_tree)

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

    def __iter__(self):
        return self.values()

    def values(self):
        attr = self.__class__._attribute
        if self._attrs == ALL_ATTRIBUTES:
            requested_attrs = self._attrs
        elif self._attrs is None:
            requested_attrs = []
        elif type(self._attrs) is not list:
            requested_attrs = [self._attrs]

        if type(requested_attrs) is list:
            if attr not in requested_attrs:
                requested_attrs.append(attr)

        reader = self._get_reader()
        results = reader.search_paged(
                paged_size = cfg.ldap.paged_search_size,
                attributes = requested_attrs)
        for entry in results:
            id = entry[attr].value
            try:
                self.__queue.remove(id)
            except ValueError:
                pass

            yield entry

        if self.__queue:
            raise MissingObjects(self.__queue)

    def keys(self):
        attr = self.__class__._attribute
        reader = self._get_reader()
        results = reader.search_paged(
                paged_size = cfg.ldap.paged_search_size,
                attributes = attr)
        for entry in results:
            id = entry[attr].value
            try:
                self.__queue.remove(id)
            except ValueError:
                pass
            yield id

        if self.__queue:
            raise MissingObjects(self.__queue)

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

        writer.commit(refresh = False)

        if self.__queue:
            raise MissingObjects(self.__queue)

    def move_all(self, dest):
        attr = self.__class__._attribute
        try:
            new_base = dest._base
        except AttributeError:
            new_base = dest

        writer = self._get_writer()

        for entry in writer:
            key = entry[attr].value
            entry.entry_move(new_base)
            self.__queue.remove(key)

        writer.commit(refresh = False)

        if self.__queue:
            raise MissingObjects(self.__queue)

    def rename(self, id, new_id):
        writer = self._get_writer([id])
        entry = writer.entries[0]
        rdn = self._make_rdn(entry, new_id)
        entry.entry_rename(rdn)
        writer.commit(refresh = False)

    def __len__(self):
        raise NotImplementedError

    def is_empty(self):
        for item in self.values():
            return False

        return True

class UserMapping(LdapObjectMapping):
    _attribute = cfg.user.attr.uid
    _object_def = User._object_def

class UnitMapping(LdapObjectMapping):
    _attribute = "organizationalUnitName"
    _object_def = Unit._object_def
