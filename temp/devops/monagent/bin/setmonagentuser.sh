#!/bin/bash
MON_AGENT_HOME='/opt/site24x7/monagent'
echo $MON_AGENT_HOME >> $MON_AGENT_HOME/logs/upgrade_script.txt
MON_AGENT_BIN_DIR=$MON_AGENT_HOME/bin
MON_AGENT_TEMP_DIR=$MON_AGENT_HOME/temp
MON_AGENT_TEMP_LOCKFILE=$MON_AGENT_TEMP_DIR/lockfile.txt
MON_AGENT_BIN_BOOT_FILE=$MON_AGENT_BIN_DIR/monagent
MON_AGENT_WATCHDOG_BIN_BOOT_FILE=$MON_AGENT_BIN_DIR/monagentwatchdog

change_switch_value(){
	sed -i "/MON_AGENT_SWITCH=\"/c\MON_AGENT_SWITCH=$1" $MON_AGENT_BIN_BOOT_FILE
	sed -i "/MON_AGENT_WATCHDOG_SWITCH=\"/c\MON_AGENT_WATCHDOG_SWITCH=$1" $MON_AGENT_WATCHDOG_BIN_BOOT_FILE
}

checkNonRoot(){
	user_value="$(cat $MON_AGENT_TEMP_LOCKFILE)"
	if [ "$user_value" == "site24x7-agent" ]; then
		change_switch_value 1
	else
		change_switch_value 0
	fi
}

main() {
	checkNonRoot
}

main