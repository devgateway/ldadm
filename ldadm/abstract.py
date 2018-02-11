# Copyright 2017, Development Gateway, Inc.
# This file is part of ldadm, see COPYING.

import logging, re, copy
try:
    import secrets # Python 3.6+
except ImportError:
    import random
try:
    from collections.abc import MutableMapping
except ImportError:
    from collections import MutableMapping

from ldap3 import ALL_ATTRIBUTES, Reader, Writer
from ldap3.utils.ciDict import CaseInsensitiveWithAliasDict
from ldap3.utils.dn import safe_dn, safe_rdn
from ldap3.core.exceptions import LDAPKeyError

from .config import cfg, ConfigAttrError
from .console import input_stderr
from .connection import ldap

log = logging.getLogger(__name__)

# these constants and escape_attribute_value() taken from ldap3 library:
# https://github.com/cannatag/ldap3
# Copyright 2014 - 2018 Giovanni Cannata
# Used under LGPLv3
STATE_ANY = 0
STATE_ESCAPE = 1
STATE_ESCAPE_HEX = 2

def escape_attribute_value(attribute_value):
    if not attribute_value:
        return ''

    if attribute_value[0] == '#':  # with leading SHARP only pairs of hex characters are valid
        valid_hex = True
        if len(attribute_value) % 2 == 0:  # string must be # + HEX HEX (an odd number of chars)
            valid_hex = False

        if valid_hex:
            for c in attribute_value:
                if c not in hexdigits:  # allowed only hex digits as per RFC 4514
                    valid_hex = False
                    break

        if valid_hex:
            return attribute_value

    state = STATE_ANY
    escaped = ''
    tmp_buffer = ''
    for c in attribute_value:
        if state == STATE_ANY:
            if c == '\\':
                state = STATE_ESCAPE
            elif c in '"#+,;<=>\00':
                escaped += '\\' + c
            else:
                escaped += c
        elif state == STATE_ESCAPE:
            if c in hexdigits:
                tmp_buffer = c
                state = STATE_ESCAPE_HEX
            elif c in ' "#+,;<=>\\\00':
                escaped += '\\' + c
                state = STATE_ANY
            else:
                escaped += '\\\\' + c
        elif state == STATE_ESCAPE_HEX:
            if c in hexdigits:
                escaped += '\\' + tmp_buffer + c
            else:
                escaped += '\\\\' + tmp_buffer + c
            tmp_buffer = ''
            state = STATE_ANY

    # final state
    if state == STATE_ESCAPE:
        escaped += '\\\\'
    elif state == STATE_ESCAPE_HEX:
        escaped += '\\\\' + tmp_buffer

    if escaped[0] == ' ':  # leading SPACE must be escaped
        escaped = '\\' + escaped

    # trailing SPACE must be escaped
    if escaped[-1] == ' ' and len(escaped) > 1 and escaped[-2] != '\\':
        escaped = escaped[:-1] + '\\ '

    return escaped

def entry_name(entry, name_attr):
    """Return consistent scalar entry common name."""

    values = entry[name_attr].values

    if len(values) == 1:
        # if there's just one value, use it
        name = values[0]
    else:
        name_vals = set(values)

        # find, if any of them are in RDN
        rdn_vals = set()
        for component in safe_rdn(entry.entry_dn, decompose = True):
            if component[0] == name_attr:
                rdn_vals.add(component[1])

        common_vals = rdn_vals & name_vals
        matched = len(common_vals)
        if matched == 1:
            # only one value used in RDN
            name = list(common_vals)[0]
        elif matched:
            # multiple values in RDN; use first of them alphabetically
            name = sorted(list(common_vals))[0]
        else:
            # none in RDN at all; use first name alphabetically
            name = sorted(list(name_vals))[0]

    return name

class MissingObjects(Exception):
    def __init__(self, name, items):
        self.name = name
        self.items = items

    def __str__(self):
        items = ", ".join(list(self.items))
        return "%s not found: %s" % (self.name, items)

class NothingSelected(ValueError):
    pass

#### How to use this MutableMapping
### List IDs:
# for key in mapping:
#     print(key)

### List items:
# for entry in mapping.items():
#     yada(entry)

### Search by ldap3 simplified query:
# for key in mapping.select( 'uidNumber: 42; 43' ):
#     print(key)

### Search by filter:
# for key in mapping.select( '(&(givenName=Not)(surname=Sure))' ):
#     print(key)

### Search by ID list:
# for key in mapping.select( ['foo', 'bar'] ):
#     print(key)

### Delete:
# mapping.select(['foo', 'bar']).delete()

### Get entry:
# entry = mapping['foo']

### Set entry:
# mapping['foo'] = attrs

