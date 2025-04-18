import json
import time
import sys
import subprocess
import traceback , os
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

from com.manageengine.monagent.util                                         import AgentUtil
from com.manageengine.monagent.logger                                       import AgentLogger
from com.manageengine.monagent                                              import AgentConstants
from com.manageengine.monagent.database                                     import DatabaseExecutor
from com.manageengine.monagent.scheduler                                    import AgentScheduler
from com.manageengine.monagent.security                                     import AgentCrypt
from com.manageengine.monagent.discovery                                    import discovery_util
try:
    import psycopg2
    AgentConstants.PSYCOPG2_MODULE = "1"
except Exception as e:
    AgentLogger.log(AgentLogger.DATABASE,"psycopg2 not imported - {}".format(e))

if 'com.manageengine.monagent.util.DatabaseUtil' in sys.modules:
    DatabaseUtil = sys.modules['com.manageengine.monagent.util.DatabaseUtil']
else:
    from com.manageengine.monagent.util import DatabaseUtil

DB_TYPE      = AgentConstants.POSTGRES_DB
DB_CONSTANTS = AgentConstants.DB_CONSTANTS[DB_TYPE]
class PostgreSQLInitializer(object):
    def __init__(self,instance,xmlString):
        try:
            if instance:
                self.load(instance,xmlString)
            self.conf_calc_time = 0
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while initializing PostgreSQLInitializer object :: Instance - {} :: Error - {}'.format(instance,e))

    def load(self,instance_name,xmlString=None):
        try:
            POSTGRES_CONFIG = DatabaseUtil.POSTGRES_CONFIG
            if not POSTGRES_CONFIG.has_section(instance_name):
                AgentLogger.log(AgentLogger.DATABASE,'Section does not exist :: Instance - {} '.format(instance_name))
            
            self.instance_name          = instance_name
            decrypted_pwd               = str(AgentCrypt.decrypt_with_ss_key(POSTGRES_CONFIG.get(instance_name,'encrypted.password')))
            password                    = '' if str(decrypted_pwd) in ['None', 'none', '0', ''] else decrypted_pwd
            if xmlString!=None:
                self.xmlString          = xmlString
            self.instance_info = {
                'password'      : password,
                'os'            : 'linux',
                'application'   : AgentConstants.POSTGRES_DB,
                'instance_name' : instance_name,
                'xmlString'     : self.xmlString,
                'time_diff'     : AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'time_diff')
            }

            config_info = ['host','port','user','mid','enabled','default_database','conf_poll_interval','perf_poll_interval','Version','db_per_thread','db_per_zip']
            
            if POSTGRES_CONFIG.has_option(instance_name,'ssl') and POSTGRES_CONFIG.get(instance_name,'ssl')=="true":
                config_info.extend(['ssl-ca','ssl-cert','ssl-key','ssl','ssl-mode'])
            
            for key in config_info:
                if POSTGRES_CONFIG.has_option(instance_name,key):
                    self.instance_info[key] = POSTGRES_CONFIG.get(instance_name,key)
                else:
                    AgentLogger.log(AgentLogger.DATABASE,'Database - Postgres :: Option - {} not present for instance - {}'.format(key,instance_name))

        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while loading PostgreSQLInitializer object :: Instance - {} :: Error - {} :: traceback - {}'.format(instance_name,e,traceback.print_exc()))
        
    def collect_basic_data(self):
        result_dict = {}
        try:
            file_name       = self.instance_info["mid"]+'_basic_data.json'
            instance_dict   = self.instance_info.copy()
            conf_folder     = AgentConstants.DB_CONSTANTS[AgentConstants.POSTGRES_DB]['CONF_FOLDER']
            instance_dict.update({
                "cached_data"       :   DatabaseUtil.read_data(conf_folder,file_name),
                "db_child_keys"     :   AgentConstants.DATABASE_CONFIG_MAPPER[AgentConstants.POSTGRES_DB].get(self.instance_name) or {},
                "collection_type"   :   '0',
                "collect_conf"      :   False
            })

            now =   int(time.time())

            if self.conf_calc_time <= now:
                instance_dict['collect_conf']       =   True
                self.conf_calc_time                 =   now + int(self.instance_info.get('conf_poll_interval') or 86400)

            cache,result_dict                       =   DatabaseExecutor.initialize(instance_dict)
            if cache:
                DatabaseUtil.write_data(cache,conf_folder,file_name)
            del instance_dict
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception :: postgres :: collect_basic_data :: Instance - {} :: Error - {}'.format(self.instance_name,e))
            traceback.print_exc()
        finally:
            return result_dict
        
    def discover_database(self):
        try:
            instance_dict                       =   self.instance_info.copy()
            instance_dict['collection_type']    =   '1'
            result_dict                         =   DatabaseExecutor.initialize(instance_dict)
            AgentLogger.log(AgentLogger.DATABASE,'postgres :: discover_database :: {}'.format(result_dict))
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception :: postgres :: discover_database :: Instance - {} :: Error - {}'.format(self.instance_name,e))
            traceback.print_exc()
        finally:
            return result_dict

    def data_collection_initialize(self,param):
        instance_name,data_collection_type = param
        postgres_result_dict = {}
        try:
            AgentLogger.log(AgentLogger.DATABASE,'=== Starting DC for Postgres Database :: Instance - {} ==='.format(instance_name))
            DB_CONSTANTS        =    AgentConstants.DB_CONSTANTS[AgentConstants.POSTGRES_DB]
            last_modified_time  =    os.path.getmtime(DB_CONSTANTS['CONF_FILE'])
            AgentLogger.log(AgentLogger.DATABASE,'PostgreSQL Database Configuration file modified : Last Modified :: {}'.format(last_modified_time))
            if last_modified_time != DB_CONSTANTS['CONFIG_LAST_CHANGE_TIME']:
                DatabaseUtil.POSTGRES_CONFIG = DatabaseUtil.get_config_parser(DB_CONSTANTS['CONF_FILE'])
                self.load(self.instance_name)

                DB_CONSTANTS['CONFIG_LAST_CHANGE_TIME'] = last_modified_time

            if data_collection_type == "0":
                # postgres_result_dict = convertToUploadFormat(self.collect_basic_data(),self.instance_info.get('mid'),"databases",AgentConstants.POSTGRES_DATABASE_PER_FILE)
                postgres_result_dict = self.collect_basic_data()
                postgres_result_dict['mid'] = self.instance_info.get('mid')
            elif data_collection_type == "1":
                postgres_result_dict = self.discover_database()
            elif data_collection_type == "2":
                self.collect_basic_data()
            AgentLogger.log(AgentLogger.DATABASE,'=== DC completed for Postgres Database :: Instance - {} ==='.format(instance_name))
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while initializing datacollection for postgres scripts :: Instance - {} :: Error - {}'.format(self.instance_name,e))
            traceback.print_exc()
        finally:
            return postgres_result_dict

