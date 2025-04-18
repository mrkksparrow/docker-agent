#!/bin/bash

CUSTOMER_NAME=site24x7
PRODUCT_NAME=Site24x7
REPOSITORY=/home/likewise-open/ZOHOCORP/mohd-pt513/workspace/git_me_agent/check_singlejson
#REPOSITORY=/home/likewise-open/ZOHOCORP/raghu-2160/eclipse/ZIDE/me_agent_ICMP 
#REPOSITORY=/home/Jim/repository/zoho/ME_Agent/ME_AGENT_1000/me_agent
#REPOSITORY=/home/Jim/repository/zoho/ME_Agent/HEAD/me_agent
DIST_DIR=/home/dist
#DIST_DIR=/home/Jim/dist
#DIST_DIR=/home/likewise-open/ZOHOCORP/raghu-2160/Agent/dist_peer 
AGENT_BINARY_NAME=$PRODUCT_NAME'Agent'
AGENT_WATCHDOG_BINARY_NAME=$PRODUCT_NAME'AgentWatchdog'
BINARY_TAR_FILE=monagent_linux_64bit.tar.gz
UPGRADE_TAR_FILE=Site24x7_Linux_64bit_Upgrade.tar.gz
AGENT_UPGRADE_TAR_FILE=Site24x7_Linux_64bit_Agent_Upgrade.tar.gz
WATCHDOG_UPGRADE_TAR_FILE=Site24x7_Linux_64bit_Watchdog_Upgrade.tar.gz
BINARY_TYPE=64-bit

SITE24X7_INSTALL_SCRIPT=Site24x7InstallScript.sh
INSTALL_FILE='monagent.install'
THIRTY_TWO_BIT_INSTALL_FILE='Site24x7_Linux_32bit.install'
SIXTY_FOUR_BIT_INSTALL_FILE='Site24x7_Linux_64bit.install'
INSTALL_SCRIPT='installscript.sh'
AGENT_PROFILE=profile.sh
AGENT_FILE=MonitoringAgent.py
AGENT_WATCH_DOG_FILE=MonitoringAgentWatchdog.py

INSTALL_FILE_LENGTH=0

LOCAL_SERVER_HOME=/opt/apache-tomcat-7.0.52
LOCAL_SERVER_APP_DIR=$LOCAL_SERVER_HOME/webapps/ROOT

createDir() {
	if [ ! -d "$1" ]; then
		mkdir -p "$1"
	fi	
}

compileUsingCxFreeze() {
	echo =======================================  CREATING BINARIES ======================================= 
	cxfreeze --include-path=$REPOSITORY/python/src --target-dir=$DIST_DIR/monagent/lib --target-name=$AGENT_BINARY_NAME $REPOSITORY/python/src/com/manageengine/monagent/$AGENT_FILE
	cxfreeze --include-path=$REPOSITORY/python/src --target-dir=$DIST_DIR/monagent/lib --target-name=$AGENT_WATCHDOG_BINARY_NAME $REPOSITORY/python/src/com/manageengine/monagent/watchdog/$AGENT_WATCH_DOG_FILE		
}

compileUsingPython331CxFreeze() {
	echo =======================================  CREATING BINARIES ======================================= 
	cxfreeze --include-path=$REPOSITORY/source/python3.3/src --target-dir=$DIST_DIR/monagent/lib --target-name=$AGENT_BINARY_NAME $REPOSITORY/source/python3.3/src/com/manageengine/monagent/$AGENT_FILE
	cxfreeze --include-path=$REPOSITORY/source/python3.3/src --target-dir=$DIST_DIR/monagent/lib --target-name=$AGENT_WATCHDOG_BINARY_NAME $REPOSITORY/source/python3.3/src/com/manageengine/monagent/watchdog/$AGENT_WATCH_DOG_FILE		
}

