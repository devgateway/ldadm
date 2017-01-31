import logging
import os

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
    except KeyError as key:
        msg = "Expected scope base|one|sub, got '%s'" % scope_str
        raise ConfigException(msg) from key

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
            msg = "Config file '%s': %s" % (err.filename, err.strerror)
            raise ConfigException(msg) from err

        cfg = yaml.safe_load(cfg_file)

        # validate server config
        try:
            if "uri" not in cfg["ldap"]:
                raise ConfigException("Missing 'uri' from dict 'ldap' in config")
        except KeyError as key:
                raise ConfigException("Missing dict 'ldap' from config") from key

        try:
            cfg["ldap"]["binddn"]
            cfg["ldap"]["bindpw"]
        except KeyError:
            cfg["ldap"]["binddn"] = None
            cfg["ldap"]["bindpw"] = None

        return cfg

    def _validate_section(self):
        try:
            section = self._full_config[self.config_section]
        except KeyError as key:
            msg = "Missing section %s from config", str(key)
            raise ConfigException(msg) from key

        if type(section) is not dict:
            msg = "'%s' must be a dict in config" % self.config_section
            raise ConfigException(msg)

        keys = ["filter", "base", "scope"]
        if self.required_settings:
            keys.extend(self.required_settings)

        try:
            for key in keys:
                if section[key] == "":
                    msg = "Empty value of '%s' in section '%s' in config" % \
                            (key, self.config_section)
                    raise ConfigException(msg)

        except KeyError as key:
            msg = "Missing member %s from section '%s' in config" % \
                    (str(key), self.config_section)
            raise ConfigException(msg) from key

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
