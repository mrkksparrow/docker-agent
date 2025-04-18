
import json,time,sys,re,subprocess
import traceback , os, glob
from collections import OrderedDict
# import multiprocessing

from com.manageengine.monagent.security import AgentCrypt
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

import six.moves.urllib.request as urlconnection
from six.moves.urllib.parse import urlencode

import com
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil
from com.manageengine.monagent.util.AgentUtil import ZipUtil
from com.manageengine.monagent.util.AgentUtil import FileZipAndUploadInfo
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants,AppConstants,DatabaseConstants
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.scheduler import AgentScheduler
try:
    import pymysql
    AgentConstants.PYMYSQL_MODULE = '1'
except Exception as e:
    AgentLogger.log(AgentLogger.DATABASE,"Error while importing pymysql in DatabaseUtil module")
    traceback.print_exc()

try:
    import psycopg2
    AgentConstants.PSYCOPG2_MODULE = "1"
except:
    AgentLogger.log(AgentLogger.DATABASE,"Error while importing psycopg2 in DatabaseUtil module")

try:
    import oracledb
    AgentConstants.PYTHON_ORACLEDB_MODULE = "1"
except:
    AgentLogger.log(AgentLogger.DATABASE,"Error while importing oracledb in DatabaseUtil module")

if 'com.manageengine.monagent.database_executor.mysql.mysql_monitoring' in sys.modules:
    mysql_monitoring = sys.modules['com.manageengine.monagent.database_executor.mysql.mysql_monitoring']
else:
    from com.manageengine.monagent.database_executor.mysql import mysql_monitoring

from com.manageengine.monagent.database_executor.postgres               import postgres_monitoring
from com.manageengine.monagent.database_executor.oracle                 import oracledb_monitoring

from com.manageengine.monagent.hadoop.data_parser import collect_data
from com.manageengine.monagent.discovery import discovery_util

try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

from com.manageengine.monagent.database_executor.mysql import NDBCluster

MYSQL_CONFIG            = None
POSTGRES_CONFIG         = None
ORACLE_CONFIG           = None

def initialize():
    try:
        if AgentUtil.is_module_enabled(AgentConstants.DATABASE_SETTING):
            for (application, config) in AgentConstants.DB_CONSTANTS.items():
                if not os.path.exists(config['CONF_FOLDER']):
                    create_db_monitoring_dir(application,config['CONF_FILE'])

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception in datbaseutil initialize :: {}'.format(e))
        traceback.print_exc()


# creates .cfg files and separate folder of database applications, inside conf directory
# .cfg files with global default configuration options [MySQL, PostgreSQL, MongoDB]
def create_db_monitoring_dir(application,config_file):
    try:
        DB_CONSTANTS = AgentConstants.DB_CONSTANTS[application]
        if not os.path.exists(DB_CONSTANTS['CONF_FOLDER']):
            AgentLogger.log(AgentLogger.DATABASE,'{} configuration folder not found, Hence creating {} config folder'.format(DB_CONSTANTS['DISPLAY_NAME'],DB_CONSTANTS['CONF_FOLDER']))
            os.mkdir(DB_CONSTANTS['CONF_FOLDER'])

        update_flag = True
        if os.path.exists(config_file):
            config = get_config_parser(config_file)
            if config!=None and config.has_section(application.upper()):
                update_flag = False
            else:
                config = configparser.ConfigParser()
        else:
            config = configparser.ConfigParser()
            AgentLogger.log(AgentLogger.DATABASE,'Creating new Config file for {}'.format(application))

        if update_flag:
            if application == AgentConstants.MYSQL_DB:
                config.add_section('MYSQL')
                config.set('MYSQL','memory','true')
                config.set('MYSQL','session','true')
                config.set('MYSQL','replication','true')
                config.set('MYSQL','top_query','true')
                config.set('MYSQL','slow_query','true')
                config.set('MYSQL','file_io','true')
                config.set('MYSQL','event_analysis','true')
                config.set('MYSQL','error_analysis','true')
                config.set('MYSQL','statement_analysis','true')
                config.set('MYSQL','user_analysis','true')
                config.set('MYSQL','host_analysis','true')
            elif application == AgentConstants.MONGODB_DB:
                config.add_section('MONGODB')
                config.set('MONGODB','dummy_1','true')
                config.set('MONGODB','dummy_2','false')
                config.set('MONGODB','dummy_3','false')
                config.set('MONGODB','dummy_4','true')
            elif application == AgentConstants.POSTGRES_DB:
                config.add_section('POSTGRES')
                config.set('POSTGRES','perf_poll_interval','300')
                config.set('POSTGRES','default_database','postgres')
                # config.set('POSTGRES','session','false')
                # config.set('POSTGRES','top_query','false')
                # config.set('POSTGRES','slow_query','false')
            elif application == AgentConstants.ORACLE_DB:
                ORACLE_DB = AgentConstants.ORACLE_DB.upper()
                config.add_section(ORACLE_DB)
                config.set(ORACLE_DB,'perf_poll_interval','300')
                config.set(ORACLE_DB,'service_name','ORCL')
                # config.set(ORACLE_DB,'ld_library_path','/opt/oracle')
                # oracledb_monitoring.is_ld_library_present(config)

            persist_config_parser(config_file,config)

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while creating Database - {} :: Configurations - {} :: Error - {}'.format(application,config_file,e))
        traceback.print_exc()


# utility function to create a config parser for database .cfg files
def get_config_parser(conf_file):
    config = None
    try:
        config = configparser.ConfigParser()
        config.optionxform=lambda option: option
        config.read(conf_file)
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception in getting config parser :: {} : {}'.format(conf_file,e))
        traceback.print_exc()
    finally:
        return config

def getDBConnection(dict_info, DB_TYPE = AgentConstants.MYSQL_DB):
    connection = None
    err={}
    try:
        sql_pwd  = dict_info['password'] if dict_info['password'] not in ['None', 'none', '0',None] else ''

        if DB_TYPE == AgentConstants.POSTGRES_DB and AgentConstants.PSYCOPG2_MODULE == "1":
            db_info = "host='{}' port={} dbname='{}' user='{}' password='{}' connect_timeout=30 sslmode='{}'".format(dict_info['host'], dict_info['port'], 'postgres', dict_info['user'], sql_pwd, dict_info.get('ssl-mode') or "prefer")
            if 'ssl' in dict_info and dict_info['ssl'] == "true":
                if 'ssl-ca' in dict_info and dict_info['ssl-ca']!="":
                    db_info+= " sslrootcert='"+dict_info['ssl-ca']+"'"
                if 'ssl-cert' in dict_info and dict_info['ssl-cert']!="" and 'ssl-key' in dict_info and dict_info['ssl-key']!="":
                    db_info+= " sslcert='"+dict_info['ssl-cert']+"' sslkey='"+dict_info['ssl-key']+"'"
            connection = psycopg2.connect(db_info)
            #connection = psycopg2.connect(host=dict_info['host'], user=dict_info['user'], password=sql_pwd, port=int(dict_info['port']),database='postgres')database="postgres")
        elif DB_TYPE == AgentConstants.MYSQL_DB:
            ssl_dict = {}
            if 'ssl' in dict_info and dict_info['ssl'] == "true":
                if 'ssl-ca' in dict_info and dict_info['ssl-ca']!="":
                    ssl_dict['ca'] = dict_info['ssl-ca']
                if 'ssl-cert' in dict_info and dict_info['ssl-cert']!="" and 'ssl-key' in dict_info and dict_info['ssl-key']!="":
                    ssl_dict['cert'] = dict_info['ssl-cert']
                    ssl_dict['key'] = dict_info['ssl-key']
            if ssl_dict:
                connection = pymysql.connect(host=dict_info['host'], user=dict_info['user'],password=sql_pwd, port=int(dict_info['port']),ssl={'ssl':ssl_dict})
            else:
                connection = pymysql.connect(host=dict_info['host'], user=dict_info['user'],password=sql_pwd, port=int(dict_info['port']))
            #connection = pymysql.connect(host=dict_info['host'], user=dict_info['user'],password=sql_pwd, port=int(dict_info['port']),ssl_ca=dict_info['ssl-ca'],ssl_key=dict_info['ssl-key'],ssl_cert=dict_info['ssl-cert'])
        elif DB_TYPE == AgentConstants.ORACLE_DB:
            # os.environ['ORACLE_HOME'] = dict_info['oracle_home']
            dsn = oracledb.makedsn(dict_info['host'],int(dict_info['port']),service_name=dict_info.get('service_name') or 'ORCL')
            connection = oracledb.connect(dsn=dsn, user=dict_info['user'], password=sql_pwd)
        return True, connection
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"Exception :: DB_TYPE - {} :: {}-{} :: Connection issue -> DatabaseUtil.getDBConnection -> {}".format(DB_TYPE,dict_info.get('host'),dict_info.get('port'),e))
        return False, str(e)

def check_new_pwd_connc(update_input_dict,DB_TYPE=AgentConstants.MYSQL_DB):
    bool_status = False
    err_msg = None
    try:
        status, connection = getDBConnection(update_input_dict,DB_TYPE)
        if status:
            cursor     = connection.cursor()
            cursor.close()
            connection.close()
            bool_status = True
        else:
            err_msg = str(connection)
    except Exception as e:
        bool_status = False
        err_msg = str(e)
        update_input_dict_cpy = update_input_dict.copy()
        del update_input_dict_cpy['password']
        AgentLogger.log(AgentLogger.DATABASE,'Exception in verifying update {} input data :: {} : {}'.format(DB_TYPE,update_input_dict_cpy, e))
        traceback.print_exc()
    finally:
        return bool_status, err_msg


# instance already registered, updating configurations [ update password, poll interval, etc ]
# password input is encrypted before storing, other possible input is directly stored
def update_instance_config_data(instance_name, dict_info, DB_TYPE, CONFIG):
    try:
        DB_CONSTANTS        = AgentConstants.DB_CONSTANTS[DB_TYPE]
        terminal_output     = '============ No Output ============'
        default_attributes  = []
        if DB_TYPE == AgentConstants.MYSQL_DB:
            default_attributes = ['user', 'database_metrics', 'session', 'replication', 'top_query', 'slow_query', 'innodb', 'binlog']
        elif DB_TYPE == AgentConstants.POSTGRES_DB:
            default_attributes = ['user']
        elif DB_TYPE == AgentConstants.ORACLE_DB:
            default_attributes = ['user']

        for each in dict_info:
            if each == 'password':
                bool_status, err_msg = check_new_pwd_connc(dict_info,DB_TYPE)
                if bool_status:
                    terminal_output = '------------------------------------------------------\n'
                    terminal_output += '                {} Instance       \n'.format(DB_CONSTANTS['DISPLAY_NAME'])
                    terminal_output += '------------------------------------------------------\n'
                    terminal_output += 'Machine Name   : {}\n'.format(AgentConstants.HOST_NAME)
                    terminal_output += 'Host           : {}\n'.format(dict_info['host'])
                    terminal_output += 'Port           : {}\n'.format(dict_info['port'])
                    terminal_output += '------------------------------------------------------\n'
                    terminal_output += '   Successfully updated {} Configuration\n'.format(DB_CONSTANTS['DISPLAY_NAME'])
                    terminal_output += '------------------------------------------------------'

                    new_encrypted_pwd = AgentCrypt.encrypt_with_ss_key(str(dict_info[each]))
                    CONFIG.set(instance_name,'encrypted.password',str(new_encrypted_pwd).replace('%',"%%"))
                    
                else:
                    terminal_output = '------------------------------------------------------\n'
                    terminal_output += '                {} Instance       \n'.format(DB_CONSTANTS['DISPLAY_NAME'])
                    terminal_output += '------------------------------------------------------\n'
                    terminal_output += 'Machine Name   : {}\n'.format(AgentConstants.HOST_NAME)
                    terminal_output += 'Host           : {}\n'.format(dict_info['host'])
                    terminal_output += 'Port           : {}\n'.format(dict_info['port'])
                    terminal_output += 'Error          : {}\n'.format(err_msg)
                    terminal_output += '------------------------------------------------------\n'
                    terminal_output += '     Failed to update {} Configuration\n'.format(DB_CONSTANTS['DISPLAY_NAME'])
                    # terminal_output += '       Restored previous configuration\n'
                    terminal_output += '------------------------------------------------------'
            
            if each in default_attributes:
                if each in dict_info:
                    CONFIG.set(instance_name,each,dict_info[each])

        AgentLogger.log(AgentLogger.DATABASE,str(terminal_output))
        AgentUtil.writeRawDataToFile(DB_CONSTANTS['TERMINAL_RESPONSE_FILE'], str(terminal_output))

        # if int(time.time() - (DB_CONSTANTS['ADD_INSTANCE_START_TIME'] or 0)) < 115:
        #     AgentLogger.log(AgentLogger.DATABASE,str(terminal_output))
        #     AgentUtil.writeRawDataToFile(DB_CONSTANTS['TERMINAL_RESPONSE_FILE'], str(terminal_output))
        # else:
        #     AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Instance - {} took more time to register hence skipping terminal responce'.format(DB_TYPE,instance_name))

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while updating instance configurations :: Database - {} :: Instance - {} :: Error - {} :: traceback -{}'.format(DB_TYPE,instance_name,e,traceback.print_exc()))

