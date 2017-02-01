import logging
import os
import copy

import yaml

class ConfigAttrError(AttributeError):
    pass

class Config:
    def __init__(self):
        self._parent = None
        self._name = None
        if not hasattr(__class__, "_cfg"):
            self._load_from_file()

    def _load_from_file(self):
        basename = "ldadm.yml"
        try:
            filename = os.path.join(os.environ["XDG_CONFIG_HOME"], basename)
        except KeyError:
            filename = os.path.join(os.environ["HOME"], ".config", basename)

        try:
            logging.debug("Loading config from %s" % filename)
            __class__._cfg = yaml.safe_load(open(filename))
            self._cfg = __class__._cfg
        except OSError as err:
            msg = "Config file '%s': %s" % (err.filename, err.strerror)
            raise ConfigException(msg) from err

    def __getattr__(self, name):
        try:
            attr = self._cfg[name]
        except KeyError as key:
            raise ConfigAttrError(self._attr_name(name)) from key
        except TypeError as err:
            raise ConfigAttrError(self._attr_name(name)) from err

        if type(attr) is dict:
            cfg = __class__()
            cfg._cfg = attr
            cfg._parent = self
            cfg._name = name
            return cfg
        elif attr is None:
            raise ConfigAttrError(self._attr_name(name))
        else:
            return attr

    def _get_path(self):
        if self._parent:
            path = self._parent._get_path() + [self._name]
        else:
            path = []

        return path

    def _attr_name(self, name = None):
        path = self._get_path()
        if name:
            path.append(name)

        return ".".join(path)

    def __str__(self):
        return self._attr_name()
