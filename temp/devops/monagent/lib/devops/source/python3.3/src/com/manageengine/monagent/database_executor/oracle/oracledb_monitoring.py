import json
import time
import sys
import re,shutil

import traceback , os, copy
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
    import oracledb
    AgentConstants.PYTHON_ORACLEDB_MODULE = "1"
except:
    AgentLogger.log(AgentLogger.DATABASE,"Error while importing oracledb in oracledb_monitoring module")

if 'com.manageengine.monagent.util.DatabaseUtil' in sys.modules:
    DatabaseUtil = sys.modules['com.manageengine.monagent.util.DatabaseUtil']
else:
    from com.manageengine.monagent.util import DatabaseUtil

DB_TYPE      = AgentConstants.ORACLE_DB
DB_CONSTANTS = AgentConstants.DB_CONSTANTS[DB_TYPE]
class OracleSQLInitializer(object):
    def __init__(self,instance,xmlString):
        try:
            self.load(instance,xmlString)
            self.conf_calc_time = 0
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while initializing OracleSQLInitializer object :: Instance - {} :: Error - {}'.format(instance,e))
    
    def loadObjForDiscovery(self,instance_name,child_keys=None):
        try:
            self.load(instance_name,"")
            if child_keys != None:
                self.instance_info["db_child_keys"]      =   child_keys
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while loading object for oracle child monitor discovery :: Instance - {} :: Error - {}'.format(instance_name,e))

    def load(self,instance_name,xmlString=None):
        try:
            ORACLE_CONFIG = DatabaseUtil.ORACLE_CONFIG
            if not ORACLE_CONFIG.has_section(instance_name):
                AgentLogger.log(AgentLogger.DATABASE,'Section does not exist :: Instance - {} '.format(instance_name))
            
            self.instance_name          = instance_name
            decrypted_pwd               = str(AgentCrypt.decrypt_with_ss_key(ORACLE_CONFIG.get(instance_name,'encrypted.password')))
            password                    = '' if str(decrypted_pwd) in ['None', 'none', '0', ''] else decrypted_pwd
            if xmlString!=None:
                self.xmlString          = xmlString
            self.instance_info = {
                'password'      : password,
                'os'            : 'linux',
                'application'   : AgentConstants.ORACLE_DB,
                'instance_name' : instance_name,
                'xmlString'     : self.xmlString,
                'time_diff'     : AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'time_diff'),
                'db_child_keys' : AgentConstants.DATABASE_CONFIG_MAPPER[AgentConstants.ORACLE_DB].get(self.instance_name) or {}
            }
            # for key in ['host','port','user','mid','enabled','default_database','conf_poll_interval','perf_poll_interval','Version','db_per_thread','db_per_zip','oracle_home']:
            for key in ['host','port','user','mid','enabled','service_name','conf_poll_interval','perf_poll_interval','Version','db_per_thread','db_per_zip','CDB_ROOT']:
                if ORACLE_CONFIG.has_option(instance_name,key):
                    self.instance_info[key] = ORACLE_CONFIG.get(instance_name,key)
                else:
                    AgentLogger.log(AgentLogger.DATABASE,'Database - OracleDB :: Option - {} not present for instance - {}'.format(key,instance_name))

        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while loading OracleSQLInitializer object :: Instance - {} :: Error - {}'.format(instance_name,e))
            traceback.print_exc()
        
    def collect_basic_data(self):
        result_dict = {}
        try:
            AgentLogger.debug(AgentLogger.DATABASE,"[DEBUG] db_child_keys - {}".format(AgentConstants.DATABASE_CONFIG_MAPPER[DB_TYPE].get(self.instance_name)))
            file_name       = self.instance_info["mid"]+'_basic_data.json'
            instance_dict   = self.instance_info.copy()
            instance_dict.update({
                "cached_data"       :   DatabaseUtil.read_data(DB_CONSTANTS['CONF_FOLDER'],file_name),
                "db_child_keys"     :   AgentConstants.DATABASE_CONFIG_MAPPER[DB_TYPE].get(self.instance_name) or {},
                "collection_type"   :   '0',
                "collect_conf"      :   False
            })

            now =   int(time.time())

            if self.conf_calc_time <= now:
                instance_dict['collect_conf']       =   True
                self.conf_calc_time                 =   now + int(self.instance_info.get('conf_poll_interval') or 86400)
                AgentLogger.log(AgentLogger.DATABASE,'instance_name - {} :: collect config data :: True '.format(self.instance_name))

            cache,result_dict                       =   DatabaseExecutor.initialize(instance_dict)
            if cache:
                DatabaseUtil.write_data(cache,DB_CONSTANTS['CONF_FOLDER'],file_name)
            del instance_dict
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception :: oracledb :: collect_basic_data :: Instance - {} :: Error - {}'.format(self.instance_name,e))
            traceback.print_exc()
        finally:
            return result_dict
        
    def discover(self,collection_type):
        try:
            instance_dict                       =   self.instance_info.copy()
            instance_dict['collection_type']    =   collection_type
            result_dict                         =   DatabaseExecutor.initialize(instance_dict)
            AgentLogger.log(AgentLogger.DATABASE,"instance_name - {} :: result_dict - {} :: discover_{} ".format(self.instance_name,result_dict,"database" if collection_type == '1' else "tablespace"))
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception :: oracledb :: discover_database :: Instance - {} :: Error - {}'.format(self.instance_name,e))
            traceback.print_exc()
        finally:
            return result_dict

    def data_collection_initialize(self,param):
        instance_name,data_collection_type = param
        oracledb_result_dict = {}
        try:
            AgentLogger.log(AgentLogger.DATABASE,'=== Starting DC for Oracle Database :: Instance - {} ==='.format(instance_name))
            last_modified_time  = os.path.getmtime(DB_CONSTANTS['CONF_FILE'])
            AgentLogger.log(AgentLogger.DATABASE,'OracleSQL Database Configuration file modified : Last Modified :: {}'.format(last_modified_time))
            if last_modified_time != DB_CONSTANTS['CONFIG_LAST_CHANGE_TIME']:
                DatabaseUtil.ORACLE_CONFIG = DatabaseUtil.get_config_parser(DB_CONSTANTS['CONF_FILE'])
                self.load(self.instance_name)

                DB_CONSTANTS['CONFIG_LAST_CHANGE_TIME'] = last_modified_time

            if data_collection_type == "0":
                oracledb_result_dict = self.collect_basic_data()
                oracledb_result_dict['mid'] = self.instance_info.get('mid')
            elif data_collection_type in ["1","2"]:
                oracledb_result_dict = self.discover(data_collection_type)
            elif data_collection_type == "3":
                self.conf_calc_time = int(time.time()) + 30
                self.collect_basic_data()
            AgentLogger.log(AgentLogger.DATABASE,'=== DC completed for Oracle Database :: Instance - {} ==='.format(instance_name))
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while initializing datacollection for oracledb scripts :: Instance - {} :: Error - {}'.format(self.instance_name,e))
            traceback.print_exc()
        finally:
            return oracledb_result_dict

