import copy, logging
try:
    from collections.abc import MutableMapping
except ImportError:
    from collections import MutableMapping

from ldap3.utils.dn import escape_attribute_value, safe_dn, safe_rdn
from ldap3 import ALL_ATTRIBUTES, ObjectDef, Reader, Writer

from .config import cfg
from .connection import ldap
from .objects import User, Unit, Project

log = logging.getLogger(__name__)

class MissingObjects(Exception):
    def __init__(self, name, items):
        self.name = name
        self.items = items

    def __str__(self):
        items = ", ".join(list(self.items))
        return "%s not found: %s" % (self.name, items)

class LdapObjectMapping(MutableMapping):
    _attribute = None
    _name = "Objects"

    def __init__(self, base = None, sub_tree = True, attrs = None):
        if not self.__class__._attribute:
            raise ValueError("Primary attribute must be defined")

        if base:
            self._base = base
        else:
            self._base = self.__class__._base

        self._attrs = attrs
        self._sub_tree = sub_tree
        self._select = None

    def select(self, criteria):
        if type(criteria) is str or criteria is None:
            self._select = criteria
        else:
            self._select = set(criteria)

        return self

    @classmethod
    def _make_rdn(cls, entry, new_val):
        # RDN can be an array: gn=John+sn=Doe
        old_rdn = safe_rdn(entry.entry_dn, decompose = True)
        new_rdn = []
        for key_val in old_rdn:
            if key_val[0] == cls._attribute:
                # primary ID element
                new_rdn.append( (key_val[0], new_val) )
            else:
                new_rdn.append(key_val)

        return "+".join( map(lambda key_val: "%s=%s" % key_val, new_rdn) )

    def _get_reader(self, ids = None):
        if ids:
            query = self.__class__._attribute + ": " + ";".join(ids)
        elif type(self._select) is set:
            query = self.__class__._attribute + ": " + ";".join(list(self._select))
        else:
            query = self._select

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
        id_attr = self.__class__._attribute
        key = attrs[id_attr]
        rdn = "=".join( [id_attr, escape_attribute_value(key)] )
        return safe_dn( [rdn, self._base] )

    def __iter__(self):
        return self.keys()

    def values(self):
        id_attr = self.__class__._attribute
        if self._attrs == ALL_ATTRIBUTES:
            requested_attrs = self._attrs
        elif self._attrs is None:
            requested_attrs = []
        elif type(self._attrs) is not list:
            requested_attrs = [self._attrs]

        if type(requested_attrs) is list:
            if id_attr not in requested_attrs:
                requested_attrs.append(id_attr)

        reader = self._get_reader()
        results = reader.search_paged(
                paged_size = cfg.ldap.paged_search_size,
                attributes = requested_attrs)
        found = set()
        for entry in results:
            id = entry[id_attr].value
            found.add(id)
            yield entry

        self.__assert_found_all(found)

    def keys(self):
        id_attr = self.__class__._attribute
        reader = self._get_reader()
        results = reader.search_paged(
                paged_size = cfg.ldap.paged_search_size,
                attributes = self.__class__._attribute)
        found = set()
        for entry in results:
            id = entry[id_attr].value
            found.add(id)
            yield id

        self.__assert_found_all(found)

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
        raise NotImplementedError

    def delete(self):
        id_attr = self.__class__._attribute
        writer = self._get_writer()

        found = set()
        for entry in writer:
            id = entry[id_attr].value
            found.add(id)
            entry.entry_delete()

        writer.commit(refresh = False)

        self.__assert_found_all(found)

    def move(self, dest):
        id_attr = self.__class__._attribute
        try:
            new_base = dest._base
        except AttributeError:
            new_base = dest

        writer = self._get_writer()

        found = set()
        for entry in writer:
            id = entry[id_attr].value
            found.add(id)
            entry.entry_move(new_base)

        writer.commit(refresh = False)

        self.__assert_found_all(found)

    def __assert_found_all(self, found):
        """Raise an exception if not all selected items have been found."""
        try:
            not_found = self._select - found
        except TypeError: # did not select by list
            return

        if not_found:
            raise MissingObjects(self.__class__._name, not_found)

    def rename(self, id, new_id):
        writer = self._get_writer([id])
        entry = writer.entries[0]
        rdn = self._make_rdn(entry, new_id)
        entry.entry_rename(rdn)
        writer.commit(refresh = False)

    def __len__(self):
        raise NotImplementedError

    def __bool__(self):
        for item in self.keys():
            return False

        return True

class UserMapping(LdapObjectMapping):
    _name = "Users"
    _attribute = cfg.user.attr.uid
    _object_def = User._object_def

class UnitMapping(LdapObjectMapping):
    _name = "Units"
    _attribute = "organizationalUnitName"
    _object_def = Unit._object_def

class ProjectMapping(LdapObjectMapping):
    _name = "Projects"
    _attribute = cfg.project.attr.id
    _object_def = Project._object_def
    _base = cfg.project.base
