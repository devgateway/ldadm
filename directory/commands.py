import logging
import sys
import random
import re

import ldap3
from ldap3 import Connection, ObjectDef, Reader, Writer
from ldap3.utils.dn import escape_attribute_value, safe_dn
from ldap3.utils.ciDict import CaseInsensitiveWithAliasDict

from .config import Config, ConfigAttrError
from .console import pretty_print, input_attributes

log = logging.getLogger(__name__)

class Command:
    def __init__(self, args):
        self._args = args
        self._cfg = Config()
        self._conn = self._connect()

    def _connect(self):
        try:
            binddn = self._cfg.ldap.binddn
            bindpw = self._cfg.ldap.bindpw
        except AttributeError:
            binddn = None
            bindpw = None

        if log.isEnabledFor(logging.DEBUG):
            ldap3.utils.log.set_library_log_detail_level(ldap3.utils.log.PROTOCOL)

        conn = ldap3.Connection(
                server = self._cfg.ldap.uri,
                user = binddn,
                password = bindpw,
                raise_exceptions = True)
        conn.bind()

        return conn

    def _args_or_stdin(self, argname):
        args = getattr(self._args, argname)
        if args:
            if not sys.__stdin__.isatty():
                log.warning("Standard input ignored, because arguments are present")
            for arg in args:
                yield arg
        else:
            with sys.__stdin__ as stdin:
                for line in stdin:
                    yield line[:-1] # in text mode linesep is always "\n"

    @staticmethod
    def _get_new_rdn(entry, attr_name, new_val):
        # RDN can be an array: gn=John+sn=Doe
        old_rdn = ldap3.utils.dn.safe_rdn(entry.entry_dn, decompose = True)
        new_rdn = []
        for key_val in old_rdn:
            if key_val[0] == attr_name:
                # primary ID element
                new_rdn.append( (key_val[0], new_val) )
            else:
                new_rdn.append(key_val)

        return "+".join( map(lambda key_val: "%s=%s" % key_val, new_rdn) )

