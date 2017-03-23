import copy, logging
try:
    from collections.abc import MutableMapping
except(ImportError):
    from collections import MutableMapping

from ldap3.utils.dn import escape_attribute_value, safe_dn

log = logging.getLogger(__name__)

class MissingObjects(Exception):
    def __init__(self, items):
        self.items = items

    def __str__(self):
        return "Objects not found: " + ", ".join(self.items)

class LdapObjectMapping(MutableMapping):
    _attribute = None

    def __init__(self, connection, base, object_def, attrs, query = None):
        if not self.__class__._attribute:
            raise ValueError("Primary attribute must be defined")

        self._conn = connection
        self._base = base
        self._attrs = attrs
        self._reader = None
        self._query = query
        self._object_def = object_def
        self._ldap_cfg = Config().ldap
        self.__queue = []

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

    def _get_reader(self, query = None):
        return Reader(
                connection = self._conn,
                base = base,
                query = query,
                object_def = self._object_def,
                sub_tree = True)

    def _get_writer(self, query = None, attrs = None):
        reader = self._get_reader(query)
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
        attr = self.__class__._attribute
        reader = self._get_reader()
        results = reader.search_paged(
                paged_size = self._ldap_cfg.paged_search_size,
                attributes = self._attrs)
        for entry in results:
            yield entry

    def keys(self):
        attr = self.__class__._attribute
        reader = self._get_reader()
        results = reader.search_paged(
                paged_size = self._ldap_cfg.paged_search_size,
                attributes = attr)
        for entry in results:
            yield entry[attr].value

    def __contains__(self, id):
        raise NotImplementedError

    def __getitem__(self, id):
        raise NotImplementedError

    def __setitem__(self, id, attrs):
        # Create a new virtual object
        attr = self.__class__._attribute
        dn = self._make_dn(attrs)
        query = "%s: %s" % (attr, id)
        writer = self._get_writer(query = query)
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
        query = attr + ": " + ";".join(self.__queue)
        writer = self._get_writer(query = query, attrs = attr)

        for entry in writer:
            key = entry[attr].value
            entry.entry_delete()
            self.__queue.remove(key)

        writer.commit()

        if self.__queue:
            raise MissingObjects(self.__queue)

    def move(self, ids, dest):
        attr = self.__class__._attribute
        base_to = dest._base
        query = attr + ": " + ";".join(ids)

        writer = self._get_writer(query = query, attrs = attr)
        for entry in writer:
            key = entry[attr].value
            entry.entry_move(base_to)
            ids.remove(key)

        writer.commit(refresh = False)

        if ids:
            raise MissingObjects(ids)

    def rename(self, id, new_id):
        attr = self.__class__._attribute
        query = "%s: %s" % (attr, id)
        writer = self._get_writer(query = query)
        entry = writer.entries[0]
        rdn = self._make_rdn(entry, new_id)
        writer.entry_rename(rdn)
        writer.entry_commit_changes(refresh = False)

    def __len__(self):
        raise NotImplementedError

class UserMapping(LdapObjectMapping):
    _attribute = cfg.user.attr.uid