# # Database List discovered and sent for child register
# def save_database_discovery_data(result_dict):
#     try:
#         monitor_type="POSTGRESQL"
#         child_type="POSTGRESQL_DATABASE"
#         if result_dict['availability'] == "1":
#             AgentLogger.debug(AgentLogger.DATABASE, '[DEBUG] DATABASE DISCOVERY DATA OBTAINED :: {}'.format(result_dict))
#             body_list_dict = DatabaseUtil.register_database_child(AgentConstants.POSTGRES_DB,result_dict,monitor_type,child_type)
#             DatabaseUtil.post_child_data_buffers(body_list_dict)
#         else:
#             AgentLogger.log(AgentLogger.DATABASE, '====== database discovery failed [POSTGRES Connection Failed] ========= {}'.format(result_dict))
#     except Exception as e:
#         AgentLogger.log(AgentLogger.DATABASE,'Postgres :: Exception while saving database discovery data :: {}'.format(e))
#         traceback.print_exc()

# def upload_cluster_config_data(result_dict):
#     try:
#         if result_dict:
#             discovery_util.post_discovery_result(result_dict,AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['014'],AgentConstants.POSTGRES_DB)
#             AgentLogger.debug(AgentLogger.DATABASE, '[DEBUG] Uploaded to Cluster Config :: {}'.format(result_dict))
#         else:
#             AgentLogger.log(AgentLogger.DATABASE, '====== postgres cluster config data collection failed [POSTGRES Connection Failed] ========= {}'.format(result_dict))
#     except Exception as e:
#         AgentLogger.log(AgentLogger.DATABASE,'Exception while uploading cluster config data :: {}'.format(e))
#         traceback.print_exc()

