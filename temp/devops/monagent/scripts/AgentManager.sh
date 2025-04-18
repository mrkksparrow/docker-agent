#!/bin/bash

USER=$(id -u -n)
HOME_DIR=$(eval echo "~$USER")
HOME_CHECK=$HOME_DIR"/site24x7/monagent/"
ROOT_CHECK="/opt/site24x7/monagent/"
SILENT_RESTART=false
START="start"
STOP="stop"
RESTART="restart"

if [ -d "$ROOT_CHECK" ]; then
    INSTALL_DIR="/opt/site24x7/"
    #INSTALL_DIR=$HOME_DIR"/site24x7/monagent/"
elif [ -d "$HOME_CHECK" ]; then
    INSTALL_DIR=$HOME_DIR"/site24x7/"
fi

PYTHON=$(which python 2>/dev/null)
PYTHON3=$(which python3 2>/dev/null)

if [[ ! -z "$PYTHON" ]]; then
    PYTHON_VAR="python"
elif [[ ! -z "$PYTHON3" ]]; then
    PYTHON_VAR="python3"
fi

PRODUCT_NAME="site24x7"
MONAGENT_HOME=$INSTALL_DIR"monagent/"
MONAGENT_CONF_DIR=$MONAGENT_HOME"conf/"
MONAGENT_APPS_DIR=$MONAGENT_CONF_DIR"apps/"
MONAGENT_SCRIPT_DIR=$MONAGENT_HOME"scripts/"
MONAGENT_METRICS_DIR=$MONAGENT_HOME"metrics/"
MONAGENT_PROMETHEUS_DIR=$MONAGENT_METRICS_DIR"prometheus/"
MONAGENT_STATSD_DIR=$MONAGENT_METRICS_DIR"statsd/"
MONAGENT_CONF_FILE=$MONAGENT_CONF_DIR"monagent.cfg"
WATCHDOG_CONF_FILE=$MONAGENT_CONF_DIR"monagentwatchdog.cfg"
MONITORS_XML_FILE=$MONAGENT_CONF_DIR"monitors.xml"
PROMETHEUS_CONF_FILE=$MONAGENT_PROMETHEUS_DIR"prometheus.cfg"
STATSD_CONF_FILE=$MONAGENT_STATSD_DIR"statsd.cfg"
AGENT_HELPER_PY_FILE=$MONAGENT_SCRIPT_DIR"/AgentManager.py"
PLUGIN_CONF_FILE=$MONAGENT_CONF_DIR"pl_id_mapper"
ENABLE_PROMETHEUS=$MONAGENT_CONF_DIR"enablePrometheus.txt"
DISABLE_PROMETHEUS=$MONAGENT_CONF_DIR"disablePrometheus.txt"
ADD_PROMETHEUS_INSTANCE=$MONAGENT_CONF_DIR"prometheus_input"
EDIT_PROMETHEUS_SCRAPE_INTERVAL=$MONAGENT_CONF_DIR"prometheus_scrape_interval"
REMOVE_PROMETHEUS_INSTANCE=$MONAGENT_CONF_DIR"remove_prometheus_instance"
UPDATE_PROMETHEUS_INSTANCE=$MONAGENT_CONF_DIR"update_prometheus_instance"
ENABLE_STATSD=$MONAGENT_CONF_DIR"enableStatsd.txt"
DISABLE_STATSD=$MONAGENT_CONF_DIR"disableStatsd.txt"
EDIT_STATSD_INSTANCE=$MONAGENT_CONF_DIR"statsd_input"
ADD_MYSQL_INSTANCE=$MONAGENT_CONF_DIR"mysql_input"
MYSQL_TERMINAL_RESPONSE_FILE=$MONAGENT_CONF_DIR"mysql_terminal_response"
REMOVE_MYSQL_INSTANCE=$MONAGENT_CONF_DIR"mysql_remove"
ADD_POSTGRES_INSTANCE=$MONAGENT_CONF_DIR"postgres_input"
POSTGRES_TERMINAL_RESPONSE_FILE=$MONAGENT_CONF_DIR"postgres_terminal_response"
REMOVE_POSTGRES_INSTANCE=$MONAGENT_CONF_DIR"postgres_remove"
ORACLE_CONF_DIR=$MONAGENT_APPS_DIR"oracledb/"
ORACLE_CONF_FILE=$ORACLE_CONF_DIR"oracle.cfg"
ADD_ORACLE_INSTANCE=$MONAGENT_CONF_DIR"oracle_input"
UPDATE_ORACLE_INSTANCE=$MONAGENT_CONF_DIR"oracle_update"
ORACLE_TERMINAL_RESPONSE_FILE=$MONAGENT_CONF_DIR"oracledb_terminal_response"
REMOVE_ORACLE_INSTANCE=$MONAGENT_CONF_DIR"oracle_remove"
DB_SSL_CONFIGURATION=$MONAGENT_CONF_DIR"db_ssl_config"
DB_SSL_TERMINAL_RESPONSE_FILE=$MONAGENT_CONF_DIR"db_ssl_terminal_response"
AGENT_VERSION_FILE=$MONAGENT_HOME"version.txt"
MONAGENT_TEMP_DIR=$MONAGENT_HOME"temp/"
MONAGENT_BIN_DIR=$MONAGENT_HOME"bin/"
MONAGENT_FILE=$MONAGENT_BIN_DIR"monagent"
WATCHDOG_FILE=$MONAGENT_BIN_DIR"monagentwatchdog"
SILENT_RESTART_FILE_DIR=$MONAGENT_TEMP_DIR"watchdogsilentrestart.txt"
LOG_DIR=$MONAGENT_HOME"logs/"
LOG_DETAILS_DIR=$LOG_DIR"details/"
HELPER_LOG_FILE=$LOG_DETAILS_DIR"helper.txt"
INSTALL_LOG=$INSTALL_DIR"site24x7install.log"
ZIPPED_LOG_FILE=$MONAGENT_TEMP_DIR"agent_logs.zip"
PS_UTIL_FLOW_FILE=$MONAGENT_TEMP_DIR"psutil_flow.txt"
LOGGING_XML_FILE=$MONAGENT_CONF_DIR"logging.xml"

enablePrometheus () {
    echo "$1" >> "$ENABLE_PROMETHEUS"
    log "Prometheus Enable Flag file created"
}

disablePrometheus () {
    echo "$1" >> "$DISABLE_PROMETHEUS"
    log "Prometheus Disable Flag file created"
}

