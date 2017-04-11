import logging, string, re
try:
    import secrets # Python 3.6+
except ImportError:
    import random

from ldap3.utils.ciDict import CaseInsensitiveWithAliasDict
from ldap3 import ObjectDef
from ldap3.core.exceptions import LDAPKeyError

from .config import cfg, ConfigAttrError
from .console import input_stderr
from .connection import ldap

log = logging.getLogger(__name__)

class LdapObject:
    _object_def = None
    _config_node = None
    _object_class = None
    _required_attrs = []

    def __init__(self, reference_object = None, pre = {}, post = {}):
        self._callbacks_pre = pre
        self._callbacks_post = post
        self._templates = self._read_templates()
        self._modifiers = self._read_modifiers()
        self.attrs = CaseInsensitiveWithAliasDict()
        self.message = ""
        self._reference = reference_object

        # resolve a message that will be output
        try:
            node = self.__class__._config_node
            if not node:
                raise ConfigAttrError()
            log.debug("Attempting to format creation message")
            message_template = node.message_on_create
            while True: # failure is not an option
                try:
                    self.message = message_template.format_map(self.attrs)
                    break
                except KeyError as err:
                    # key missing yet, try to resolve recursively
                    missing_key = err.args[0]
                    log.debug("%s missing yet, resolving recursively" % missing_key)
                    self._resolve_attribute(missing_key)

        except ConfigAttrError:
            log.debug("Template not set for creation message, skipping")
            pass # if this dict is missing, ignore

        # Resolve each attribute recursively
        for attr_def in self.__class__._object_def:
            key = attr_def.key
            if key in self._templates \
                    or key in self.__class__._required_attrs \
                    or attr_def.mandatory:
                if key.lower() == "objectclass":
                    self.attrs[key] = self.__class__._object_class
                else:
                    self._resolve_attribute(key)

    def _read_modifiers(self):
        """Read from config how to modify string(s) of the default value"""

        result = CaseInsensitiveWithAliasDict()
        safe_modifiers = ['capitalize', 'casefold', 'lower', 'swapcase', 'title', 'upper']

        try:
            node = self.__class__._config_node
            if not node:
                raise ConfigAttrError()
            modifiers = node.attr.modify.__dict__["_cfg"]
            # read key, value from config; get aliases from schema
            for raw_name, value in modifiers.items():
                if value not in safe_modifiers:
                    msg = "%s() is not a permitted modifier for %s" % (value, raw_name)
                    raise ValueError(msg)

                attr_names = self._canonicalize_name(raw_name)
                result[attr_names] = value
                log.debug("Modifier for %s: %s" % (", ".join(attr_names), value))
        except ConfigAttrError:
            pass # if this dict is missing, ignore

        return result

    def _read_templates(self):
        """Read format strings from config to use as default values for attributes"""

        result = CaseInsensitiveWithAliasDict()

        try:
            node = self.__class__._config_node
            if not node:
                raise ConfigAttrError()
            templates = node.attr.templates.__dict__["_cfg"]
            # read key, value from config; get aliases from schema
            for raw_name, value in templates.items():
                attr_names = self._canonicalize_name(raw_name)
                log.debug("Reading template for " + ", ".join(attr_names))
                result[attr_names] = value if type(value) is list else str(value)
        except ConfigAttrError:
            pass # if this dict is missing, ignore

        return result

    @classmethod
    def _canonicalize_name(cls, raw_name):
        """Normalize attribute name to use as CaseInsensitiveWithAliasDict index"""
        # rewritten from ldap3 library:
        # take properly cased attribute name, add other names as aliases
        definition = cls._object_def[raw_name]
        all_names = [definition.key]
        if definition.oid_info:
            for name in definition.oid_info.name:
                if definition.key.lower() != name.lower():
                    all_names.append(name)

        return all_names

    def _resolve_attribute(self, raw_name):
        """Fill attribute value from input, get defaults from template, or reference entry"""

        def execute_callback(callback, arg):
            name = "%s(%s)" % (callback.__qualname__, repr(arg))
            doc = callback.__doc__
            if doc:
                log.debug("For %s, calling %s # %s" % (key, name, doc))
            else:
                log.debug("For %s, calling %s" % (key, name))

            result = callback(arg)
            log.debug( "%s returned %s" % (name, repr(result)) )

            return result

        # use unambiguous name as the dictionary key
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
                        # resolve each member of the list
                        for template in self._templates[key]:
                            log.debug("\tAttempting to format '%s'" % template)
                            # try to format string from a dictionary
                            value = template.format_map(self.attrs)
                            # apply the string modifier to each member
                            if key in self._modifiers:
                                modifier = self._modifiers[key]
                                modify = getattr(value, modifier)
                                log.debug("Applying %s() to '%s'" % (modifier, value))
                                value = modify()

                            default.append(value)
                    else:
                        # try to format string from a dictionary
                        log.debug("Attempting to format '%s'" % self._templates[key])
                        default = self._templates[key].format_map(self.attrs)
                        # apply the string modifier
                        if key in self._modifiers:
                            modifier = self._modifiers[key]
                            modify = getattr(default, modifier)
                            log.debug("Applying %s() to '%s'" % (modifier, default))
                            default = modify()

                    break # resolving the formatter complete, go on
                except KeyError as err:
                    # key missing yet, try to resolve recursively
                    missing_key = err.args[0]
                    log.debug("%s missing yet, resolving recursively" % missing_key)
                    self._resolve_attribute(missing_key)

        elif self._reference:
            # if a reference entry is given, take default value from there
            try:
                default = self._reference[key]
            except LDAPKeyError:
                pass # unless there's no such attribute in the reference

        else:
            default = None

        # indirectly apply callbacks: give them current default, receive new default
        try:
            callback = self._callbacks_pre[key]
            default = execute_callback(callback, default)
        except KeyError:
            pass # no callback set
        except Exception as err:
            # the callback failed; resort to user input
            log.warn(err)
            default = None

        # prepare a human-readable default prompt; convert dict to semicolon-delimited string
        if default:
            if type(default) is list:
                default_str = "; ".join(default)
            else:
                default_str = str(default)

            prompt = "%s [%s]: " % (key, default_str)

        else:
            prompt = "%s: " % key

        while True:
            response = input_stderr(prompt)

            if response == ".":
                break # dot entered, delete this attribute
            elif not response:
                # use default if possible
                result = default if default else None

                # indirectly apply callbacks
                try:
                    callback = self._callbacks_post[key]
                    result = execute_callback(callback, result)
                except KeyError: # no callback set
                    pass
                except Exception as err:
                    # the callback failed; require user input again
                    log.error(err)
                    continue

                if result:
                    self.attrs[names] = result
                    break
                else:
                    log.error("%s requires a value" % key)
                    continue

            else:
                # try to split string into a list
                matches = re.split(r'\s*;\s+', response)
                if len(matches) == 1:
                    result = response # seems to be a single value
                else:
                    log.debug("Adding list %s" % repr(matches))
                    result = matches

                try:
                    callback = self._callbacks_post[key]
                    result = execute_callback(callback, result)
                except KeyError:
                    pass # no callback set
                except Exception as err:
                    # the callback failed; require user input again
                    log.error(err)
                    continue

                self.attrs[names] = result
                break

    def __repr__(self):
        return repr(self.attrs)