def schedule_data_collection(instance_name,oracledb_obj,data_collection_type):
    try:
        ORACLE_CONFIG = DatabaseUtil.ORACLE_CONFIG
        mid = ORACLE_CONFIG.get(instance_name,"mid")
        
        if data_collection_type == "0":
            task_name                 = mid+"_basic"
            poll_interval_variable    = 'perf_poll_interval'
        elif data_collection_type == "1":
            task_name                 = mid+"_discover_database"
            poll_interval_variable    = "discover"
        elif data_collection_type == "2":
            task_name                 = mid+"_discover_tablespace"
            poll_interval_variable    = "discover"
        elif data_collection_type == "3":
            task_name                 = mid+"_dummy_data"
            poll_interval_variable    = "dummy"
        else:
            task_name                 = 'None'
            poll_interval_variable    = 'None'

        if poll_interval_variable == "one_day_task":
            poll_interval             = 86400
        elif poll_interval_variable in ["discover","dummy"]:
            poll_interval             = 0
        elif ORACLE_CONFIG.has_option(instance_name, poll_interval_variable):
            poll_interval             = int(ORACLE_CONFIG.get(instance_name, poll_interval_variable))
        elif ORACLE_CONFIG.has_option(AgentConstants.ORACLE_DB, poll_interval_variable):
            poll_interval             = int(ORACLE_CONFIG.get(AgentConstants.ORACLE_DB, poll_interval_variable))
        else:
            poll_interval = 300

        task            =   oracledb_obj.data_collection_initialize
        taskargs        =   (instance_name,data_collection_type)
        
        if poll_interval_variable == "discover":
            callback    =   DatabaseUtil.save_database_discovery_data
        else: 
            callback    =   save_data

        scheduleInfo=AgentScheduler.ScheduleInfo()
        if data_collection_type in ['1','2','3']:
            scheduleInfo.setIsPeriodic(False)
        else:
            scheduleInfo.setIsPeriodic(True)
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName(task_name)
        if data_collection_type in ["0"] :
            scheduleInfo.setTime(time.time()+60)
        elif data_collection_type == "2":
            scheduleInfo.setTime(time.time()+10)
        else:
            scheduleInfo.setTime(time.time())
        scheduleInfo.setTask(task)
        scheduleInfo.setTaskArgs(taskargs)
        if data_collection_type != '3':
            scheduleInfo.setCallback(callback)
        scheduleInfo.setInterval(poll_interval)
        scheduleInfo.setLogger(AgentLogger.DATABASE)
        AgentLogger.log(AgentLogger.DATABASE, '======================= Scheduling Data Collection for OracleSQL Monitor ======================= :: '+str(instance_name)+' :: '+str(task_name))
        AgentScheduler.schedule(scheduleInfo)
        if poll_interval != 0: # add scheduler object to the mapper that only repeats
            AgentConstants.DATABASE_OBJECT_MAPPER[AgentConstants.ORACLE_DB][task_name] = scheduleInfo
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while scheduling oracledb monitor for polling :: {} : {}'.format(instance_name,e))

