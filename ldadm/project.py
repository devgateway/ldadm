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

    def _get_project(self, project_name):
        projects = ProjectMapping(limit = [project_name])

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

        # Get default values from a reference object
        if self._args.defaults:
            source_obj = self._get_project(self._args.defaults, ALL_ATTRIBUTES)
        else:
            source_obj = None

        post = {
                cfg.project.attr.manager: self._get_dns,
                cfg.project.attr.member: self._get_dns
                }
        project = Project(reference_object = source_obj, post = post)
        id = project.attrs[attr_name]
        projects = ProjectMapping()
        projects[id] = project.attrs

        if project.message:
            print(project.message)

    def on_project_delete(self):
        project_names = list(self._args_or_stdin("project"))
        if not project_names:
            return

        projects = ProjectMapping(limit = project_names)
        for name in project_names:
            del projects[name]

        try:
            projects.commit_delete()
        except MissingObjects as err:
            raise RuntimeError("Projects not found: " + ", ".join(err.items))