changePrometheusScrapeInterval () {
    echo "$1" >> $EDIT_PROMETHEUS_SCRAPE_INTERVAL
    log "Prometheus Scrape Interval added to prometheus_scrape_interval file :: $1"
}

enableStatsd () {
    echo "$1" >> "$ENABLE_STATSD"
    log "Statsd Enable Flag file created"
}

disableStatsd () {
    echo "$1" >> "$DISABLE_STATSD"
    log "Statsd Disable Flag file created"
}

addPrometheusInstance() {
    echo "$1" >> $ADD_PROMETHEUS_INSTANCE
    log "Prometheus Intance added to prometheus_input file :: $1"
}

removePrometheusInstance () {
    echo "$1" >> "$REMOVE_PROMETHEUS_INSTANCE"
    log "Prometheus Intance added to remove_prometheus_instance file :: $1"
}

updatePrometheusInstance () {
    echo "$1" >> "$UPDATE_PROMETHEUS_INSTANCE"
    log "Prometheus Intance added to update_prometheus_instance file :: $1"
}

editStatsdInstance () {
    echo "$1" >> "$EDIT_STATSD_INSTANCE"
    log "Statsd Intance input param added to statsd_input :: $1"
}

addMySQLInstance () {
     echo "$1" > "$ADD_MYSQL_INSTANCE"
     log "MySQL Intance added to mysql_input file"
}

removeMySQLInstance () {
    echo "$1" > "$REMOVE_MYSQL_INSTANCE"
    log "MySQL Intance added to mysql_remove file :: $1"
}

addDatabaseInstance () {
    if [[ $1 = "Oracle Database" ]]; then
        ADD_DATABASE_INSTANCE="$ADD_ORACLE_INSTANCE"
    elif [[ $1 = "Postgres" ]]; then
        ADD_DATABASE_INSTANCE="$ADD_POSTGRES_INSTANCE"
    elif [[ $1 = "MySQL" ]]; then
        ADD_DATABASE_INSTANCE="$ADD_MYSQL_INSTANCE"
    fi
    echo "$2" > "$ADD_DATABASE_INSTANCE"
    log "'$1' Instance added to '$ADD_DATABASE_INSTANCE' file"
}

updateDatabaseInstance () {
    if [[ $1 = "Oracle Database" ]]; then
        UPDATE_DATABASE_INSTANCE="$UPDATE_ORACLE_INSTANCE"
    fi
    echo "$2" > "$UPDATE_DATABASE_INSTANCE"
    log "'$1' Instance updated to '$UPDATE_DATABASE_INSTANCE' file :: $2"
}
removeDatabaseInstance () {
    if [[ $1 = "Oracle Database" ]]; then
        REMOVE_DATABASE_INSTANCE=$REMOVE_ORACLE_INSTANCE
    elif [[ $1 = "Postgres" ]]; then
        REMOVE_DATABASE_INSTANCE=$REMOVE_POSTGRES_INSTANCE
    elif [[ $1 = "MySQL" ]]; then
        REMOVE_DATABASE_INSTANCE=$REMOVE_MYSQL_INSTANCE
    fi
    echo "$2" > "$REMOVE_DATABASE_INSTANCE"
    log "'$1' Instance added to '$REMOVE_DATABASE_INSTANCE' file :: $2"
}

updateSSLConfiguration () {
    echo "$2" > "$DB_SSL_CONFIGURATION"
    log "Update ssl configuration for '$1' Instance :: file - '$DB_SSL_CONFIGURATION' :: $2"
}

displayVersion () {
    echo "Site24x7 Linux Server Agent $(<$AGENT_VERSION_FILE)"
}

createSilentRestart () {
    echo "" >> "$SILENT_RESTART_FILE_DIR"
    log "Agent silent restart flag file created"
}

restartAgent () {
    $MONAGENT_FILE $RESTART
    log "Agent restart command executed"
}

restartwatchdog() {
    $WATCHDOG_FILE $RESTART
}

log () {
    echo $(date "+%d-%m-%y %H:%M:%S:%3N")"  -  $1" >> $HELPER_LOG_FILE
}

helpMessage () {
    echo -e "\033[4mOPTIONS AND ARGUMENTS\033[0m\n"
    echo -e '-edit_proxy                            : To edit Site24x7 agent proxy communication configurations\n'
    echo -e '-set_limit                             : To set maximum limit for Site24x7 agent CPU & memory consumption\n'
    echo -e '-ziplogs                               : Archives the Site24x7 agent logs into '$ZIPPED_LOG_FILE'\n'
    echo -e '-newmonitor                            : New monitor creation for the same UUID/Hostname servers\n'
    echo -e '-createmonitor                         : New monitor creation for the server monitor deleted in Site24x7\n'
    echo -e '-cpu_sar                               : To use SAR utility for monitoring CPU\n'
    echo -e '-debug_on / -debug_off                 : To enable/disable agent logging in debug mode\n'
    echo -e '-edit_devicekey                        : To change device key, the monitor currently pointed for monitoring\n'
    echo -e 'prometheus --enable=true               : Enables Prometheus Monitoring, use prometheus_config param to pass on the prometheus monitoring configuration\n'
    echo -e 'prometheus --enable=false              : Disables prometheus from Data Collection\n'
    echo -e 'prometheus --add_config="<args>"       : Adds the instance to prometheus data collection\n'
    echo -e '                                         Arguments : [{"prometheus_url": "<url>","include_pattern": "<pattern_1>|<pattern_2>","instance_name": "<instance_name_to_add>"}]\n'
    echo -e 'statsd --enable=true                   : Enables Statsd Monitoring, use statsd_config param to edit the default statsd monitoring configuration [localhost, 8125]\n'
    echo -e 'statsd --enable=false                  : Disables statsd from Data Collection\n'
    echo -e 'statsd --update_config="<args>"        : Changes hostname and port in the statsd monitoring configuration\n'
    echo -e '                                         Arguments : [{"hostname": "<hostname>","port": "<port>"}]\n'
    echo -e 'prometheus --remove_config="<args>"    : Removes the instance from prometheus data collection\n'
    echo -e '                                         Arguments : [{"instance_name": "<instance_name_to_remove>"}]\n'
    echo -e 'prometheus --scrape_interval="<args>"  : Changes the Scrape interval for specific instance or all instances\n'
    echo -e '                                         Arguments : <instance_name>:<scrape_interval_value>  OR  <scrape_interval_value>\n'
    echo -e 'mysql --add_instance                   : Add MySQL instance for data collection\n'
    echo -e 'mysql --update_instance                : Update the MySQL instance [user/password]\n'
    echo -e 'mysql --remove_instance                : Removes the MySQL instance from data collection\n'
    echo -e 'mysql --update_ssl_configuration       : Update SSL Configuration for the MySQL instance\n'
    echo -e 'mysql --delete_ssl_configuration       : Delete SSL Configuration for the MySQL instance\n'
    echo -e 'postgres --add_instance                : Add Postgres instance for data collection\n'
    echo -e 'postgres --update_instance             : Update the Postgres instance [user/password]\n'
    echo -e 'postgres --remove_instance             : Removes the Postgres instance from data collection\n'
    echo -e 'postgres --update_ssl_configuration    : Update SSL Configuration for the Postgres instance\n'
    echo -e 'postgres --delete_ssl_configuration    : Delete SSL Configuration for the Postgres instance\n'
    echo -e 'oracledb --add_instance                : Add Oracle instance for data collection\n'
    echo -e 'oracledb --update_instance             : Update the Oracle instance [user/password]\n'
    echo -e 'oracledb --remove_instance             : Removes the Oracle instance from data collection\n'
    echo -e 'oracledb --update_library_path         : Updates LD_LIBRARY_PATH for oracle monitoring\n'
    echo -e '[option] --view                        : Displays a report for the given option\n'
    echo -e '                                         Options : prometheus | statsd | plugin\n'
    echo -e '-version                               : Displays the version of the Site24x7 Agent\n'
}

