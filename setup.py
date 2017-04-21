# Copyright 2017, Development Gateway, Inc.
# This file is part of ldadm, see COPYING.

from setuptools import setup

setup(
        name = "ldadm",
        version = "1.0",
        license = "GPLv3+",
        description = "Manage LDAP accounts",
        author = "Development Gateway",
        python_requires = ">= 3.4",
        packages = ["ldadm"],
        install_requires = [
            "PyYAML",
            "ldap3 >= 2.2.2",
            "sshpubkeys >= 2.2.0"
            ],
        entry_points = {
            "console_scripts": [
                "ldadm = ldadm.main:main"
                ]
            }
        )