def register_database_monitor(dict_param,instance_name,db_type,config,conf_file):
    register_status = False
    app_key = None
    try:
        request_params = AgentUtil.get_default_reg_params()
        request_params.update(dict_param)

        register_status , app_key = apps_registration(db_type,instance_name,dict_param,conf_file,config,request_params)
        AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: registration successful :: App key - {} :: dict_param - {}'.format(db_type,app_key,dict_param))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while registering {} monitor Param - {} :: Error - {}'.format(db_type,dict_param,e))
        traceback.print_exc()
    finally:
        return register_status, app_key

def apps_registration(app_name,instance_name,instance_dict, conf_file, config=None, request_params={}):
    reg_status, app_key = False, None
    try:
        str_requestParameters = urlencode(request_params)
        str_url = AgentConstants.APPLICATION_DISCOVERY_SERVLET + str_requestParameters
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.STDOUT)
        requestInfo.set_method(AgentConstants.HTTP_GET)
        requestInfo.set_url(str_url)
        requestInfo.set_dataType('application/json')
        requestInfo.add_header("Content-Type", 'application/json')
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
        CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'ADS')
        AgentLogger.debug(AgentLogger.DATABASE, "[DEBUG] Database - {} :: Instance - {} :: response headers - {} :: error code - {}".format(app_name,instance_name,dict_responseHeaders,errorCode)+'\n')
        if dict_responseHeaders and app_name+"key" in dict_responseHeaders:
            app_key = dict_responseHeaders[app_name+"key"]
        if bool_isSuccess and app_key and not app_key.lower() in (app_name, "0", ):
            reg_status = True
            AgentLogger.log(AgentLogger.DATABASE, "Database - {} :: Instance :: {} is registered successfully | App id : {} | Registration Status : {} ". format(app_name, instance_name, app_key, reg_status)+'\n')
        else:
            AgentLogger.log(AgentLogger.DATABASE, "Database - {} :: Instance :: {} is not registered successfully  | App id : {} | Registration Status : {} ". format(app_name, instance_name, app_key, reg_status)+'\n')

        if dict_responseHeaders and "mysqlNDBmonkey" in dict_responseHeaders and reg_status:
            NDBCluster.AppRegistrationResponse(dict_responseHeaders,dict_responseData,config,instance_name)

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE, "Database - {} :: Instance :: {} registration failed  | Registration Status : {} | Exception : {} ". format(app_name, instance_name, reg_status, e)+'\n')
        traceback.print_exc()
    finally:
        return reg_status, app_key


def clear_database_config_files():
    try:
        AgentLogger.log(AgentLogger.DATABASE,"Agent Key Change Detected, Clear Config Files Operation Initiated")
        
        for database_name,DB_CONSTANTS in AgentConstants.DB_CONSTANTS.items():
            config = get_config_parser(DB_CONSTANTS['CONF_FILE'])

            if config==None:
                continue
            
            AgentLogger.log(AgentLogger.DATABASE,"Hence deleting {} Instances".format(DB_CONSTANTS["DISPLAY_NAME"]))
            _sections = config.sections()
            for each_instance in _sections:
                if each_instance != database_name.upper():
                    config.remove_section(each_instance)
                    AgentLogger.log(AgentLogger.DATABASE,"{} Instance :: {} :: removed successfully".format(DB_CONSTANTS["DISPLAY_NAME"],each_instance))
            persist_config_parser(DB_CONSTANTS['CONF_FILE'], config)
        
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"Exception while clearing database config files - Error : {}".format(e))
        traceback.print_exc()


def child_database_discover(dict_task):
    try:
        if 'MONITOR_ID' in dict_task:
            mid = dict_task['mid']
            mysql_config = get_config_parser(AgentConstants.MYSQL_CONF_FILE)
            for instance in mysql_config:
                if instance not in ['MYSQL','DEFAULT'] and mysql_config.get(instance, 'mid') == mid:
                    mysql_monitoring.schedule_database_discovery(instance)
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while scheduling database discover task :: Error - {}'.format(e))
        traceback.print_exc()
    finally:
        return None

# update database config
def update_database_config_data(database, config_dict):
    config_update_dict = {}
    try:
        pass
        if database == "MYSQLDB":
            is_change = False
            mysql_config = get_config_parser(AgentConstants.MYSQL_CONF_FILE)
            for instance in config_dict:
                config_update_dict[instance['mid']] = {}
                if 'poll_interval' in instance:
                    config_update_dict[instance['mid']]['poll_interval'] = instance['poll_interval']
                if 'extra_metrics' in instance:
                    config_update_dict[instance['mid']]['extra_metrics'] = instance['extra_metrics']
                if 'replication' in instance['child_keys']:
                    config_update_dict[instance['mid']]['replication_child_keys'] = instance['child_keys']['replication']
                if 'mysql_replication_seconds_behind_master' in instance['child_keys']:
                    config_update_dict[instance['mid']]['mysql_replication_seconds_behind_master'] = instance['child_keys']['mysql_replication_seconds_behind_master']
                if 'MYSQL_DATABASE' in instance['child_keys']:
                    config_update_dict[instance['mid']]['child_keys'] = instance['child_keys']['MYSQL_DATABASE']
                    AgentLogger.log(AgentLogger.STDOUT,'Child Database added for data collection :: {} : {}'.format(instance['mid'],instance['child_keys']['MYSQL_DATABASE']))
                else:
                    config_update_dict[instance['mid']]['child_keys'] = {}
                config_update_dict[instance['mid']]['status'] = instance['status']

            for section in mysql_config:
                if section not in ['MYSQL','DEFAULT'] and mysql_config.get(section,'enabled') == 'true':
                    mon_id = mysql_config.get(section,'mid')
                    if mon_id in config_update_dict:
                        AgentConstants.DATABASE_CONFIG_MAPPER['mysql'][section] = {}
                        AgentConstants.DATABASE_CONFIG_MAPPER['mysql'][section] = config_update_dict[mon_id]['child_keys']
                        if 'replication_child_keys' in config_update_dict[mon_id]:
                            AgentConstants.DATABASE_CONFIG_MAPPER['mysql_replication'][section] = config_update_dict[mon_id]['replication_child_keys']
                        if 'mysql_replication_seconds_behind_master' in config_update_dict[mon_id]:
                            AgentConstants.DATABASE_CONFIG_MAPPER['mysql_replication_seconds_behind_master'][section] = config_update_dict[mon_id]['mysql_replication_seconds_behind_master']
                        AgentLogger.debug(AgentLogger.DATABASE,'[DEBUG] Child Database added for data collection :: {} : {}'.format(section,config_update_dict[mon_id]['child_keys']))
                        if mysql_config.get(section,'status') != config_update_dict[mon_id]['status']:
                            is_change = True
                            mysql_config.set(section,'status',config_update_dict[mon_id]['status'])
                        if 'poll_interval' in config_update_dict[mon_id]:
                            if mysql_config.has_option(section, 'poll_interval'):
                                if mysql_config.get(section,'poll_interval') != config_update_dict[mon_id]['poll_interval']:
                                    is_change = True
                                    if '-insight' in section:
                                        if [mon_id+'_insight'] in AgentConstants.DATABASE_OBJECT_MAPPER['mysql']:
                                            AgentConstants.DATABASE_OBJECT_MAPPER['mysql'][mon_id+'_insight'].setInterval(int(config_update_dict[mon_id]['poll_interval']))
                                    else:
                                        if [mon_id+'_basic'] in AgentConstants.DATABASE_OBJECT_MAPPER['mysql']:
                                            AgentConstants.DATABASE_OBJECT_MAPPER['mysql'][mon_id+'_basic'].setInterval(int(config_update_dict[mon_id]['poll_interval']))
                                    mysql_config.set(section,'poll_interval',config_update_dict[mon_id]['poll_interval'])
                            else:
                                is_change = True
                                if '-insight' in section:
                                    if [mon_id+'_insight'] in AgentConstants.DATABASE_OBJECT_MAPPER['mysql']:
                                        AgentConstants.DATABASE_OBJECT_MAPPER['mysql'][mon_id+'_insight'].setInterval(int(config_update_dict[mon_id]['poll_interval']))
                                else:
                                    if [mon_id+'_basic'] in AgentConstants.DATABASE_OBJECT_MAPPER['mysql']:
                                        AgentConstants.DATABASE_OBJECT_MAPPER['mysql'][mon_id+'_basic'].setInterval(int(config_update_dict[mon_id]['poll_interval']))
                                mysql_config.set(section,'poll_interval',config_update_dict[mon_id]['poll_interval'])
                        if 'extra_metrics' in config_update_dict[instance['mid']]:
                            is_change = True
                            mysql_config.set(section,'db_size_top_tb',config_update_dict[mon_id]['extra_metrics'])
                        pass
            if is_change:
                persist_config_parser(AgentConstants.MYSQL_CONF_FILE,mysql_config)
                mysql_monitoring.start_mysql_data_collection()
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while updating database config :: Database - {} : Error - {}'.format(database,e))
        traceback.print_exc()
    finally:
        return None

def is_host_local_instance(host, port=None):
    is_local = False
    try:
        if host in ['localhost', '127.0.0.1', '0.0.0.0', AgentConstants.IP_ADDRESS, AgentConstants.HOST_NAME] or host in AgentConstants.IP_LIST:
            is_local = True
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"Exception while checking instance is local/remote - Error : {}".format(e))
        traceback.print_exc()
    finally:
        return is_local