compileUsingBbFreeze() {
	bb-freeze $SOURCE_DIR/ManageEngine/me_agent/$AGENT_FILE
	cp -rvf $SCRIPTS_DIR/dist/* $BINARY_DIR/ManageEngine/me_agent/
	bb-freeze $SOURCE_DIR/ManageEngine/me_agent/$AGENT_WATCH_DOG_FILE
	cp -rvf $SCRIPTS_DIR/dist/ME_AgentWatchdog $BINARY_DIR/ManageEngine/me_agent/
	rm -f $BINARY_DIR/ManageEngine/me_agent/py $BINARY_DIR/ManageEngine/me_agent/library.zip
	#rm -rf $SCRIPTS_DIR/dist/
}

cleanOldFiles() {
	rm -rf $DIST_DIR/monagent
	rm -f $DIST_DIR/$BINARY_TAR_FILE
	rm -f $DIST_DIR/$INSTALL_FILE
}

generateBinaries() {	
	createDir $DIST_DIR/monagent/
# Generating Binary
	#compileUsingCxFreeze
	compileUsingPython331CxFreeze
	#compileUsingBbFreeze
		
}

copyConfFiles() {
	cp -rvf $REPOSITORY/product_package/* $DIST_DIR/monagent/
	cp -rvf $REPOSITORY/product_package/* $DIST_DIR/monagent/
}

copylibFiles() {
	cp -vf /lib/x86_64-linux-gnu/libc.so.6 $DIST_DIR/monagent/lib/
}

createInstallFile() {
	chmod 777 $DIST_DIR/$UPGRADE_TAR_FILE
	AGENT_VERSION=`cat $REPOSITORY/product_package/version.txt`
	cat $REPOSITORY/build/install_script/$INSTALL_FILE $REPOSITORY/product_package/bin/$AGENT_PROFILE $REPOSITORY/build/install_script/$INSTALL_SCRIPT > $DIST_DIR/$INSTALL_FILE
	chmod 777 $DIST_DIR/$INSTALL_FILE
}

copyInstallFiles() {
	rm -f $DIST_DIR/$SITE24X7_INSTALL_SCRIPT
	cp -vf $REPOSITORY/build/install_script/$SITE24X7_INSTALL_SCRIPT $DIST_DIR
	cp -vf $REPOSITORY/build/install_script/$SITE24X7_INSTALL_SCRIPT $LOCAL_SERVER_APP_DIR
	cp -vf $DIST_DIR/$INSTALL_FILE $LOCAL_SERVER_APP_DIR/$SIXTY_FOUR_BIT_INSTALL_FILE
	chmod 777 $DIST_DIR/$SITE24X7_INSTALL_SCRIPT
}

updateVariablesInInstallFiles() {
	INSTALL_FILE_LENGTH=`wc -l $DIST_DIR/$INSTALL_FILE | awk '{print $1}'`
	INSTALL_FILE_LENGTH=`expr $INSTALL_FILE_LENGTH + 1`
	echo "Length of $DIST_DIR/$INSTALL_FILE : "$INSTALL_FILE_LENGTH
	sed -i "s/__AGENT_VERSION__/$AGENT_VERSION/g" $DIST_DIR/$INSTALL_FILE
	sed -i "s/__AGENT_VERSION__/$AGENT_VERSION/g" $DIST_DIR/$SITE24X7_INSTALL_SCRIPT
	sed -i "s/__FILE_LENGTH__/$INSTALL_FILE_LENGTH/g" $DIST_DIR/$INSTALL_FILE
	sed -i "s/__BINARY_TAR_FILE__/$BINARY_TAR_FILE/g" $DIST_DIR/$INSTALL_FILE
	sed -i "s/__MON_AGENT_BINARY_TYPE__/$BINARY_TYPE/g" $DIST_DIR/$INSTALL_FILE
}

cleanInstallFiles() {
	rm -vf $DIST_DIR/$INSTALL_FILE
	rm -vf $LOCAL_SERVER_APP_DIR/$SIXTY_FOUR_BIT_INSTALL_FILE
	rm -vf $LOCAL_SERVER_APP_DIR/$SITE24X7_INSTALL_SCRIPT
}

cleanTempFiles() {
	rm -rf $DIST_DIR/monagent/
	rm -f $DIST_DIR/$AGENT_UPGRADE_TAR_FILE
	rm -f $DIST_DIR/$WATCHDOG_UPGRADE_TAR_FILE
	rm -f $DIST_DIR/$BINARY_TAR_FILE
	#rm -f $DIST_DIR/Sit*
}

createTarFiles() {
	echo "CREATING BINARY TAR FILE : $DIST_DIR/$BINARY_TAR_FILE"
	cd $DIST_DIR/monagent/
	tar -zcvf $DIST_DIR/$AGENT_UPGRADE_TAR_FILE version.txt bno.txt lib/Site24x7Agent 
	tar -zcvf $DIST_DIR/$WATCHDOG_UPGRADE_TAR_FILE lib/Site24x7AgentWatchdog bin/upgrade.sh
	cd $DIST_DIR
	tar -zcvf $DIST_DIR/$UPGRADE_TAR_FILE $AGENT_UPGRADE_TAR_FILE $WATCHDOG_UPGRADE_TAR_FILE
	tar -zcf $DIST_DIR/$BINARY_TAR_FILE monagent/
	chmod 777 $DIST_DIR/$BINARY_TAR_FILE	
}

appendTarAndInstallFiles() {
	cat $DIST_DIR/$BINARY_TAR_FILE >> $DIST_DIR/$INSTALL_FILE
}

setUser() {
	USER="$1"
	if [ "$USER" = "j" ]; then
		DIST_DIR=/home/Jim/dist
		REPOSITORY=/home/Jim/repository/zoho/ME_Agent/HEAD/me_agent
	fi
}

generateInstallFile() {
	cleanInstallFiles
	createTarFiles
	createInstallFile
	updateVariablesInInstallFiles
	appendTarAndInstallFiles
	copyInstallFiles
	cleanTempFiles
}

parseInput() {
	setUser $1
}

cls() {
	printf "\ec"
} 

main() {
	cls
	cleanOldFiles
	parseInput "$@"
	generateBinaries
	copyConfFiles
	#copylibFiles
	generateInstallFile	
}

main $@




