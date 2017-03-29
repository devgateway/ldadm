# ldadm — manage LDAP accounts

## Synopsis

	ldadm [OPTIONS…] {user|unit|list|server|project} [ARGUMENTS…]

### User commands

	ldadm user list [--suspended]
	ldadm user search [--suspended] LDAP_FILTER
	ldadm user show [--suspended] [USER_NAME…]
	ldadm user {suspend|restore|delete} [USER_NAME…]
	ldadm user add [--defaults USER_NAME]
	ldadm user rename OLD_NAME NEW_NAME
	ldadm user key list USER_NAME
	ldadm user key delete USER_NAME KEY_NAME…
	ldadm user key add [--file FILE_NAME] USER_NAME

### Unit commands

	ldadm unit list
	ldadm unit show [--full] UNIT
	ldadm unit add [--parent PARENT_UNIT]
	ldadm unit delete UNIT
	ldadm unit assign UNIT [USER_NAME…]

### List commands

	ldadm list list
	ldadm list {show|search|delete|add} [LIST…] [ARGUMENTS…]
	ldadm list {useradd|userdel} LIST [USER_NAME…]

## User commands

### Listing users

	ldadm user list [--suspended]

List active user IDs, one per line. If `--suspended` argument is given, only list inactive accounts.

### Searching for users using LDAP filter

	ldadm user search [--suspended] LDAP_FILTER

Search active user accounts using LDAP search syntax, print matching user IDs. If `--suspended` argument is given, only search inactive accounts.

Search implies logical AND with all objectClasses from `user` section in the configuration file; i.e. the final search filter will look like:

	(&(&(objectClass=inetOrgPerson)(objectClass=posixAccount))(surname=Sure))

You are responsible for escaping the filter properly.

### Displaying user attributes

	ldadm user show [--suspended] [USER_NAME…]

Display all user attributes. If `--full` argument is given, also display operational attributes. If `--suspended` argument is given, only show inactive accounts.

One or more user names may be given as arguments, or provided from standard input. If they're given as arguments, standard input is ignored.

### Suspending and restoring users

	ldadm user suspend [USER_NAME…]
	ldadm user restore [USER_NAME…]

Move user accounts from active to suspended unit, or vice versa. LDAP server must preserve the account unique ID on these LDAP move operations.

### Deleting suspended users

	ldadm user delete [USER_NAME…]

Delete the accounts from LDAP completely. Only suspended accounts will be considered, so if you want an active account deleted, you must suspend it first.

### Creating a new user

	ldadm user add [--defaults USER_NAME]

Create a new user account. Necessary attributes will be requested from user input. Necessary attributes include:

* those that are defined in LDAP schema as required,

* those for which templates have been defined in the configuration file,

* and the ones required by this program.

