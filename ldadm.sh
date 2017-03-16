_ldadm() {
	local CUR="${COMP_WORDS[COMP_CWORD]}"
	local KWD_OBJECTS="user list"
	local KWD_SUSPENDED="--suspended"
	local KWD_LOGLEVEL="--loglevel"
	local KWD_DEFAULTS="--defaults -d"
	local OBJ_START
	local PREV
	local REPLY
	_init_completion || return

	# detect index of object, such as user, list, etc
	if [[ "${COMP_WORDS[1]}" = "$KWD_LOGLEVEL" ]]; then
		OBJ_START=3
	else
		OBJ_START=1
	fi

	# call per-object completion
	case "${COMP_WORDS[OBJ_START]}" in
		user) __ldadm_complete_user ;;
		list) __ldadm_complete_list ;;
		*)    __ldadm_complete_default ;;
	esac
}

# complete log levels or objects
__ldadm_complete_default() {
	case $COMP_CWORD in
		1) REPLY="$KWD_LOGLEVEL $KWD_OBJECTS" ;;
		2) REPLY="DEBUG INFO WARNING ERROR CRITICAL" ;;
		3) REPLY="$KWD_OBJECTS" ;;
		*) REPLY=""
	esac

	COMPREPLY=($(compgen -W "$REPLY" -- $CUR))
}

# list active or suspended users
__ldadm_list_users() {
	if [[ $1 = "suspended" ]]; then
		eval "ldadm user list $KWD_SUSPENDED"
	else
		ldadm user list
	fi
}

# complete user commands
__ldadm_complete_user() {
	# adjust COMP_CWORD for easier indexing, skip loglevel args
	let COMP_CWORD=(COMP_CWORD - OBJ_START + 1)
	local USERS

	case "${COMP_WORDS[OBJ_START + 1]}" in
		list|search|find)
			if [[ $COMP_CWORD -eq 3 ]]; then
				REPLY="$KWD_SUSPENDED"
				compopt -o nospace
			fi
			;;
		info|show)
			if [[ $COMP_CWORD -eq 3 ]]; then
				case "$CUR" in
					-*) REPLY="$KWD_SUSPENDED" ;;
					*)  REPLY="$KWD_SUSPENDED $(__ldadm_list_users)" ;;
				esac
			else
				if [[ "${COMP_WORDS[OBJ_START + 2]}" = "$KWD_SUSPENDED" ]]; then
					REPLY="$(__ldadm_list_users suspended)"
				else
					REPLY="$(__ldadm_list_users)"
				fi
			fi
			;;
		suspend|ban|lock|disable)
			REPLY="$(__ldadm_list_users)"
			;;
		restore|unban|enable|delete|remove)
			REPLY="$(__ldadm_list_users suspended)"
			;;
		add|create)
			USERS=$(__ldadm_list_users)
			case "$COMP_CWORD" in
				3) REPLY="$KWD_DEFAULTS" ;;
				4) REPLY="$(__ldadm_list_users suspended) $(__ldadm_list_users)" ;;
			esac
			;;
		rename)
			if [[ $COMP_CWORD -eq 3 ]]; then
				REPLY="$(__ldadm_list_users)"
			fi
			;;
		key)
			local PREV
			local keycmd="${COMP_WORDS[3]}"
			users=$(ldadm user list)
			case "$keycmd" in
				add|create|delete|remove)
					PREV="${COMP_WORDS[COMP_CWORD - 1]}"
					if [[ "$PREV" == "-f" || "$PREV" == "--file" ]]; then
						_filedir
					else
						COMPREPLY=($(compgen -W "-f --file $users" -- $CUR))
					fi
					;;
				list|show)
					COMPREPLY=($(compgen -W "$users" -- $CUR))
					;;
				*)
					COMPREPLY=($(compgen -W "add create delete remove list show" -- $CUR))
			esac
			;;
		*)
			REPLY="list search find show info suspend ban lock disable restore
			unban enable delete remove add create rename key"
			;;
	esac
	COMPREPLY=($(compgen -W "$REPLY" -- $CUR))
}

# complete list commands
__ldadm_complete_list() {
}

complete -F _ldadm ldadm
