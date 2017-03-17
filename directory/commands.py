import logging
import sys
import random

import ldap3
from ldap3 import Connection, ObjectDef, Reader, Writer
from ldap3.utils.dn import escape_attribute_value, safe_dn
from sshpubkeys import SSHKey, InvalidKeyError

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

    def _get_unique_id_number(self, *args_ignored):
        umin = self._cfg.user.nuid.min
        umax = self._cfg.user.nuid.max
        attr_name = self._cfg.user.attr.nuid

        n = 50 # candidates for the unique UID
        candidates = set( random.randint(umin, umax) for i in range(n) )

        # find existing UIDs, and remove them from the list of candidates
        for active in (True, False):
            query = attr_name + ": " + "; ".join( map(str, candidates) )
            users = self._search(
                    attrs = attr_name,
                    active = active,
                    query = query)

            collisions = set( user[attr_name].value for user in users )
            candidates -= collisions
            if collisions:
                log.debug("UID collisions skipped: " + " ".join(map(str, collisions)))

        try:
            # randomly return one of the remaining candidates
            return random.choice(list(candidates))
        except IndexError as err:
            raise RuntimeError("Couldn't create a unique UID in %i attempts" % n) from err

    def _uid_unique(self, uid):
        # raise an exception if UID is not unique
        for active in (True, False):
            query = "%s: %s" % (self._cfg.user.attr.uid, uid)
            users = self._search(
                    attrs = None,
                    query = query,
                    active = active)
            if len(list(users)):
                status = "an active" if active else "a suspended"
                raise RuntimeError("UID %s in use by %s user" % (uid, status))
        return uid

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
            if not reader.search(ldap3.ALL_ATTRIBUTES):
                raise RuntimeError("User %s not found" % self._args.defaults[0])
            source_obj = reader.entries[0]
        else:
            source_obj = None

        handlers = {
                self._cfg.user.attr.nuid: self._get_unique_id_number,
                self._cfg.user.attr.uid: self._uid_unique,
                self._cfg.user.attr.passwd: User.make_password
                }

        User.object_def = self.__user
        user = User(
                config_node = self._cfg.user,
                reference_object = source_obj,
                handlers = handlers
                )

        log.debug("Final object:\n" + repr(user))

        # Create a new virtual object
        uid = user.attrs[uid_attr_name]
        rdn = "=".join( [uid_attr_name, escape_attribute_value(uid)] )
        dn = safe_dn([rdn, base])
        query = "%s: %s" % (uid_attr_name, uid)
        writer = self._get_writer(base, query)
        entry = writer.new(dn)

        # Set object properties from ciDict
        for key in user.attrs:
            setattr(entry, key, user.attrs[key])

        # Write the object to LDAP
        entry.entry_commit_changes(refresh = False)

    def list_keys(self):
        username = self._args.username
        pubkey_attr = self._cfg.user.attr.pubkey
        base = self._cfg.user.base.active
        query = "%s: %s" % (self._cfg.user.attr.uid, username)

        reader = self._get_reader(base, query)
        if not reader.search(pubkey_attr):
            raise RuntimeError("User %s not found" % username)

        try:
            keys = reader.entries[0][pubkey_attr]
        except Exception:
            log.warning("User %s has no public keys" % usernames)
            return

        for key in keys:
            if type(key) is bytes:
                key_string = key.decode("utf-8")
            elif type(key) is str:
                key_string = key
            else:
                raise TypeError("Public key must be bytes or str")

            try:
                pk = SSHKey(key_string)
                pk.parse()
                if pk.comment:
                    desc = "%s (%s)" % (pk.hash_md5(), pk.comment)
                else:
                    desc = pk.hash_md5()
                print(desc)
                continue

            except NotImplementedError as err:
                log.warning("User %s has an unsupported key: " % (username, err))
            except InvalidKeyError as err:
                log.error("User %s has an invalid key: " % (username, err))
            print("(Cannot display key)")

#    def add_key(self):
#        pass
##    def delete_key(self):
