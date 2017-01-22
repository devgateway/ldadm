# ldadm — manage LDAP accounts

## Synopsis

	ldadm help COMMAND
	
	ldadm [OPTIONS…] {user|list|server|project} [ARGUMENTS…]

### User commands

	ldadm user list
	ldadm user search
	ldadm user {show|enable|disable|delete|add|rename|grant} [-r] [USERNAME…]
	ldadm user keys list USERNAME
	ldadm user keys {delete|add} [-f FILENAME] USERNAME

### List commands

	ldadm list list
	ldadm list {show|search|delete|add} [LIST…] [ARGUMENTS…]
	ldadm list {useradd|userdel} LIST [USERNAME…]
