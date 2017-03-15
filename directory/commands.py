import logging
import sys
import random

import ldap3
from ldap3 import Connection, ObjectDef, Reader, Writer
from ldap3.utils.dn import escape_attribute_value, safe_dn

from .config import Config
from .console import pretty_print, input_attributes
from .objects import User

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

    def add(self):
        uid_attr_name = self._cfg.user.attr.uid
        base = self._cfg.user.base.active

        # Get default values from a reference object
        if self._args.defaults:
            query = "%s: %s" % (uid_attr_name, self._args.defaults)
            reader = self._get_reader(base, query)
            reader.search(ldap3.ALL_ATTRIBUTES)
            source_obj = reader.entries[0]
        else:
            source_obj = None

        handlers = {
                self._cfg.user.attr.nuid: self._get_unique_id_number,
                self._cfg.user.attr.uid: self._uid_unique,
                self._cfg.user.attr.passw: self._create_password
                }

        User.object_def = self.__user
        user = User(
                config_node = self._cfg.user.attr,
                reference_object = source_obj,
                handlers = handlers
                )

        log.debug("Final object:\n" + repr(user))
        # Create a new virtual object
        uid = user.attrs[uid_attr_name]
        rdn = "=".join( [uid_attr_name, escape_attribute_value(uid)] )
        dn = safe_dn([rdn, base])
        entry = writer.new(dn)

        # Set object properties from ciDict
        # Write the object to LDAP

##    def list_keys(self):
#    def add_key(self):
#        pass
##    def delete_key(self):
