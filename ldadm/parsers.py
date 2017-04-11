
# abstract parsers
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