callAgentHelperPy () {
    $PYTHON_VAR $AGENT_HELPER_PY_FILE $@
}

defaultMessage () {
    echo ''
    echo 'Usage: AgentManager.sh [option] ...'
    echo ''
    echo 'prometheus [args]'
    echo '           --enable=true/false'
    echo "           --add_config='<args>'"
    echo "           --remove_config='<args>'"
    echo "           --scrape_interval='<args>'"
    echo '           --view'
    echo ''
    echo 'statsd [args]'
    echo '           --enable=true/false'
    echo "           --update_config='<args>'"
    echo '           --view'
    echo ''
    echo 'mysql [args]'
    echo "           --add_instance='<args>'"
    echo "           --update_instance='<args>'"
    echo "           --remove_instance='<args>'"
    echo 'postgres [args]'
    echo "           --add_instance"
    echo "           --update_instance"
    echo "           --remove_instance"
    echo 'oracledb [args]'
    echo "           --add_instance"
    echo "           --update_instance"
    echo "           --remove_instance"
    echo "           --update_library_path"
    echo 'plugin [args]'
    echo '           --view'
    echo ''
    echo '-version'
    echo ''
}

check_oracle_attribute_present (){
    if [[ -f $ORACLE_CONF_FILE ]]; then
        attribute=$(cat $ORACLE_CONF_FILE 2>/dev/null | grep $1 |awk 'BEGIN {FS=" ?= ?"}{print $2}')
        if [[ -n "$attribute" ]]; then
            return "0"
        fi
    fi
    return "1"
}

null_check (){
    if [[ -z "$2" ]]; then
        echo "Provided value for $1 is empty."
        log "Provided value for $1 is empty."
    fi
}