def schedule_data_collection(instance_name,postgres_obj,data_collection_type):
    try:
        POSTGRES_CONFIG = DatabaseUtil.POSTGRES_CONFIG
        mid = POSTGRES_CONFIG.get(instance_name,"mid")
        
        if data_collection_type == "0":
            task_name                 = mid+"_basic"
            poll_interval_variable    = 'perf_poll_interval'
        elif data_collection_type == "1":
            task_name                 = mid+"_discover_database"
            poll_interval_variable    = "discover_database"
        elif data_collection_type == "2":
            task_name                 = mid+"_dummy_data"
            poll_interval_variable    = "dummy"
        else:
            task_name                 = 'None'
            poll_interval_variable    = 'None'

        if poll_interval_variable == "one_day_task":
            poll_interval             = 86400
        elif poll_interval_variable in ["discover_database","dummy"]:
            poll_interval             = 0
        elif POSTGRES_CONFIG.has_option(instance_name, poll_interval_variable):
            poll_interval             = int(POSTGRES_CONFIG.get(instance_name, poll_interval_variable))
        elif POSTGRES_CONFIG.has_option('POSTGRES', poll_interval_variable):
            poll_interval             = int(POSTGRES_CONFIG.get('POSTGRES', poll_interval_variable))
        else:
            poll_interval = 300

        task            =   postgres_obj.data_collection_initialize
        taskargs        =   (instance_name,data_collection_type)
        
        if data_collection_type == "1":
            callback    =   DatabaseUtil.save_database_discovery_data
        else: 
            callback    =   save_data

        scheduleInfo=AgentScheduler.ScheduleInfo()
        if data_collection_type in ['1','2']:
            scheduleInfo.setIsPeriodic(False)
        else:
            scheduleInfo.setIsPeriodic(True)
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName(task_name)
        if data_collection_type == "0":
            scheduleInfo.setTime(time.time()+60)
        else:
            scheduleInfo.setTime(time.time())
        scheduleInfo.setTask(task)
        scheduleInfo.setTaskArgs(taskargs)
        scheduleInfo.setCallback(callback)
        scheduleInfo.setInterval(poll_interval)
        scheduleInfo.setLogger(AgentLogger.DATABASE)
        AgentLogger.log(AgentLogger.DATABASE, '======================= Scheduling Data Collection for PostgreSQL Monitor ======================= :: '+str(instance_name)+' :: '+str(task_name))
        AgentScheduler.schedule(scheduleInfo)
        if poll_interval != 0: # add scheduler object that only repeats to the mapper
            AgentConstants.DATABASE_OBJECT_MAPPER[AgentConstants.POSTGRES_DB][task_name] = scheduleInfo
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while scheduling postgres monitor for polling :: {} : {}'.format(instance_name,e))

