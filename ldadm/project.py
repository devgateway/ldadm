import logging
from argparse import ArgumentParser

from ldap3.core.exceptions import LDAPEntryAlreadyExistsResult, LDAPKeyError, \
        LDAPAttributeOrValueExistsResult
from ldap3 import ALL_ATTRIBUTES, ObjectDef

from .command import Command
from .abstract import MissingObjects, LdapObjectMapping, LdapObject
from .config import cfg
from .user import single_user, multi_user, UserMapping
from .unit import UnitMapping, single_unit, multi_unit
from .console import pretty_print
from .connection import ldap

log = logging.getLogger(__name__)

single_project = ArgumentParser(add_help = False)
single_project.add_argument("project",
        metavar = "PROJECT",
        help = "Project name")

multi_project = ArgumentParser(add_help = False)
multi_project.add_argument("project",
        metavar = "PROJECT_NAME",
        nargs = "*",
        help = "One or more project names. If omitted, read from stdin.")

class Project(LdapObject):
    _config_node = cfg.project
    _object_class = cfg.project.objectclass
    _object_def = ObjectDef(object_class = _object_class, schema = ldap)

class ProjectMapping(LdapObjectMapping):
    _name = "Projects"
    _attribute = cfg.project.attr.id
    _object_def = Project._object_def
    _base = cfg.project.base

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
            },
            "unit": {
                "kwargs": {
                    "help": "Project units (categories)"
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
                            "help": "List projects in the unit"
                        },
                        "arguments": {
                            "--full": {
                                "action": "store_true",
                                "help": "List projects in nested units, too"
                            }
                        }
                    },
                    "add": {
                        "kwargs": {
                            "aliases": ["create"],
                            "help": "Add a project unit (category)"
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
                            "help": "Delete an project unit (category)"
                        }
                    },
                    "assign": {
                        "kwargs": {
                            "parents": [single_unit, multi_project],
                            "help": "Move projects to the unit (category)"
                        }
                    }
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

    def on_project_unit_list(self):
        units = UnitMapping(cfg.project.base)
        for unit in units:
            print(unit)

    def on_project_unit_show(self):
        units = UnitMapping(cfg.project.base)
        base = units[self._args.unit].entry_dn

        projects = ProjectMapping(base = base, sub_tree = self._args.full)
        for uid in projects:
            print(uid)

    def on_project_unit_add(self):
        units = UnitMapping(cfg.project.base)
        units.add(parent_name = self._args.parent)

    def on_project_unit_delete(self):
        unit_names = list(self._args_or_stdin("unit"))
        if unit_names:
            units = UnitMapping(cfg.project.base).select(unit_names)
            try:
                units.delete()
            except LDAPNotAllowedOnNotLeafResult as err:
                raise RuntimeError("One or more units not empty") from err

    def on_project_unit_assign(self):
        base = cfg.project.base
        units = UnitMapping(base)
        unit = units[self._args.unit]

        projects = ProjectMapping(base = base)
        projects.select(self._args_or_stdin("project"))
        projects.move(unit.entry_dn)
