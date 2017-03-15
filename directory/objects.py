import logging, string, re
try:
    import secrets # Python 3.6+
except ImportError:
    import random

from ldap3.utils.ciDict import CaseInsensitiveWithAliasDict

from .config import ConfigAttrError

log = logging.getLogger(__name__)

class User:
    object_def = None

    @staticmethod
    def make_password(*args_ignored):
        len_min = 10
        len_max = 18
        alphabet = string.ascii_letters + string.punctuation + string.digits

        try:
            length = len_min + secrets.randbelow(len_max - len_min + 1)
            chars = [ secrets.choice(alphabet) for i in range(length) ]
        except NameError:
            log.warning("Python module 'secrets' not available, suggesting insecure password")
            length = random.randrange(len_min, len_max)
            chars = [ random.choice(alphabet) for i in range(length) ]

        return ''.join(chars)

    def __init__(self, config_node, reference_object = None, handlers = []):
        self._reference = reference_object
        self._handlers = handlers
        self._templates = self._read_templates(config_node)
        self.attrs = CaseInsensitiveWithAliasDict()

        self._required_attrs = [ self._canonicalize_name(config_node.passwd)[0] ]

        # Resolve each attribute recursively
        for attr_def in __class__.object_def:
            key = attr_def.key
            if key in self._templates or key in self._required_attrs or attr_def.mandatory:
                if key.lower() != "objectclass":
                    self._resolve_attribute(key)

    def _read_templates(self, config_node):
        result = CaseInsensitiveWithAliasDict()

        try:
            templates = config_node.templates.__dict__["_cfg"]
            # read key, value from config; get aliases from schema
            for raw_name, value in templates.items():
                attr_names = self._canonicalize_name(raw_name)
                log.debug("Reading template for " + ", ".join(attr_names))
                result[attr_names] = value if type(value) is list else str(value)
        except ConfigAttrError:
            pass

        return result

    def _canonicalize_name(self, raw_name):
        definition = __class__.object_def[raw_name]
        all_names = [definition.key]
        if definition.oid_info:
            for name in definition.oid_info.name:
                if definition.key.lower() != name.lower():
                    all_names.append(name)

        return all_names

    def _resolve_attribute(self, raw_name):
        names = self._canonicalize_name(raw_name)
        key = names[0]

        if key in self.attrs: # already resolved
            log.debug("%s already resolved" % key)
            return

        if key in self._templates:
            # try to interpolate default value recursively
            log.debug("Trying to resolve template %s" % key)
            while True: # failure is not an option
                try:
                    if type(self._templates[key]) is list:
                        log.debug("%s is a list:" % key)
                        default = []
                        for template in self._templates[key]:
                            log.debug("\tAttempting to format '%s'" % template)
                            default.append( template.format_map(self.attrs) )
                    else:
                        log.debug("Attempting to format '%s'" % self._templates[key])
                        default = self._templates[key].format_map(self.attrs)

                    # TODO: modifiers?
                    break
                except KeyError as err:
                    # key missing yet, try to resolve recursively
                    missing_key = err.args[0]
                    log.debug("%s missing yet, resolving recursively" % missing_key)
                    self._resolve_attribute(missing_key)

        elif self._reference:
            # if a reference entry is given, take default value from there
            try:
                default = self._reference[key]
            except ldap3.core.exceptions.LDAPKeyError:
                pass

        else:
            default = None

        if key in self._handlers:
            handler = self._handlers[key]
            try:
                log.debug("Calling handler %s" % key)
                default = handler(default)
            except Exception as err:
                log.error(err)
                default = None

        if default:
            if type(default) is list:
                default_str = "; ".join(default)
            else:
                default_str = str(default)

            prompt = "%s [%s]: " % (key, default_str)

        else:
            prompt = "%s: " % key

        response = input(prompt)

        if response == ".":
            pass
        elif not response:
            if default:
                self.attrs[names] = default
            else:
                while not response:
                    log.error("%s requires a value" % key)
                    response = input(prompt)
                self.attrs[names] = response
        else:
            matches = re.split(r'\s*;\s', response)
            if len(matches) == 1:
                self.attrs[names] = response
            else:
                log.debug("Adding list %s" % repr(matches))
                self.attrs[names] = matches

    def __repr__(self):
        return repr(self.attrs)
