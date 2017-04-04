import argparse, logging

log = logging.getLogger(__name__)

# abstract parsers
single_user = argparse.ArgumentParser(add_help = False)
single_user.add_argument("username",
        metavar = "USER_NAME",
        help = "User ID")

multi_user = argparse.ArgumentParser(add_help = False)
multi_user.add_argument("username",
        metavar = "USER_NAME",
        nargs = "*",
        help = "One or more UIDs. If omitted, read from stdin.")

only_suspended = argparse.ArgumentParser(add_help = False)
only_suspended.add_argument("--suspended",
        action = "store_true",
        help = "Only include suspended users")

single_unit = argparse.ArgumentParser(add_help = False)
single_unit.add_argument("unit",
        metavar = "UNIT",
        help = "Unit name")

multi_unit = argparse.ArgumentParser(add_help = False)
multi_unit.add_argument("unit",
        metavar = "UNIT_NAME",
        nargs = "*",
        help = "One or more unit names. If omitted, read from stdin.")

# concrete parsers, more readable than a ton of statements
_parsers = {
}

def get_args():
    ap = argparse.ArgumentParser(description = "Manage LDAP accounts")

    subcommands = ap.add_subparsers(description = "Objects to manage", dest = "subcommand")
    subcommands.required = True

    for name, options in _parsers.items():
        add_parser(subcommands, "", name, options)

    args = ap.parse_args()
    return args