setup_database_instance () {
    # $1 is database name, $2 is param (i.e. --add_instance,etc..), $3 is TERMINAL_RESPONSE_FILE
    # PARAM=`echo $2 | awk -F= '{print $1}'`
    TERMINAL_RESPONSE_FILE="$3"
    PARAM="$4"
    VALUE=`echo $2 | awk -F= '{print $2}'`

    if [[ -f $TERMINAL_RESPONSE_FILE ]]; then
        rm -R $TERMINAL_RESPONSE_FILE # deleting the response file if present. 
    fi
    terminal_response_for_db=false

    if [[ $PARAM = "--add_instance" || $PARAM = "--update_instance" ]]; then
        gv_oracle_ld_library_path=''
        normal_flow=true
        # if [[ "$1" = "Oracle Database" ]]; then
        #     ld_lib_in_cfg=$(cat $ORACLE_CONF_FILE 2>/dev/null | grep ld_library_path |awk 'BEGIN {FS=" ?= ?"}{print $2}')
        #     check_oracle_attribute_present "ld_library_path"
        #     if [[ "$?" -ne "0" ]]; then 
        #         setup_database_instance "$1" "$2" "$3" "--update_library_path"
        #         if [[ "$?" -eq "1" ]]; then 
        #             normal_flow=false
        #         fi
        #     else
        #         echo -e "\nThe LD_LIBRARY_PATH have already been set to $ld_lib_in_cfg"
        #     fi
        # fi
        PARAM="$4"
        if [[ "$normal_flow" = true ]]; then 
            echo ""
            echo -e "The $1 instance is installed in ...\n"
            display_hostname=$(cat /etc/hostname 2>/dev/null)
            echo -e '1. This server - '$display_hostname'\n2. Remote server\n'
            read -p "Enter 1 or 2 : " choosen_host
            echo -e "\nEnter $1 instance's credentials \n"
            if [[ "$choosen_host" = "1" ]]; then
                hostname='127.0.0.1'
                if [[ -z "$display_hostname" ]]; then
                    display_hostname='127.0.0.1'
                fi
                echo -e "Host Name              : "$display_hostname
            else
                read -p "Host Name              : " hostname
            fi
            read -p "Port                   : " port
            read -p "Username               : " username
            read -s -p "Password               : " password
            echo ""
            if [[ "$1" = 'Oracle Database' ]]; then
                    read -p "Service Name           : " oracle_service_name 
                    # read -p "Oracle Home            : " oracle_home
                    # while [[ ${oracle_home:0:1} = '$' || ${oracle_home:0:1} != '/' ]];
                    # do 
                    #     echo -e "\nPlease manually provide the absolute path of \$ORACLE_HOME"
                    #     read -p "Oracle Home            : " oracle_home
                    # done
            fi


            null_check "Hostname" "$hostname"
            null_check "Port" "$port"
            null_check "Username" "$username"

            if [[ -z "$hostname" || -z "$port" || -z "$username" ]]; then
                echo "Quitting the process."
                return 
            fi

            VALUE='[{"host":"'$hostname'","port":"'$port'","user":"'$username'","password":"'$password
            # VALUE=$VALUE'","IsLocalhost":"'$IsLocalhost
                if [[ $1 = 'Oracle Database' ]]; then
                    null_check "Service Name" "$oracle_service_name"
                    VALUE=$VALUE'","service_name":"'$oracle_service_name
                #    VALUE=$VALUE'","oracle_home":"'$oracle_home
                    if [[ -z "$oracle_service_name" ]]; then
                        return
                    fi
                else
                    echo ""
                    read -p "Do you want to configure SSL? (Y/n) : " config_ssl
                    if [[ $config_ssl = 'Y' || $config_ssl = 'y' ]]; then
                        read -p "ssl ca path            : " ssl_ca
                        read -p "ssl cert path          : " ssl_cert
                        read -p "ssl key path           : " ssl_key
                        # null_check "ssl ca path" "$ssl_ca"
                        # null_check "ssl cert path" "$ssl_cert"
                        # null_check "ssl key path" "$ssl_key"
                        VALUE=$VALUE'","ssl-ca":"'$ssl_ca'","ssl-cert":"'$ssl_cert'","ssl-key":"'$ssl_key'","ssl":"true'
                    fi
                fi
            VALUE=$VALUE'"}]'

            #echo $VALUE
            if [[ $PARAM = "--add_instance" ]]; then
                    echo -e '\nAdding '$1' instance ['$hostname'-'$port']...\n'
            else
                    echo -e '\nUpdating '$1' instance ['$hostname'-'$port']...\n'
            fi

            addDatabaseInstance "$1" "$VALUE"
            terminal_response_for_db=true
        fi
    elif [[ $PARAM = "--update_ssl_configuration" ]]; then
        
        TERMINAL_RESPONSE_FILE="$DB_SSL_TERMINAL_RESPONSE_FILE"
        if [[ -f $TERMINAL_RESPONSE_FILE ]]; then
            rm -R $TERMINAL_RESPONSE_FILE # deleting the response file if present. 
        fi
        
        echo ""
        echo -e "The $1 instance is installed in ...\n"
        display_hostname=$(cat /etc/hostname 2>/dev/null)
        echo -e '1. This server - '$display_hostname'\n2. Remote server\n'
        read -p "Enter 1 or 2 : " choosen_host
        echo -e "\nEnter $1 instance's credentials \n"
        if [[ "$choosen_host" = "1" ]]; then
            hostname='127.0.0.1'
            if [[ -z "$display_hostname" ]]; then
                display_hostname='127.0.0.1'
            fi
            echo -e "Host Name              : "$display_hostname
        else
            read -p "Host Name              : " hostname
        fi
        read -p "Port                   : " port        
        read -p "ssl ca path            : " ssl_ca
        read -p "ssl cert path          : " ssl_cert
        read -p "ssl key path           : " ssl_key
        echo -e '\n'
        VALUE='[{"instance":"'$hostname'-'$port'", "host":"'$hostname'","port":"'$port'", "database":"'$1'","ssl-ca":"'$ssl_ca'","ssl-cert":"'$ssl_cert'","ssl-key":"'$ssl_key'","ssl":"true", "action":"update'
        VALUE=$VALUE'"}]'

        updateSSLConfiguration "$1" "$VALUE"
        terminal_response_for_db=true

    elif [[ $PARAM = "--delete_ssl_configuration" ]]; then

        TERMINAL_RESPONSE_FILE="$DB_SSL_TERMINAL_RESPONSE_FILE"
        if [[ -f $TERMINAL_RESPONSE_FILE ]]; then
            rm -R $TERMINAL_RESPONSE_FILE # deleting the response file if present. 
        fi

        echo "Enter [host/port] of the instance to delete the ssl configuration "
        read -p "Host Name              : " hostname
        read -p "Port                   : " port
        echo -e '\n'
        echo 'Deleting ssl configuration for '$1' instance ['$hostname'-'$port'] '

        VALUE='[{"instance":"'$hostname'-'$port'", "host":"'$hostname'", "port":"'$port'", "database":"'$1'", "action":"delete"}]'
        #echo $VALUE
        
        updateSSLConfiguration "$1" "$VALUE"
        terminal_response_for_db=true

    elif [[ $PARAM = "--remove_instance" ]]; then
        echo "Enter [host/port] of the instance to be deleted "
        read -p "Host Name              : " hostname
        read -p "Port                   : " port
        echo -e '\n'
        echo 'Deleting '$1' instance ['$hostname'-'$port'] '

        VALUE='[{"instance":"'$hostname'-'$port'", "host":"'$hostname'", "port":"'$port'"}]'
        #echo $VALUE
        
        removeDatabaseInstance "$1" "$VALUE"
        terminal_response_for_db=true
        TERMINAL_RESPONSE_FILE="$DB_SSL_TERMINAL_RESPONSE_FILE"

    elif [[ $PARAM = "--update_library_path" && $1 = 'Oracle Database' ]]; then
        check_oracle_attribute_present "ld_library_path"
        # ld_library_present=$(cat $ORACLE_CONF_FILE 2>/dev/null | grep ld_library_present |awk 'BEGIN {FS=" ?= ?"}{print $2}')

        if [[ $? -ne "0" ]]; then
            # echo -e "\nLD_LIBRARY_PATH environment variable have not been set yet. "
            echo ""
            update_ld_lib='Y'
        else
            ld_lib_in_cfg=$(cat $ORACLE_CONF_FILE 2>/dev/null | grep ld_library_path |awk 'BEGIN {FS=" ?= ?"}{print $2}')
            echo -e "\nLD_LIBRARY_PATH has already been set to $ld_lib_in_cfg"
            read -p "Are you sure you want to update the LD_LIBRARY_PATH ? [y|n] : " update_ld_lib
        fi
        if [[ $update_ld_lib = 'Y' || $update_ld_lib = 'y' ]]; then
            read -p "Please enter Oracle LD_LIBRARY_PATH    :   " gv_oracle_ld_library_path
            if [[ -z "$gv_oracle_ld_library_path" ]]; then
                echo -e "\nPlease provide a valid path."
                exit 1
            elif [[ ${gv_oracle_ld_library_path:0:1} != '/' ]]; then
                echo -e "\nPlease provide the absolute path of oracle instant client."
                exit 1
            fi
            # while [[ ${gv_oracle_ld_library_path:0:1} != '/' ]];
            # do 
            #     echo -e "\nPlease provide the absolute path of \$LD_LIBRARY_PATH"
            #     read -p "Oracle LD_LIBRARY_PATH    :    " gv_oracle_ld_library_path
            # done
            log "User input for Oracle LD_LIBRARY_PATH is $gv_oracle_ld_library_path :: current user - $(whoami)"

            updateDatabaseInstance "$1" "{ \"LD_LIBRARY_PATH\" : \"$gv_oracle_ld_library_path\" }" 
            export LD_LIBRARY_PATH="$gv_oracle_ld_library_path"
            terminal_response_for_db=true
        fi

    else
        defaultMessage
        echo "Try 'AgentManager.sh -h' for more information."
    fi
    found_terminal_response_file="0"
    if [[ "$terminal_response_for_db" = true ]] ; then
        for (( each=1; each<=20; each++ ))
            do
                if [[ -f $TERMINAL_RESPONSE_FILE ]]; then
                    if [[ "$PARAM" = "--update_library_path" && $1 = 'Oracle Database' ]]; then
                        # export LD_LIBRARY_PATH="$gv_oracle_ld_library_path"
                        check_oracle_attribute_present "new_ld_library_path"
                        if [[ "$?" -eq "0" ]]; then
                            echo -e "\nUpdating the LD_LIBRARY_PATH..."
                            createSilentRestart
                            $MONAGENT_FILE $RESTART 2>/dev/null 1>/dev/null
                            log "Agent restart command executed"
                            cat $TERMINAL_RESPONSE_FILE
                            rm -R $TERMINAL_RESPONSE_FILE
                            continue
                        fi
                    fi
                    cat $TERMINAL_RESPONSE_FILE
                    echo -e '\n'
                    rm -R $TERMINAL_RESPONSE_FILE
                    found_terminal_response_file="1"
                    break
                else
                    sleep 6
                fi
            done
        if [[ "$found_terminal_response_file" -eq "0" ]]; then
            log "Have not recevied terminal response file."
            if [[ "$PARAM" = "--update_library_path" && $1 = 'Oracle Database' ]]; then
                return "1"
            # else
            #     echo -e "\n Something went wrong please try again..."
            fi
        fi
    fi
}