class User(LdapObject):
    _config_node = cfg.user
    _object_class = cfg.user.objectclass
    # Load attribute definitions by ObjectClass
    _object_def = ObjectDef(object_class = _object_class, schema = ldap)


    @staticmethod
    def make_password(*args_ignored):
        """Generate a random password of random length"""

        len_min = 10
        len_max = 18
        alphabet = string.ascii_letters + string.punctuation + string.digits

        # select random password length within given limits
        # then for each position randomly select a character from the alphabet
        try:
            length = len_min + secrets.randbelow(len_max - len_min + 1)
            chars = [ secrets.choice(alphabet) for i in range(length) ]
        except NameError:
            log.warning("Python module 'secrets' not available, suggesting insecure password")
            length = random.randrange(len_min, len_max)
            chars = [ random.choice(alphabet) for i in range(length) ]

        return ''.join(chars)

    def __init__(self, reference_object = None, pre = {}, post = {}):
        self.__class__._required_attrs = [ self._canonicalize_name(cfg.user.attr.passwd)[0] ]
        super().__init__(reference_object = reference_object, pre = pre, post = post)

class Unit(LdapObject):
    try:
        _config_node = cfg.unit
    except ConfigAttrError:
        _config_node = None

    _object_class = "organizationalUnit"
    # Load attribute definitions by ObjectClass
    _object_def = ObjectDef(object_class = _object_class, schema = ldap)