def dict_chunk_to_list(dict_chunk):
    result_list = []
    try:
        for db_data in dict_chunk:
            result_list.append([data for db_name,data in db_data.items()])
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception in dict_chunk_to_list :: database - oracledb :: error - {}'.format(e))
    return result_list

def save_data(output):
    try:
        ORACLE_CONFIG = DatabaseUtil.ORACLE_CONFIG
        ORACLE_DB=AgentConstants.ORACLE_DB.upper()
        if output:
            mid = output.get('mid')
            if mid ==None:
                return
            last_chunk = {}
            if output.get('PDBS'):
                DatabaseUtil.set_files_in_zip_to_upload()
                databases = output.pop("PDBS")
                single_file_data = {'mid':mid}
                file_size_bytes = int(ORACLE_CONFIG.get(ORACLE_DB, 'file_size_bytes')) if ORACLE_CONFIG.has_option(ORACLE_DB, 'file_size_bytes') else 153600
                dict_chunks = dict_chunk_to_list(AgentUtil.dict_chunk_with_file_size(databases, file_size_bytes)) or []
                len_dict_chunks =   len(dict_chunks)

                for index in range(len_dict_chunks-1):
                    single_file_data['PDB'] = dict_chunks[index]
                    status, file_name = DatabaseUtil.save_database_data(single_file_data,AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['012'],ORACLE_DB)
                    if status:
                        AgentLogger.log(AgentLogger.DATABASE, "Child Database monitoring Data Collected [old flow] | Database Name : {} | File Name : {} | DB Data in File : {}".format(ORACLE_DB,file_name,len(dict_chunks[index])))
                        time.sleep(.001)
                    else:
                        AgentLogger.log(AgentLogger.DATABASE, "Failed to store child db data [old flow] :: {}-{}".format(ORACLE_DB,mid))
                
                if len_dict_chunks > 0:
                    last_chunk['PDB'] = dict_chunks[len_dict_chunks-1]
            elif 'PDBS' in output:
                output.pop("PDBS")
            
            if last_chunk:
                output.update(last_chunk)
            dir_prop = AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['012']
            status,file_path=DatabaseUtil.save_database_data(output,dir_prop,ORACLE_DB)
            AgentLogger.log(AgentLogger.DATABASE, "Oracle SQL DC Saved - {} :: file path - {}".format(status,file_path))

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE," Oracle SQL :: Error in save_data - {}\n".format(e))

