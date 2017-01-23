# ldadm — manage LDAP accounts

## Synopsis

	ldadm help COMMAND
	
	ldadm [OPTIONS…] {user|list|server|project} [ARGUMENTS…]

### User commands

	ldadm user list
	ldadm user search
	ldadm user {show|suspend|restore|delete} [USERNAME…]
	ldadm user add [-r] [USERNAME]
	ldadm user rename OLDNAME NEWNAME
	ldadm user keys list USERNAME
	ldadm user keys {delete|add} [-f FILENAME] USERNAME

### List commands

	ldadm list list
	ldadm list {show|search|delete|add} [LIST…] [ARGUMENTS…]
	ldadm list {useradd|userdel} LIST [USERNAME…]
