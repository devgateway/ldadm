_ldadm() {
	local cur="${COMP_WORDS[COMP_CWORD]}"
	local kwd_objects="user list"
	local kwd_suspended="--suspended"
	local kwd_loglevel="--loglevel"
	local kwd_defaults="--defaults -d"
	local obj_start
	local prev
	local REPLY
	_init_completion || return
	COMPREPLY=()

	if [[ "${COMP_WORDS[1]}" = "$kwd_loglevel" ]]; then
		obj_start=3
	else
		obj_start=1
	fi

	case "${COMP_WORDS[obj_start]}" in
		user) __ldadm_user ;;
		list) ;;
		*) __ldadm_default ;;
	esac
}

__ldadm_default() {
	case $COMP_CWORD in
		1) REPLY="$kwd_loglevel $kwd_objects" ;;
		2) REPLY="DEBUG INFO WARNING ERROR CRITICAL" ;;
		3) REPLY="$kwd_objects" ;;
		*) REPLY=""
	esac

	COMPREPLY=($(compgen -W "$REPLY" -- $cur))
}

__ldadm_list_users() {
	if [[ $1 = "suspended" ]]; then
		eval "ldadm user list $kwd_suspended"
	else
		ldadm user list
	fi
}

__ldadm_user() {
	let COMP_CWORD=(COMP_CWORD - obj_start + 1)
	local users
	case "${COMP_WORDS[obj_start + 1]}" in
		list|search|find)
			if [[ $COMP_CWORD -eq 3 ]]; then
				REPLY="$kwd_suspended"
				compopt -o nospace
			fi
			;;
		info|show)
			if [[ $COMP_CWORD -eq 3 ]]; then
				case "$cur" in
					-*) REPLY="$kwd_suspended" ;;
					*)  REPLY="$kwd_suspended $(__ldadm_list_users)" ;;
				esac
			else
				if [[ "${COMP_WORDS[obj_start + 2]}" = "$kwd_suspended" ]]; then
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
			users=$(__ldadm_list_users)
			case "$COMP_CWORD" in
				3) REPLY="$kwd_defaults" ;;
				4) REPLY="$(__ldadm_list_users suspended) $(__ldadm_list_users)" ;;
			esac
			;;
		rename)
			if [[ $COMP_CWORD -eq 3 ]]; then
				REPLY="$(__ldadm_list_users)"
			fi
			;;
		key)
			local prev
			local keycmd="${COMP_WORDS[3]}"
			users=$(ldadm user list)
			case "$keycmd" in
				add|create|delete|remove)
					prev="${COMP_WORDS[COMP_CWORD - 1]}"
					if [[ "$prev" == "-f" || "$prev" == "--file" ]]; then
						_filedir
					else
						COMPREPLY=($(compgen -W "-f --file $users" -- $cur))
					fi
					;;
				list|show)
					COMPREPLY=($(compgen -W "$users" -- $cur))
					;;
				*)
					COMPREPLY=($(compgen -W "add create delete remove list show" -- $cur))
			esac
			;;
		*)
			REPLY="list search find show info suspend ban lock disable restore
			unban enable delete remove add create rename key"
			;;
	esac
	COMPREPLY=($(compgen -W "$REPLY" -- $cur))
}

complete -F _ldadm ldadm
