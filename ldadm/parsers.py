from argparse import ArgumentParser

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

single_unit = ArgumentParser(add_help = False)
single_unit.add_argument("unit",
        metavar = "UNIT",
        help = "Unit name")

multi_unit = ArgumentParser(add_help = False)
multi_unit.add_argument("unit",
        metavar = "UNIT_NAME",
        nargs = "*",
        help = "One or more unit names. If omitted, read from stdin.")

single_project = ArgumentParser(add_help = False)
single_project.add_argument("project",
        metavar = "PROJECT",
        help = "Project name")

multi_project = ArgumentParser(add_help = False)
multi_project.add_argument("project",
        metavar = "PROJECT_NAME",
        nargs = "*",
        help = "One or more project names. If omitted, read from stdin.")
