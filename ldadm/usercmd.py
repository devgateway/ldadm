import random, re, logging

from ldap3 import ALL_ATTRIBUTES, ObjectDef, Reader, Writer
from ldap3.core.exceptions import LDAPEntryAlreadyExistsResult, LDAPKeyError
from ldap3.core.exceptions import LDAPAttributeOrValueExistsResult
from ldap3.utils.dn import escape_attribute_value, safe_dn
from sshpubkeys import SSHKey, InvalidKeyException

from .console import pretty_print
from .objects import User
from .command import Command
from .collections import UserMapping
from .config import cfg

log = logging.getLogger(__name__)

class UserCommand(Command):
    def __init__(self, args):
        super().__init__(args)
        self.__user = ObjectDef(
                object_class = cfg.user.objectclass,
                schema = self._conn)

    def _get_unique_id_number(self, *args_ignored):
        umin = cfg.user.nuid.min
        umax = cfg.user.nuid.max
        attr_name = cfg.user.attr.nuid

        n = 50 # candidates for the unique UID
        candidates = set( random.randint(umin, umax) for i in range(n) )

        # find existing UIDs, and remove them from the list of candidates
        for base in (cfg.user.base.suspended, cfg.user.base.active):
            query = attr_name + ": " + "; ".join( map(str, candidates) )
            users = UserMapping(
                    connection = self._conn,
                    base = base,
                    limit = query,
                    object_def = self.__user,
                    attrs = attr_name)

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
        query = "%s: %s" % (cfg.user.attr.uid, uid)
        for base in (cfg.user.base.suspended, cfg.user.base.active):
            collisions = UserMapping(
                    connection = self._conn,
                    base = base,
                    limit = query,
                    object_def = self.__user)
            if not collisions.is_empty():
                raise RuntimeError("UID %s already in use" % uid)

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
            base_from = cfg.user.base.suspended
            base_to = cfg.user.base.active
        else:
            base_from = cfg.user.base.active
            base_to = cfg.user.base.suspended

        users = UserMapping(
                connection = self._conn,
                base = base_from,
                limit = usernames,
                object_def = self.__user)

        users.move_all(base_to)

    def _list_users(self, limit = None):
        if self._args.suspended:
            base = cfg.user.base.suspended
        else:
            base = cfg.user.base.active

        users = UserMapping(
                connection = self._conn,
                base = base,
                limit = limit,
                object_def = self.__user,
                attrs = None)
        for uid in users.keys():
            print(uid)

    def list_users(self):
        self._list_users()

    def search(self):
        self._list_users(limit = self._args.filter)

    def show(self):
        usernames = list(self._args_or_stdin("username"))
        if self._args.suspended:
            base = cfg.user.base.suspended
        else:
            base = cfg.user.base.active

        users = UserMapping(
                connection = self._conn,
                base = base,
                limit = usernames,
                object_def = self.__user,
                attrs = ALL_ATTRIBUTES) # TODO: operational attributes
        for user_entry in users:
            pretty_print(user_entry)

    def suspend(self):
        usernames = list(self._args_or_stdin("username"))
        self._set_active(usernames, active = False)

    def restore(self):
        usernames = list(self._args_or_stdin("username"))
        self._set_active(usernames, active = True)

    def delete(self):
        usernames = list(self._args_or_stdin("username"))
        if not usernames:
            return

        users = UserMapping(
                connection = self._conn,
                base = cfg.user.base.suspended,
                limit = usernames,
                object_def = self.__user)
        for username in usernames:
            del users[username]

        users.commit_delete()

    def _get_writer(self, base, query, attrs = None):
        if not attrs:
            attrs = cfg.user.attr.uid

        reader = Reader(
                connection = self._conn,
                base = base,
                query = query,
                object_def = self.__user,
                sub_tree = True)
        reader.search(attrs)
        return Writer.from_cursor(reader)

    def rename(self):
        base = cfg.user.base.active

        users = UserMapping(
                connection = self._conn,
                base = base,
                object_def = self.__user)
        try:
            users.rename(self._args.oldname, self._args.newname)
        except LDAPEntryAlreadyExistsResult as err:
            msg = "User '%s' already exists" % self._args.newname
            raise RuntimeError(msg) from err

    def add(self):
        uid_attr_name = cfg.user.attr.uid
        base = cfg.user.base.active

        # Get default values from a reference object
        if self._args.defaults:
            source_obj = self._get_user(self._args.defaults, ALL_ATTRIBUTES)
        else:
            source_obj = None

        handlers = {
                cfg.user.attr.nuid: self._get_unique_id_number,
                cfg.user.attr.uid: self._uid_unique,
                cfg.user.attr.passwd: User.make_password
                }

        User.object_def = self.__user
        user = User(
                config_node = cfg.user,
                reference_object = source_obj,
                handlers = handlers
                )

        log.debug("Final object:\n" + repr(user))

        # Write the object to LDAP
        uid = user.attrs[uid_attr_name]
        users = UserMapping(
                connection = self._conn,
                base = cfg.user.base.active,
                object_def = self.__user)
        users[uid] = user.attrs

        # Print the message
        if user.message:
            print(user.message)

    def _get_user(self, username, attrs = None):
        users = UserMapping(
                connection = self._conn,
                base = cfg.user.base.active,
                limit = [username],
                object_def = self.__user,
                attrs = attrs)

        user_list = [u for u in users]
        try:
            return user_list[0]
        except KeyError as err:
            raise RuntimeError("User %s not found" % username) from err

    def _get_keys(self, username):
        pubkey_attr = cfg.user.attr.pubkey

        user = self._get_user(username, pubkey_attr)

        try:
            keys = user[pubkey_attr]
        except LDAPKeyError:
            log.info("User %s has no public keys" % usernames)
            keys = []

        return keys

    def list_keys(self):
        username = self._args.username

        for key in self._get_keys(username):
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
                    output = "%s (%s)" % (pk.hash_md5(), pk.comment)
                else:
                    output = pk.hash_md5()
            except NotImplementedError as err:
                log.warning("User %s has an unsupported key: %s" % (username, err))
                output = "(Unsupported key)"
            except InvalidKeyError as err:
                log.error("User %s has an invalid key: %s" % (username, err))
                output = "(Invalid key)"

            print(output)

    def add_key(self):
        username = self._args.username

        # get the writable entry
        pubkey_attr = cfg.user.attr.pubkey
        user = self._get_user(username, pubkey_attr).entry_writable()

        keys = user[pubkey_attr]

        # parse each key; warn on unsupported, fail on invalid
        for key_string in self._args_or_stdin("key_file"):
            try:
                pk = SSHKey(key_string)
                pk.parse()
            except NotImplementedError as err:
                log.warning("Unsupported key: %s" % err)

            keys += key_string

        try:
            user.entry_commit_changes(refresh = False)
        except LDAPAttributeOrValueExistsResult as err:
            raise RuntimeError("Key already exists") from err

    def delete_key(self):
        username = self._args.username
        re_md5 = re.compile(r"([0-9A-Fa-f]{2}.?){15}[0-9A-Fa-f]{2}$")

        def just_hex(md5_str):
            match = re_md5.search(md5_str)
            try:
                return match.group(0).lower()
            except AttributeError as err:
                raise ValueError("Invalid MD5 hash: %s" % md5_str) from err

        # read args; make a dict of moduli with no delimiters
        keys_to_delete = {}
        for val in self._args_or_stdin("key_names"):
            try:
                # assume it's MD5
                keys_to_delete[ just_hex(val) ] = val
            except ValueError:
                # else it's a comment
                keys_to_delete[val] = val

        # get the writable entry
        pubkey_attr = cfg.user.attr.pubkey

        user = self._get_user(username, pubkey_attr).entry_writable()

        try:
            keys = user[pubkey_attr]

            # compare each key hash with that dict, then delete matching
            for key in keys.values:
                if type(key) is bytes:
                    key_string = key.decode("utf-8")
                elif type(key) is str:
                    key_string = key
                else:
                    raise TypeError("Public key must be bytes or str")

                pk = SSHKey(key_string)
                pk.parse()
                modulus = just_hex( pk.hash_md5() )
                comment = pk.comment

                for item in (modulus, comment):
                    if item in keys_to_delete:
                        keys -= key
                        del keys_to_delete[item]

            user.entry_commit_changes(refresh = False)

            if keys_to_delete:
                missing_keys = ", ".join( keys_to_delete.values() )
                log.warning("Keys not found for user %s: %s" % (username, missing_keys) )

        except LDAPKeyError:
            log.info("User %s has no public keys" % username)
