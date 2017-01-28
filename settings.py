import yaml
import os
import sys

class Settings:
    def __init__(self):
        try:
            cfg_dir = os.environ["XDG_CONFIG_HOME"]
        except KeyError:
            cfg_dir = os.environ["HOME"] + "/.config"

        try:
            cfg_file = open(cfg_dir + "/ldadm.yml")
        except OSError as err:
            sys.exit("Config file '%s': %s" % (err.filename, err.strerror))
