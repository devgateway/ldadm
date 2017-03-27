#!/usr/bin/python3
import argparse, logging, sys, importlib

log_levels = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG
}

ap = argparse.ArgumentParser(description = "Manage LDAP accounts")

ap.add_argument("--loglevel",
        dest = "log_level",
        default = "WARNING",
        type = str,
        choices = log_levels.keys(),
        help = "Set logging verbosity")

subcommands = ap.add_subparsers(
        description = "Objects to manage",
        dest = "subcommand"
        )
subcommands.required = True

# User commands

user_parser = subcommands.add_parser("user",
        help = "User accounts")
user_parser.set_defaults(_class = "UserCommand")
user_parser.set_defaults(_module = "usercmd")

user = user_parser.add_subparsers(title = "User command")

only_suspended = argparse.ArgumentParser(add_help = False)
only_suspended.add_argument("--suspended",
        action = "store_true",
        help = "Only include suspended users")

p = user.add_parser("list",
        parents = [only_suspended],
        help = "List all active or suspended users")
p.set_defaults(_event = "list")

search = user.add_parser("search",
        parents = [only_suspended],
        aliases = ["find"],
        help = "Search users with LDAP filter")
search.add_argument("filter",
        metavar = "LDAP_FILTER",
        help = "Search filter")
search.set_defaults(_event = "search")

# User commands that accept zero or more UIDs

multi_user_parser = argparse.ArgumentParser(add_help = False)
multi_user_parser.add_argument("username",
        metavar = "USER_NAME",
        nargs = "*",
        help = "One or more UIDs. If omitted, read from stdin.")

show = user.add_parser("show",
        aliases = ["info"],
        parents = [multi_user_parser, only_suspended],
        help = "Show details for accounts")
show.set_defaults(_event = "show")
show.add_argument("--full",
        action = "store_true",
        help = "Also show operational attributes")

p = user.add_parser("suspend",
        aliases = ["lock", "ban", "disable"],
        parents = [multi_user_parser],
        help = "Make accounts inactive")
p.set_defaults(_event = "suspend")

p = user.add_parser("restore",
        aliases = ["unlock", "unban", "enable"],
        parents = [multi_user_parser],
        help = "Re-activate accounts")
p.set_defaults(_event = "restore")

p = user.add_parser("delete",
        aliases = ["remove"],
        parents = [multi_user_parser],
        help = "Irreversibly destroy suspended accounts")
p.set_defaults(_event = "delete")

# Other user commands

user_add = user.add_parser("add",
        aliases = ["create"],
        help = "Add a new account")
user_add.set_defaults(_event = "add")
user_add.add_argument("-d", "--defaults",
        dest = "defaults",
        metavar = "USER_NAME",
        nargs = 1,
        help = "Suggest defaults from an existing user")

user_rename = user.add_parser("rename",
        help = "Change account UID")
user_rename.add_argument("oldname",
        metavar = "OLD_NAME",
        help = "Old UID")
user_rename.add_argument("newname",
        metavar = "NEW_NAME",
        help = "New UID")
user_rename.set_defaults(_event = "rename")

# Public key commands

key_parser = user.add_parser("key",
        help = "Manipulate user SSH public key")
key = key_parser.add_subparsers(title = "Key command")

single_user_parser = argparse.ArgumentParser(add_help = False)
single_user_parser.add_argument("username",
        metavar = "USER_NAME",
        help = "User ID")

p = key.add_parser("list",
        aliases = ["show"],
        parents = [single_user_parser],
        help = "List public keys for a user")
p.set_defaults(_event = "keys_list")

p = key.add_parser("add",
        aliases = ["create"],
        parents = [single_user_parser],
        help = "Add a public key to a user")
p.set_defaults(_event = "key_add")
p.add_argument("-f", "--file",
        dest = "key_file",
        metavar = "FILE_NAME",
        type = argparse.FileType("r"),
        nargs = 1,
        help = "Read public key from file")

p = key.add_parser("delete",
        aliases = ["remove"],
        parents = [single_user_parser],
        help = "Remove a public key from a user")
p.set_defaults(_event = "key_delete")
p.add_argument("key_names",
        metavar = "KEY_NAME",
        nargs = "*",
        help = "Public key MD5 modulus or comment")

# Unit commands

unit_parser = subcommands.add_parser("unit",
        help = "Organizational units")
unit_parser.set_defaults(_class = "UnitCommand")
unit_parser.set_defaults(_module = "unitcmd")

unit = unit_parser.add_subparsers(title = "Unit command")

p = unit.add_parser("list",
        help = "List all units")
p.set_defaults(_event = "list")

# List commands

list_parser = subcommands.add_parser("list",
        help = "Mailing lists")
list_parser.set_defaults(_class = "ListCommand")
list_parser.set_defaults(_module = "listcmd")

args = ap.parse_args()

log_level = log_levels[args.log_level]
logging.basicConfig(level = log_level)

def main():
    logging.debug("Invoking %s.%s" % (args._class, args._event))

    try:
        commands = importlib.import_module("." + args._module, "ldadm")
        command_instance = getattr(commands, args._class)(args)
        handler = getattr(command_instance, "on_" + args._event)
        handler()
    except Exception as e:
        if log_level == logging.DEBUG:
            raise RuntimeError("Daisy… Daisy…") from e
        else:
            sys.exit(str(e))

if __name__ == "__main__":
    main()