def update_database_config_data(database, config_dict):
    config_update_dict = {}
    try:
        AgentLogger.log(AgentLogger.DATABASE,'============== Received update config for database - {} =============='.format(database))
        AgentLogger.debug(AgentLogger.DATABASE,'[DEBUG] received config_dict - {} '.format(config_dict))
        if database == DB_TYPE:
            is_change = False
            oracledb_config = DatabaseUtil.get_config_parser(DB_CONSTANTS['CONF_FILE'])

            for instance in config_dict:
                config_update_dict[instance['mid']] = {}
                for key in ['perf_poll_interval','conf_poll_interval','query_selection_config','status']:
                    if key in instance:
                        config_update_dict[instance['mid']][key]    =   str(instance[key])
                if 'child_keys' in instance:
                    config_update_dict[instance['mid']]['child_keys'] = instance['child_keys']
                    AgentLogger.log(AgentLogger.STDOUT,'Oracle SQL :: Child Database added for data collection :: {} : {}'.format(instance['mid'],instance['child_keys']))

            for section in oracledb_config:
                if section in [DB_TYPE.upper(),'DEFAULT']:
                    continue
                if oracledb_config.has_option(section,'enabled') and oracledb_config.get(section,'enabled') == 'true':
                    if oracledb_config.has_option(section,'mid'):
                        mon_id = oracledb_config.get(section,'mid')
                    else:
                        AgentLogger.log(AgentLogger.DATABASE,'mid not present for section :: {} :: Database - {}'.format(section,database))
                        continue

                    if mon_id in config_update_dict:
                        if 'child_keys' in config_update_dict[mon_id]:
                            AgentConstants.DATABASE_CONFIG_MAPPER[DB_TYPE][section] = config_update_dict[mon_id]['child_keys']

                        AgentLogger.log(AgentLogger.DATABASE,'[INFO] Oracle SQL :: Child Database added for data collection :: {} : {}'.format(section,config_update_dict[mon_id].get('child_keys')))
                        if 'status' in config_update_dict[mon_id] and (oracledb_config.has_option(section,'status') and oracledb_config.get(section,'status') != config_update_dict[mon_id]['status']):
                            is_change = True
                            if config_update_dict[mon_id]['status'] in ['0','3','5']:
                                oracledb_config.set(section,'status',config_update_dict[mon_id]['status'])
                        
                        for option in ['perf_poll_interval','conf_poll_interval','query_selection_config']:
                            if option in config_update_dict[mon_id]:
                                is_change = True
                                oracledb_config.set(section,option,config_update_dict[mon_id][option])
            
            if is_change:
                DatabaseUtil.persist_config_parser(DB_CONSTANTS['CONF_FILE'],oracledb_config)
                start_oracledb_data_collection()
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while updating database config :: Database - {} : Error - {}'.format(database,e))
        traceback.print_exc()

