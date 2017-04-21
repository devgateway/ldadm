_ldadm() {
	local CUR="${COMP_WORDS[COMP_CWORD]}"
	local COMMAND='LOG_LEVEL=CRITICAL ldadm'
	local KWD_OBJECTS="user list project"
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
		project) __ldadm_complete_project ;;
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

__ldadm_list_projects() {
	eval "$COMMAND project list"
}

__ldadm_list_units() {
	eval "$COMMAND $1 unit list"
}

__ldadm_list_servers() {
	#eval "$COMMAND server list"
	:
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
		rename|passwd)
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
		unit)
			__ldadm_complete_unit __ldadm_list_users user
			return
			;;
		*)
			REPLY="list search find show info suspend ban lock disable restore
			unban enable delete remove add create rename key passwd unit"
			;;
	esac
	COMPREPLY=($(compgen -W "$REPLY" -- $CUR))
}

# complete list commands
__ldadm_complete_list() {
	return 1
}

# complete project commands
__ldadm_complete_project() {
	case "${COMP_WORDS[2]}" in
		list|add|create) ;;
		show|info)
				REPLY="$(__ldadm_list_projects)" ;;
		delete|remove) REPLY="$(__ldadm_list_projects)" ;;
		assign)
			case "$COMP_CWORD" in
				3) REPLY="$(__ldadm_list_projects)" ;;
				*) REPLY="$(__ldadm_list_users) $(__ldadm_list_servers)" ;;
			esac
			;;
		manage)
			case "$COMP_CWORD" in
				3) REPLY="$(__ldadm_list_projects)" ;;
				4) REPLY="$(__ldadm_list_users)" ;;
			esac
			;;
		unit)
			__ldadm_complete_unit __ldadm_list_projects project
			return
			;;
		*)
			REPLY="list show info assign add create delete remove manage unit"
			;;
	esac
	COMPREPLY=($(compgen -W "$REPLY" -- $CUR))
}

# complete unit subcommands
__ldadm_complete_unit() {
	# $1 is a function to list leaves in unit tree, e.g. users, or projects
	list_units="$COMMAND $2 unit list" # $2: top level subcommand of ldadm

	case "${COMP_WORDS[3]}" in
		list) ;;
		add)
			case "$COMP_CWORD" in
				4) REPLY="$KWD_PARENT" ;;
				5) REPLY="$(eval $list_units)" ;;
			esac
			;;
		show|info)
			case "$COMP_CWORD" in
				4)
					case "$CUR" in
						-*) REPLY="$KWD_FULL" ;;
						*)  REPLY="$KWD_FULL $(eval $list_units)" ;;
					esac
					;;
				5)
					REPLY="$(eval $list_units)" ;;
			esac
			;;
		delete|remove) REPLY="$(eval $list_units)" ;;
		assign)
			case "$COMP_CWORD" in
				4) REPLY="$(eval $list_units)" ;;
				*) REPLY="$($1)" ;;
			esac
			;;
		*)
			REPLY="list show info assign add create delete remove"
			;;
	esac

	COMPREPLY=($(compgen -W "$REPLY" -- $CUR))
}

complete -F _ldadm ldadm
