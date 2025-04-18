# This file should not contain any product specific variable names. Will be replaced during upgrade.
#MON_AGENT_HOME="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
#MON_AGENT_HOME=$( cd -P -- "$(dirname -- "$(command -v -- "$0")")" && pwd -P )
MON_AGENT_PRODUCT_PROFILE=$MON_AGENT_HOME/.product_profile
MON_AGENT_PROFILE=$MON_AGENT_HOME/.profile
. $MON_AGENT_PRODUCT_PROFILE
. $MON_AGENT_PROFILE
variableUpdate 2>/dev/null
isRootUser() {
	RETVAL=$SUCCESS
	if [ "$(id -u)" != "0" ]; then
		RETVAL=$FAILURE
	fi
	return $RETVAL
}

#Usage : log <file> <message>
logToFile() {
	echo $(date +"%F %T.%N") "    $2" >> $1 2>&1
}

#Usage : log <file> <message> <{PRINT|GPRINT|RPRINT}>
log() {	
	if [ "$3" = "$ECHO_PRINT" ]; then
		echo "$2"
	elif [ "$3" = "$ECHO_GPRINT" ]; then
		echo "${FONT_GREEN}$2${FONT_RESET}"
	elif [ "$3" = $ECHO_RPRINT ]; then
		echo "${FONT_RED}$2${FONT_RESET}"	
	elif [ "$3" = "$PRINT" ]; then
		echo "$2"
		logToFile $1 "$2"		
	elif [ "$3" = "$GPRINT" ]; then
		echo "${FONT_GREEN}$2${FONT_RESET}"
		logToFile $1 "$2"
	elif [ "$3" = "$RPRINT" ]; then
		echo "${FONT_RED}$2${FONT_RESET}"
		logToFile $1 "$2"
	else
		logToFile $1 "$2"
	fi
}
