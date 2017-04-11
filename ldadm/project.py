import logging

from ldap3.core.exceptions import LDAPEntryAlreadyExistsResult, LDAPKeyError, \
        LDAPAttributeOrValueExistsResult
from ldap3 import ALL_ATTRIBUTES

from .command import Command
from .collections import ProjectMapping, UserMapping, MissingObjects
from .config import cfg
from .objects import Project
from .parsers import single_user, multi_user, single_project, multi_project
from .console import pretty_print

log = logging.getLogger(__name__)

class ProjectCommand(Command):
    __base = cfg.project.base
    parser_name = "project"
    parser_args = {
        "kwargs": {
            "help": "Projects"
        },
        "subparsers_title": "Project command",
        "subparsers": {
            "list": {
                "kwargs": {
                    "help": "List all projects"
                }
            },
            "show": {
                "kwargs": {
                    "parents": [multi_project],
                    "aliases": ["info"],
                    "help": "List project attributes"
                }
            },
            "add": {
                "kwargs": {
                    "aliases": ["create"],
                    "help": "Add a project"
                },
                "arguments": {
                    "--defaults": {
                        "dest": "defaults",
                        "metavar": "PROJECT",
                        "nargs": 1,
                        "help": "Suggest defaults from an existing project"
                    }
                }
            },
            "delete": {
                "kwargs": {
                    "parents": [multi_project],
                    "aliases": ["remove"],
                    "help": "Delete projects"
                }
            },
            "assign": {
                "kwargs": {
                    "parents": [single_project],
                    "help": "Make users members of the project"
                },
                "arguments": {
                    "names": {
                        "metavar": "NAME",
                        "help": "User or server ID",
                        "nargs": "+"
                    }
                }
            },
            "manage": {
                "kwargs": {
                    "parents": [single_project, single_user],
                    "help": "Make user the manager of the project"
                }
            }
        }
    }

    def _get_dn(self, names):
        if type(names) is list:
            name_list = names
        else:
            name_list = [names]

        users = UserMapping(base = cfg.user.base.active)
        users.select(name_list)

        try:
            results = list( users.dns() )
        except MissingObjects:
            try:
                servers = ServerMapping().select(name_list)
                results = list( servers.dns() )
            except MissingObjects as err:
                msg = "Unknown users or servers: " + ", ".join(err.items)
                raise RuntimeError(msg) from err

        if type(names) is list:
            return results
        else:
            return results[0]

    def on_project_list(self):
        projects = ProjectMapping()
        for name in projects:
            print(name)

    def on_project_show(self):
        projects = ProjectMapping(attrs = ALL_ATTRIBUTES)
        projects.select(self._args_or_stdin("project"))
        for entry in projects.values():
            pretty_print(entry)

    def on_project_add(self):
        attr_name = ProjectMapping._attribute
        projects = ProjectMapping(attrs = ALL_ATTRIBUTES)

        # Get default values from a reference object
        if self._args.defaults:
            source_obj = projects[self._args.defaults]
        else:
            source_obj = None

        post = {
                cfg.project.attr.manager: self._get_dn,
                cfg.project.attr.member: self._get_dn
                }
        project = Project(reference_object = source_obj, post = post)
        id = project.attrs[attr_name]
        projects[id] = project.attrs

        if project.message:
            print(project.message)

    def on_project_delete(self):
        project_names = list(self._args_or_stdin("project"))
        if project_names:
            projects = ProjectMapping()
            projects.select(project_names).delete()

    def on_project_assign(self):
        project_name = self._args.project
        attr_name = cfg.project.attr.member

        projects = ProjectMapping(attrs = attr_name)
        project = projects[project_name].entry_writable()
        members = project[attr_name]

        names = list(self._args_or_stdin("names"))
        if not names:
            raise RuntimeError("Expected user or server IDs to assign to %s" % project_name)

        members += self._get_dn(names)

        try:
            project.entry_commit_changes(refresh = False)
        except LDAPAttributeOrValueExistsResult as err:
            raise RuntimeError("One or more users already assigned to this project") from err

    def on_project_manage(self):
        user_name = self._args.username
        attr_name = cfg.project.attr.manager

        projects = ProjectMapping(attrs = attr_name)
        project = projects[self._args.project].entry_writable()

        users = UserMapping(base = cfg.user.base.active)
        users.select([user_name])
        dn = list( users.dns() )[0]

        setattr(project, attr_name, dn)
        project.entry_commit_changes(refresh = False)
