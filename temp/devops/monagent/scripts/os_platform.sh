#!/bin/bash
OS_BINARY_TYPE=''
THIRTY_TWO_BIT='32-bit'
SIXTY_FOUR_BIT='64-bit'
USER_TYPE=''
INSTALL_SCRIPT_NAME=$(readlink -f $0)
getHardwarePlatform(){
	if [ "`which file`" = "" ]; then		
	    if [ `/usr/bin/getconf LONG_BIT` = "64" ]; then
		    OS_BINARY_TYPE="$SIXTY_FOUR_BIT"

		elif [ `/usr/bin/getconf LONG_BIT` = "32" ]; then
		    OS_BINARY_TYPE="$THIRTY_TWO_BIT"

		fi
	else
		if /usr/bin/file /sbin/init | grep 'ELF 64-bit' &>/dev/null; then
		    OS_BINARY_TYPE="$SIXTY_FOUR_BIT"

		elif /usr/bin/file /sbin/init | grep 'ELF 32-bit' &>/dev/null; then
		    OS_BINARY_TYPE="$THIRTY_TWO_BIT"

		elif [ `/usr/bin/getconf LONG_BIT` = "64" ]; then
		    OS_BINARY_TYPE="$SIXTY_FOUR_BIT"

		elif [ `/usr/bin/getconf LONG_BIT` = "32" ]; then
		    OS_BINARY_TYPE="$THIRTY_TWO_BIT"

		fi
	fi	
}

isRootUser(){
        if [ "$(id -u)" != "0" ]; then
	    
            	USER_TYPE="1"
	
	else
              
		USER_TYPE="0"		

        fi
}

cleanUpTempFiles() {
	if [ -f $INSTALL_SCRIPT_NAME ]; then
    		rm -f $INSTALL_SCRIPT_NAME	
	fi

}

getHardwarePlatform
isRootUser
cleanUpTempFiles

echo $OS_BINARY_TYPE'|'$USER_TYPE