### Check if empty:
# if mapping:
#     yada

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

    @staticmethod
    def _get_dn(names, mapping):
        if type(names) is list:
            name_list = names
        else:
            name_list = [names]

        mapping.select(name_list)

        results = list( mapping.dns() )

        if type(names) is list:
            return results
        else:
            return results[0]

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
            # simplified query language can't search by multi-value attrs;
            # take just the first value then
            criteria = map(lambda x: x[0] if type(x) is list else x, ids)
            query = self.__class__._attribute + ": " + ";".join(criteria)
        elif type(self._select) is set:
            criteria = []
            for value in self._select:
                try:
                    if value != "":
                        criteria.append(value)
                except TypeError:
                    pass

            if criteria:
                query = self.__class__._attribute + ": " + ";".join(criteria)
            else:
                raise NothingSelected("No items selected")
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
        if type(key) is list:
            key = key[0]
        rdn = "=".join( [id_attr, escape_attribute_value(key)] )
        return safe_dn( [rdn, self._base] )

    def __iter__(self):
        return self.keys()

    def _find_items(self, ids = None):
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

        try:
            reader = self._get_reader(ids)
        except NothingSelected as nothing:
            log.info("No objects selected")
            raise StopIteration from nothing

        results = reader.search_paged(
                paged_size = cfg.ldap.paged_search_size,
                attributes = requested_attrs)
        found = set()
        for entry in results:
            id = entry[id_attr].value
            if type(id) is list:
                for value in id:
                    found.add(value)
            else:
                found.add(id)

            yield entry

        self.__assert_found_all(found)

    def values(self):
        return self._find_items()

    def _iter_entries(self, dns):
        id_attr = self.__class__._attribute
        reader = self._get_reader()
        results = reader.search_paged(
                paged_size = cfg.ldap.paged_search_size,
                attributes = self.__class__._attribute)
        found = set()
        for entry in results:
            for value in entry[id_attr].values:
                found.add(value)

            if dns:
                yield entry.entry_dn
            else:
                yield entry_name(entry, id_attr)

        self.__assert_found_all(found)

    def dns(self):
        return self._iter_entries(dns = True)

    def keys(self):
        return self._iter_entries(dns = False)

    def __contains__(self, id):
        raise NotImplementedError

    def __getitem__(self, id):
        entries = self._find_items([id])
        return [e for e in entries][0]

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
            if type(id) is list:
                for value in id:
                    found.add(value)
            else:
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
            if type(id) is list:
                for value in id:
                    found.add(value)
            else:
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
            return True

        return False

