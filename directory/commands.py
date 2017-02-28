import logging
import sys
import random

import ldap3

from .config import cfg
from .directory import Directory, DirectoryMapping
from .console import pretty_print

log = logging.getLogger(__name__)

class Command:
    def __init__(self, args):
        self._args = args
        self._dir = Directory()

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

class UserCommand(Command):
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

    def list_users(self):
        if self._args.suspended:
            user_entries = self._dir.suspended_users()
        else:
            user_entries = self._dir.active_users()

        for uid in user_entries:
            print(uid)

    def search(self):
        if self._args.suspended:
            user_entries = self._dir.suspended_users()
        else:
            user_entries = self._dir.active_users()

        matches = user_entries.search(self._args.filter)
        for uid in matches:
            print(uid)

    def show(self):
        if self._args.full:
            attrs = [ldap3.ALL_ATTRIBUTES, ldap3.ALL_OPERATIONAL_ATTRIBUTES]
        else:
            attrs = ldap3.ALL_ATTRIBUTES

        user_entries = self._dir.active_users(attrs)

        for uid in self._args_or_stdin("username"):
            try:
                pretty_print(user_entries[uid])
            except IndexError:
                log.error("User %s not found" % uid)

    def suspend(self):
        active = self._dir.active_users()
        suspended = self._dir.suspended_users()

        for uid in self._args_or_stdin("username"):
            active.move(uid, suspended)

    def restore(self):
        active = self._dir.active_users()
        suspended = self._dir.suspended_users()

        for uid in self._args_or_stdin("username"):
            suspended.move(uid, active)

    def delete(self):
        suspended = self._dir.suspended_users()

        try:
            for uid in self._args_or_stdin("username"):
                del suspended[uid]
        except IndexError as ie:
            msg = "User '%s' is not among suspended users" % uid
            raise RuntimeError(msg) from ie

    def rename(self):
        try:
            self._dir.active_users().rename(
                    old_id = self._args.oldname,
                    new_id = self._args.newname)
        except ldap3.core.exceptions.LDAPEntryAlreadyExistsResult as err:
            msg = "User '%s' already exists" % self._args.newname
            raise RuntimeError(msg) from err

#    def add(self):
#        user = cfg.user
#        (dn, attrs) = self._input_entry(user.objectclass, user.templates)
#        self._add_entry(dn, user.objectclass, attrs)
#
##    def list_keys(self):
#    def add_key(self):
#        pass
##    def delete_key(self):