def discover_child(dict_task,collection_type):
    try:
        # 1 for database discovery
        # 2 for tablespace discovery
        ORACLE_CONFIG = DatabaseUtil.ORACLE_CONFIG
        oracledb_obj = OracleSQLInitializer("","")
        pdb_list = None
        mid = None
        instance_name = None
        if "mid" in dict_task:
            mid = dict_task["mid"]
        else:
            AgentLogger.log(AgentLogger.DATABASE," 'mid' not present for the CLIENT_CHILD_DISCOVER action.")
            return
        
        if dict_task["MONITOR_TYPE"] == "ORACLE_DB":
            for instance in ORACLE_CONFIG:
                if instance not in [AgentConstants.ORACLE_DB.upper(),'DEFAULT'] and ORACLE_CONFIG.has_option(instance, 'mid') and ORACLE_CONFIG.get(instance, 'mid') == mid:
                    instance_name = instance
                    break
            pdb_list = {instance_name:{"ORACLE_PDB":{}}} if dict_task["CHILD_TYPE"] == "ORACLE_TABLESPACE" else None
        elif dict_task["MONITOR_TYPE"] == "ORACLE_PDB" and dict_task["CHILD_TYPE"] == "ORACLE_TABLESPACE":
            pdb_list = {}
            db_child_keys = AgentConstants.DATABASE_CONFIG_MAPPER[AgentConstants.ORACLE_DB] or {}
            for section_name,instance_child_keys in db_child_keys.items():
                keys = instance_child_keys.get("ORACLE_PDB") or {}
                for name,child_key in keys.items():
                    if child_key["mid"] == mid:
                        pdb_list = {"ORACLE_PDB":{name:child_key}}
                        instance_name = section_name
                        break
        if instance_name != None:
            AgentLogger.log(AgentLogger.DATABASE,"instance_name - {} :: pdb_list for discovery - {}".format(instance_name,pdb_list))
            oracledb_obj.loadObjForDiscovery(instance_name,pdb_list)
            schedule_data_collection(instance_name,oracledb_obj,collection_type)

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while scheduling discover_child task :: collection_type - {} :: Error - {}'.format(collection_type,e))
        traceback.print_exc()

def update_oracle_library_path():
    msg="\n"
    LD_LIBRARY_PATH=None
    try:
        ORACLE_DB = AgentConstants.ORACLE_DB.upper()
        oracle_update_file = os.path.join(AgentConstants.AGENT_CONF_DIR,'oracle_update')
        bool_status, sql_instance = DatabaseUtil.check_input_data_file(oracle_update_file)

        if bool_status and sql_instance:
            AgentLogger.log(AgentLogger.DATABASE,'oracle_update file found.')
            AgentLogger.log(AgentLogger.DATABASE,'User input received for LD_LIBRARY_PATH - {}'.format(sql_instance))
            sql_instance = json.loads(sql_instance)
            if  type(sql_instance) is dict and sql_instance.get("LD_LIBRARY_PATH"):
                LD_LIBRARY_PATH = str(sql_instance["LD_LIBRARY_PATH"]).strip(' ') if sql_instance.get("LD_LIBRARY_PATH") else None
            else:
                AgentLogger.log(AgentLogger.DATABASE,'LD_LIBRARY_PATH not present in json while updating LD_LIBRARY_PATH using --update_path option. sql_instance - {}'.format(sql_instance))
        else:
            AgentLogger.log(AgentLogger.DATABASE,'Cannot read oracle_update file. sql_instance - {}'.format(sql_instance))

        if LD_LIBRARY_PATH==None:
            msg="\nSomething went wrong. Please try again..."
        elif not os.path.exists(LD_LIBRARY_PATH):
            msg="\nProvided path does not exist."
        else:
            product_profile_data = (DatabaseUtil.read_data("",AgentConstants.AGENT_PRODUCT_PROFILE_FILE) or "").splitlines()
            remove_index = []
            for index,line in enumerate(product_profile_data):
                if "LD_LIBRARY_PATH" in line:
                    remove_index.append(index)
            if remove_index:
                for ind,rmi in enumerate(remove_index):
                    product_profile_data.pop(rmi-ind)
            if DatabaseUtil.ORACLE_CONFIG.has_option(ORACLE_DB,"ld_library_path"):
                ld_lib_str = 'LD_LIBRARY_PATH={}:{};export LD_LIBRARY_PATH'.format(DatabaseUtil.ORACLE_CONFIG.get(ORACLE_DB,"ld_library_path"),LD_LIBRARY_PATH)
            else:
                ld_lib_str = 'LD_LIBRARY_PATH={};export LD_LIBRARY_PATH'.format(LD_LIBRARY_PATH)
            product_profile_data.append(ld_lib_str)
            data="\n".join(product_profile_data)
            AgentUtil.writeRawDataToFile(AgentConstants.AGENT_PRODUCT_PROFILE_FILE,data)

            DatabaseUtil.ORACLE_CONFIG.set(ORACLE_DB,"new_ld_library_path",LD_LIBRARY_PATH)
            DatabaseUtil.persist_config_parser(AgentConstants.ORACLE_DB_CONF_FILE,DatabaseUtil.ORACLE_CONFIG)
            AgentLogger.log(AgentLogger.DATABASE,"LD_LIBRARY_PATH persisted.")
            # msg = "\nSuccessfully updated the LD_LIBRARY_PATH." 
        
        if os.path.exists(oracle_update_file):
            os.remove(oracle_update_file)
        
        AgentLogger.log(AgentLogger.DATABASE,"LD_LIBRARY_PATH - {} , msg - {} ".format(LD_LIBRARY_PATH,msg))

        response_file = AgentConstants.DB_CONSTANTS[AgentConstants.ORACLE_DB]["TERMINAL_RESPONSE_FILE"]
        AgentUtil.writeRawDataToFile(response_file,msg)
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while updating oracle library path :: Error - {}'.format(e))

