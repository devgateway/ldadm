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
                    "parents": [single_project, multi_user],
                    "help": "Make users members of the project"
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

    def _get_project(self, project_name, attrs = None):
        projects = ProjectMapping(limit = [project_name], attrs = attrs)

        try:
            project_list = [p for p in projects]
            return project_list[0]
        except MissingObjects as err:
            raise RuntimeError("Project %s not found" % project_name) from err

    def _get_dns(self, names):
        if type(names) is list:
            limit = names
        else:
            limit = [names]

        users = UserMapping(base = cfg.user.base.active, limit = limit)

        try:
            results = [u.entry_dn for u in users]
        except MissingObjects:
            try:
                servers = ServerMapping(limit = limit)
                results = [s.entry_dn for s in servers]
            except MissingObjects as err:
                msg = "Unknown users or servers: " + ", ".join(err.items)
                raise RuntimeError(msg) from err

        if type(names) is list:
            return results
        else:
            return results[0]

    def on_project_list(self):
        projects = ProjectMapping()
        for name in projects.keys():
            print(name)

    def on_project_show(self):
        project_names = list(self._args_or_stdin("project"))
        projects = ProjectMapping(limit = project_names, attrs = ALL_ATTRIBUTES)
        try:
            for project_entry in projects:
                pretty_print(project_entry)
        except MissingObjects as err:
            raise RuntimeError("Projects not found: " + ", ".join(err.items))

    def on_project_add(self):
        attr_name = ProjectMapping._attribute
        projects = ProjectMapping(attrs = ALL_ATTRIBUTES)

        # Get default values from a reference object
        if self._args.defaults:
            source_obj = projects[self._args.defaults]
        else:
            source_obj = None

        post = {
                cfg.project.attr.manager: self._get_dns,
                cfg.project.attr.member: self._get_dns
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

        project = self._get_project(project_name, attr_name).entry_writable()
        members = project[attr_name]

        usernames = list(self._args_or_stdin("username"))
        users = UserMapping(base = cfg.user.base.active, limit = usernames)
        new_members = self._get_dns( list(users.keys()) )
        members += new_members

        try:
            project.entry_commit_changes(refresh = False)
        except LDAPAttributeOrValueExistsResult as err:
            raise RuntimeError("One or more users already assigned to this project") from err

    def on_project_manage(self):
        project_name = self._args.project
        user_name = self._args.username
        attr_name = cfg.project.attr.manager

        project = self._get_project(project_name, attr_name).entry_writable()
        users = UserMapping(base = cfg.user.base.active, limit = [user_name])
        user_name = list(users.keys())[0]

        setattr(project, attr_name, self._get_dns(user_name))
        project.entry_commit_changes(refresh = False)
