# Copyright 2017, Development Gateway, Inc.
# This file is part of ldadm, see COPYING.

import random, re, logging
from argparse import FileType, ArgumentParser

from ldap3 import ALL_ATTRIBUTES, ObjectDef
from ldap3.core.exceptions import LDAPEntryAlreadyExistsResult, \
        LDAPKeyError, LDAPAttributeOrValueExistsResult
from sshpubkeys import SSHKey, InvalidKeyException

from .console import pretty_print
from .command import Command
from .abstract import LdapObjectMapping, MissingObjects, LdapObject
from .unit import UnitMapping, single_unit, multi_unit
from .config import cfg
from .connection import ldap

log = logging.getLogger(__name__)

single_user = ArgumentParser(add_help = False)
single_user.add_argument("username",
        metavar = "USER_NAME",
        help = "User ID")

multi_user = ArgumentParser(add_help = False)
multi_user.add_argument("username",
        metavar = "USER_NAME",
        nargs = "*",
        help = "One or more UIDs. If omitted, read from stdin.")

only_suspended = ArgumentParser(add_help = False)
only_suspended.add_argument("--suspended",
        action = "store_true",
        help = "Only include suspended users")

class User(LdapObject):
    _config_node = cfg.user
    _object_class = cfg.user.objectclass
    # Load attribute definitions by ObjectClass
    _object_def = ObjectDef(object_class = _object_class, schema = ldap)


    @staticmethod
    def make_password(*args_ignored):
        """Generate a random password of random length"""

        len_min = 10
        len_max = 18
        alphabet = string.ascii_letters + string.punctuation + string.digits

        # select random password length within given limits
        # then for each position randomly select a character from the alphabet
        try:
            length = len_min + secrets.randbelow(len_max - len_min + 1)
            chars = [ secrets.choice(alphabet) for i in range(length) ]
        except NameError:
            log.warning("Python module 'secrets' not available, suggesting insecure password")
            length = random.randrange(len_min, len_max)
            chars = [ random.choice(alphabet) for i in range(length) ]

        return ''.join(chars)

    def __init__(self, reference_object = None, pre = {}, post = {}):
        self.__class__._required_attrs = [ self._canonicalize_name(cfg.user.attr.passwd)[0] ]
        super().__init__(reference_object = reference_object, pre = pre, post = post)

class UserMapping(LdapObjectMapping):
    _name = "Users"
    _attribute = cfg.user.attr.uid
    _object_def = User._object_def

    @staticmethod
    def get_dn(names):
        mapping = __class__(base = cfg.user.base.active)
        try:
            return __class__._get_dn(names, mapping)
        except MissingObjects as err:
            msg = "Unknown users: " + ", ".join(err.items)
            raise RuntimeError(msg) from err