def save_data(output):
    try:
        POSTGRES_CONFIG = DatabaseUtil.POSTGRES_CONFIG
        if output:
            # for part in output:
            #     dir_prop = AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['012']
            #     status,file_path=DatabaseUtil.save_database_data(part,dir_prop,"POSTGRESQL")
            #     AgentLogger.log(AgentLogger.DATABASE, "\nPostgres DC Saved - file path - {}\n".format(status,file_path))
            mid = output.get('mid')
            if mid ==None:
                return
            last_chunk = {}
            if output.get('databases'):
                DatabaseUtil.set_files_in_zip_to_upload()
                databases = output.pop("databases")
                single_file_data = {'mid':mid}
                file_size_bytes = int(POSTGRES_CONFIG.get('POSTGRES', 'file_size_bytes')) if POSTGRES_CONFIG.has_option('POSTGRES', 'file_size_bytes') else 153600
                dict_chunks = AgentUtil.dict_chunk_with_file_size(databases, file_size_bytes)
                len_dict_chunks =   len(dict_chunks)

                for index in range(len_dict_chunks-1):
                    single_file_data['Databases'] = dict_chunks[index]
                    status, file_name = DatabaseUtil.save_database_data(single_file_data,AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['012'],"POSTGRESQL")
                    if status:
                        AgentLogger.log(AgentLogger.DATABASE, "Child Database monitoring Data Collected [old flow] | Database Name : {} | File Name : {} | DB Data in File : {}".format("postgres",file_name,len(dict_chunks[index])))
                        time.sleep(.001)
                    else:
                        AgentLogger.log(AgentLogger.DATABASE, "Failed to store child db data [old flow] :: {}-{}".format("postgres",mid))
                
                if len_dict_chunks > 0:
                    last_chunk['Databases'] = dict_chunks[len_dict_chunks-1]
            
            if last_chunk:
                output.update(last_chunk)
            dir_prop = AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['012']
            status,file_path=DatabaseUtil.save_database_data(output,dir_prop,"POSTGRESQL")
            AgentLogger.log(AgentLogger.DATABASE, "Postgres DC Saved - {} :: file path - {}".format(status,file_path))



    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE," \nPostgres :: Error in save_data - {}\n".format(e))


# def convertToUploadFormat( collected_data, mid, metric_to_chunk, max_db_per_file ):
#     try:
#         final_list              =   []
#         collected_data['mid']   =   mid
#         dblist                  =   (collected_data.get(metric_to_chunk) and collected_data.pop(metric_to_chunk)) or {}

#         result  =   AgentUtil.list_chunks(dblist, max_db_per_file)
#         final_list.append( collected_data )

#         for db in result:
#             final_list.append({metric_to_chunk:db, 'mid': mid})

#         return final_list
#     except Exception as e:
#         AgentLogger.log(AgentLogger.DATABASE, "\nException :: convertToUploadFormat - {}".format(e) )

# update database config
def update_database_config_data(database, config_dict):
    config_update_dict = {}
    try:
        AgentLogger.log(AgentLogger.DATABASE,'============== Received update config for database - {} =============='.format(database))
        conf_file       =   DB_CONSTANTS['CONF_FILE']
        if database == "POSTGRESQL":
            is_change = False
            postgres_config = DatabaseUtil.get_config_parser(conf_file)

            for instance in config_dict:
                config_update_dict[instance['mid']] = {}
                for key in ['perf_poll_interval','conf_poll_interval','query_selection_config','status']:
                    if key in instance:
                        config_update_dict[instance['mid']][key]    =   str(instance[key])
                if 'child_keys' in instance and 'POSTGRESQL_DATABASE' in instance['child_keys']:
                    config_update_dict[instance['mid']]['child_keys'] = instance['child_keys']['POSTGRESQL_DATABASE']
                    AgentLogger.log(AgentLogger.STDOUT,'Postgres :: Child Database added for data collection :: {} : {}'.format(instance['mid'],instance['child_keys']['POSTGRESQL_DATABASE']))

            for section in postgres_config:
                if section in [DB_TYPE.upper(),'DEFAULT']:
                    continue
                # instance_name=(AgentConstants.DATABASE_CONFIG_MAPPER[DB_TYPE].get(section) or {}).get('section_name') or section
                # if section in AgentConstants.DATABASE_CONFIG_MAPPER[DB_TYPE]:
                #     AgentConstants.DATABASE_CONFIG_MAPPER[DB_TYPE].pop(section)
                # if postgres_config.get(section,'enabled') == 'true' or section != instance_name:
                if postgres_config.has_option(section,'enabled') and postgres_config.get(section,'enabled') == 'true':
                    if postgres_config.has_option(section,'mid'):
                        mon_id = postgres_config.get(section,'mid')
                    else:
                        AgentLogger.log(AgentLogger.DATABASE,'mid not present for section :: {} :: Database - {}'.format(section,database))
                        continue
                    if mon_id in config_update_dict:
                        if 'child_keys' in config_update_dict[mon_id]:
                            AgentConstants.DATABASE_CONFIG_MAPPER[DB_TYPE][section] = config_update_dict[mon_id]['child_keys']
                        AgentLogger.debug(AgentLogger.DATABASE,'[DEBUG] Postgres :: Child Database added for data collection :: {} : {}'.format(section,config_update_dict[mon_id].get('child_keys')))
                        if 'status' in config_update_dict[mon_id] and (postgres_config.has_option(section,'status') and postgres_config.get(section,'status') != config_update_dict[mon_id]['status']):
                            is_change = True
                            if config_update_dict[mon_id]['status'] in ['0','3','5']:
                                postgres_config.set(section,'status',config_update_dict[mon_id]['status'])
                        
                        for option in ['perf_poll_interval','conf_poll_interval','query_selection_config']:
                            if option in config_update_dict[mon_id]:
                                is_change = True
                                postgres_config.set(section,option,config_update_dict[mon_id][option])
                        # upload_cluster_config_data({"mid":mon_id,"databases":AgentConstants.DATABASE_CONFIG_MAPPER[AgentConstants.POSTGRES_DB][section]})
            
            if is_change:
                DatabaseUtil.persist_config_parser(conf_file,postgres_config)
                start_postgres_data_collection()
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while updating database config :: Database - {} : Error - {}'.format(database,e))
        traceback.print_exc()
    finally:
        return None

