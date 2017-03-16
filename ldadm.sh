_log() {
	echo "[$(date +%r)] WORDS: $COMP_WORDS; CWORD=$COMP_CWORD; $@" >>/tmp/compl.log
}

_ldadm() {
	local cur="${COMP_WORDS[COMP_CWORD]}"
	local kwd_objects="user list"
	local levels="DEBUG INFO WARNING ERROR CRITICAL"
	local kwd_loglevel="--loglevel"
	local obj_start
	local prev
	local words
	_init_completion || return
	COMPREPLY=()

	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case "${COMP_WORDS[1]}" in
		$kwd_loglevel)
			obj_start=3
			if [[ $COMP_CWORD -eq 2 ]]; then
				COMPREPLY=($(compgen -W "$levels" -- $cur))
				return 0
			fi
			words="$kwd_objects"
			;;
		*)
			obj_start=1
			words="$kwd_objects $kwd_loglevel"
			;;
	esac

	case "${COMP_WORDS[obj_start]}" in
		user) _ldadm_user ;;
		list) ;;
		*)
			COMPREPLY=($(compgen -W "$words" -- $cur))
			;;
	esac
}

_ldadm_user() {
	local users
	case "${COMP_WORDS[obj_start + 1]}" in
		list|search|find)
			if [[ $COMP_CWORD -eq $(($obj_start + 2)) ]]; then
				COMPREPLY=($(compgen -W "--suspended" -- $cur))
				compopt -o nospace
			fi
			;;
		info|show)
			case "$COMP_CWORD" in
				3)
					case "$cur" in
						-*)
							COMPREPLY=($(compgen -W "--suspended" -- $cur))
							return 0
							;;
						*)
							users=$(ldadm user list)
							COMPREPLY=($(compgen -W "$users" -- $cur))
							return 0
							;;
					esac
					;;
				4)
					if [[ "${COMP_WORDS[3]}" = "--suspended" ]]; then
						users=$(ldadm user list --suspended)
					else
						users=$(ldadm user list)
					fi
					COMPREPLY=($(compgen -W "$users" -- $cur))
			esac
			;;
		suspend|ban|lock|disable)
			users=$(ldadm user list)
			COMPREPLY=($(compgen -W "$users" -- $cur))
			;;
		restore|unban|enable)
			users=$(ldadm user list --suspended)
			COMPREPLY=($(compgen -W "$users" -- $cur))
			;;
		delete|remove)
			users=$(ldadm user list --suspended)
			COMPREPLY=($(compgen -W "$users" -- $cur))
			;;
		add|create)
			users=$(ldadm user list)
			case "$COMP_CWORD" in
				3)
					COMPREPLY=($(compgen -W "-t --template $users" -- $cur))
					;;
				4)
					users=$(ldadm user list)
					COMPREPLY=($(compgen -W "$users" -- $cur))
					;;
			esac
			;;
		rename)
			if [[ $COMP_CWORD -eq 3 ]]; then
				users=$(ldadm user list)
				COMPREPLY=($(compgen -W "$users" -- $cur))
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
			COMPREPLY=($(compgen -W "list search find show info suspend ban lock
			disable restore unban enable delete remove add create rename key
			" -- $cur))
			;;
	esac
}

complete -F _ldadm ldadm