class UserCommand(Command):
    parser_name = "user"
    parser_args = {
        "kwargs": {
            "help": "User accounts"
        },
        "subparsers_title": "User command",
        "subparsers": {
            "list": {
                "kwargs": {
                    "parents": [only_suspended],
                    "help": "List all active or suspended users"
                },
            },
            "search": {
                "kwargs": {
                    "parents": [only_suspended],
                    "help": "Search users with LDAP filter"
                },
                "arguments": {
                    "filter": {
                        "metavar": "LDAP_FILTER",
                        "help": "Search filter"
                    }
                }
            },
            "show": {
                "kwargs": {
                    "aliases": ["info"],
                    "parents": [multi_user, only_suspended],
                    "help": "Show details for accounts"
                },
                "arguments": {
                    "--full": {
                        "action": "store_true",
                        "help": "Also show operational attributes"
                    }
                }
            },
            "suspend": {
                "kwargs": {
                    "aliases": ["lock", "ban", "disable"],
                    "parents": [multi_user],
                    "help": "Make accounts inactive"
                }
            },
            "restore": {
                "kwargs": {
                    "aliases": ["unlock", "unban", "enable"],
                    "parents": [multi_user],
                    "help": "Re-activate accounts"
                }
            },
            "delete": {
                "kwargs": {
                    "aliases": ["remove"],
                    "parents": [multi_user],
                    "help": "Irreversibly destroy suspended accounts"
                }
            },
            "add": {
                "kwargs": {
                    "aliases": ["create"],
                    "help": "Add a new account"
                },
                "arguments": {
                    "--defaults": {
                        "dest": "defaults",
                        "metavar": "USER_NAME",
                        "nargs": 1,
                        "help": "Suggest defaults from an existing user"
                    }
                }
            },
            "passwd": {
                "kwargs": {
                    "help": "Reset user password"
                },
                "arguments": {
                    "username": {
                        "metavar": "USERNAME",
                        "help": "User ID"
                    }
                }
            },
            "rename": {
                "kwargs": {
                    "help": "Change account UID"
                },
                "arguments": {
                    "oldname": {
                        "metavar": "OLD_NAME",
                        "help": "Old UID"
                    },
                    "newname": {
                        "metavar": "NEW_NAME",
                        "help": "New UID"
                    }
                }
            },
            "unit": {
                "kwargs": {
                    "help": "Organizational units"
                },
                "subparsers_title": "Unit command",
                "subparsers": {
                    "list": {
                        "kwargs": {
                            "help": "List all units"
                        }
                    },
                    "show": {
                        "kwargs": {
                            "parents": [single_unit],
                            "aliases": ["info"],
                            "help": "List members of the unit"
                        },
                        "arguments": {
                            "--full": {
                                "action": "store_true",
                                "help": "List members in nested units, too"
                            }
                        }
                    },
                    "add": {
                        "kwargs": {
                            "aliases": ["create"],
                            "help": "Add an organizational unit"
                        },
                        "arguments": {
                            "--parent": {
                                "metavar": "PARENT_UNIT",
                                "help": "Create nested in this unit"
                            }
                        }
                    },
                    "delete": {
                        "kwargs": {
                            "parents": [multi_unit],
                            "aliases": ["remove"],
                            "help": "Delete an organizational unit"
                        }
                    },
                    "assign": {
                        "kwargs": {
                            "parents": [single_unit, multi_user],
                            "help": "Move users to the organizational unit"
                        }
                    }
                }
            },
            "key": {
                "kwargs": {
                    "help": "Manipulate user SSH public key"
                },
                "subparsers_title": "Key command",
                "subparsers": {
                    "list": {
                        "kwargs": {
                            "aliases": ["show"],
                            "parents": [single_user],
                            "help": "List public keys for a user"
                        }
                    },
                    "add": {
                        "kwargs": {
                            "aliases": ["create"],
                            "parents": [single_user],
                            "help": "Add a public key to a user"
                        },
                        "arguments": {
                            "--file": {
                                "dest": "key_file",
                                "metavar": "FILE_NAME",
                                "type": FileType("r"),
                                "nargs": 1,
                                "help": "Read public key from file"
                            }
                        }
                    },
                    "delete": {
                        "kwargs": {
                            "aliases": ["remove"],
                            "parents": [single_user],
                            "help": "Remove a public key from a user"
                        },
                        "arguments": {
                            "key_names": {
                                "metavar": "KEY_NAME",
                                "nargs": "*",
                                "help": "Public key MD5 modulus or comment"
                            }
                        }
                    }
                }
            }
        }
    }

    def _get_unique_id_number(self, *args_ignored):
        """Suggest a unique user ID number"""

        umin = cfg.user.nuid.min
        umax = cfg.user.nuid.max
        attr_name = cfg.user.attr.nuid

        n = 50 # candidates for the unique UID
        candidates = set( random.randint(umin, umax) for i in range(n) )

        # find existing UIDs, and remove them from the list of candidates
        for base in (cfg.user.base.suspended, cfg.user.base.active):
            users = UserMapping(base = base, attrs = attr_name)
            try:
                query = attr_name + ": " + "; ".join( map(str, candidates) )
                users.select(query)
            except MissingObjects:
                pass

            collisions = set( user[attr_name].value for user in users.values() )
            candidates -= collisions
            if collisions:
                log.debug("UID collisions skipped: " + " ".join(map(str, collisions)))

        try:
            # randomly return one of the remaining candidates
            return random.choice(list(candidates))
        except IndexError as err:
            raise RuntimeError("Couldn't create a unique UID in %i attempts" % n) from err

    def _uid_unique(self, uid):
        """Check if user ID is unique among active and suspended users"""

        query = "%s: %s" % (cfg.user.attr.uid, uid)
        for base in (cfg.user.base.suspended, cfg.user.base.active):
            collisions = UserMapping(base = base)
            try:
                collisions.select(query)
            except MissingObjects:
                pass

            if collisions:
                raise RuntimeError("UID %s already in use" % uid)

        return uid

    def _set_active(self, usernames, active = True):
        if active:
            base_from = cfg.user.base.suspended
            base_to = cfg.user.base.active
        else:
            base_from = cfg.user.base.active
            base_to = cfg.user.base.suspended

        users = UserMapping(base = base_from)
        users.select(usernames).move(base_to)

    def _list_users(self, filter = None):
        if self._args.suspended:
            base = cfg.user.base.suspended
        else:
            base = cfg.user.base.active

        users = UserMapping(base = base)
        for uid in users.select(filter):
            print(uid)

    def on_user_list(self):
        self._list_users()

    def on_user_search(self):
        self._list_users(filter = self._args.filter)

    def on_user_show(self):
        if self._args.suspended:
            base = cfg.user.base.suspended
        else:
            base = cfg.user.base.active

        # TODO: operational attributes
        users = UserMapping(base = base, attrs = ALL_ATTRIBUTES)
        users.select( self._args_or_stdin("username") )
        for user_entry in users.values():
            pretty_print(user_entry)

    def on_user_suspend(self):
        usernames = self._args_or_stdin("username")
        self._set_active(usernames, active = False)

    def on_user_restore(self):
        usernames = self._args_or_stdin("username")
        self._set_active(usernames, active = True)

    def on_user_delete(self):
        usernames = list(self._args_or_stdin("username"))
        if usernames:
            users = UserMapping(base = cfg.user.base.suspended)
            users.select(usernames).delete()

    def on_user_rename(self):
        base = cfg.user.base.active

        users = UserMapping(base = base)
        try:
            users.rename(self._args.oldname, self._args.newname)
        except LDAPEntryAlreadyExistsResult as err:
            msg = "User '%s' already exists" % self._args.newname
            raise RuntimeError(msg) from err

    def on_user_add(self):
        base = cfg.user.base.active

        # Get default values from a reference object
        if self._args.defaults:
            source_obj = self._get_user(self._args.defaults, ALL_ATTRIBUTES)
        else:
            source_obj = None

        pre = {
            cfg.user.attr.nuid: self._get_unique_id_number,
            cfg.user.attr.uid: self._uid_unique,
            cfg.user.attr.passwd: User.make_password
        }

        user = User(reference_object = source_obj, pre = pre)

        # Write the object to LDAP
        uid = user.attrs[UserMapping._attribute]
        users = UserMapping(base = cfg.user.base.active)
        users[uid] = user.attrs

        # Print the message
        if user.message:
            print(user.message)

    def _get_user(self, username, attrs = None):
        users = UserMapping(base = cfg.user.base.active, attrs = attrs)
        return users[username]

    def on_user_passwd(self):
        username = self._args.username
        passwd_attr = cfg.user.attr.passwd
        user = self._get_user(username).entry_writable()
        password = User.make_password()

        setattr(user, passwd_attr, password)
        user.entry_commit_changes(refresh = False)

        print(password)

    def on_user_key_list(self):
        username = self._args.username

        def get_keys():
            pubkey_attr = cfg.user.attr.pubkey

            user = self._get_user(username, pubkey_attr)

            try:
                keys = user[pubkey_attr]
            except LDAPKeyError:
                log.info("User %s has no public keys" % usernames)
                keys = []

            return keys

        for key in get_keys():
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

    def on_user_key_add(self):
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

    def on_user_key_delete(self):
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

    def on_user_unit_list(self):
        units = UnitMapping(cfg.user.base.active)
        for unit in units:
            print(unit)

    def on_user_unit_show(self):
        units = UnitMapping(cfg.user.base.active)
        base = units[self._args.unit].entry_dn

        users = UserMapping(base = base, sub_tree = self._args.full)
        for uid in users:
            print(uid)

    def on_user_unit_add(self):
        units = UnitMapping(cfg.user.base.active)
        units.add(parent_name = self._args.parent)

    def on_user_unit_delete(self):
        unit_names = list(self._args_or_stdin("unit"))
        if unit_names:
            units = UnitMapping(cfg.user.base.active).select(unit_names)
            try:
                units.delete()
            except LDAPNotAllowedOnNotLeafResult as err:
                raise RuntimeError("One or more units not empty") from err

    def on_user_unit_assign(self):
        base = cfg.user.base.active
        units = UnitMapping(base)
        unit = units[self._args.unit]

        users = UserMapping(base = base)
        users.select(self._args_or_stdin("username"))
        users.move(unit.entry_dn)