def child_database_discover(dict_task):
    try:
        POSTGRES_CONFIG = DatabaseUtil.POSTGRES_CONFIG
        postgres_obj = PostgreSQLInitializer("","")
        if 'MONITOR_ID' in dict_task:
            mid = dict_task['mid']
            for instance in POSTGRES_CONFIG:
                if instance not in [AgentConstants.POSTGRES_DB.upper(),'DEFAULT'] and POSTGRES_CONFIG.get(instance, 'mid') == mid:
                    postgres_obj.load(instance,"")
                    schedule_data_collection(instance,postgres_obj,"1")
        AgentLogger.log(AgentLogger.DATABASE,'postgres - received rediscover request')
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Database - {} :: Exception while scheduling database discover task :: Error - {}'.format(AgentConstants.POSTGRES_DB,e))
        traceback.print_exc()
    finally:
        return None

# check with DatabaseUtil file and remove - rediscover_postgres_instances
def rediscover_postgres_instances():
    try:
        DatabaseUtil.stop_all_instance(DB_TYPE)
        checked_local_instance_port_list = []

        POSTGRES_CONFIG = DatabaseUtil.POSTGRES_CONFIG = DatabaseUtil.get_config_parser(DB_CONSTANTS['CONF_FILE'])
        postgres_instance_list = DatabaseUtil.discover_sql_db(DB_TYPE,DB_CONSTANTS)

        for each_instance in POSTGRES_CONFIG:
            if each_instance not in [DB_TYPE.upper(), 'DEFAULT']:
                port = POSTGRES_CONFIG.get(each_instance,'port')
                host = POSTGRES_CONFIG.get(each_instance,'host')
                checked_local_instance_port_list.append(port)
                if POSTGRES_CONFIG.get(each_instance,'user') == '0' or POSTGRES_CONFIG.get(each_instance,'enabled') == 'false':
                    is_exist = False
                    for single_process in postgres_instance_list:
                        if str(port) == single_process['port'] and str(host) == single_process['host']:
                            register_status,app_key = DatabaseUtil.register_database_monitor(single_process,each_instance,DB_TYPE,POSTGRES_CONFIG,DB_CONSTANTS['CONF_FILE'])
                            is_exist = True
                            if register_status and app_key:
                                AgentLogger.log(AgentLogger.DATABASE,'re-Registering Dummy Instance Sucessfull | Instance Name :: {} | New Key :: {} | Old Key :: {}'.format(each_instance,app_key,POSTGRES_CONFIG.get(each_instance,'mid')))
                                POSTGRES_CONFIG.set(each_instance,'mid',app_key)
                            else:
                                AgentLogger.log(AgentLogger.DATABASE,'re-Registering Dummy Instance Failed | Instance Name :: {} | Old Key :: {}'.format(each_instance,POSTGRES_CONFIG.get(each_instance,'mid')))
                    if not is_exist:
                        AgentLogger.log(AgentLogger.DATABASE,'re-Registering Dummy Instance Not Found | Instance Name :: {} | Old Key :: {}'.format(each_instance,POSTGRES_CONFIG.get(each_instance,'mid')))
                else:
                    register_status, app_key = DatabaseUtil.reregister_instance(each_instance, POSTGRES_CONFIG,DB_TYPE)
                    if not POSTGRES_CONFIG.has_option(each_instance,'is_remote'):
                        checked_local_instance_port_list.append(port)
                    if register_status and app_key:
                        AgentLogger.log(AgentLogger.DATABASE,'re-Registering POSTGRES Instance Sucessfull | Instance Name :: {} | New Key :: {} | Old Key :: {}'.format(each_instance,app_key,POSTGRES_CONFIG.get(each_instance,'mid')))
                        POSTGRES_CONFIG.set(each_instance,'mid',app_key)
                    else:
                        AgentLogger.log(AgentLogger.DATABASE,'re-Registering POSTGRES Instance Failed | Instance Name :: {} | Old Key :: {}'.format(each_instance,POSTGRES_CONFIG.get(each_instance,'mid')))

        for single_process in postgres_instance_list:
            instance_name = str(single_process['host']) +"-"+ str(single_process['port'])
            if str(single_process['port']) not in checked_local_instance_port_list:
                AgentLogger.log(AgentLogger.DATABASE,'re-Registering New POSTGRES Instance from Process | Instance Name :: {}'.format(instance_name))
                DatabaseUtil.create_instance_section_from_process(instance_name, single_process,DB_TYPE,DB_CONSTANTS,POSTGRES_CONFIG)

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while rediscovering POSTGRES Database :: Error - {}'.format(e))
        traceback.print_exc()

