import logging
import os
import sys

import yaml
import ldap3

class ConfigException(Exception):
    pass

def get_scope(scope_str):
    ldap_scopes = {
            "base": ldap3.BASE,
            "one": ldap3.LEVEL,
            "sub": ldap3.SUBTREE
            }
    try:
        scope = ldap_scopes[scope_str.lower()]
    except KeyError:
        raise ConfigException("Expected scope base|one|sub, got %s" % scope_str)

    return scope

class Command:
    def __init__(self, args):
        self._args = args
        self._cfg = self._load_config()
        cfg_ldap = cfg["ldap"]
        self._ldap = ldap3.Connection(
                server = cfg_ldap["uri"],
                user = cfg_ldap["binddn"],
                password = cfg_ldap["bindpw"],
                raise_exceptions = True)

    def _load_config(self):
        try:
            cfg_dir = os.environ["XDG_CONFIG_HOME"]
        except KeyError:
            cfg_dir = os.environ["HOME"] + "/.config"

        try:
            cfg_path = cfg_dir + "/ldadm.yml"
            logging.debug("Loading config from %s" % cfg_path)
            cfg_file = open(cfg_path)
        except OSError as err:
            raise ConfigException("Config file '%s': %s" % (err.filename, err.strerror))

        cfg = yaml.safe_load(cfg_file)

        # validate server config
        if "ldap" not in cfg:
            raise ConfigException("Missing 'ldap' dict from config")
        if "uri" not in cfg["ldap"]:
            raise ConfigException("Missing 'uri' string from 'ldap' dict in config")

        if "binddn" not in cfg["ldap"]:
            cfg["ldap"]["binddn"] = None
            cfg["ldap"]["bindpw"] = None

        return cfg

    def _validate_config(self, section, keys):

class UserCommand(Command):
    def __init__(self, args):
        super(__class__, self).__init__(self, args)
        self.cfg = self._cfg["user"]
        for key in ("base"

    def list_users(self):
        cfg_user = self._cfg["user"]
        self._ldap.search(
                search_base = cfg_user["base"], 
                search_filter = cfg_user["filter"],
                search_scope = get_scope(cfg_user["scope"]),
                attributes = cfg_user["id_attr"])

#    def search(self):
#    def show(self):
#    def suspend(self):
#    def restore(self):
#    def delete(self):
#    def add(self):
#    def rename(self):
#    def list_keys(self):
    def add_key(self):
        pass
#    def delete_key(self):