def rediscover_sql_instances(DB_TYPE):
    try:
        DB_CONSTANTS = AgentConstants.DB_CONSTANTS[DB_TYPE]
        stop_all_instance(DB_TYPE)
        checked_local_instance_port_list = []

        CONFIG = get_config_parser(DB_CONSTANTS['CONF_FILE'])
        copy_to_global_config(DB_TYPE,CONFIG)

        sql_instance_list = discover_sql_db(DB_TYPE,DB_CONSTANTS)

        for each_instance in CONFIG:
            if each_instance in [DB_TYPE.upper(), 'DEFAULT']:
                continue

            port = CONFIG.get(each_instance,'port')
            host = CONFIG.get(each_instance,'host')
            checked_local_instance_port_list.append(port)
            if CONFIG.get(each_instance,'user') == '0' or CONFIG.get(each_instance,'enabled') == 'false':
                is_exist = False
                for single_process in sql_instance_list:
                    if str(port) == single_process['port'] and str(host) == single_process['host']:
                        
                        register_status,app_key = register_database_monitor(single_process,each_instance,DB_CONSTANTS['APP_KEY'],CONFIG,DB_CONSTANTS['CONF_FILE'])
                        is_exist = True
                        if register_status and app_key:
                            AgentLogger.log(AgentLogger.DATABASE,'re-Registering Dummy Instance Successful | Database :: {} | Instance Name :: {} | New Key :: {} | Old Key :: {}'.format(each_instance,app_key,CONFIG.get(each_instance,'mid')))
                            CONFIG.set(DB_TYPE,each_instance,'mid',app_key)
                        else:
                            AgentLogger.log(AgentLogger.DATABASE,'re-Registering Dummy Instance Failed | Database :: {} | Instance Name :: {} | Old Key :: {}'.format(DB_TYPE,each_instance,CONFIG.get(each_instance,'mid')))
                if not is_exist:
                    AgentLogger.log(AgentLogger.DATABASE,'re-Registering Dummy Instance Not Found | Database :: {} | Instance Name :: {} | Old Key :: {}'.format(DB_TYPE,each_instance,CONFIG.get(each_instance,'mid')))
            else:
                register_status, app_key = reregister_instance(each_instance, CONFIG, DB_TYPE)
                if not CONFIG.has_option(each_instance,'is_remote'):
                    checked_local_instance_port_list.append(port)
                if register_status and app_key:
                    AgentLogger.log(AgentLogger.DATABASE,'re-Registering {} Instance Successful | Instance Name :: {} | New Key :: {} | Old Key :: {}'.format(DB_TYPE,each_instance,app_key,CONFIG.get(each_instance,'mid')))
                    CONFIG.set(each_instance,'mid',app_key)
                else:
                    AgentLogger.log(AgentLogger.DATABASE,'re-Registering {} Instance Failed | Instance Name :: {} | Old Key :: {}'.format(DB_TYPE,each_instance,CONFIG.get(each_instance,'mid')))

        for single_process in sql_instance_list:
            instance_name = str(single_process['host']) +"-"+ str(single_process['port'])
            if str(single_process['port']) not in checked_local_instance_port_list:
                AgentLogger.log(AgentLogger.DATABASE,'re-Registering New {} Instance from Process | Instance Name :: {}'.format(DB_TYPE,instance_name))
                create_instance_section_from_process(instance_name, single_process,DB_TYPE,DB_CONSTANTS,CONFIG)

        copy_to_global_config(DB_TYPE,CONFIG)
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while rediscovering {} Database :: Error - {}'.format(DB_TYPE,e))
        traceback.print_exc()

def start_database_monitoring(DB_TYPE):
    try:
        if DB_TYPE == AgentConstants.MYSQL_DB:
            mysql_monitoring.start_mysql_data_collection()
        elif DB_TYPE == AgentConstants.POSTGRES_DB:
            postgres_monitoring.start_postgres_data_collection()
        elif DB_TYPE == AgentConstants.ORACLE_DB:
            oracledb_monitoring.start_oracledb_data_collection()
        else:
            AgentLogger.log(AgentLogger.DATABASE,"invalid DB_TYPE while starting database monitor - {}".format(DB_TYPE))
            
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"Database - {} :: Exception while starting database monitor - Error : {}".format(DB_TYPE,e))
        traceback.print_exc()

def rediscover_database_monitoring():
    try:
        for db in [AgentConstants.MYSQL_DB,AgentConstants.POSTGRES_DB,AgentConstants.ORACLE_DB]:
            rediscover_sql_instances(db)
            start_database_monitoring(db)

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"Exception while rediscovering database monitor - Error : {}".format(e))
        traceback.print_exc()


# used to stop all thread created for mysql instance in mysql.cfg
def stop_all_instance(database=None, mid=None):
    try:
        if database == AgentConstants.MYSQL_DB:
            if mid:
                if mid+"_insight" in AgentConstants.DATABASE_OBJECT_MAPPER[database]:
                    AgentScheduler.deleteSchedule(AgentConstants.DATABASE_OBJECT_MAPPER[database][mid+"_insight"])
                    AgentConstants.DATABASE_OBJECT_MAPPER[database].pop(mid+"_insight")
                else:
                    if mid+"_basic" in AgentConstants.DATABASE_OBJECT_MAPPER[database]:
                        AgentScheduler.deleteSchedule(AgentConstants.DATABASE_OBJECT_MAPPER[database][mid+"_basic"])
                        AgentConstants.DATABASE_OBJECT_MAPPER[database].pop(mid+"_basic")
                    elif mid+"_onedaytask" in AgentConstants.DATABASE_OBJECT_MAPPER[database]:
                        AgentScheduler.deleteSchedule(AgentConstants.DATABASE_OBJECT_MAPPER[database][mid+"_onedaytask"])
                        AgentConstants.DATABASE_OBJECT_MAPPER[database].pop(mid+"_onedaytask")
                    elif mid+"_database_discover" in AgentConstants.DATABASE_OBJECT_MAPPER[database]:
                        AgentScheduler.deleteSchedule(AgentConstants.DATABASE_OBJECT_MAPPER[database][mid+"_database_discover"])
                        AgentConstants.DATABASE_OBJECT_MAPPER[database].pop(mid+"_database_discover")
                    elif mid+"dummy_data" in AgentConstants.DATABASE_OBJECT_MAPPER[database]:
                        AgentScheduler.deleteSchedule(AgentConstants.DATABASE_OBJECT_MAPPER[database][mid+"dummy_data"])
                        AgentConstants.DATABASE_OBJECT_MAPPER[database].pop(mid+"dummy_data")
                    elif mid+"_insight" in AgentConstants.DATABASE_OBJECT_MAPPER[database]:
                        AgentScheduler.deleteSchedule(AgentConstants.DATABASE_OBJECT_MAPPER[database][mid+"_insight"])
                        AgentConstants.DATABASE_OBJECT_MAPPER[database].pop(mid+"_insight")
                    elif mid+"_child_db" in AgentConstants.DATABASE_OBJECT_MAPPER[database]:
                        AgentScheduler.deleteSchedule(AgentConstants.DATABASE_OBJECT_MAPPER[database][mid+"_child_db"])
                        AgentConstants.DATABASE_OBJECT_MAPPER[database].pop(mid+"_child_db")
            else:
                db_obj_temp_dict = AgentConstants.DATABASE_OBJECT_MAPPER.copy()
                instance_to_be_poped = []
                for instance in db_obj_temp_dict[database]:
                    AgentScheduler.deleteSchedule(AgentConstants.DATABASE_OBJECT_MAPPER[database][instance])
                    AgentLogger.log(AgentLogger.DATABASE,'mysql :: Deleting Database scheduled tasks :: {}'.format(instance))
                    instance_to_be_poped.append(instance)
                for instance in instance_to_be_poped:
                    AgentConstants.DATABASE_OBJECT_MAPPER[database].pop(instance)
        elif database in [AgentConstants.POSTGRES_DB,AgentConstants.ORACLE_DB]:
            if mid:
                for suffix in ['_basic']:
                    task_name = mid+suffix
                    AgentScheduler.deleteSchedule(AgentConstants.DATABASE_OBJECT_MAPPER[database][task_name])
                    AgentConstants.DATABASE_OBJECT_MAPPER[database].pop(task_name)
            else:
                for instance in AgentConstants.DATABASE_OBJECT_MAPPER[database]:
                    AgentScheduler.deleteSchedule(AgentConstants.DATABASE_OBJECT_MAPPER[database][instance])
                    AgentLogger.log(AgentLogger.DATABASE,'{} :: Deleting Database scheduled tasks :: {}'.format(database,instance))
                AgentConstants.DATABASE_OBJECT_MAPPER[database]={}


    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while killing all scheduled task :: Database - {} : Error - {}'.format(database,e))
        traceback.print_exc()
    finally:
        return None

def deleteDBScheduleWithMID(DB_TYPE,mid,remove_cache_files=False):
    try:
        if DB_TYPE == AgentConstants.MYSQL_DB:
            removable_suffix_list = ["_basic","_onedaytask","_child_db","_insight"]
        elif DB_TYPE in [AgentConstants.POSTGRES_DB,AgentConstants.ORACLE_DB]:
            removable_suffix_list = ["_basic","_onedaytask"]
        else:
            return

        DB_CONSTANTS = AgentConstants.DB_CONSTANTS[DB_TYPE]

        for suffix in removable_suffix_list:
            task_name = mid+suffix
            tmp = AgentConstants.DATABASE_OBJECT_MAPPER[DB_TYPE].get(task_name)
            if tmp:
                AgentScheduler.deleteSchedule(tmp)
                AgentConstants.DATABASE_OBJECT_MAPPER[DB_TYPE].pop(task_name)
                AgentLogger.log(AgentLogger.DATABASE,"Database - {}, Removed scheduled task :: Task Name - {}".format(DB_CONSTANTS['DISPLAY_NAME'],task_name))
        if remove_cache_files:
            removable_files = os.listdir(DB_CONSTANTS['CONF_FOLDER'])
            for file in removable_files:
                if file.startswith(mid)==True:
                    os.remove(os.path.join(DB_CONSTANTS["CONF_FOLDER"],file))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"Database - {} :: Exception :: deleteDBScheduleWithMID :: task_name -> {} Error -> {}".format(DB_TYPE,mid, e))

def suspend_or_delete_database_monitor(DB_TYPE, config_update,is_delete_action=False):
    Action = 'Delete' if is_delete_action else 'Suspend'
    try:
        DB_CONSTANTS = AgentConstants.DB_CONSTANTS[DB_TYPE]
        AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: {} Action Received'.format(DB_CONSTANTS['DISPLAY_NAME'],Action))

        CONFIG = get_global_config(DB_TYPE)
        mon_id = config_update['mid']
        sections_list = CONFIG.sections()
        flag = False
        for section in sections_list:
            if section == DB_TYPE.upper():
                continue
            remove_section = False
            if CONFIG.has_option(section, "mid") and CONFIG.get(section, 'mid') == mon_id:
                remove_section = is_delete_action
                AgentLogger.log(AgentLogger.DATABASE,'{} Action received :: Database - {} : Instance - {} '.format(Action,DB_CONSTANTS['DISPLAY_NAME'],section))
                flag = True
                if CONFIG.get(section, 'enabled') == 'true':
                    # '3' for delete action and '5' for suspend action
                    CONFIG.set(section,'status','3' if is_delete_action else '5')
                    # if '-insight' in section:
                    #     removable_suffix_list=["_insight"]  
                    deleteDBScheduleWithMID(DB_TYPE,mon_id,True)

                    if DB_TYPE == AgentConstants.MYSQL_DB:
                        if CONFIG.has_option(section,"NDB_status") and CONFIG.get(section,"NDB_status") != "3":
                            remove_section = False
                        if os.path.exists(os.path.join(DB_CONSTANTS['CONF_FOLDER'], str(section)+'_conf.json')):
                            os.remove(os.path.join(DB_CONSTANTS['CONF_FOLDER'], str(section)+'_conf.json'))
                else:
                    CONFIG.set(DB_TYPE.upper(),'discover_instance','false')
                    if is_delete_action:
                        AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Delete Action received for free monitor, hence removing instance and disabling auto-dicover.'.format(DB_CONSTANTS['DISPLAY_NAME']))
                    else:
                        AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Suspend Action received for free monitor, hence skipping'.format(DB_CONSTANTS['DISPLAY_NAME']))
            elif DB_TYPE == AgentConstants.MYSQL_DB and CONFIG.has_option(section,"mysqlNDBmonkey") and CONFIG.get(section,"mysqlNDBmonkey") == mon_id:
                remove_section = is_delete_action
                NDBCluster.deleteScheduleWithMID(mon_id)
                CONFIG.set(section,"NDB_status","3")
                if CONFIG.has_option(section,"status") and CONFIG.get(section,"status") != "3":
                    remove_section = False
                
            if is_delete_action and remove_section:
                CONFIG.remove_section(section)
                AgentLogger.log(AgentLogger.DATABASE,'Removed Section :: Database - {} : Instance - {} '.format(DB_TYPE,section))


        if flag:
            persist_config_parser(DB_CONSTANTS['CONF_FILE'],CONFIG)
            copy_to_global_config(DB_TYPE,CONFIG)

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE, "Exception while handling {} action :: Database - {} : Received Action - {} : Error - {}". format(Action,DB_TYPE, config_update, e))
        traceback.print_exc()