def start_oracledb_data_collection(initial=False):
    try:
        if DatabaseUtil.ORACLE_CONFIG == None:
            DatabaseUtil.ORACLE_CONFIG = DatabaseUtil.get_config_parser(DB_CONSTANTS['CONF_FILE'])
        CONFIG          = DatabaseUtil.ORACLE_CONFIG

        DatabaseUtil.stop_all_instance(AgentConstants.ORACLE_DB)

        xmlString = DatabaseUtil.read_data(DB_CONSTANTS['CONF_FOLDER'],DB_CONSTANTS['XML_QUERY_FILE_NAME'])
        for instance in CONFIG:
            if instance in [DB_TYPE.upper(), 'DEFAULT']:
                continue
            if CONFIG.get(instance,'enabled') == 'true' and CONFIG.get(instance,'status') == '0':
                oracledb_obj = OracleSQLInitializer(instance,xmlString)
                if initial:
                    schedule_data_collection(instance,oracledb_obj,"3")
                schedule_data_collection(instance,oracledb_obj,"0")
                if CONFIG.has_option(instance,'discover_database') and CONFIG.get(instance,'discover_database') == 'true':
                    schedule_data_collection(instance,oracledb_obj,"1")
                    schedule_data_collection(instance,oracledb_obj,"2")
                    CONFIG.remove_option(instance,'discover_database')
                elif AgentConstants.DATABASE_CONFIG_MAPPER[DB_TYPE] and CONFIG.has_option(instance,'discover_tablespace') and CONFIG.get(instance,'discover_tablespace') == 'true':
                    schedule_data_collection(instance,oracledb_obj,"2")
                    CONFIG.remove_option(instance,'discover_tablespace')
        DB_CONSTANTS['CONFIG_LAST_CHANGE_TIME'] = os.path.getmtime(DB_CONSTANTS['CONF_FILE'])

        DatabaseUtil.persist_config_parser(DB_CONSTANTS['CONF_FILE'], CONFIG)
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception in start_oracledb_data_collection :: {}'.format(e))