class UserCommand(Command):
    def __init__(self, args):
        super().__init__(args)
        self.__user = ObjectDef(
                object_class = self._cfg.user.objectclass,
                schema = self._conn)

    def _get_unique_id_number(self):
        user = cfg.user
        umin = user.nuid.min
        umax = user.nuid.max
        attr = user.attr.nuid

        steps = 50 # subranges of umin--umax, candidates for the unique UID
        def ranged_random(step):
            """Generate a random int in each subrange umin--umax"""
            step_size = int((umax - umin) / steps)
            return umin + step_size * step + random.randint(0, step_size)

        # make a list random unique ints, one per subrange
        nuids = list( map(ranged_random, range(steps)) )

        def remove_collisions(base):
            """Find existing UIDs and remove them from the candidate UID list"""
            conditions = map(lambda n: "(%s=%i)" % (attr, n), nuids)
            filt = "(|%s)" % "".join(conditions)

            log.debug("Searching for UID collisions in '%s'" % base)
            entries = self._ldap.extend.standard.paged_search(
                    search_base = base,
                    search_filter = filt,
                    search_scope = scope(user.scope),
                    attributes = attr)
            for entry in entries:
                collision = entry["attributes"][attr]
                nuids.remove(collision)
                log.debug("UID collision %i skipped" % collision)

        # find existing UIDs, and remove them from the list of candidates
        remove_collisions(user.base.active)
        remove_collisions(user.base.suspended)

        if nuids:
            # randomly return one of the remaining candidates
            return nuids[random.randrange(0, len(nuids))]
        else:
            raise NotFound("Couldn't find a unique UID in %i attempts" % steps)

    def _uid_unique(self, uid):
        # check if UID is unique
        for active in (True, False):
            try:
                self._get_single_entry(uid, active = active)
                return False
            except NotFound:
                pass

        return True

    @staticmethod
    def __assert_empty(usernames, critical = True):
        if usernames:
            msg = "Users not found: " + ", ".join(usernames)
            if critical:
                raise RuntimeError(msg)
            else:
                log.error(msg)

    def _set_active(self, usernames, active = True):
        if active:
            base_from = self._cfg.user.base.suspended
            base_to = self._cfg.user.base.active
        else:
            base_from = self._cfg.user.base.active
            base_to = self._cfg.user.base.suspended

        query = "%s: %s" % ( self._cfg.user.attr.uid, ";".join(usernames) )

        users = self._get_writer(base_from, query)

        for user in users:
            uid = user[self._cfg.user.attr.uid].value
            user.entry_move(base_to)
            usernames.remove(uid)

        users.commit()

        self.__assert_empty(usernames)

    def _search(self, attrs = None, query = None, active = True, operational = False):
        if active:
            base = self._cfg.user.base.active
        else:
            base = self._cfg.user.base.suspended

        reader = self._get_reader(base, query)
        reader.get_operational_attributes = operational
        return reader.search_paged(
                paged_size = self._cfg.ldap.paged_search_size,
                attributes = attrs)

    def list_users(self):
        attrs = self._cfg.user.attr.uid
        for user in self._search(attrs, active = not self._args.suspended):
            print(user[self._cfg.user.attr.uid])

    def search(self):
        query = self._args.filter
        attrs = self._cfg.user.attr.uid
        for user in self._search(attrs, query, active = not self._args.suspended):
            print(user[self._cfg.user.attr.uid])

    def show(self):
        usernames = list(self._args_or_stdin("username"))
        query = "%s: %s" % ( self._cfg.user.attr.uid, ";".join(usernames) )

        users = self._search(
                attrs = ldap3.ALL_ATTRIBUTES,
                query = query,
                active = not self._args.suspended,
                operational = self._args.full)
        for user in users:
            pretty_print(user)
            uid = user[self._cfg.user.attr.uid].value
            usernames.remove(uid)

        self.__assert_empty(usernames)

    def suspend(self):
        usernames = list(self._args_or_stdin("username"))
        self._set_active(usernames, active = False)

    def restore(self):
        usernames = list(self._args_or_stdin("username"))
        self._set_active(usernames, active = True)

    def delete(self):
        usernames = list(self._args_or_stdin("username"))
        query = "%s: %s" % ( self._cfg.user.attr.uid, ";".join(usernames) )

        users = self._get_writer(self._cfg.user.base.suspended, query)

        for user in users:
            uid = user[self._cfg.user.attr.uid].value
            user.entry_delete()
            usernames.remove(uid)

        users.commit()

        self.__assert_empty(usernames)

    def _get_reader(self, base, query):
        if self._cfg.user.scope.lower() == "one":
            sub_tree = False
        else:
            sub_tree = True

        return Reader(
                connection = self._conn,
                base = base,
                query = query,
                object_def = self.__user,
                sub_tree = sub_tree)

    def _get_writer(self, base, query):
        attrs = self._cfg.user.attr.uid
        reader = self._get_reader(base, query)
        reader.search(attrs)
        return Writer.from_cursor(reader)

    def rename(self):
        base = self._cfg.user.base.active
        query = "%s: %s" % (self._cfg.user.attr.uid, self._args.oldname)

        user = self._get_writer(base, query).entries[0]
        try:
            rdn = self._get_new_rdn(
                    entry = user,
                    attr_name = self._cfg.user.attr.uid,
                    new_val = self._args.newname)
            user.entry_rename(rdn)
            user.entry_commit_changes(refresh = False)
        except ldap3.core.exceptions.LDAPEntryAlreadyExistsResult as err:
            msg = "User '%s' already exists" % self._args.newname
            raise RuntimeError(msg) from err

    def _read_templates(self):
        templates = CaseInsensitiveWithAliasDict()

        try:
            raw_templates = self._cfg.user.attr.templates.__dict__["_cfg"]
        except ConfigAttrError:
            raw_templates = {}

        # read key, value from config; get aliases from schema
        for raw_attr_name, value in raw_templates.items():
            names = self._attribute_names(raw_attr_name)
            log.debug("Reading template for " + ", ".join(names))
            templates[names] = value if type(value) is list else str(value)

        return templates

    def _attribute_names(self, raw_attr_name):
        definition = self.__user[raw_attr_name]
        names = [definition.key]
        if definition.oid_info:
            for name in definition.oid_info.name:
                if definition.key.lower() != name.lower():
                    log.debug("%s != %s" % (definition.key, name))
                    names.append(name)

        return templates

    def add(self):
        base = self._cfg.user.base.active
        uid_attr_name = self._cfg.user.attr.uid

        templates = self._read_templates()

        # Get default values from a reference object
        if self._args.defaults:
            query = "%s: %s" % (uid_attr_name, self._args.defaults)
            reader = self._get_reader(base, query)
            reader.search(ldap3.ALL_ATTRIBUTES)
            source_obj = reader.entries[0]
        else:
            source_obj = None

        # Get list of all possible attributes and aliases
        writer = Writer(
                connection = self._conn,
                object_def = self.__user)
        # create a virtual entry, which never gets committed, just to store attributes
        # we don't know the actual DN yet
        fake_rdn = uid_attr_name + "=_new_"
        new_attrs = CaseInsensitiveWithAliasDict()

        # Get all mandatory and required optional attributes into new_attrs
        attr_handlers = {
                self._cfg.user.attr.nuid: "_get_unique_id_number",
                self._cfg.user.attr.uid: "_uid_unique",
                self._cfg.user.attr.passw: "_create_password"
                }

        def resolve_attribute(raw_attr_name):
            names = self._attribute_names(raw_attr_name)
            log.debug("Attribute %s is %s" % (raw_attr_name, repr(names)))
            attr_name = names[0]

            if attr_name in new_attrs: # already resolved
                log.debug("%s already resolved" % attr_name)
                return

            if attr_name in templates:
                # try to interpolate default value recursively
                log.debug("Trying to resolve template %s" % attr_name)
                while True: # failure is not an option
                    try:
                        if type(templates[attr_name]) is list:
                            default = []
                            for template in templates[attr_name]:
                                log.debug("\tAttempting to format '%s'" % template)
                                default.append( template.format_map(new_attrs) )
                        else:
                            log.debug("Attempting to format '%s'" % templates[attr_name])
                            default = templates[attr_name].format_map(new_attrs)

                        # TODO: modifiers?
                        break
                    except KeyError as err:
                        # key missing yet, try to resolve recursively
                        key = err.args[0]
                        log.debug("%s missing yet, resolving recursively" % key)
                        resolve_attribute(key)

            elif source_obj:
                # if a reference entry is given, take default value from there
                try:
                    default = source_obj[attr_name]
                except ldap3.core.exceptions.LDAPKeyError:
                    pass

            else:
                default = None

            if attr_name in attr_handlers:
                handler = getattr(self, attr_handlers[attr_name])
                try:
                    log.debug("Calling handler %s" % attr_handlers[attr_name])
                    default = handler(default)
                except Exception as err:
                    log.error(err)
                    default = None

            if default:
                if type(default) is list:
                    default_str = "; ".join(default)
                else:
                    default_str = str(default)

                prompt = "%s [%s]: " % (attr_name, default_str)

            else:
                prompt = "%s: " % attr_name

            response = input(prompt)

            if response == ".":
                pass
            elif not response:
                new_attrs[attr_name] = default
            else:
                matches = re.split(r'\s*;\s', response)
                if len(matches) == 1:
                    new_attrs[names] = response
                else:
                    log.debug("Adding as a list")
                    new_attrs[names] = matches

        # Resolve each attribute recursively
        for attr_def in self.__user:
            key = attr_def.key
            if key in templates or attr_def.mandatory:
                resolve_attribute(key)

        # Create a new virtual object
        uid = new_attrs[uid_attr_name]
        rdn = "=".join( [uid_attr_name, escape_attribute_value(uid)] )
        dn = safe_dn([rdn, base])
        entry = writer.new(dn)

        # Set object properties from ciDict
        # Write the object to LDAP

##    def list_keys(self):
#    def add_key(self):
#        pass
##    def delete_key(self):