# suspend database monitor action [consolidated request]
# called from DMSHandler
def suspend_database_monitor(DB_TYPE, config_update):
    try:
        suspend_or_delete_database_monitor(DB_TYPE,config_update,is_delete_action=False)
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE, "Exception :: Database - {} :: suspend_database_monitor :: action - {} :: Error - {}". format(DB_TYPE, config_update, e))

# delete database monitor action [consolidated request]
# called from DMSHandler
def delete_database_monitoring(DB_TYPE, config_update):
    try:
        suspend_or_delete_database_monitor(DB_TYPE,config_update,is_delete_action=True)
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE, "Exception :: Database - {} :: delete_database_monitoring :: action - {} :: Error - {}". format(DB_TYPE, config_update, e))

# activate database monitor action [consolidated request]
# called from DMSHandler
def activate_database_monitor(DB_TYPE, config_update):
    flag = False
    try:
        DB_CONSTANTS = AgentConstants.DB_CONSTANTS[DB_TYPE]
        AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Activate Action Received :: action - {}'.format(DB_CONSTANTS['DISPLAY_NAME'],config_update))
        mon_id = config_update['mid']
        CONFIG = get_global_config(DB_TYPE)
        section_list = CONFIG.sections()
        for section in section_list:
            if section != DB_TYPE.upper() and CONFIG.has_option(section,'mid') and CONFIG.get(section, 'mid') == mon_id:
                AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Activate Action received :: Instance - {} '.format(DB_TYPE,section))
                if CONFIG.has_option(section, 'enabled'):
                    if CONFIG.get(section, 'enabled') == 'true':
                        CONFIG.set(section,'status','0')
                        flag = True
                        AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Status changed for section - {}'.format(DB_TYPE,section))
                    else:
                        AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Activate Action received for free monitor, hence skipping')
                else:
                    AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: enabled option not present for section - {}'.format(DB_TYPE,section))

        if flag:
            persist_config_parser(DB_CONSTANTS['CONF_FILE'],CONFIG)
            start_database_monitoring(DB_TYPE)

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE, "Exception while activating database monitor :: Database - {} : Task - {} : Error - {}". format(DB_TYPE, config_update, e))
        traceback.print_exc()

''' CAN REMOVE [ NO USE ]
# update configuration from server [suspend, delete, activate]
# called from AppUtil.update_app_config_data with the apps config update obtained from configuration update servlet
def update_app_config_data(database, config_update):
    try:
        if database == "MYSQLDB":
            is_persist = False
            if "mid" in config_update:
                mon_id = config_update['mid']
                mysql_config = get_config_parser(AgentConstants.MYSQL_CONF_FILE)
                for section in mysql_config:
                    if section not in ['DEFAULT', 'MYSQL'] and mysql_config.get(section, 'mid') == mon_id:
                        if "status" in config_update:
                            mysql_config.set(section, 'status', config_update['status'])
                            is_persist = True
                        if 'child_discover' in config_update and config_update['child_discover'] == 'true':
                            if 'child_keys' in config_update and not config_update['child_keys']:
                                AgentConstants.DATABASE_CONFIG_MAPPER['mysql'][mon_id] = {}
                                AgentConstants.DATABASE_CONFIG_MAPPER['mysql'][mon_id] = config_update['child_keys']
            if is_persist:
                persist_config_parser(AgentConstants.MYSQL_CONF_FILE,mysql_config)

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE, "Exception while updating configuration :: Database - {} :: Config - {} :: Error - {}". format(database, config_update, e)+'\n')
        traceback.print_exc()
'''


# def add_configurations(input_file, conf_file):
#     try:
#         bool_FileLoaded, mysql_instance = AgentUtil.loadDataFromFile(input_file)
#         config = get_config_parser(conf_file)
#         is_modified = False
#         if mysql_instance:
#             for instance in mysql_instance:
#                 instance_name = instance['host'] + "-" + instance['port']
#                 config.add_section(instance_name)
#                 if all(each in instance for each in ['host', 'port', 'user', 'password']):
#                     config.set(instance_name, 'host', instance['host'])
#                     config.set(instance_name, 'port', instance['port'])
#                     config.set(instance_name, 'user', instance['user'])
#                     config.set(instance_name, 'password', instance['password'])
#                     config.set(instance_name, 'mid', '0')
#                     config.set(instance_name, 'enabled', 'false')
#                     is_modified = True
#                 else:
#                     AgentLogger.log(AgentLogger.DATABASE, "========================== Database Input Param is not given Properly for instance ========================== :: {}".format(instance))
#                     config.remove_section(instance['instance_name'])
#                     continue
#                 for each in ['file_io', 'session', 'memory', 'top_query', 'slow_query', 'events', 'error_statement']:
#                     if each in instance:
#                         config.set(instance_name, each, instance[each])
#             if is_modified:
#                 persist_config_parser(conf_file,config)
#         else:
#             AgentLogger.log(AgentLogger.DATABASE,'input file instnace not loaded :: {} '.format(input_file))
#     except Exception as e:
#         AgentLogger.log(AgentLogger.DATABASE,'Exception while checking Database input config file presence check :: {} : {}'.format(input_file,e))
#         traceback.print_exc()

def check_input_data_file(file_path):
    bool_status = False
    data_instance = None
    try:
        if os.path.exists(file_path):
            bool_status, data_instance = AgentUtil.loadRawDataFromFile(file_path)
            bool_status = True
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while checking user input file File - {} :: Error - {}'.format(file_path,e))
        traceback.print_exc()
    finally:
        return bool_status, data_instance

def read_data(path,filename):
    try:
        rdata=None
        config_file = os.path.join(path,filename)
        if os.path.exists(config_file):
            file=open(config_file,'r')
            rdata=file.read()
            file.close()
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while reading file :: {} : {}'.format(os.path.join(path,filename),e))
        traceback.print_exc()
    return rdata

def write_data(data,path,filename):
    try:
        file=open(os.path.join(path,filename),mode='w+')
        file.write(json.dumps(data))
        file.close()
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while writing file :: {} : {}'.format(os.path.join(path,filename),e))
        traceback.print_exc()

def is_discovery_enabled(application, config):
    try:
        discovery_enabled = True
        if config.has_option(application, 'discover_instance'):
            if config.get(application, 'discover_instance') == 'false':
                discovery_enabled = False
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while checking auto discover Status :: Database - {} :: Error - {}'.format(application,e))
        traceback.print_exc()
    finally:
        return discovery_enabled

def persist_config_parser(conf_file,config):
    try:
        with open(conf_file, 'w') as configfile:
            config.write(configfile)
        configfile.close()
        AgentLogger.log(AgentLogger.DATABASE,'Database Info persisted successfully :: {}'.format(conf_file))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception in persisting config parser :: {}'.format(conf_file,e))
        traceback.print_exc()
    finally:
        return config

def discover_db_from_process(application,command,version):
    discover_op_list = []
    x_proctocol_finder = {}
    try:
        output = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.read().decode("utf-8").splitlines()
        for each in output:
            discover_op_dict = {}
            each = " ".join(each.split())
            each = each.split(" ")
            if ':::' in each[3]:
                port = each[3].split(":::")[1]
                host = 'localhost'
            else:
                host,port = each[3].split(":")
            host = AgentConstants.HOST_NAME
            #host = "localhost"
            pid = each[6].split("/")[0]
            if AgentConstants.PSUTIL_OBJECT:
                proc = AgentConstants.PSUTIL_OBJECT.Process(int(pid))
                uname = proc.username()
                pname = proc.name()
            else:
                proc = subprocess.Popen("ps -eo pid,uname,comm | grep -v grep | grep -i {}".format(pid), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.read().decode("utf-8").splitlines()
                uname = " ".join(proc[0].split()).split(" ")[1]
                pname = " ".join(proc[0].split()).split(" ")[2]
            discover_op_dict['host'] = host
            discover_op_dict['port'] = port
            discover_op_dict['user'] = uname
            discover_op_dict['pname'] = pname
            discover_op_dict[application] = 'true'
            discover_op_dict['Version'] = version
            if str(int(int(port)/10)) not in x_proctocol_finder:
                x_proctocol_finder[port] = discover_op_dict
            else:
                AgentLogger.log(AgentLogger.DATABASE,'Port is 10 * of another port running, hence considered as xprotocol port and skiping instance :: {}'.format(port))
            if str(int(int(port)*10)) in x_proctocol_finder:
                x_proctocol_finder.pop(str(int(int(port)*10)))
                AgentLogger.log(AgentLogger.DATABASE,'Port is 10 * of another port running, hence considered as xprotocol port and skiping instance :: {}'.format(str(int(int(port)*10))))
        for port in x_proctocol_finder:
            discover_op_list.append(x_proctocol_finder[port])
        AgentLogger.log(AgentLogger.DATABASE,'Successfully discovered instance from process Database - {} :: Process - {}'.format(application,discover_op_list))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while discovering process :: Database - {} :: Error - {}'.format(application,e))
        traceback.print_exc()
    finally:
        return discover_op_list

def save_database_data(result_data, dir_prop, file_name_key=None):
    status = True
    file_name = None
    try:
        if type(result_data) is dict:
            result_data['MSPCUSTOMERID'] = AgentConstants.CUSTOMER_ID
            result_data['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        file_name = FileUtil.getUniqueDatabaseFileName(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'), file_name_key)
        if file_name:
            file_path = os.path.join(dir_prop['data_path'], file_name)
            file_obj = AgentUtil.FileObject()
            file_obj.set_fileName(file_name)
            file_obj.set_filePath(file_path)
            file_obj.set_data(result_data)
            file_obj.set_dataType('json' if type(result_data) is dict else "xml")
            file_obj.set_mode('wb')
            file_obj.set_dataEncoding('UTF-16LE')
            file_obj.set_loggerName(AgentLogger.DATABASE)
            file_obj.set_logging(False)
            status, file_path = FileUtil.saveData(file_obj)
    except Exception as e:
        AgentLogger.log([AgentLogger.DATABASE,AgentLogger.STDERR], '*************************** Exception while saving collected data : '+'*************************** '+ repr(e) + '\n')
        traceback.print_exc()
        status = False
    return status, file_name

def post_child_data_buffers(body_list_dict):
    try:
        for each_body in body_list_dict:
            AgentLogger.debug(AgentLogger.DATABASE,'[DEBUG] database child discovery data :: {}'.format(each_body))
            discovery_util.post_discovery_result(each_body,AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['013'])
    except Exception as e:
        AgentLogger.log([AgentLogger.DATABASE,AgentLogger.STDERR], '*************************** Exception while posting child database buffer : '+'*************************** '+ repr(e) + '\n')
        traceback.print_exc()