class LdapObject:
    _object_def = None
    _config_node = None
    _object_class = None
    _required_attrs = []

    def __init__(self, reference_object = None, pre = {}, post = {}):
        self._callbacks_pre = pre
        self._callbacks_post = post
        self._templates = self._read_templates()
        self._modifiers = self._read_modifiers()
        self.attrs = CaseInsensitiveWithAliasDict()
        self.message = ""
        self._reference = reference_object

        # resolve a message that will be output
        try:
            node = self.__class__._config_node
            if not node:
                raise ConfigAttrError()
            log.debug("Attempting to format creation message")
            message_template = node.message_on_create
            while True: # failure is not an option
                try:
                    self.message = message_template.format_map(self.attrs)
                    break
                except KeyError as err:
                    # key missing yet, try to resolve recursively
                    missing_key = err.args[0]
                    log.debug("%s missing yet, resolving recursively" % missing_key)
                    self._resolve_attribute(missing_key)

        except ConfigAttrError:
            log.debug("Template not set for creation message, skipping")
            pass # if this dict is missing, ignore

        # Resolve each attribute recursively
        for attr_def in self.__class__._object_def:
            key = attr_def.key
            if key in self._templates \
                    or key in self.__class__._required_attrs \
                    or attr_def.mandatory \
                    or key.lower() == self.__class__.attribute.lower():
                if key.lower() == "objectclass":
                    self.attrs[key] = self.__class__._object_class
                else:
                    self._resolve_attribute(key)

    def _read_modifiers(self):
        """Read from config how to modify string(s) of the default value"""

        result = CaseInsensitiveWithAliasDict()
        safe_modifiers = ['capitalize', 'casefold', 'lower', 'swapcase', 'title', 'upper']

        try:
            node = self.__class__._config_node
            if not node:
                raise ConfigAttrError()
            modifiers = node.attr.modify.__dict__["_cfg"]
            # read key, value from config; get aliases from schema
            for raw_name, value in modifiers.items():
                if value not in safe_modifiers:
                    msg = "%s() is not a permitted modifier for %s" % (value, raw_name)
                    raise ValueError(msg)

                attr_names = self._canonicalize_name(raw_name)
                result[attr_names] = value
                log.debug("Modifier for %s: %s" % (", ".join(attr_names), value))
        except ConfigAttrError:
            pass # if this dict is missing, ignore

        return result

    def _read_templates(self):
        """Read format strings from config to use as default values for attributes"""

        result = CaseInsensitiveWithAliasDict()

        try:
            node = self.__class__._config_node
            if not node:
                raise ConfigAttrError()
            templates = node.attr.templates.__dict__["_cfg"]
            # read key, value from config; get aliases from schema
            for raw_name, value in templates.items():
                attr_names = self._canonicalize_name(raw_name)
                log.debug("Reading template for " + ", ".join(attr_names))
                result[attr_names] = value if type(value) is list else str(value)
        except ConfigAttrError:
            pass # if this dict is missing, ignore

        return result

    @classmethod
    def _canonicalize_name(cls, raw_name):
        """Normalize attribute name to use as CaseInsensitiveWithAliasDict index"""
        # rewritten from ldap3 library:
        # take properly cased attribute name, add other names as aliases
        definition = cls._object_def[raw_name]
        all_names = [definition.key]
        if definition.oid_info:
            for name in definition.oid_info.name:
                if definition.key.lower() != name.lower():
                    all_names.append(name)

        return all_names

    def _resolve_attribute(self, raw_name):
        """Fill attribute value from input, get defaults from template, or reference entry"""

        def execute_callback(callback, arg):
            name = "%s(%s)" % (callback.__qualname__, repr(arg))
            doc = callback.__doc__
            if doc:
                log.debug("For %s, calling %s # %s" % (key, name, doc))
            else:
                log.debug("For %s, calling %s" % (key, name))

            result = callback(arg)
            log.debug( "%s returned %s" % (name, repr(result)) )

            return result

        # use unambiguous name as the dictionary key
        names = self._canonicalize_name(raw_name)
        key = names[0]

        if key in self.attrs: # already resolved
            log.debug("%s already resolved" % key)
            return

        if key in self._templates:
            # try to interpolate default value recursively
            log.debug("Trying to resolve template %s" % key)
            while True: # failure is not an option
                try:
                    if type(self._templates[key]) is list:
                        log.debug("%s is a list:" % key)
                        default = []
                        # resolve each member of the list
                        for template in self._templates[key]:
                            log.debug("\tAttempting to format '%s'" % template)
                            # try to format string from a dictionary
                            value = template.format_map(self.attrs)
                            # apply the string modifier to each member
                            if key in self._modifiers:
                                modifier = self._modifiers[key]
                                modify = getattr(value, modifier)
                                log.debug("Applying %s() to '%s'" % (modifier, value))
                                value = modify()

                            default.append(value)
                    else:
                        # try to format string from a dictionary
                        log.debug("Attempting to format '%s'" % self._templates[key])
                        default = self._templates[key].format_map(self.attrs)
                        # apply the string modifier
                        if key in self._modifiers:
                            modifier = self._modifiers[key]
                            modify = getattr(default, modifier)
                            log.debug("Applying %s() to '%s'" % (modifier, default))
                            default = modify()

                    break # resolving the formatter complete, go on
                except KeyError as err:
                    # key missing yet, try to resolve recursively
                    missing_key = err.args[0]
                    log.debug("%s missing yet, resolving recursively" % missing_key)
                    self._resolve_attribute(missing_key)

        elif self._reference:
            # if a reference entry is given, take default value from there
            try:
                default = self._reference[key]
            except LDAPKeyError:
                pass # unless there's no such attribute in the reference

        else:
            default = None

        # indirectly apply callbacks: give them current default, receive new default
        try:
            callback = self._callbacks_pre[key]
            default = execute_callback(callback, default)
        except KeyError:
            pass # no callback set
        except Exception as err:
            # the callback failed; resort to user input
            log.warn(err)
            default = None

        # prepare a human-readable default prompt; convert dict to semicolon-delimited string
        if default:
            if type(default) is list:
                default_str = "; ".join(default)
            else:
                default_str = str(default)

            prompt = "%s [%s]: " % (key, default_str)

        else:
            prompt = "%s: " % key

        while True:
            response = input_stderr(prompt)

            if response == ".":
                break # dot entered, delete this attribute
            elif not response:
                # use default if possible
                result = default if default else None

                # indirectly apply callbacks
                try:
                    callback = self._callbacks_post[key]
                    result = execute_callback(callback, result)
                except KeyError: # no callback set
                    pass
                except Exception as err:
                    # the callback failed; require user input again
                    log.error(err)
                    continue

                if result:
                    self.attrs[names] = result
                    break
                else:
                    log.error("%s requires a value" % key)
                    continue

            else:
                # try to split string into a list
                matches = re.split(r'\s*;\s+', response)
                if len(matches) == 1:
                    result = response # seems to be a single value
                else:
                    log.debug("Adding list %s" % repr(matches))
                    result = matches

                try:
                    callback = self._callbacks_post[key]
                    result = execute_callback(callback, result)
                except KeyError:
                    pass # no callback set
                except Exception as err:
                    # the callback failed; require user input again
                    log.error(err)
                    continue

                self.attrs[names] = result
                break

    def __repr__(self):
        return repr(self.attrs)