Templates may be defined in the configuration file. They use [Python format string syntax](https://docs.python.org/3/library/string.html#formatstrings), and can be single values or lists. Templates may use other templates (single values only, not lists), and will be interpolated recursively. You are responsible for avoiding recursive loops in that case. After interpolation, the values may additionally undergo one string modification each. Modifications are [Python string methods](https://docs.python.org/3/library/stdtypes.html#string-methods), and the permitted ones are: capitalize, casefold, lower, swapcase, title, upper.

If `--defaults` argument is used, default attribute values are read from that user. However, templates will have precedence over those defaults.

The attributes required by this program are: user ID, numeric user ID, and password. Their actual names must be defined in the configuration file.

Default passwords will be generated randomly using secure **secrets** module if available (Python 3.6+), or using insecure **random** module. In the latter case, a warning will be issued.

Numeric user IDs can not be generated sequentially, because that would require storing the maximum used value somewhere, and LDAP does not provide this capability without customization. Therefore, this program generates random numeric user IDs from the range defined in the configuration file. Currently, newer Debian and RedHat based systems safely allow numeric UID between 1000 and 60000. This program will detect and avoid UID and numeric UID collisions.

After the default values are determined or generated, the user will be prompted to accept, delete, or change them. Entering empty value will accept default, and entering a dot (.) will ignore the attribute. Multiple values can be separated using a semicolon (;).

After the account has been created, a message defined as `message_on_create` in the configuration file may be printed to standard output. Since attribute prompts are printed on standard error, you can easily feed the output to another program, e.g. send a welcome message with an email client:

	kmail --composer --body "$(ldadm user add)"

### Renaming a user

	ldadm user rename OLD_NAME NEW_NAME

Modify user RDN (relative distinguished name). LDAP server must keep the object unique ID. Only the attribute comprising the RDN will be changed, but not other attributes (such as canonical name, cn).

### Listing user's SSH public keys

	ldadm user key list USER_NAME

List MD5 hashes and comments (if present) for the user's SSH public keys. Unsupported and invalid keys will be printed as a placeholder, but will not result in an error. Missing public key attribute will not cause an error either.

### Deleting SSH public keys from a user

	ldadm user key delete USER_NAME KEY_NAME…

Delete public keys from the user by MD5 hash or comment. MD5 prefix and separators are ignored, only 16 hex digits are used. If those are not found, the argument is considered the comment part of the key.

### Adding SSH public keys to a user

	ldadm user key add [--file FILE_NAME] USER_NAME

Add public keys to the user, reading one key per line from the given file, or standard input. Only single-line keys (OpenSSH format) are supported, not PEM-encoded PKCS#1 ones.

## Unit commands

### Listing units

	ldadm unit list

Search for units in subtree scope, i.e. including the root unit, and display their IDs (names).

### Listing users in a unit

	ldadm unit show [--full] UNIT

List user IDs belonging to a unit. If `--full` argument is given, a subtree search is made, i.e. users from nested units are included.

### Creating a new unit

	ldadm unit add [--parent PARENT_UNIT]

Add a new unit, prompting the user for required attributes. If `--parent` argument is given, create the new one nested under that unit.

### Deleting a unit

	ldadm unit delete UNIT

Removing an empty unit. LDAP server must refuse the operation if the unit is not empty.

### Moving people to a unit

	ldadm unit assign UNIT [USER_NAME…]

Assign users to a unit, moving their accounts from their current unit(s). User names are read from argument list, or standard input.

## Configuration file

The program will look for the configuration file in these locations:

1. `${XDG_CONFIG_HOME}/ldadm.yml`

2. `${HOME}/.config/ldadm.yml`

The first file found will be used. The file is in [YAML format](http://yaml.org/).

### Section `ldap`

Contains generic parameters for LDAP server connection and search.

* `uri` — LDAP server URI. Everything permitted by libldap is accepted, including port specification and space-separated multiple URIs.

* `binddn`, `bindpw` — optional DN and password to connect as. If omitted, anonymous bind is used.

* `paged_search_size` — multiple object operations are performed using paged search, fetching this many objects at a time. Be sure to set it lower than your server search size limit (default is usually 500).

### Section `user`

Contains settings and templates for user account objects.

* `base` — a dictionary with LDAP search bases for user accounts: `active` and `suspended`.

* `nuid` — a dictionary defining the range for numeric user IDs: `min` and `max`.

* `message_on_create` — an optional message printed when a user account has been created. Using YAML indented delimiting is recommended for readability. Note that YAML discards the first indented empty string, so use two indented empty strings when you want an empty line printed.

* `objectclass` — a list of LDAP object classes implied in account search and creation.

* `attr` — a dictionary defining the actual attribute names in your directory and templates for new accounts.

#### Dictionary `attr`

* `uid`, `nuid`, `passwd` — attribute names for user ID, numeric user ID, and user password, respectively.

* `templates` — an optional dictionary, where keys are attribute names, and values are Python formatting strings (or lists thereof), that can refer to other attributes. Be sure to quote the values if they start with a brace, because braces are special in YAML. Don't cause infinite recursion by defining attributes using each other.

* `modify` — an optional dictionary, where keys are attribute names, and values are Python string functions. Functions get applied to default attribute values after formatting, but before confirming with the user. Permitted functions are: capitalize, casefold, lower, swapcase, title, upper.

## Environment

* `XDG_CONFIG_HOME`, `HOME` — used to search the configuration file, see details above.

* `LOG_LEVEL` — logging verbosity. Valid levels are: CRITICAL, ERROR, WARNING, INFO, and DEBUG; with WARNING being the default. If level is DEBUG, unexpected exceptions are not trapped, and backtrace is printed.