def register_database_child(result_dict,key_name='database_name'):
    size_of_data = 0
    page_number = 0
    total_pages = 0
    list_divided = []
    single_body = {}
    single_body['Data'] = []
    try:
        database_list   = result_dict['list']
        # if DB_TYPE == AgentConstants.MYSQL_DB:
        #     child_type      =   'MYSQL_DATABASE'
        #     monitor_type    =   'MYSQLDB'
        
        # elif DB_TYPE == AgentConstants.POSTGRES_DB:
        #     child_type      =   'POSTGRESQL_DATABASE'
        #     monitor_type    =   'POSTGRESQL'
        # elif DB_TYPE == AgentConstants.ORACLE_DB:
        #     child_type      =   'ORACLE_DATABASE'
        #     monitor_type    =   'ORACLE_SQL'

        for database in database_list:
            if size_of_data > AppConstants.APP_DISCOVERY_DATA_SIZE and single_body:
                page_number += 1
                total_pages += 1
                single_body['pagenumber'] = page_number
                list_divided.append(single_body)
                single_body = {}
                single_body['Data'] = []
                size_of_data = 0
            size_of_data += (len(database)+13)
            single_body['Data'].append({key_name:str(database)})

        if len(single_body['Data']) > 0:
            page_number += 1
            total_pages += 1
            single_body['pagenumber'] = page_number
            list_divided.append(single_body)

        for each_body in list_divided:
            each_body['totalpages'] = total_pages
            each_body['request'] = {}
            each_body['request']['AGENT_REQUEST_ID'] = '-1'
            each_body['request']['CHILD_TYPE'] = result_dict['child_type']
            each_body['request']['MONITOR_TYPE'] = result_dict['monitor_type']
            each_body['request']['MONITOR_ID'] = result_dict['mid']
            
    except Exception as e:
        AgentLogger.log([AgentLogger.DATABASE,AgentLogger.STDERR], 'Exception while registering database child :: result_dict - {} :: Error - {}'.format(result_dict,e))
        traceback.print_exc()
    finally:
        return list_divided

def upload_cluster_config(db,cluster_config_data):
    try:
        AgentLogger.log(AgentLogger.STDOUT, 'uploading cluster config =======> {0}'.format(json.dumps(cluster_config_data)))
        discovery_util.post_discovery_result(cluster_config_data,AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['014'],'mysql')
    except Exception as e:
        AgentLogger.log([AgentLogger.DATABASE, AgentLogger.STDERR], ' *************************** Exception while uploading server inventory  *************************** ' + repr(e))
        traceback.print_exc()

def set_files_in_zip_to_upload():
    try:
        AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['012']['files_in_zip'] = int(AgentUtil.UPLOAD_CONFIG.get('012', 'files_in_zip')) if AgentUtil.UPLOAD_CONFIG.has_option('012', 'files_in_zip') else 5
    except Exception as e:
        AgentLogger.log([AgentLogger.DATABASE, AgentLogger.STDERR], ' *************************** Exception while updating files to zip for database data upload  *************************** ' + repr(e))
        traceback.print_exc()

def persist_database_data(db_name,result_dict,collection_type,mid=None):
    try:
        data_files_path_list = []
        if collection_type == "6":
            database_data_per_file = None
            old_flow_result_data = {}
            set_files_in_zip_to_upload()
            old_flow_result_data['Databases'] = {}
            old_flow_result_data['mid'] = mid
            file_size_bytes = int(MYSQL_CONFIG.get('MYSQL', 'file_size_bytes')) if MYSQL_CONFIG.has_option('MYSQL', 'file_size_bytes') else 153600
            for db_data_dicts in AgentUtil.dict_chunk_with_file_size(result_dict, file_size_bytes):
                old_flow_result_data['Databases'] = db_data_dicts
                status, file_name = save_database_data(old_flow_result_data,AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['012'],"MYSQLDB")
                if status:
                    AgentLogger.log(AgentLogger.DATABASE, "Child Database monitoring Data Collected [old flow] | Database Name : {} | File Name : {} | DB Data in File : {}".format(db_name,file_name,len(db_data_dicts)))
                else:
                    AgentLogger.log(AgentLogger.DATABASE, "Failed to store child db data [old flow] :: {}-{}".format(db_name,mid))
        elif collection_type in ['0']:
            status, file_name = save_database_data(result_dict,AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['012'],"MYSQLDB")
            if status:
                AgentLogger.log(AgentLogger.DATABASE, "Database performance monitoring Data Collected | Database Name : {} | Persist Status : {} | File Path : {}".format(db_name,status,file_name))
            else:
                AgentLogger.log(AgentLogger.DATABASE, "Failed to store mysql performance data :: {}-{}".format(db_name,mid))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception in persisting database data :: {} : {}'.format(db_name,e))
        traceback.print_exc()


# initialization of database monitor -- reusable functions
#-----------------------------------------------------------------------------------------------------------

def get_global_config(DB_TYPE):
    try:
        if DB_TYPE == AgentConstants.MYSQL_DB:
            return MYSQL_CONFIG
        if DB_TYPE == AgentConstants.POSTGRES_DB:
            return POSTGRES_CONFIG
        if DB_TYPE == AgentConstants.ORACLE_DB:
            return ORACLE_CONFIG
        
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception in get_global_config :: Database - {} : Error - {}'.format(DB_TYPE,e))
        traceback.print_exc()

def copy_to_global_config(DB_TYPE,CONFIG):
    try:
        global MYSQL_CONFIG,POSTGRES_CONFIG,ORACLE_CONFIG
        if DB_TYPE == AgentConstants.MYSQL_DB:
            MYSQL_CONFIG = CONFIG
        elif DB_TYPE == AgentConstants.POSTGRES_DB:
            POSTGRES_CONFIG = CONFIG
        elif DB_TYPE == AgentConstants.ORACLE_DB:
            ORACLE_CONFIG = CONFIG
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception in persist_to_global_config :: Database - {} : Error - {}'.format(DB_TYPE,e))
        traceback.print_exc()

# encrypt the password for the instance that is enabled and registered for data collection
def verify_password_encryption(DB_TYPE,CONFIG):
    try:
        for section in CONFIG:
            if section in ['DEFAULT', DB_TYPE.upper()]:
                continue
            if not CONFIG.has_option(section, 'encrypted.password'):
                if CONFIG.get(section, 'user') != '0' and CONFIG.has_option(section, 'password') and CONFIG.get(section, 'password') != '0':
                    if CONFIG.has_option(section, 'password'):
                        encrpted_value = AgentCrypt.encrypt_with_ss_key(CONFIG.get(section, 'password'))
                        CONFIG.set(section,'encrypted.password',str(encrpted_value).replace("%","%%"))
                        CONFIG.remove_option(section, 'password')
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while verifying password encryption :: Database - {} :: Error - {}'.format(DB_TYPE,e))
        traceback.print_exc()

# creates a instance for auto discovered instance, and register as free monitor in server
# if registered successfully, mid stored else instance is removed
def create_instance_section_from_process(instance_name, dict_info, DB_TYPE, DB_CONSTANTS, CONFIG):
    try:
        CONFIG.add_section(instance_name)
        CONFIG.set(instance_name,'host',dict_info['host'])
        CONFIG.set(instance_name,'port',dict_info['port'])
        CONFIG.set(instance_name,'user','0')
        CONFIG.set(instance_name,'password','0')
        CONFIG.set(instance_name,'mid','0')
        CONFIG.set(instance_name,'enabled','false')

        register_status,app_key = register_database_monitor(dict_info,instance_name,DB_CONSTANTS['APP_KEY'],CONFIG,DB_CONSTANTS['CONF_FILE'])

        if register_status and not app_key in ['0', None]:
            AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Instance - {} registered successfully :: App key - {}'.format(DB_TYPE,instance_name,app_key))
            CONFIG.set(instance_name,'mid',app_key)
        else:
            AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Instance - {} not registered from process, hence removing instance :: Process - {}'.format(DB_TYPE,instance_name,dict_info))
            CONFIG.set(instance_name,'mid','1234')
            CONFIG.remove_section(instance_name)
        persist_config_parser(DB_CONSTANTS['CONF_FILE'], CONFIG)

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while creating instance for {} process :: Instance -  {} :: Error - {}'.format(DB_TYPE,instance_name,e))
        traceback.print_exc()

# checks the input host is for local machine or remote
# possible ip and host name is checked
# [IMPORTANT] need to add more ip in case of multiple interface in the server machine   # bharath IP_LIST added [check testing after reverse merge]
def check_local_instance_exists(host, port,CONFIG,DB_TYPE):
    is_exist = False
    instance_name = None
    try:
        for each in ['localhost', '127.0.0.1', '0.0.0.0', AgentConstants.IP_ADDRESS, AgentConstants.HOST_NAME]:
            if CONFIG.has_section(each+"-"+port):
                is_exist = True
                instance_name = each+"-"+port
        for each in AgentConstants.IP_LIST: # bharath change
            if CONFIG.has_section(each+"-"+port):
                is_exist = True
                instance_name = each+"-"+port
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'{} monitor not registered :: {}'.format(DB_TYPE,e))
    finally:
        return is_exist, instance_name

