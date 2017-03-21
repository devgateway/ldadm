from setuptools import setup

setup(
        name = "ldadm",
        version = "1.0",
        description = "Manage LDAP accounts",
        author = "Development Gateway",
        python_requires = ">= 3.4",
        packages = ["ldadm"],
        install_requires = [
            "ldap3 >= 2.2.2",
            "sshpubkeys >= 2.2.0"
            ],
        entry_points = {
            "console_scripts": [
                "ldadm = ldadm.main:main"
                ]
            }
        )
