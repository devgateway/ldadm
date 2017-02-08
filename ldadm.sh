_ldadm() {
	local cur prev obj cmd active suspended
	_init_completion || return
	COMPREPLY=()
	cur="${COMP_WORDS[COMP_CWORD]}"
	obj="${COMP_WORDS[1]}"
	cmd="${COMP_WORDS[2]}"

	case "$obj" in
		user)
			case "$cmd" in
				list|search|find)
					if [[ $COMP_CWORD -eq 3 ]]; then
						COMPREPLY=($(compgen -W "--suspended" -- $cur))
					fi
					;;
				show|info|suspend|ban|lock|disable)
					active=$(ldadm user list)
					COMPREPLY=($(compgen -W "$active" -- $cur))
					;;
				restore|unban|enable)
					suspended=$(ldadm user list --suspended)
					COMPREPLY=($(compgen -W "$suspended" -- $cur))
					;;
				delete|remove)
					active=$(ldadm user list)
					suspended=$(ldadm user list --suspended)
					COMPREPLY=($(compgen -W "$active $suspended" -- $cur))
					;;
				add|create)
					case "$COMP_CWORD" in
						3)
							COMPREPLY=($(compgen -W "-t --template $active" -- $cur))
							;;
						4)
							active=$(ldadm user list)
							COMPREPLY=($(compgen -W "$active" -- $cur))
							;;
					esac
					;;
				rename)
					if [[ $COMP_CWORD -eq 3 ]]; then
						active=$(ldadm user list)
						COMPREPLY=($(compgen -W "$active" -- $cur))
					fi
					;;
				key)
					local keycmd="${COMP_WORDS[3]}"
					case "$keycmd" in
						add|create|delete|remove)
							prev="${COMP_WORDS[COMP_CWORD - 1]}"
							if [[ "$prev" == "-f" || "$prev" == "--file" ]]; then
								_filedir
							else
								active=$(ldadm user list)
								COMPREPLY=($(compgen -W "-f --file $active" -- $cur))
							fi
							;;
						list|show)
							active=$(ldadm user list)
							COMPREPLY=($(compgen -W "$active" -- $cur))
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
			;;
		list)
			;;
		*)
			COMPREPLY=($(compgen -W "user list" -- $cur))
			return 0
			;;
	esac
}

complete -F _ldadm ldadm