archive_logs(){
    mkdir -p $MONAGENT_TEMP_DIR
    if [ $(command -v zip) ]; then    
        zip -rq $ZIPPED_LOG_FILE $LOG_DIR $INSTALL_LOG
        if ! unzip -l $ZIPPED_LOG_FILE | grep -q '2 files'; then
            echo -e "\033[32m$LOG_DIR folder archived successfully into $ZIPPED_LOG_FILE\033[0m"
        else
            echo -e "\033[0;31mLogs folder archiving failed !! Kindly zip the entire $LOG_DIR folder manually.\033[0m"
            exit 1
        fi
    else
        echo -e "\033[0;31mZip utility is required to archive the agent log files. Either install it or zip the complete $LOG_DIR manually.\033[0m"
        exit 1
    fi
}

upload_logs() {
    read -p "Enter your E-mail id* (to associate the uploaded file): " email_id
    read -p "Enter the ticket id* (for which the log is required): " ticket_id
    read -p "Do you want to view the log archive before uploading to $PRODUCT_NAME ?: " view_consent
    if [ "$view_consent" == "y" ]; then
        unzip -l $ZIPPED_LOG_FILE
        unzip -l $ZIPPED_LOG_FILE >> $INSTALL_LOG 
        echo -e "\n\nYou can also manually verify the archive contents in the file located in $ZIPPED_LOG_FILE"
    fi
    read -p "Proceed with upload [Ensure bonitas.zohocorp.com is whitelisted] ? (y/n): " upload_consent >> $INSTALL_LOG
    upload_consent="${upload_consent:-"n"}"
    echo "Customer consent $upload_consent to upload log under the mail id: $email_id for the ticket id $ticket_id" >> $INSTALL_LOG
    if [ "$upload_consent" == "y" ] || [ "$upload_consent" == "Y" ]; then
        callAgentHelperPy upload_logs $ticket_id $email_id
    else
        echo "\033[0;31mAgent log upload is cancelled !!!\033[0m"
        echo "Agent log upload is cancelled !!!" >> $INSTALL_LOG
    fi
}

