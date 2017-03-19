# ldadm — manage LDAP accounts

## Synopsis

	ldadm [OPTIONS…] {user|list|server|project} [ARGUMENTS…]

### User commands

	ldadm user list [--suspended]
	ldadm user search [--suspended] LDAP_FILTER
	ldadm user show [--suspended] [USER_NAME…]
	ldadm user {suspend|restore|delete} [USER_NAME…]
	ldadm user add [{-d|--defaults} USER_NAME]
	ldadm user rename OLD_NAME NEW_NAME
	ldadm user key list USER_NAME
	ldadm user key delete USER_NAME KEY_NAME…
	ldadm user key add [{-f|--file} FILE_NAME] USER_NAME

### List commands

	ldadm list list
	ldadm list {show|search|delete|add} [LIST…] [ARGUMENTS…]
	ldadm list {useradd|userdel} LIST [USER_NAME…]