def set_ld_library_path():
    is_success,err_msg,response_flag = False,"",False
    try:
        DB_CONSTANTS = AgentConstants.DB_CONSTANTS[AgentConstants.ORACLE_DB]
        AgentLogger.log(AgentLogger.DATABASE,'LD_LIBRARY_PATH obtained from environment while agent startup - {}'.format(os.environ.get("LD_LIBRARY_PATH")))
        if os.path.exists(DB_CONSTANTS['CONF_FILE']):
            CONFIG = DatabaseUtil.get_config_parser(DB_CONSTANTS['CONF_FILE'])
            ORACLE_DB  = AgentConstants.ORACLE_DB.upper()
            if CONFIG!=None and CONFIG.has_section(ORACLE_DB):
                if CONFIG.has_option(ORACLE_DB,"ld_library_path"):
                    AgentLogger.log(AgentLogger.DATABASE,'LD_LIBRARY_PATH present in cfg file - {}'.format(CONFIG.get(ORACLE_DB,"ld_library_path")))
                if CONFIG.has_option(ORACLE_DB,"new_ld_library_path"):
                    try:
                        new_ld_lib = os.path.abspath(CONFIG.get(ORACLE_DB,"new_ld_library_path"))
                        response_flag = True
                        oracledb.init_oracle_client(lib_dir=new_ld_lib)
                        is_success = True
                        CONFIG.set(ORACLE_DB,"ld_library_path",new_ld_lib)
                        AgentLogger.log(AgentLogger.DATABASE,'Initialized to new LD_LIBRARY_PATH - {}'.format(new_ld_lib))
                        err_msg = "Successfully updated the LD_LIBRARY_PATH."
                    except Exception as e:
                        err_msg = str(e)
                        AgentLogger.log(AgentLogger.DATABASE,'Exception while initializing new LD_LIBRARY_PATH - {}'.format(e))        
                    CONFIG.remove_option(ORACLE_DB,"new_ld_library_path")
                    DatabaseUtil.persist_config_parser(AgentConstants.ORACLE_DB_CONF_FILE,CONFIG)
                if CONFIG.has_option(ORACLE_DB,"ld_library_path") and not is_success:
                    try:
                        oracledb.init_oracle_client(lib_dir=CONFIG.get(ORACLE_DB,"ld_library_path"))
                        is_success = True
                        err_msg = "The below shown error has occurred:\n"+err_msg
                        err_msg +="\n\nPlease check if you have provided the appropriate Instant Client Library and try again."
                    except Exception as e:
                        err_msg = "The below shown error has occurred:\n"+err_msg
                        err_msg +="\nPlease check if you have provided the appropriate Instant Client Library and try again."
                        AgentLogger.log(AgentLogger.DATABASE,'Exception while initializing existing LD_LIBRARY_PATH - {}'.format(e))
            if response_flag:
                response_file = AgentConstants.DB_CONSTANTS[AgentConstants.ORACLE_DB]["TERMINAL_RESPONSE_FILE"]
                AgentUtil.writeRawDataToFile(response_file,err_msg)
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception in set_ld_library_path :: Error - {}'.format(e))
    return is_success,err_msg

# check oracle dir exist in app and create it, with default SQL configuration instance for discovery
def initialize():
    try:
        if AgentConstants.PYTHON_ORACLEDB_MODULE!="1":
            AgentLogger.log(AgentLogger.DATABASE,'python_oracledb module not found')
            return

        set_ld_library_path()
        if DatabaseUtil.setup_config_file(AgentConstants.ORACLE_DB) != True:
            AgentLogger.log(AgentLogger.DATABASE,'config setup failed for oracle monitor')
            return
        
        if os.path.exists(AgentConstants.ORACLE_DB_UPDATE_FILE):
            AgentLogger.log(AgentLogger.DATABASE,'oracle_update file found while agent is being starting.')
            update_oracle_library_path()

        start_oracledb_data_collection(initial=True)

        # # used for file change notifier
        # AgentConstants.ORACLE_INIT = True
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while initializing oracledb monitor :: {}'.format(e))