if [[ $# -eq 0 ]]; then
    defaultMessage
    echo "Try 'AgentManager.sh -h' for more information."
fi

if [[ $1 == "prometheus" && ! -z "$2" ]]; then
    PARAM=`echo $2 | awk -F= '{print $1}'`
    VALUE=`echo $2 | awk -F= '{print $2}'`
    if [[ $PARAM = "--enable" ]]; then
        output=$($PYTHON_VAR $AGENT_HELPER_PY_FILE "checkPrometheus")
        if [[ $VALUE = "true" ]]; then
            if [[ $output = 'disabled' ]]; then
                SILENT_RESTART=true
                enablePrometheus $2
            else
                echo 'Prometheus Already Enabled'
                echo "Try 'AgentManager.sh prometheus --view' for more information."
            fi
        elif [[ $VALUE == "false" ]]; then
            if [[ $output == 'enabled' ]]; then
                SILENT_RESTART=true
                disablePrometheus $2
            else
                echo 'Prometheus Already Disabled'
                echo "Try 'AgentManager.sh prometheus --view' for more information."
            fi
        fi
    elif [[ $PARAM == "--add_config" ]]; then
        output=$($PYTHON_VAR $AGENT_HELPER_PY_FILE "checkPrometheusAddInput" "$VALUE")
        if [[ $output = 'valid' ]]; then
            SILENT_RESTART=true
            addPrometheusInstance "$VALUE"
        elif [[ $output == 'Instance Name already exists' ]]; then
            echo "$output"
            echo "Try 'AgentManager.sh prometheus --view' for more information."
        else
            echo 'Prometheus Add Configuration Format not valid'
            echo "Try 'AgentManager.sh -h' for more information."
        fi
    elif [[ $PARAM == "--scrape_interval" ]]; then
        output=$($PYTHON_VAR $AGENT_HELPER_PY_FILE "checkPrometheusScrapeInterval" "$VALUE")
        if [[ $output = 'valid' ]]; then
            SILENT_RESTART=true
            changePrometheusScrapeInterval "$VALUE"
        else
            echo "$output"
            echo "Try 'AgentManager.sh prometheus --view' for more information."
        fi
    elif [[ $PARAM = "--remove_config" ]]; then
        output=$($PYTHON_VAR $AGENT_HELPER_PY_FILE "checkPrometheusRemoveInput" "$VALUE")
        if [[ $output = 'valid' ]]; then
            SILENT_RESTART=true
            removePrometheusInstance "$VALUE"
        elif [[ $output == 'Instance Name does not exists' ]]; then
            echo "$output"
            echo "Try 'AgentManager.sh prometheus --view' for more information."
        else
            echo 'Prometheus Remove Configuration Format not valid'
            echo "Try 'AgentManager.sh -h' for more information."
        fi
    elif [[ $PARAM = "--view" ]]; then
        callAgentHelperPy "$1"
    else
        defaultMessage
        echo "Try 'AgentManager.sh -h' for more information."
    fi

elif [[ $1 == "statsd" && ! -z "$2" ]]; then
    PARAM=`echo $2 | awk -F= '{print $1}'`
    VALUE=`echo $2 | awk -F= '{print $2}'`
    if [[ $PARAM = "--enable" ]]; then
        output=$($PYTHON_VAR $AGENT_HELPER_PY_FILE "checkStatsd")
        if [[ $VALUE = "true" ]]; then
            if [[ $output = 'disabled' ]]; then
                SILENT_RESTART=true
                enableStatsd $2
            else
                echo 'Statsd Already Enabled'
                echo "Try 'AgentManager.sh statsd --view' for more information."
            fi
        elif [[ $VALUE == "false" ]]; then
            if [[ $output == 'enabled' ]]; then
                SILENT_RESTART=true
                disableStatsd $2
            else
                echo 'Statsd Already Disabled'
                echo "Try 'AgentManager.sh statsd --view' for more information."
            fi
        fi
    elif [[ $PARAM = "--update_config" ]]; then
        output=$($PYTHON_VAR $AGENT_HELPER_PY_FILE "checkStatsdEditInput" "$VALUE")
        if [[ $output = 'valid' ]]; then
            SILENT_RESTART=true
            editStatsdInstance "$VALUE"
        else
            echo 'Statsd Edit Configuration Format not valid'
            echo "Try 'AgentManager.sh -h' for more information."
        fi
    elif [[ $PARAM = "--view" ]]; then
        callAgentHelperPy "$1"
    else
        defaultMessage
        echo "Try 'AgentManager.sh -h' for more information."
    fi

elif [[ $1 == "mysql" && ! -z "$2" ]]; then
    PARAM=`echo $2 | awk -F= '{print $1}'`
    VALUE=`echo $2 | awk -F= '{print $2}'`
    setup_database_instance "MySQL" "$2" "$MYSQL_TERMINAL_RESPONSE_FILE" "$PARAM"

    # comment the above and uncomment the below code if any problem arises

#     if [[ $PARAM = "--add_instance" ]]; then
#             echo -e "\nEnter MySQL instance's user credentials \n"
#             read -p "Does the instance installed in this machine?(y/n)" IsLocalhost
#             if [[ $IsLocalhost = 'y' ]]; then
#                 hostname='localhost'
#             else
#                 read -p "Host Name              : " hostname
#             fi
#             read -p "Port                   : " port
#             read -p "Username               : " username
#             read -s -p "Password               : " password
#             echo -e '\n'
#             #read -p "Do you want to change the default data collection configuration (y/n) " change_default_config
#             if [[ $change_default_config = 'y' ]]; then
#                 echo -e "\nEnter your choice for the modules to monitor "
#                 read -p "Top Query           (y/n)     : " top_query
#                 read -p "Statement Analysis  (y/n)     : " stmt_anlys
#                 read -p "Event Analysis      (y/n)     : " evnt_anlys
#                 read -p "File IO             (y/n)     : " file_io
#                 read -p "Slow Query          (y/n)     : " slow_query
#                 echo -e '\n'
#             fi
#             #echo 'Adding mysql instance ['$hostname'-'$port'] for data collection'

#             #VALUE='[{"host":"'$hostname'","port":"'$port'","user":"'$username'","password":"'$password'"}]'

#             VALUE='[{"host":"'$hostname'","port":"'$port'","user":"'$username'","password":"'$password'"'
#                 if [[ $stmt_anlys = 'n' ]]; then
#                    VALUE=$VALUE',"statement_analysis":"false"'
#                 fi
#                 if [[ $evnt_anlys = 'n' ]]; then
#                    VALUE=$VALUE',"event_analysis":"false"'
#                 fi
#                 if [[ $file_io = 'n' ]]; then
#                     VALUE=$VALUE',"file_io":"false"'
#                 fi
#                 if [[ $top_query = 'n' ]]; then
#                     VALUE=$VALUE',"top_query":"false"'
#                 fi
#                 if [[ $slow_query = 'n' ]]; then
#                     VALUE=$VALUE',"slow_query":"false"'
#                 fi
#                 #if [[ $change_poll = 'y' ]]; then
#                 #    VALUE=$VALUE',"basic_poll_interval":"'$basic_poll_interval'","insight_poll_interval":"'$insight_poll_interval'"'
#                 #fi

#                 VALUE=$VALUE'}]'

#             #echo $VALUE

#             echo -e '\nAdding MySQL instance ['$hostname'-'$port']...\n'
#             if [[ -f $MYSQL_TERMINAL_RESPONSE_FILE ]]; then
#               rm -R $MYSQL_TERMINAL_RESPONSE_FILE
#             fi
#             addMySQLInstance "$VALUE"
#             for (( each=1; each<=20; each++ ))
#             do
#                 if [[ -f $MYSQL_TERMINAL_RESPONSE_FILE ]]; then
#                     cat $MYSQL_TERMINAL_RESPONSE_FILE
#                     echo -e '\n'
#                     rm -R $MYSQL_TERMINAL_RESPONSE_FILE
#                     break
#                 else
#                     sleep 6
#                 fi
#             done


#     elif [[ $PARAM = "--remove_instance" ]]; then
#             echo "Enter [host/port] of the instance to be deleted "
#             read -p "Host Name              : " hostname
#             read -p "Port                   : " port
#             echo -e '\n'
#             echo 'Deleting MySQL instance ['$hostname'-'$port'] '

#             VALUE='[{"instance":"'$hostname'-'$port'", "host":"'$hostname'", "port":"'$port'"}]'
#             #echo $VALUE
#             if [[ -f $MYSQL_TERMINAL_RESPONSE_FILE ]]; then
#               rm -R $MYSQL_TERMINAL_RESPONSE_FILE
#             fi
#             removeMySQLInstance "$VALUE"
#             for (( each=1; each<=20; each++ ))
#                 do
#                     if [[ -f $MYSQL_TERMINAL_RESPONSE_FILE ]]; then
#                         cat $MYSQL_TERMINAL_RESPONSE_FILE
#                         echo -e '\n'
#                         rm -R $MYSQL_TERMINAL_RESPONSE_FILE
#                         break
#                     else
#                         sleep 6
#                     fi
#                 done

#     elif [[ $PARAM = "--update_instance" ]]; then
#         echo -e "\nEnter [host/port] of the instance to be updated "
#         read -p "Host Name              : " hostname
#         read -p "Port                   : " port
#         read -p "Username               : " username
#         read -s -p "Password               : " password
#         echo -e '\n'
#         #read -p "Do you want to change the default data collection configuration (y/n) " change_default_config
#         if [[ $change_default_config = 'y' ]]; then
#             echo -e "\nEnter your choice for the modules to monitor "
#             read -p "Top Query           (y/n)     : " top_query
#             read -p "Statement Analysis  (y/n)     : " stmt_anlys
#             read -p "Event Analysis      (y/n)     : " evnt_anlys
#             read -p "File IO             (y/n)     : " file_io
#             read -p "Slow Query          (y/n)     : " slow_query
#             echo -e '\n'
#         fi



#         #read -p "Do you want to change poll interval of data collection (y/n) : " change_poll
#         #if [[ $change_poll = 'y' ]]; then
#         #    echo "Enter poll interval in seconds"
# #            read -p "Basic Poll Interval    : " basic_poll_interval
# #            read -p "Insight Poll Interval  : " insight_poll_interval
# #            echo ''
# #        fi



#         VALUE='[{"host":"'$hostname'","port":"'$port'","user":"'$username'","password":"'$password'"'
#             if [[ $stmt_anlys = 'n' ]]; then
#                VALUE=$VALUE',"statement_analysis":"false"'
#             fi
#             if [[ $evnt_anlys = 'n' ]]; then
#                VALUE=$VALUE',"event_analysis":"false"'
#             fi
#             if [[ $file_io = 'n' ]]; then
#                 VALUE=$VALUE',"file_io":"false"'
#             fi
#             if [[ $top_query = 'n' ]]; then
#                 VALUE=$VALUE',"top_query":"false"'
#             fi
#             if [[ $slow_query = 'n' ]]; then
#                 VALUE=$VALUE',"slow_query":"false"'
#             fi
#             #if [[ $change_poll = 'y' ]]; then
#             #    VALUE=$VALUE',"basic_poll_interval":"'$basic_poll_interval'","insight_poll_interval":"'$insight_poll_interval'"'
#             #fi

#             VALUE=$VALUE'}]'
#         echo -e '\nUpdating MySQL instance ['$hostname'-'$port']...\n'
#         #echo $VALUE
#         if [[ -f $MYSQL_TERMINAL_RESPONSE_FILE ]]; then
#           rm -R $MYSQL_TERMINAL_RESPONSE_FILE
#         fi
#         addMySQLInstance "$VALUE"
#         for (( each=1; each<=20; each++ ))
#         do
#             if [[ -f $MYSQL_TERMINAL_RESPONSE_FILE ]]; then
#                 cat $MYSQL_TERMINAL_RESPONSE_FILE
#                 echo -e '\n'
#                 rm -R $MYSQL_TERMINAL_RESPONSE_FILE
#                 break
#             else
#                 sleep 6
#             fi
#         done

#     else
#         defaultMessage
#         echo "Try 'AgentManager.sh -h' for more information."
#     fi

elif [[ $1 == "postgres" && ! -z "$2" ]]; then
    PARAM=`echo $2 | awk -F= '{print $1}'`
    VALUE=`echo $2 | awk -F= '{print $2}'`

    setup_database_instance "Postgres" "$2" "$POSTGRES_TERMINAL_RESPONSE_FILE" "$PARAM"

elif [[ $1 == "oracledb" && ! -z "$2" ]]; then
    PARAM=`echo $2 | awk -F= '{print $1}'`
    VALUE=`echo $2 | awk -F= '{print $2}'`

    setup_database_instance "Oracle Database" "$2" "$ORACLE_TERMINAL_RESPONSE_FILE" "$PARAM"

elif [[ $1 == "plugin" && ! -z "$2" ]]; then
    PARAM=`echo $2 | awk -F= '{print $1}'`
    VALUE=`echo $2 | awk -F= '{print $2}'`
    if [[ $PARAM = "--view" ]]; then
        callAgentHelperPy "$1"
    else
        defaultMessage
        echo "Try 'AgentManager.sh -h' for more information."
    fi
elif [[ $1 = '-h' || $1 = '-help' ]]; then
    echo ''
    echo 'Usage: AgentManager.sh [option] ...'
    echo ''
    helpMessage

elif [[ $1 = '-version' || $1 = '-v' ]]; then
    displayVersion

elif [[ $1 = '-ziplogs' ]]; then
    archive_logs
    if [ $? = 0 ]; then
        read -p "Do you want to upload the log files to $PRODUCT_NAME ? (y/n): " upload_choice
        upload_choice="${upload_choice:-"n"}"
        if [ "$upload_choice" == "y" ] || [ "$upload_choice" == "Y" ]; then
            upload_logs
        else
            echo "Agent logs are not uploaded to $PRODUCT_NAME"
        fi
    fi

elif [[ $1 = '-upload_logs' ]]; then
    archive_logs
    upload_logs

elif [[ $1 = '-newmonitor' || $1 = '-createmonitor' ]]; then
    if [ $(command -v sed) ]; then
        if [ $1 = '-newmonitor' ]; then
            sed -i 's/site24x7 = SITE24X7$/site24x7 = SITE24X7NEW/' $MONAGENT_CONF_FILE
        fi
        sed -i 's/agent_key = .*/agent_key = 0/' $MONAGENT_CONF_FILE
        createSilentRestart
        restartAgent
        if [ $? = 0 ]; then
            echo -e "\033[32mNew monitor creation for the deleted monitor (or) same UUID/Hostname servers request successfull.\033[0m"
        else
            echo -e "\033[0;31mNew monitor creation for the same UUID/Hostname servers request failed.\033[0m"
        fi
    else
        echo -e "\033[0;31msed utility is required to process this request.\033[0m Kindly follow https://support.site24x7.com/portal/en/kb/articles/how-to-set-up-monitoring-for-a-cloned-linux-server-with-the-same-host-name"  
    fi

elif [[ $1 = '-psutil' ]]; then
    touch $PS_UTIL_FLOW_FILE
    createSilentRestart
    restartAgent
    echo -e "\033[32mPSUTIL FLOW CHANGED SUCCESSFULLY.\033[0m"

elif [[ $1 = '-cpu_sar' ]]; then
    if [ $(command -v sar) ]; then
        if [ $(command -v sed) ]; then
            sed -i 's/CPU_STATS_IMPL/CPU_SAR_IMPL/' $MONITORS_XML_FILE
            createSilentRestart
            restartAgent
            echo -e "\033[32mRequest for monitoring CPU based on SAR successfull.\033[0m"
        else
            echo -e "\033[0;31msed utility is required to process this request.\033[0m"
        fi  
    else
        echo -e "\033[0;31mSAR utility not found in the server. Kindly install the same for monitoring CPU based on SAR\033[0m"
    fi

elif [[ $1 = '-debug_on' ]]; then
    if [ $(command -v sed) ]; then
        sed -i 's/level="3"/level="1"/' $LOGGING_XML_FILE
        if [ $? = 0 ]; then
            createSilentRestart
            restartAgent
            echo -e "\033[32mAgent logging set to debug mode.\033[0m"
        else
            echo -e "\033[0;31mUnable to set debug mode for logging. Kindly do it manually.\033[0m"
        fi
    else
        echo -e "\033[0;31msed utility is required to process this request.\033[0m"
    fi  

elif [[ $1 = '-debug_off' ]]; then
    if [ $(command -v sed) ]; then
        sed -i 's/level="1"/level="3"/' $LOGGING_XML_FILE
        if [ $? = 0 ]; then
            createSilentRestart
            restartAgent
            echo -e "\033[32mAgent logging set to normal mode.\033[0m"
        else
            echo -e "\033[0;31mUnable to set normal mode for logging. Kindly do it manually.\033[0m"
        fi
    else
        echo -e "\033[0;31msed utility is required to process this request.\033[0m"
    fi

elif [[ $1 = '-set_limit' ]]; then
    if [ $(command -v sed) ]; then
        presentCPU=`grep 'CPU' $WATCHDOG_CONF_FILE | awk '{print $3}'`
        presentMemory=`grep 'MEMORY' $WATCHDOG_CONF_FILE | awk '{print $3}'`
        
        read -p "Enter new agent CPU threshold (%): " CPU
        read -p "Enter new agent memory threshold (%): " MEM
        
        #setting values when no input
        CPU="${CPU:-$presentCPU}"
        MEM="${MEM:-$presentMemory}"
        
        sed -i "s/CPU =.*/CPU = $CPU/I" $WATCHDOG_CONF_FILE
        sed -i "s/MEMORY =.*/MEMORY = $MEM/I" $WATCHDOG_CONF_FILE
        restartwatchdog
        if [ $? = 0 ]; then
            echo -e "\n\033[32mSite24x7 Agent's threshold changed to CPU: $CPU% and Memory: $MEM% successfully.\033[0m"
        else
            echo -e "\033[0;31mAction to change limit of Site24x7 consumption failed.\033[0m"
        fi
    else
        echo -e "\033[0;31msed utility is required to process this request.\033[0m"
    fi

elif [[ $1 = '-sysclock' ]]; then
    if [ $(command -v sed) ]; then
        old_interval=`grep 'SYSCLOCK_INTERVAL' $WATCHDOG_CONF_FILE | awk '{print $3}'`
        read -p "Enter new value: " interval
        #setting old value when no input
        INT="${interval:-$old_interval}"
        sed -i "s/SYSCLOCK_INTERVAL =.*/SYSCLOCK_INTERVAL = $INT/I" $WATCHDOG_CONF_FILE
        restartwatchdog
    else
        echo -e "\033[0;31msed utility is required to process this request.\033[0m"
    fi

elif [[ $1 = '-edit_proxy' ]]; then
    if [ $(command -v sed) ]; then
        echo -e "You can ignore values that not applicable by pressing Enter"
        
        read -p "Enter proxy server name / IP address: " server
        if [ "$server" != "" ]; then
            sed -i "s/proxy_server_name.*/proxy_server_name = $server/"  $MONAGENT_CONF_FILE
        fi
        
        read -p "Enter proxy server port: " port
        if [ "$port" != "" ]; then
            sed -i "s/proxy_server_port.*/proxy_server_port = $port/"  $MONAGENT_CONF_FILE
        fi
        
        read -p "Enter proxy server username: " username
        if [ "$username" != "" ]; then
            sed -i "s/proxy_user_name.*/proxy_user_name = $username/"  $MONAGENT_CONF_FILE
        fi
        
        read -p "Enter proxy server password: " password
        if [ "$password" != "" ]; then
            sed -i "s/proxy_password.*/proxy_password = $password/"  $MONAGENT_CONF_FILE
        fi
        if [ "$server" != "" ]; then 
            createSilentRestart
            restartAgent
            echo -e "\033[32mProvided proxy configuration set\033[0m"
            echo -e "Still agent not reaching the proxy server?, Change [PROXY_INFO] section of $MONAGENT_CONF_FILE for necessary corrections"
        fi
    else
        echo -e "\033[0;31msed utility is required to process this request.\033[0m"
    fi

elif [[ $1 = '-edit_devicekey' ]]; then
    if [ $(command -v sed) ]; then
        echo -e "\033[0;31m[WARNING] Modifying device key will create a new monitor in the provided account in respective datacenter. Change with caution !!!\033[0m"
        read -p "Enter new device key: " device_key
        if [ "$device_key" != "" ]; then
            sed -i 's/agent_key = .*/agent_key = 0/' $MONAGENT_CONF_FILE
            sed -i "s/^.*customer_id.*/customer_id = $device_key/"  $MONAGENT_CONF_FILE
            if [ $? = 0 ]; then
                createSilentRestart
                restartAgent
                echo -e "\033[32mNew device key configured. Ensure the monitor creation in Site24x7.\033[0m"
                echo -e "NOTE: Your device key will be encrypted and stored in Site24x7 agent."
            else
                echo -e "\033[0;31mUnable to modify device key. Kindly do it manually.\033[0m"
            fi
        fi
    else
        echo -e "\033[0;31msed utility is required to process this request.\033[0m"
    fi

else
    echo -e "Unknown option\n. For more details, refer 'AgentManager.sh -h'"
fi

if [[ $SILENT_RESTART = true ]]; then
    createSilentRestart
    restartAgent
fi
