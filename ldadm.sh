_ldadm() {
	local CUR="${COMP_WORDS[COMP_CWORD]}"
	local COMMAND='LOG_LEVEL=CRITICAL ldadm'
	local KWD_OBJECTS="user list unit"
	local KWD_SUSPENDED="--suspended"
	local KWD_DEFAULTS="--defaults"
	local KWD_FILE="--file"
	local KWD_FULL="--full"
	local KWD_PARENT="--parent"
	local REPLY
	local COMPLETION_LIB=
	if [[ -n "$(type _init_completion 2>/dev/null)" ]]; then
		_init_completion
		COMPLETION_LIB=y
	fi

	# call per-object completion
	case "${COMP_WORDS[1]}" in
		user) __ldadm_complete_user ;;
		list) __ldadm_complete_list ;;
		unit) __ldadm_complete_unit ;;
		*) COMPREPLY=($(compgen -W "$KWD_OBJECTS" -- $CUR)) ;;
	esac
}

# list active or suspended users
__ldadm_list_users() {
	local CMDLINE="$COMMAND user list"
	if [[ $1 = "suspended" ]]; then
		CMDLINE="$CMDLINE $KWD_SUSPENDED"
	fi
	eval "$CMDLINE"
}

__ldadm_list_units() {
	eval "$COMMAND unit list"
}

# complete user commands
__ldadm_complete_user() {
	local USERS

	case "${COMP_WORDS[2]}" in
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
				if [[ "${COMP_WORDS[3]}" = "$KWD_SUSPENDED" ]]; then
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
			USERS=$(__ldadm_list_users)
			case "${COMP_WORDS[3]}" in
				add|create)
					case $COMP_CWORD in
						4) REPLY="$KWD_FILE" ;;
						5)
							if [[ -n "$COMPLETION_LIB" ]]; then
								_filedir
							else
								compopt -o default
							fi
							return 0
							;;
					esac
					;;
				delete|remove)
					if [[ $COMP_CWORD -eq 4 ]]; then
						REPLY="$(__ldadm_list_users)"
					else
						return 0
					fi
					;;
				list|show) REPLY="$(__ldadm_list_users)" ;;
				*) REPLY="add create delete remove list show" ;;
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
	return 1
}

# complete unit commands
__ldadm_complete_unit() {
	case "${COMP_WORDS[2]}" in
		list) ;;
		add)
			case "$COMP_CWORD" in
				3) REPLY="$KWD_PARENT" ;;
				4) REPLY="$(__ldadm_list_units)" ;;
			esac
			;;
		show|info)
			case "$COMP_CWORD" in
				3)
					case "$CUR" in
						-*) REPLY="$KWD_FULL" ;;
						*)  REPLY="$KWD_FULL $(__ldadm_list_units)" ;;
					esac
					;;
				4)
					REPLY="$(__ldadm_list_units)" ;;
			esac
			;;
		delete|remove) REPLY="$(__ldadm_list_units)" ;;
		assign)
			case "$COMP_CWORD" in
				3) REPLY="$(__ldadm_list_units)" ;;
				*) REPLY="$(__ldadm_list_users)" ;;
			esac
			;;
		*)
			REPLY="list show info assign add create delete remove"
			;;
	esac
	COMPREPLY=($(compgen -W "$REPLY" -- $CUR))
}

complete -F _ldadm ldadm