# database version taken separately with [mysql -V|psql -V] command
# pid found using netstat and other params collected from psutil with pid
# x protocol mysql port is ignored, checking with flow [a port 10 multiple of another port is considers x protocol port]
def discover_sql_db(DB_TYPE,DB_CONSTANTS):
    discover_op_list,output = [],None
    try:
        version = None
        output = subprocess.Popen(DB_CONSTANTS['VERSION_COMMAND'], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.read().decode("utf-8").split()
        if output:
            if DB_TYPE == AgentConstants.MYSQL_DB or DB_TYPE == AgentConstants.ORACLE_DB:
                pattern = re.compile(r'\d+\.\d+\.\d')
                for each in output:
                    if pattern.search(each):
                        version = each
                        break
            elif DB_TYPE == AgentConstants.POSTGRES_DB:
                if len(output)>=3:
                    version = output[2]
        elif DB_TYPE == AgentConstants.ORACLE_DB and version == None:
            # if os.path.exists("/etc/oraInst.loc"):
            tmp = subprocess.Popen("ls -l /proc/$(ps -ef|grep pmon |grep -v grep| awk '{print $2}')/cwd | awk  '{for(i=1;i<NF;i++){ if(\"->\"==$i){print $(i+1)}}}'", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.read().decode("utf-8")
            tmp = re.findall("\/\d+",tmp)
            version = tmp[0].replace('/','') if len(tmp)>0 else None
        
        AgentLogger.log(AgentLogger.DATABASE,'[info] dummy discovery - database - {} :: version - {} \noutput - {}'.format(DB_TYPE,version,output))
        discover_op_list = discover_db_from_process(DB_TYPE,DB_CONSTANTS['PID_COMMAND'],version)
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception in discovering {} instance for dummy addition :: {}'.format(DB_TYPE,e))
        traceback.print_exc()
    finally:
        return discover_op_list

def db_ssl_config(DB_TYPE=None):
    db_type,terminal_output,restart = None,None,False
    try:
        db_ssl_config_file = os.path.join(AgentConstants.AGENT_CONF_DIR,AgentConstants.db_ssl_config)
        bool_status, sql_instance = check_input_data_file(db_ssl_config_file)
        AgentLogger.log(AgentLogger.DATABASE,'db_ssl_config :: updating ssl configuration :: DB_TYPE - {}'.format(DB_TYPE))
        if bool_status and sql_instance:
            AgentLogger.log(AgentLogger.DATABASE,'db_ssl_config :: updating ssl configuration :: sql_instance - {}'.format(sql_instance))
            sql_instance = json.loads(sql_instance)
            for single_instance in sql_instance:
                terminal_dict = OrderedDict({
                    'Instance Name' :   single_instance['instance'],
                    'Host'          :   single_instance['host'],
                    'Port'          :   single_instance['port']
                })
                db_type = str(single_instance.get('database')).lower()
                if db_type and db_type in [AgentConstants.MYSQL_DB,AgentConstants.POSTGRES_DB] and (DB_TYPE == None or DB_TYPE == db_type):
                    DB_CONSTANTS = AgentConstants.DB_CONSTANTS[db_type]
                    CONFIG = get_global_config(db_type)
                    instance_name = single_instance['instance']
                    if CONFIG.has_section(instance_name):
                        AgentLogger.log(AgentLogger.DATABASE,'db_ssl_config :: instance name - {}'.format(instance_name))
                        action = single_instance.get("action")
                        if action == "update":
                            dict_params = single_instance.copy()
                            dict_params['user'] = CONFIG.get(instance_name,'user')
                            bool_status,err_msg = False,"Failed to connect"
                            if CONFIG.has_option(instance_name,'encrypted.password'):
                                dict_params['password'] = str(AgentCrypt.decrypt_with_ss_key(CONFIG.get(instance_name,'encrypted.password')))
                                bool_status, err_msg = check_new_pwd_connc(dict_params,db_type)
                            if bool_status:
                                CONFIG.set(instance_name,'ssl','true')
                                CONFIG.set(instance_name,'ssl-ca',dict_params["ssl-ca"])
                                CONFIG.set(instance_name,'ssl-cert',dict_params['ssl-cert'])
                                CONFIG.set(instance_name,'ssl-key',dict_params['ssl-key'])
                                if db_type == AgentConstants.POSTGRES_DB:
                                    CONFIG.set(instance_name,'ssl-mode','prefer')
                                result = '      Updated {} SSL Configuration'.format(DB_CONSTANTS['DISPLAY_NAME'])
                                restart = True
                            else:
                                terminal_dict['Error'] = str(err_msg)
                                result = '      {} SSL Configuration Update Failed'.format(DB_CONSTANTS['DISPLAY_NAME'])
                        elif action == "delete":
                            if CONFIG.has_option(instance_name,"ssl") and CONFIG.get(instance_name,'ssl') == "true":
                                CONFIG.set(instance_name,'ssl','false')
                                if CONFIG.has_option(instance_name,'ssl-ca'):
                                    CONFIG.remove_option(instance_name,'ssl-ca')
                                if CONFIG.has_option(instance_name,'ssl-cert'):
                                    CONFIG.remove_option(instance_name,'ssl-cert')
                                if CONFIG.has_option(instance_name,'ssl-key'):
                                    CONFIG.remove_option(instance_name,'ssl-key')
                                if db_type == AgentConstants.POSTGRES_DB and CONFIG.has_option(instance_name,'ssl-mode'):
                                    CONFIG.remove_option(instance_name,'ssl-mode')
                                result = '      Removed {} SSL Configuration'.format(DB_CONSTANTS['DISPLAY_NAME'])
                                restart = True
                            else:
                                result = '      {} SSL Configuration already removed'.format(DB_CONSTANTS['DISPLAY_NAME'])
                    else:
                        result = '      {} Instance not found'.format(DB_CONSTANTS['DISPLAY_NAME'])
                    if result:
                        terminal_output = generate_terminal_output(db_type,DB_CONSTANTS['DISPLAY_NAME'],terminal_dict,single_instance,None,result)
                    persist_config_parser(DB_CONSTANTS['CONF_FILE'], CONFIG)
                    if os.path.exists(db_ssl_config_file):
                        os.remove(db_ssl_config_file)
                    break
            if DB_TYPE == None and os.path.exists(db_ssl_config_file):
                os.remove(db_ssl_config_file)

            if terminal_output:
                AgentLogger.log(AgentLogger.DATABASE,terminal_output)
                AgentUtil.writeRawDataToFile(AgentConstants.db_ssl_terminal_response_file, str(terminal_output))
            
            if restart:
                if CONFIG.get(instance_name,'enabled') == "true":
                    stop_all_instance(db_type,CONFIG.get(instance_name,'mid'))
                if db_type == AgentConstants.MYSQL_DB:
                    mysql_monitoring.initialize()
                elif db_type == AgentConstants.POSTGRES_DB:
                    postgres_monitoring.initialize()
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while updating/removing ssl configuration :: {}'.format(e))
        traceback.print_exc()

def remove_sql_instance(DB_TYPE,from_terminal=False):
    try:
        # step 3

        terminal_output,result,terminal_dict,restart   = None,None,{},False
        DB_CONSTANTS    = AgentConstants.DB_CONSTANTS[DB_TYPE]
        CONFIG          = get_config_parser(DB_CONSTANTS['CONF_FILE'])

        bool_status, sql_instance = check_input_data_file(DB_CONSTANTS['REMOVE_FILE'])
        if sql_instance:
            AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: sql_remove file found, adding input configurations to {}'.format(DB_TYPE,DB_CONSTANTS['REMOVE_FILE']))
            sql_instance = json.loads(sql_instance)
            for single_instance in sql_instance:
                terminal_dict = OrderedDict({
                    'Instance Name' :   single_instance['instance'],
                    'Host'          :   single_instance['host'],
                    'Port'          :   single_instance['port']
                })
                if CONFIG.has_section(single_instance['instance']):
                    if CONFIG.get(single_instance['instance'],'enabled') == "true":
                        stop_all_instance(DB_TYPE,CONFIG.get(single_instance['instance'],'mid'))
                        CONFIG.set(single_instance['instance'],'status','3')
                        result = '      Successfully removed {} Monitoring'.format(DB_CONSTANTS['DISPLAY_NAME'])
                        restart = True
                    else:
                        result = '      {} Instance already removed'.format(DB_CONSTANTS['DISPLAY_NAME'])
                else:
                    result = '      {} Instance not found'.format(DB_CONSTANTS['DISPLAY_NAME'])
                if result and from_terminal:
                    terminal_output = generate_terminal_output(DB_TYPE,DB_CONSTANTS['DISPLAY_NAME'],terminal_dict,single_instance,None,result)
            persist_config_parser(DB_CONSTANTS['CONF_FILE'], CONFIG)
            os.remove(DB_CONSTANTS['REMOVE_FILE'])

            if from_terminal and terminal_output:
                AgentUtil.writeRawDataToFile(DB_CONSTANTS['TERMINAL_RESPONSE_FILE'], str(terminal_output))
            
            if restart:
                if DB_TYPE == AgentConstants.MYSQL_DB:
                    mysql_monitoring.initialize()
                elif DB_TYPE == AgentConstants.POSTGRES_DB:
                    postgres_monitoring.initialize()
                elif DB_TYPE == AgentConstants.ORACLE_DB:
                    oracledb_monitoring.initialize()
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,"Exception while removing sql instance :: Database - {} :: Error - {}".format(DB_TYPE,e))
        traceback.print_exc()

# possible actions [update a new section of remote mysql / convert free monitor to basic monitor]
# here password is saved as password first, upcoming flow will encrypt password
# updates the given input in config, and gets the instance configuration for registration
def update_database_input_data(instance_name, sql_instance, CONFIG, DB_TYPE):
    try:
        # if 'LD_LIBRARY_PATH' in sql_instance:
        #     restart = oracle_sql_monitoring.update_oracle_library_path(False,sql_instance["LD_LIBRARY_PATH"])
        #     if restart:
        #         sql_instance_creds = sql_instance.copy()
        #         sql_instance_creds.pop("LD_LIBRARY_PATH")
        #         AgentUtil.writeRawDataToFile(AgentConstants.ORACLE_CRED_TEMP_FILE,json.dumps([sql_instance_creds]))
        #         AgentLogger.log(AgentLogger.DATABASE,"Restarting the Linux agent. Received user input for LD_LIBRARY_PATH for oracle database.")
        #         AgentUtil.RestartAgent()     

        credentials = ['host','port','user','password']
        properties = {'enabled':'false','discover_database':'true','status':'0'}
        for attribute in credentials:
            CONFIG.set(instance_name,attribute,str(sql_instance[attribute]).replace('%','%%'))
        
        if DB_TYPE == AgentConstants.POSTGRES_DB:
            CONFIG.set(instance_name,'default_database','postgres')
            if not CONFIG.has_option(instance_name,'ssl-mode'):
                CONFIG.set(instance_name,'ssl-mode','prefer')
            for each in sql_instance:
                if each in ['ssl','ssl-ca','ssl-cert','ssl-key']:
                    CONFIG.set(instance_name,each,sql_instance[each])
        elif DB_TYPE == AgentConstants.ORACLE_DB:
            CONFIG.set(instance_name,'service_name',sql_instance['service_name'])
            # CONFIG.set(instance_name,'oracle_home',sql_instance['oracle_home'])
            properties['CDB_ROOT'] = "CDB$ROOT"

        if DB_TYPE in [AgentConstants.ORACLE_DB,AgentConstants.POSTGRES_DB]:
            properties.update({'perf_poll_interval':'300','conf_poll_interval':'86400','query_selection_config':'{}','db_per_thread':'5','db_per_zip':'50',"discover_tablespace":"true"})

        for key,value in properties.items():
            CONFIG.set(instance_name,key,str(value))
        
        if DB_TYPE == AgentConstants.MYSQL_DB:
            for each in sql_instance:
                if each in ['statement_analysis', 'event_analysis', 'file_io', 'top_query', 'slow_query', 'basic_monitoring', 'insight_monitoring', 'poll_interval','ssl','ssl-ca','ssl-cert','ssl-key']:
                    CONFIG.set(instance_name,each,sql_instance[each])

        # AgentLogger.log(AgentLogger.DATABASE,'db - {} :: instance_name - {} :: sql_instance - {}'.format(DB_TYPE,instance_name,sql_instance))

        get_registration_data(sql_instance,instance_name,CONFIG,DB_TYPE)

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while updating {} input data Instance - {} :: Error - {}'.format(DB_TYPE,instance_name,e))
        traceback.print_exc()

def execute_query(cursor,query):
    try:
        cursor.execute(query)
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while executing query - {} :: Error - {}'.format(query,e))

# checks the mysql input, by creating mysql connection and collects instance uuid/version using query
# collects master and slave status, instance type [master, slave, standalone]
# node which does not have show master status output [binlog file] is considered as slave
# node which does not have both master status and slave status is considered as standalone
# other than this situation if the node has master status then it is considered as master
def check_sql_input_config(dict_info,DB_TYPE):
    output_dict     = {}
    bool_success    = False
    err_msg         = None
    connection      = None
    try:
        status, connection = getDBConnection(dict_info,DB_TYPE)
        if status:
            cursor  =   connection.cursor()
            execute_query(cursor,AgentConstants.DB_CONSTANTS[DB_TYPE]['DISCOVERY_PARAM_QUERY'])

            if DB_TYPE == AgentConstants.MYSQL_DB:
                is_mariadb   = False
                for each in cursor:
                    if each[0]   == "server_uuid":
                        output_dict["uuid"]          = each[1]
                    elif each[0] == "version":
                        output_dict["Version"]       = each[1] #mysql_version
                
                AgentLogger.log(AgentLogger.DATABASE,str(output_dict.get("Version")))
                if (output_dict.get("Version") or "").lower().find("mariadb") !=-1:
                    # output_dict['mariadb'] = 'true'
                    is_mariadb             =  True
                    execute_query(cursor,AgentConstants.MARIADB_DISCOVERY_PARAM_QUERY)
                    id = cursor.fetchone()
                    AgentLogger.log(AgentLogger.DATABASE,str(id))
                    output_dict['uuid'] = id[1] if len(id) > 0 else None
                
                # SHOW MASTER STATUS
                execute_query(cursor,AgentConstants.MYSQL_REPLICATION_MASTER_STATUS_QUERY)
                master_status = cursor.fetchall()
                if not master_status:
                    execute_query(cursor,AgentConstants.MYSQL_REPLICATION_BINARY_LOG_STATUS_QUERY)
                    master_status = cursor.fetchall()
                # SHOW SLAVE STATUS
                execute_query(cursor,AgentConstants.MYSQL_REPLICATION_SLAVE_STATUS_QUERY)
                slave_status = cursor.fetchone()
                if not slave_status:
                    execute_query(cursor,AgentConstants.MYSQL_REPLICATION_REPLICA_STATUS_QUERY)
                    slave_status = cursor.fetchone()


                if not master_status and not slave_status:
                    output_dict['instance_type'] = 'STANDALONE'
                elif master_status and not slave_status:
                    output_dict['instance_type'] = 'MASTER'
                elif master_status and slave_status:      # [master - master] / [secondary slave] setup suituations
                    output_dict['instance_type'] = 'MASTER'
                elif not master_status and slave_status:
                    output_dict['instance_type'] = 'SLAVE'
                    output_dict['master_uuid'] = str(slave_status[40])
                
                try:
                    if subprocess.Popen(AgentConstants.AMAZON_LINUX_CMD, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.read().decode('utf-8')=='TRUE':
                        output_dict['dbPlatform'] = "AMAZON_LINUX_MARIADB" if is_mariadb else "AMAZON_LINUX_MYSQL"
                        execute_query(cursor,"show global variables where variable_name in ('basedir','datadir','tmpdir','innodb_data_home_dir')")
                        dirs = cursor.fetchall()
                        for dir in dirs:
                            if str(dir[1]).lower().find('rds') != -1:
                                output_dict['dbPlatform']   = "AMAZON_RDS_MARIADB" if is_mariadb else "AMAZON_RDS_MYSQL"
                                break

                    if cursor.execute(AgentConstants.MYSQL_AURORA_VERSION_QUERY):
                        output_dict['dbPlatform']           = "AURORA_MARIADB" if is_mariadb else "AURORA_MYSQL"
                        output_dict['cloudDBVersion']       = str(cursor.fetchone()[1])
                except Exception as e:
                    AgentLogger.log(AgentLogger.DATABASE,'Exception while executing RDS AURORA MySQL identification query :: {}'.format(e))

            elif DB_TYPE == AgentConstants.POSTGRES_DB:
                result                              =   cursor.fetchall()
                output_dict['instance_type']        =   'primary' if result[0][0] else 'standby'
                output_dict['Version']              =   result[0][1]
                output_dict['system_identifier']    =   result[0][2]

                try:
                    if subprocess.Popen(AgentConstants.AMAZON_LINUX_CMD, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.read().decode('utf-8')=='TRUE':
                        output_dict['dbPlatform']       = "AMAZON_LINUX_POSTGRES"

                    if cursor.execute(AgentConstants.POSTGRES_AURORA_VERSION_QUERY):
                        output_dict['dbPlatform']       = "AURORA_POSTGRES"
                        output_dict['cloudDBVersion']    = str(cursor.fetchone()[0])
                except Exception as e:
                    AgentLogger.log(AgentLogger.DATABASE,'Exception while executing RDS AURORA Postgres identification query :: {}'.format(e))


            elif DB_TYPE == AgentConstants.ORACLE_DB:
                result                              =   cursor.fetchall()
                output_dict['database_role']        =   result[0][0]
                output_dict['Version']              =   result[0][1]
                output_dict['dbid']                 =   result[0][2]
                output_dict['instance_number']      =   result[0][3]
                output_dict['instance_name']        =   result[0][4]
                output_dict['database_type']        =   result[0][5]
                output_dict['CDB']                  =   result[0][6]

            if not output_dict.get('dbPlatform'):
                output_dict['dbPlatform'] = 'ON_PREMISE'
            cursor.close()
            connection.close()
            bool_success = True
        else:
            err_msg = connection
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while verifying {} input :: Error - {}'.format(DB_TYPE,e))
        err_msg = str(e)
        traceback.print_exc()
    finally:
        return bool_success, output_dict, err_msg

# given database instance input is verified with given input credentials
# if already registered as free monitor, mid is sent with registration as param,
# enabled=true is for two purpose [directly register as basic monitor / convert free to basic monitor]
def generate_terminal_output(DB_TYPE,DB_DISPLAY_NAME,terminal_dict,instance_name,status,status_description=''):
    try:
        div     = '---------------------------------------------------\n'
        # terminal_output = 'Machine Name - {}\n\n'.format(AgentConstants.HOST_NAME)+div
        terminal_output = ''+div
        # if status:
        #     terminal_output += '        [{}] {} Instance       \n{}'.format(status,DB_DISPLAY_NAME,div)
        # else:
        terminal_output += '           {} Instance       \n{}'.format(DB_DISPLAY_NAME,div)

        # ordered_list    =   list(terminal_dict.keys())
        # ordered_list.sort()
        for key,val in terminal_dict.items():
            terminal_output += '{} {}: {}\n'.format(key,' '*(20-len(key)),val)
        
        if status == 'SUCCESS':
            status_description =   '      Successfully added {} Monitor'.format(DB_DISPLAY_NAME)
        elif status == 'FAILURE':
            status_description =   '      Failed to add {} Monitor'.format(DB_DISPLAY_NAME)

        terminal_output += div + status_description + '\n' + div

        return terminal_output
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while generating terminal output for Database - {} :: Instance - {} :: Error - {}'.format(DB_TYPE,instance_name,e))

def get_registration_data(dict_info,instance_name,CONFIG,DB_TYPE,rediscover=False):
    try:
        global MYSQL_CONFIG
        DB_CONSTANTS            = AgentConstants.DB_CONSTANTS[DB_TYPE] 
        DB_DISPLAY_NAME         = DB_CONSTANTS['DISPLAY_NAME']
        dict_info_for_log_print = dict_info.copy()
        if dict_info and dict_info.get('password'):
            dict_info_for_log_print.pop('password')
        
        is_persisted  = False
        result_dict   = {}
        terminal_output = '============ No Output ============'
        # check whether the given input is valide [ connection established ]

        bool_success, output_dict, err_msg = check_sql_input_config(dict_info,DB_TYPE)
        AgentLogger.log(AgentLogger.DATABASE,'sql_config - {} :: Database - {} :: Instance - {}'.format(output_dict,DB_TYPE,instance_name))
        # if DB_TYPE == AgentConstants.ORACLE_DB:
        #     result_dict['oracle_sql']     = 'true'
        # else:
        #     result_dict[DB_TYPE]          = 'true'
        result_dict[DB_TYPE]          = 'true'

        terminal_dict = OrderedDict()
        terminal_dict.update({ 'Host' : dict_info['host'], 'Port' : dict_info['port'] })

        if bool_success:
            app_key         = None
            register_status = False

            result_dict['host']              = dict_info['host']
            result_dict['port']              = dict_info['port']
            result_dict['user']              = dict_info['user']
            result_dict['enabled']           = 'true'
            result_dict.update(output_dict)

            if DB_TYPE == AgentConstants.MYSQL_DB:
                if 'uuid' not in result_dict and output_dict.get('Version').lower().find('mariadb') != -1:
                    result_dict['uuid'] = 'MariaDB-' + dict_info.get('host') + '-' + str(dict_info.get('port'))
                
                if output_dict.get('mariadb'):
                    DB_DISPLAY_NAME = 'MariaDB'

                if output_dict.get('dbPlatform'):
                    result_dict['dbPlatform']       = output_dict['dbPlatform']
                else:
                    result_dict['dbPlatform']       = 'ON_PREMISE'
                
                if output_dict.get('cloudDBVersion'):
                    result_dict['cloudDBVersion']    = output_dict['cloudDBVersion']
                
                NDBCluster.AppRegistrationRequest(dict_info,MYSQL_CONFIG,instance_name,result_dict,rediscover)
            elif DB_TYPE == AgentConstants.ORACLE_DB and result_dict.pop('CDB') == 'NO' and CONFIG.has_section(instance_name):
                CONFIG.set(instance_name,"CDB_ROOT",str(result_dict.get("instance_name")).upper())

            if CONFIG.has_section(instance_name):
                CONFIG.set(instance_name,"Version",str(result_dict.get('Version')))

            # check whether the instance is local database server or remote instance [ server decides whether to show server related data on database summary page ]
            if not (result_dict['host'] in ['localhost', '127.0.0.1', '0.0.0.0', AgentConstants.IP_ADDRESS, AgentConstants.HOST_NAME] or result_dict['host'] in AgentConstants.IP_LIST):
                result_dict['isRemote']      = 'true'
            else:
                result_dict['isRemote']      = 'false'
                result_dict['host']          = AgentConstants.HOST_NAME

            if CONFIG.has_option(instance_name,'mid'):
                mid = CONFIG.get(instance_name,'mid')
                result_dict['appkey']        = mid
            else:
                mid                          = '0'

            # register database instance to server
            AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: result_dict - {}'.format(DB_TYPE,result_dict))

            register_status,app_key = register_database_monitor(result_dict,instance_name,DB_CONSTANTS['APP_KEY'],CONFIG,DB_CONSTANTS['CONF_FILE'])

            if rediscover:
                return register_status, app_key

            # monitor already registered as free monitor, now converted to basic monitor
            if register_status and not app_key in ['0', None] and mid not in ['0', None]:
                CONFIG.set(instance_name,'enabled','true')
                CONFIG.set(instance_name,'discover_database','true')
                CONFIG.set(instance_name,'status','0')
                is_persisted = True
                AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Instance - {} :: New Key - {} :: Old key - {} converted from free to basic monitor'.format(DB_TYPE,instance_name,app_key,mid))
                if DB_TYPE == AgentConstants.ORACLE_DB:
                    CONFIG.set(instance_name,'discover_tablespace','true')
            # remote instance, directly registered as basic instance [in which mid would be previously 0]
            elif register_status and not app_key in ['0', None] and mid in ['0', None]:
                AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Instance - {} :: App key - {} directly registered as basic monitor'.format(DB_TYPE,instance_name,app_key))
                CONFIG.set(instance_name,'mid',app_key)
                CONFIG.set(instance_name,'enabled','true')
                CONFIG.set(instance_name,'discover_database','true')
                CONFIG.set(instance_name,'status','0')
                is_persisted = True
                if DB_TYPE == AgentConstants.ORACLE_DB:
                    CONFIG.set(instance_name,'discover_tablespace','true')
            # registering as basic monitor failed [app key received from server is none]
            else:
                AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Instance - {} not registered from input, hence removing instance :: Input - {}'.format(DB_TYPE,instance_name,dict_info_for_log_print))
                # CONFIG.set(instance_name,'mid','1234')       # hardcoded non 0 number for development purpose [remove before release]
                CONFIG.set(instance_name,'enabled','true')
                CONFIG.remove_section(instance_name)

            if DB_TYPE == AgentConstants.MYSQL_DB:
                uuid_key_name = 'Server ID' if output_dict.get('mariadb') else 'UUID' 
                terminal_dict.update({
                    uuid_key_name       : output_dict.get("uuid"),
                    'Instance Type'     : output_dict.get("instance_type"),
                    'Version'           : output_dict["Version"]
                })
            elif DB_TYPE == AgentConstants.ORACLE_DB:
                terminal_dict.update({
                    'DBID'              : output_dict["dbid"],
                    'Instance Number'   : output_dict.get("instance_number"),
                    'Database Role'     : output_dict.get("database_role"),
                    'Version'           : output_dict["Version"]
                })
            elif DB_TYPE == AgentConstants.POSTGRES_DB:
                terminal_dict.update({
                    'System Identifier' : output_dict["system_identifier"],
                    'Instance Type'     : output_dict.get("instance_type"),
                    'Version'           : output_dict["Version"]
                })
            if is_persisted:
                terminal_output = generate_terminal_output(DB_TYPE,DB_DISPLAY_NAME,terminal_dict,instance_name,'SUCCESS')
            else:
                terminal_dict["Error"] = "Unable to create "+DB_DISPLAY_NAME+" Monitor"
                terminal_output = generate_terminal_output(DB_TYPE,DB_DISPLAY_NAME,terminal_dict,instance_name,'FAILURE')
        else:
            terminal_dict['Error'] = err_msg
            terminal_output = generate_terminal_output(DB_TYPE,DB_DISPLAY_NAME,terminal_dict,instance_name,'FAILURE')

            AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Instance - {} input not valid :: Input - {}'.format(DB_TYPE,instance_name,dict_info_for_log_print))
            CONFIG.remove_section(instance_name)
        
        AgentLogger.log(AgentLogger.DATABASE,'{}'.format(str(terminal_output)))
        AgentUtil.writeRawDataToFile(DB_CONSTANTS['TERMINAL_RESPONSE_FILE'], str(terminal_output))
        # if int(time.time() - (DB_CONSTANTS['ADD_INSTANCE_START_TIME'] or 0)) < 115:
        #     AgentLogger.log(AgentLogger.DATABASE,'{}'.format(str(terminal_output)))
        #     AgentUtil.writeRawDataToFile(DB_CONSTANTS['TERMINAL_RESPONSE_FILE'], str(terminal_output))
        # else:
        #     AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Instance - {} took more time to register hence skipping terminal responce'.format(DB_TYPE,instance_name))

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while registering instance in server :: Database - {} :: Instance - {} :: Error - {} :: traceback - {}'.format(DB_TYPE,instance_name,e,traceback.print_exc()))

def reregister_instance(instance_name, CONFIG, DB_TYPE):
    bool_success = False
    app_key = None
    try:
        sql_instance = {}
        sql_instance['host']               = CONFIG.get(instance_name,'host')
        sql_instance['port']               = CONFIG.get(instance_name,'port')
        sql_instance['user']               = CONFIG.get(instance_name,'user')
        sql_instance['password']           = str(AgentCrypt.decrypt_with_ss_key(CONFIG.get(instance_name,'encrypted.password')))
        
        if DB_TYPE in AgentConstants.POSTGRES_DB:
            sql_instance['default_database']   = CONFIG.get(instance_name,'default_database')
        if DB_TYPE == AgentConstants.ORACLE_DB:
            sql_instance['service_name']   = CONFIG.get(instance_name,'service_name')

        bool_success, app_key = get_registration_data(sql_instance,instance_name,CONFIG,DB_TYPE,True)

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while re-registering monitor :: Database - {} :: Error - {}'.format(DB_TYPE,e))
        traceback.print_exc()
    finally:
        return bool_success, app_key

# creates instance name from the input user given [host + port]
# identifies whether the given input is for database discovered in process [netstat -lntp] possible match [localhost, 127.0.0.1, 0.0.0.0, machine ip, machine hostname]
# if local database input with other possible host is given in input, past created instance name is changed with the given new input [ new host name + port ]
def get_instance_name(instance,CONFIG,DB_TYPE):
    old_instance_name = None
    new_instance_name = None
    try:
        instance['port'] = str(int(instance['port']))
        new_instance_name = instance['host']+"-"+instance['port']
        old_instance_name = AgentConstants.HOST_NAME+"-"+instance['port']
        if instance['host'] in ['localhost', '127.0.0.1', '0.0.0.0', AgentConstants.IP_ADDRESS, AgentConstants.HOST_NAME] or instance['host'] in AgentConstants.IP_LIST:
            AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Instance Registered from process {} :: New instance name {}'.format(DB_TYPE,old_instance_name, new_instance_name))
            if CONFIG.has_section(old_instance_name) and new_instance_name != old_instance_name:
                CONFIG.add_section(new_instance_name)
                CONFIG.set(new_instance_name,'host',instance['host'])
                CONFIG.set(new_instance_name,'port',instance['port'])
                CONFIG.set(new_instance_name,'user','0')
                CONFIG.set(new_instance_name,'password','0')
                CONFIG.set(new_instance_name,'mid',CONFIG.get(old_instance_name,'mid'))
                CONFIG.set(new_instance_name,'enabled','false')
                CONFIG.remove_section(old_instance_name)
                AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: removed instance name :: {}'.format(DB_TYPE,old_instance_name))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while verifying instance name with host name :: Database - {} :: {}'.format(DB_TYPE,e))
    finally:
        return old_instance_name, new_instance_name


# step 1   : Create folder and config file for specific database i.e mysql or postgres or oracle
# step 2   : Check for db input file (ex:mysql_input,postgres_input) present in conf folder [multiple instance supported]
#      2.1 : For each instance create or update the .cfg file and send ADS [converted to basic monitor]
#      2.2 : Remove the input file once input is updated to the .cfg file
# step 3   : Check for (mysql_remove | postgres_remove) file present in conf folder [multiple instance supported]
#      3.1 : For each instance, enabled=false and status=3 is defined in mysql.cfg [status (5)-suspended (3)-deleted]
#      3.2 : Remove the (mysql_remove | postgres_remove) file once the instance is marked for deletion in .cfg file
# step 4   : Check for (mysql | postgres) process running in the local machine
#      4.1 : If process instance list found, ADS with basic metrics sent [free monitor] [one time poll]
# step 5   : Encrypt the password for the instance that is enabled and registered for data collection
# step 6   : For instance in .cfg file [enabled = true] and [xxx_status = 0] data collection is started
#      6.1 : If basic_monitoring=true, basic data collections is scheduled, and 1 day once master slave replication status change is scheduled [cluster config]
#      6.2 : if insight_monitoring=true, insight data collections is scheduled. [for now disabled by default] [server side work going on]
def setup_config_file(DB_TYPE):
    try:
        DB_CONSTANTS = AgentConstants.DB_CONSTANTS[DB_TYPE]
        AgentLogger.log(AgentLogger.DATABASE, '====================== Initializing database monitoring for - {} ======================'.format(DB_TYPE))
        # if not DB_CONSTANTS.get('ADD_INSTANCE_START_TIME'):
        #     DB_CONSTANTS['ADD_INSTANCE_START_TIME'] = time.time()
        
        # step 1
        create_db_monitoring_dir(DB_TYPE,DB_CONSTANTS['CONF_FILE'])
        
        CONFIG = get_config_parser(DB_CONSTANTS['CONF_FILE'])
        copy_to_global_config(DB_TYPE,CONFIG)
        
        db_ssl_config(DB_TYPE)

        # step 2
        bool_status, sql_instance = check_input_data_file(DB_CONSTANTS['INPUT_FILE'])
        if sql_instance:
            AgentLogger.log(AgentLogger.DATABASE,'{} - sql_input file found, adding input configurations to {}'.format(DB_TYPE,DB_CONSTANTS['CONF_FILE']))
            sql_instance = json.loads(sql_instance)
            for single_instance in sql_instance:
                send_registration = False
                old_instance_name, instance_name = get_instance_name(single_instance,CONFIG,DB_TYPE)
                # instance not present [ add configurations and registering directly as basic monitor ]
                if not CONFIG.has_section(instance_name) or not CONFIG.has_option(instance_name, 'mid'):
                    if CONFIG.has_section(instance_name):
                        CONFIG.remove_section(instance_name)
                    CONFIG.add_section(instance_name)
                    if not is_host_local_instance(single_instance['host']):
                        CONFIG.set(instance_name,'is_remote','true')
                    send_registration = True
                else:
                    # instance already registered, possible actions : [ update configurations / convert free to basic monitor ]
                    if CONFIG.get(instance_name, 'mid') not in ['0', None]:
                        # instance already registered as basic monitor [ update user/password/other options ]
                        if CONFIG.get(instance_name, 'user') not in ['0','None', None] and CONFIG.has_option(instance_name,'encrypted.password'):
                            update_instance_config_data(instance_name, single_instance,DB_TYPE,CONFIG)
                        # instance registered as free monitor [ updating configurations and converting to basic monitor ]
                        else:
                            send_registration = True
                if send_registration:
                    # if old_instance_name not in AgentConstants.DATABASE_CONFIG_MAPPER[DB_TYPE]:
                    #     AgentConstants.DATABASE_CONFIG_MAPPER[DB_TYPE][old_instance_name]={"section_name":instance_name}
                    update_database_input_data(instance_name, single_instance,CONFIG,DB_TYPE)

            if os.path.exists(DB_CONSTANTS['INPUT_FILE']):
                os.remove(DB_CONSTANTS['INPUT_FILE'])

        # step 3
        remove_sql_instance(DB_TYPE)

        # step 4
        sql_instance_list = discover_sql_db(DB_TYPE,DB_CONSTANTS) if is_discovery_enabled(DB_TYPE.upper(), CONFIG) else "disabled"

        # for each process instance found earlier, one section is created in DATABASE_FILE.cfg and sent to ADS, if mid got stored in DATABASE_FILE.cfg else mid = 0
        # [enabled = false] second registration needed after user gives user/password data
        # auto discover can be disabled using the option [ Database_Name.cfg -> discover_instance -> false]
        if sql_instance_list != "disabled":
            for single_instance in sql_instance_list:
                instance_name = str(single_instance['host'])+'-'+str(single_instance['port'])
                bool_status, matched_instance_name = check_local_instance_exists(single_instance['host'], single_instance['port'],CONFIG,DB_TYPE)
                if not bool_status and not CONFIG.has_section(instance_name):
                    create_instance_section_from_process(instance_name, single_instance, DB_TYPE, DB_CONSTANTS, CONFIG)
        else:
            AgentLogger.log(AgentLogger.DATABASE,'auto discover {} instance from process running is disabled'.format(DB_TYPE))
        
        # step 5
        verify_password_encryption(DB_TYPE,CONFIG)

        # step 6
        persist_config_parser(DB_CONSTANTS['CONF_FILE'], CONFIG)

        # used to reinit config variables once [database].cfg modified
        DB_CONSTANTS['CONFIG_LAST_CHANGE_TIME'] = os.path.getmtime(DB_CONSTANTS['CONF_FILE'])

        return True
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while initializing {} monitoring :: {}'.format(DB_TYPE,e))
        traceback.print_exc()
        if os.path.exists(DB_CONSTANTS['INPUT_FILE']):
            AgentLogger.log(AgentLogger.DATABASE,'Removing {} input file due to exception :: {}'.format(DB_TYPE,e))
            os.remove(DB_CONSTANTS['INPUT_FILE'])


# Persisting DC of database monitor -- reusable functions
#-----------------------------------------------------------------------------------------------------------
# Database List discovered and sent for child register
def save_database_discovery_data(result_dict):
    try:
        key_name = 'database_name'
        list_data = [result_dict]
        if "list_data" in result_dict:
            list_data = result_dict.get("list_data")
            key_name = 'name'

        AgentLogger.log(AgentLogger.DATABASE, '[INFO] DATABASE DISCOVERY DATA OBTAINED :: {}'.format(list_data))
        for result in list_data:
            if result['availability'] == "1":
                body_list_dict = register_database_child(result,key_name)
                post_child_data_buffers(body_list_dict)
            else:
                AgentLogger.log(AgentLogger.DATABASE, '====== database discovery failed [{} Connection Failed] ========= {}'.format(result_dict.get("monitor_type"),result_dict))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while saving database discovery data :: {} : result_dict :: {}'.format(e,result_dict))
        traceback.print_exc()