def start_postgres_data_collection():
    try:
        if DatabaseUtil.POSTGRES_CONFIG == None:
            DatabaseUtil.POSTGRES_CONFIG = DatabaseUtil.get_config_parser(DB_CONSTANTS['CONF_FILE'])
        CONFIG          =   DatabaseUtil.POSTGRES_CONFIG
        DatabaseUtil.stop_all_instance(DB_TYPE)

        xmlString = DatabaseUtil.read_data(DB_CONSTANTS['CONF_FOLDER'],DB_CONSTANTS['XML_QUERY_FILE_NAME'])
        for instance in CONFIG:
            if instance in [DB_TYPE.upper(), 'DEFAULT']:
                continue
            if CONFIG.get(instance,'enabled') == 'true' and CONFIG.get(instance,'status') == '0':
                postgres_obj = PostgreSQLInitializer(instance,xmlString)
                schedule_data_collection(instance,postgres_obj,"0")
                if CONFIG.has_option(instance,'discover_database') and CONFIG.get(instance,'discover_database') == 'true':
                    schedule_data_collection(instance,postgres_obj,"1")
                    CONFIG.remove_option(instance,'discover_database')
        AgentConstants.POSTGRES_CONFIG_LAST_CHANGE_TIME = os.path.getmtime(DB_CONSTANTS['CONF_FILE'])

        DatabaseUtil.persist_config_parser(DB_CONSTANTS['CONF_FILE'], CONFIG)
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception in start_postgres_data_collection :: {}'.format(e))


# check postgres dir exist in app and create it, with default SQL configuration instance for discovery
def initialize():
    try:
        if AgentConstants.PSYCOPG2_MODULE!="1":
            AgentLogger.log(AgentLogger.DATABASE,'psycopg2 not found')
            return

        if DatabaseUtil.setup_config_file(AgentConstants.POSTGRES_DB) != True:
            AgentLogger.log(AgentLogger.DATABASE,'config setup failed for postgres monitor')
            return
        start_postgres_data_collection()
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while initializing postgres monitoring :: {}'.format(e))
        traceback.print_exc()
        if os.path.exists(AgentConstants.POSTGRES_INPUT_FILE):
            AgentLogger.log(AgentLogger.DATABASE,'Removing POSTGRES input file due to exception :: {}'.format(e))
            os.remove(AgentConstants.POSTGRES_INPUT_FILE)

