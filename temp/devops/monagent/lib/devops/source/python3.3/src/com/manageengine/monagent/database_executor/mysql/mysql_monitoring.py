'''
Created on 10-June-2022

@author: kavin
'''

import json
import time
import sys
import re
import subprocess
import traceback , os
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

#from com.manageengine.monagent.actions.FileChangeNotifier import FileChangeNotify
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants,AppConstants,DatabaseConstants
from com.manageengine.monagent.database import DatabaseExecutor
from com.manageengine.monagent.scheduler import AgentScheduler
from com.manageengine.monagent.security import AgentCrypt

try:
    import pymysql
    AgentConstants.PYMYSQL_MODULE='1'
except Exception as e:
    traceback.print_exc()

if 'com.manageengine.monagent.util.DatabaseUtil' in sys.modules:
    DatabaseUtil = sys.modules['com.manageengine.monagent.util.DatabaseUtil']
else:
    from com.manageengine.monagent.util import DatabaseUtil

from com.manageengine.monagent.database_executor.mysql import NDBCluster

# class to initialize variables to be sent to the database code [common linux/windows]
# dict of variables for different kinds of data collection is formed using this class
# data_collection_type
# 0-basic data
# 1-insight data
# 2-replica change conf update (1 day)
# 3-Database list Discovery
# 5-Startup Data collection(dummy data)
# 6-Child Database data collection]
class MySQLInitializer(object):
    # mysql.cfg is loaded in object variable as config parser
    def __init__(self,instance):
        try:
            pass
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while initializing mysql scheduler object :: Instance - {} :: Error - {}'.format(instance,e))
            traceback.print_exc()


    # object variables for the input to be sent for the database code alone is initialized, with respect to the data collection type
    def init(self,instance,data_collection_type):
        try:
            # common variables for all collection types
            self.instance                    = instance
            self.host                        = DatabaseUtil.MYSQL_CONFIG.get(instance,'host')
            self.user                        = DatabaseUtil.MYSQL_CONFIG.get(instance,'user')
            self.port                        = DatabaseUtil.MYSQL_CONFIG.get(instance,'port')
            self.mid                         = DatabaseUtil.MYSQL_CONFIG.get(instance,'mid')
            decrypted_pwd                    = str(AgentCrypt.decrypt_with_ss_key(DatabaseUtil.MYSQL_CONFIG.get(instance,'encrypted.password')))
            self.password                    = '' if str(decrypted_pwd) in ['None', 'none', '0', ''] else decrypted_pwd
            # if insight data collection
            if data_collection_type == "1":
                self.session                 = DatabaseUtil.MYSQL_CONFIG.get(instance,'session') if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'session') else DatabaseUtil.MYSQL_CONFIG.get('MYSQL','session')
                self.memory                  = DatabaseUtil.MYSQL_CONFIG.get(instance,'memory') if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'memory') else DatabaseUtil.MYSQL_CONFIG.get('MYSQL','memory')
                self.top_query               = DatabaseUtil.MYSQL_CONFIG.get(instance,'top_query') if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'top_query') else DatabaseUtil.MYSQL_CONFIG.get('MYSQL','top_query')
                self.slow_query              = DatabaseUtil.MYSQL_CONFIG.get(instance,'slow_query') if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'slow_query') else DatabaseUtil.MYSQL_CONFIG.get('MYSQL','slow_query')
                self.file_io                 = DatabaseUtil.MYSQL_CONFIG.get(instance,'file_io') if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'file_io') else DatabaseUtil.MYSQL_CONFIG.get('MYSQL','file_io')
                self.event_analysis          = DatabaseUtil.MYSQL_CONFIG.get(instance,'event_analysis') if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'event_analysis') else DatabaseUtil.MYSQL_CONFIG.get('MYSQL','event_analysis')
                self.error_analysis          = DatabaseUtil.MYSQL_CONFIG.get(instance,'error_analysis') if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'error_analysis') else DatabaseUtil.MYSQL_CONFIG.get('MYSQL','error_analysis')
                self.statement_analysis      = DatabaseUtil.MYSQL_CONFIG.get(instance,'statement_analysis') if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'statement_analysis') else DatabaseUtil.MYSQL_CONFIG.get('MYSQL','statement_analysis')
                self.host_analysis           = DatabaseUtil.MYSQL_CONFIG.get(instance,'host_analysis') if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'host_analysis') else DatabaseUtil.MYSQL_CONFIG.get('MYSQL','host_analysis')
                self.user_analysis           = DatabaseUtil.MYSQL_CONFIG.get(instance,'user_analysis') if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'user_analysis') else DatabaseUtil.MYSQL_CONFIG.get('MYSQL','user_analysis')
            # Child Data Collection / Basic Data Collection / Dummy Startup data collection needs [child key(db names), and previous data dict for volatile data]
            # db_size_top_tb is as of now restricted [INFORMATION_SCHEMA] issue, but will work for smaller databases
            # [db_size_top_tb] add db name in list in mysql.cfg
            elif data_collection_type in  ["0", "5", "6"]:
                self.child_keys              = AgentConstants.DATABASE_CONFIG_MAPPER['mysql'][instance] if instance in AgentConstants.DATABASE_CONFIG_MAPPER['mysql'] else {}
                self.db_size_top_tb          = DatabaseUtil.MYSQL_CONFIG.get(instance,'db_size_top_tb') if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'db_size_top_tb') else []
                self.db_schedule_count       = DatabaseUtil.MYSQL_CONFIG.get(instance,'database_thread_count') if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'database_thread_count') else "5"
                self.db_list_count           = DatabaseUtil.MYSQL_CONFIG.get(instance,'database_per_zip') if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'database_per_zip') else "50"
                self.time_diff               = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'time_diff')
                self.previous_data           = {}
            self.data_dict                   = {}
            # assinging common attributes for all mysql collection type here
            self.data_dict['application']           = 'mysql'
            self.data_dict['os']                    = 'linux'
            self.data_dict['instance']              = self.instance
            self.data_dict['mid']                   = self.mid
            self.data_dict['host']                  = self.host
            self.data_dict['port']                  = self.port
            self.data_dict['user']                  = self.user
            self.data_dict['password']              = self.password

            if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'ssl') and DatabaseUtil.MYSQL_CONFIG.get(instance,'ssl')=="true":
                if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'ssl-ca'):
                    self.data_dict['ssl-ca']            = DatabaseUtil.MYSQL_CONFIG.get(instance,'ssl-ca')
                if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'ssl-cert'):
                    self.data_dict['ssl-cert']            = DatabaseUtil.MYSQL_CONFIG.get(instance,'ssl-cert')
                if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'ssl-key'):
                    self.data_dict['ssl-key']            = DatabaseUtil.MYSQL_CONFIG.get(instance,'ssl-key')
                self.data_dict['ssl'] = "true"
            # conf_key contains conf data, stored in mysql folder, sent to server, only on data onchange, verified every polling in agent side
            self.conf_key                    = {}
            if DatabaseUtil.MYSQL_CONFIG.has_option(instance,'Version'):
                self.data_dict['Version']        = DatabaseUtil.MYSQL_CONFIG.get(instance,'Version')
            else:
                connection_status, connection = DatabaseUtil.getDBConnection(self.data_dict,AgentConstants.MYSQL_DB)
                if connection_status:
                    cursor = connection.cursor()
                    DatabaseUtil.execute_query(cursor,AgentConstants.MYSQL_VERSION_QUERY)
                    _version = cursor.fetchone()
                    cursor.close()
                    connection.close()
                    self.data_dict['Version']       = _version[0]
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while assigning value to mysql config :: {} : {}'.format(self.instance,e))
            traceback.print_exc()


    # happens every time agent restarted, or mysql flow restarted [adding instance]
    # some mysql data are non-volatile [keep on increasing] no use for graph for that type
    # previous data is stored and subtracted with current data. [this flow for the previous data for the 1st dc]
    # collects startup dummy data
    def collect_dummy_dc(self):
        result_dict = {}
        try:
            # common attributes are assingned in init method itself
            self.data_dict['collection_type']       = '5'

            # child key data stored from configuration serverlet, after database discovery, all database are registered as child monitor and id for each is sent in configuration serverlet
            # dc happens only for the database list came from configuration serverlet
            # AppUtil.update_app_config_data() -> DatabaseUtil.update_database_config_data()
            self.data_dict['child_keys']            = AgentConstants.DATABASE_CONFIG_MAPPER['mysql'][self.instance] if self.instance in AgentConstants.DATABASE_CONFIG_MAPPER['mysql'] else {}

            # calling database code for data collection
            result_dict                             = DatabaseExecutor.initialize(self.data_dict)
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while passing input to dummy data dc scripts :: Instance - {} :: Error - {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            # returned to save_dummy_data() from data_collection_initialize()
            return result_dict


    # conf metrics is received only if any onchange occurred in least any one of the conf metrics or
    # instance_name_conf.json file not present, or no conf_key is sent to database code [first time poll for instance]
    # previous data is stored and subtracted with current data.
    # collects basic data collection
    def collect_perf_data(self):
        result_dict = {}
        try:
            DB_TYPE         = AgentConstants.MYSQL_DB
            DB_CONSTANTS    = AgentConstants.DB_CONSTANTS[DB_TYPE]
            if AgentConstants.CONF_UPLOAD_FLAG == True:
                AgentLogger.log(AgentLogger.DATABASE,'CONF data upload flag : True | hence, getting new conf data from dc')
                self.conf_key = {}
                AgentConstants.CONF_UPLOAD_FLAG = False
            elif os.path.exists(os.path.join(DB_CONSTANTS['CONF_FOLDER'], self.instance+'_conf.json')):
                conf_data = DatabaseUtil.read_data(DB_CONSTANTS['CONF_FOLDER'], self.instance+'_conf.json')
                self.conf_key = json.loads(conf_data)

            # common attributes are assingned in init method itself
            self.data_dict['collection_type']       = '0'

            # to calculate current time "ct" in database agent
            self.data_dict['time_diff']             = self.time_diff
            # conf data is checked with the current data, only any change occured, sent added to data to push to server
            self.data_dict['conf_key']              = self.conf_key
            # previous data contains the last polled's current value of non-volatile metrics, it is subtracted with present data to get periodic volatile data
            self.data_dict['previous_data']         = AgentConstants.DATABASE_PREVIOUS_DATA['mysql'][self.instance+'_perf'] if (self.instance+'_perf') in AgentConstants.DATABASE_PREVIOUS_DATA['mysql'] else {} # self.previous_data

            self.data_dict['replication_child_keys']= AgentConstants.DATABASE_CONFIG_MAPPER['mysql_replication'][self.instance] if self.instance in AgentConstants.DATABASE_CONFIG_MAPPER['mysql_replication'] else {}
            self.data_dict['mysql_replication_seconds_behind_master']= AgentConstants.DATABASE_CONFIG_MAPPER['mysql_replication_seconds_behind_master'][self.instance] if self.instance in AgentConstants.DATABASE_CONFIG_MAPPER['mysql_replication_seconds_behind_master'] else {}

            # calling database code for data collection
            result_dict                             = DatabaseExecutor.initialize(self.data_dict)
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while passing input to mysql basic monitor dc scripts :: Instance - {} :: Error - {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            # returned to data_save() from data_collection_initialize()
            return result_dict


    # collects all the list of database available in the instance
    # registers in server as separate monitor
    def collect_database_discovery_data(self):
        result_dict = {}
        try:
            # common attributes are assingned in init method itself
            self.data_dict['collection_type']       = '3'

            # calling database code for data collection
            result_dict                             = DatabaseExecutor.initialize(self.data_dict)
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while passing input to mysql database discover scripts :: Instance - {} :: Error - {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            # returned to save_database_discovery_data() from data_collection_initialize()
            return result_dict


    # collects only insight monitor metrics
    # each module enabled for insight data collection is sent as a variable to database code
    # currently not enabled =[[ IMPORTANT ]]= need to discuss with selva anna
    def collect_insight_data(self):
        result_dict = {}
        try:
            # common attributes are assingned in init method itself
            self.data_dict['collection_type']       = '1'

            self.data_dict['session']               = self.session
            self.data_dict['memory']                = self.memory
            self.data_dict['top_query']             = self.top_query
            self.data_dict['slow_query']            = self.slow_query
            self.data_dict['file_io']               = self.file_io
            self.data_dict['event_analysis']        = self.event_analysis
            self.data_dict['statement_analysis']    = self.statement_analysis
            self.data_dict['error_analysis']        = self.error_analysis
            self.data_dict['host_analysis']         = self.host_analysis
            self.data_dict['user_analysis']         = self.user_analysis

            # calling database code for data collection
            result_dict                             = DatabaseExecutor.initialize(self.data_dict)
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while passing input to mysql dc scripts :: Instance - {} :: Error - {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            # returned to data_save() from data_collection_initialize()
            return result_dict


    # collects only replica change metrics [cluster config servlet]
    # polled one day once to update any onchange occurred on master slave status
    # add sample result data =[[ IMPORTANT ]]=
    def collect_replication_change_data(self):
        result_dict = {}
        try:
            conf_folder = AgentConstants.DB_CONSTANTS[AgentConstants.MYSQL_DB]['CONF_FOLDER']
            if os.path.exists(os.path.join(conf_folder, self.instance+'_conf.json')):
                conf_data = DatabaseUtil.read_data(conf_folder, self.instance+'_conf.json')
                self.conf_key = json.loads(conf_data)

            # common attributes are assingned in init method itself
            self.data_dict['collection_type']       = '2'
            self.data_dict['conf_key']              = self.conf_key
            self.data_dict['replication_child_keys']= AgentConstants.DATABASE_CONFIG_MAPPER['mysql_replication'][self.instance] if self.instance in AgentConstants.DATABASE_CONFIG_MAPPER['mysql_replication'] else {}
            
            # calling database code for data collection
            result_dict                             = DatabaseExecutor.initialize(self.data_dict)
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while passing input to mysql replication dc scripts :: Instance - {} :: Error - {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            # returned to save_cluster_config_data() from data_collection_initialize()
            return result_dict


    # collects data for the child db that is sent from server in config serverlet
    # first time collects dummy data, next polling will happen by subtracting the previous values to get the periodic data
    def collect_child_db_data(self):
        result_dict = {}
        try:
            schedule_data                           = {}

            # common attributes are assingned in init method itself
            self.data_dict['collection_type']       = '6'

            # to calculate current time "ct" in database agent
            self.data_dict['time_diff']             = self.time_diff
            self.data_dict['mid']                   = self.mid
            schedule_data['db_per_thread']          = self.db_schedule_count
            schedule_data['db_per_zip']             = self.db_list_count
            self.data_dict['scheduler']             = schedule_data


            # [db_size_top_tb] as of now not told to cx, if user wants to monitor size related metrics irrespective of INFORMATION_SCHEMA issue, add db name in list in mysql.cfg
            self.data_dict['db_size_top_tb']        = self.db_size_top_tb
            # previous data contains the last polled's current value of non-volatile metrics, it is subtracted with present data to get periodic volatile data
            self.data_dict['previous_data']         = AgentConstants.DATABASE_PREVIOUS_DATA['mysql'][self.instance+'_child_data'] if (self.instance+'_child_data') in AgentConstants.DATABASE_PREVIOUS_DATA['mysql'] else {} # self.previous_data
            # data collection will happen only for the database which are in child_keys [added from configuration serverlet]
            self.data_dict['child_keys']            = AgentConstants.DATABASE_CONFIG_MAPPER['mysql'][self.instance] if self.instance in AgentConstants.DATABASE_CONFIG_MAPPER['mysql'] else {}

            # calling database code for data collection
            result_dict                             = DatabaseExecutor.initialize(self.data_dict)
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while passing input to mysql child database data collection :: Instance - {} :: Error - {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            # returned to data_save()
            return result_dict


    # for each polling this method is called first
    # separate function for each type of data collections is called
    def data_collection_initialize(self,task_args_list):
        # task_args_list contains instance name and collection type
        mysql_result_dict      = {}
        instance               = task_args_list[0]
        data_collection_type   = task_args_list[1]
        try:
            AgentLogger.log(AgentLogger.DATABASE,'=== Starting DC for MySQL Database :: Instance - {} ==='.format(instance))
            DB_CONSTANTS    =   AgentConstants.DB_CONSTANTS[AgentConstants.MYSQL_DB]
            # reint mysql.cfg config parser, if last edited time differes
            last_modified_time = os.path.getmtime(DB_CONSTANTS['CONF_FILE'])
            if last_modified_time != DB_CONSTANTS['CONFIG_LAST_CHANGE_TIME']:
                DatabaseUtil.MYSQL_CONFIG = DatabaseUtil.get_config_parser(DB_CONSTANTS['CONF_FILE'])
                self.init(instance,data_collection_type)
                DB_CONSTANTS['CONFIG_LAST_CHANGE_TIME'] = last_modified_time
                AgentLogger.log(AgentLogger.DATABASE,'MySQL Database Configuration file modified : Last Modified :: {}'.format(last_modified_time))

            if data_collection_type   == "0": # basic monitor
                mysql_result_dict         = self.collect_perf_data()
            elif data_collection_type == "1": # insight monitor
                mysql_result_dict         = self.collect_insight_data()
            elif data_collection_type == "2": # replication change task
                mysql_result_dict         = self.collect_replication_change_data()
            elif data_collection_type == "3": # database discovery task
                mysql_result_dict         = self.collect_database_discovery_data()
            elif data_collection_type == "5": # dummy start up data collection task
                mysql_result_dict         = self.collect_dummy_dc()
            elif data_collection_type == "6": # child database monitors
                mysql_result_dict         = self.collect_child_db_data()
            AgentLogger.log(AgentLogger.DATABASE,'=== DC completed for MySQL Database :: Instance - {} ==='.format(instance))
        except Exception as e:
            AgentLogger.log(AgentLogger.DATABASE,'Exception while initializing datacollection for mysql scripts :: Instance - {} :: Error - {}'.format(instance,e))
            traceback.print_exc()
        finally:
            # sent to respective result callback methods
            return mysql_result_dict


# schedules a separate thread for each mysql monitos and tasks
# start of the thread from data_collection_initialize()
# final data received from the thread is consolidated in respective callback methods
# collection type 4 reserved for windows dc
def schedule_data_collection(instance,data_collection_type):
    try:
        if data_collection_type in ['7','8','9']:
            ndb_obj,instance    = instance
            mid                 = DatabaseUtil.MYSQL_CONFIG.get(instance,"mysqlNDBmonkey")
        elif data_collection_type == '10':
            pass
        else:
            mid       = DatabaseUtil.MYSQL_CONFIG.get(instance,'mid')
            mysql_obj = MySQLInitializer(instance)
            mysql_obj.init(instance,data_collection_type)

        # poll interval will be taken if section has option [poll_interval_variable]
        # task name is created based on collection type to schedule thread
        if data_collection_type   == "0":
            poll_interval_variable    = 'poll_interval'
            task_name                 = mid+"_basic"
        elif data_collection_type == "1":
            poll_interval_variable    = 'poll_interval'
            task_name                 = mid+"_insight"
        elif data_collection_type == "2":
            poll_interval_variable    = 'one_day_task'
            task_name                 = mid+"_onedaytask"
        elif data_collection_type == "3":
            poll_interval_variable    = 'database_discover'
            task_name                 = mid+"_database_discover"
        elif data_collection_type == "5":
            poll_interval_variable    = 'dummy_data'
            task_name                 = mid+"_dummy_data"
        elif data_collection_type == "6":
            poll_interval_variable    = 'basic_poll_interval'
            task_name                 = mid+"_child_db"
        elif data_collection_type == "7":
            poll_interval_variable    = 'child_discovery'
            task_name                 = mid+"_ndb_child_discovery"
        elif data_collection_type == "8":
            poll_interval_variable    = 'NDB_perf_pollinterval'
            task_name                 = mid+"_ndb_perf"
        elif data_collection_type == "9":
            poll_interval_variable    = 'NDB_conf_pollinterval'
            task_name                 = mid+"_ndb_conf"
        elif data_collection_type == "10":
            poll_interval_variable    = 'one_day_task'
            task_name                 = "ndb_node_discovery"
        else:
            poll_interval_variable    = 'None'
            task_name                 = 'None'

        if poll_interval_variable == 'one_day_task':
            poll_interval             = int(86400)      # 24 hours = 86400 sec
        elif poll_interval_variable in ['database_discover', 'dummy_data','child_discovery']:
            poll_interval             = 0               # database discovery one time task
        elif DatabaseUtil.MYSQL_CONFIG.has_option(instance, poll_interval_variable):
            poll_interval             = int(DatabaseUtil.MYSQL_CONFIG.get(instance, poll_interval_variable))
        elif DatabaseUtil.MYSQL_CONFIG.has_option('MYSQL', poll_interval_variable):
            poll_interval             = int(DatabaseUtil.MYSQL_CONFIG.get('MYSQL', poll_interval_variable))
        else:
            poll_interval = 300                                         # default value must be changed to 300 before release

        # method where each data collection is called separately
        if data_collection_type in ['7','8','9']:
            task        = ndb_obj.data_collection_initialize
        elif data_collection_type == '10':
            task        = NDBCluster.getNodeDiscovery
        else:
            task            = mysql_obj.data_collection_initialize
        taskargs        = (instance,data_collection_type)

        # callback where the thread task result data will be received
        if data_collection_type   == '5':
            callback    = save_dummy_data
        elif data_collection_type == '3':
            callback    = DatabaseUtil.save_database_discovery_data
        elif data_collection_type == '2':
            callback    = save_cluster_config_data
        elif data_collection_type == '8':
            callback    = NDBCluster.savePerf
        elif data_collection_type in ['9','10']:
            callback    = NDBCluster.saveConf
        else:
            callback    = data_save

        # thread scheduler object
        scheduleInfo = AgentScheduler.ScheduleInfo()
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName(task_name)
        scheduleInfo.setTask(task)
        scheduleInfo.setTaskArgs(taskargs)
        if data_collection_type not in ['7']:
            scheduleInfo.setCallback(callback)
        scheduleInfo.setCallback(callback)
        scheduleInfo.setInterval(poll_interval)     # change to poll interval
        scheduleInfo.setLogger(AgentLogger.DATABASE)

        # only one polling collection types [ dummy startup data collection, database discovery task ]
        if data_collection_type in ['5', '3','7']:
            scheduleInfo.setIsPeriodic(False)
        else:
            scheduleInfo.setIsPeriodic(True)

        # delay time to start thread for the first time [ basic data collection, child database data collection]
        # must wait for dummy data collection thread to finish [non-volatile data issue]
        if data_collection_type in ['0', '6']:
            scheduleInfo.setTime(time.time()+60)
        else:
            scheduleInfo.setTime(time.time())

        AgentLogger.log(AgentLogger.DATABASE, '=================== Scheduling Data Collection for MySQL Monitor =================== :: '+str(instance)+' :: '+str(task_name))
        AgentScheduler.schedule(scheduleInfo)
        if poll_interval != 0: # add scheduler object that only repeats to the mapper
            AgentConstants.DATABASE_OBJECT_MAPPER['mysql'][task_name] = scheduleInfo

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while scheduling mysql monitor for polling :: {} : {}'.format(instance,e))
        traceback.print_exc()
    finally:
        pass


# Stores the startup data in DATABASE_PREVIOUS_DATA [basic monitor - (<InstanceName>_perf) / child database monitors (<InstanceName>_child_data)]
def save_dummy_data(result_dict):
    try:
        if result_dict['collection_type'] == '5':
            if result_dict['availability'] == "1":
                AgentConstants.DATABASE_PREVIOUS_DATA['mysql'][result_dict['instance']+'_child_data'] = {}
                AgentConstants.DATABASE_PREVIOUS_DATA['mysql'][result_dict['instance']+'_child_data'] = result_dict['child_data']
                AgentLogger.log(AgentLogger.DATABASE, 'DUMMY CHILD DATA OBTAINED :: {} - {}'.format(result_dict['instance'], AgentConstants.DATABASE_PREVIOUS_DATA['mysql'][result_dict['instance']+'_child_data']))
                result_dict.pop('child_data')
                AgentConstants.DATABASE_PREVIOUS_DATA['mysql'][result_dict['instance']+'_perf']       = {}
                AgentConstants.DATABASE_PREVIOUS_DATA['mysql'][result_dict['instance']+'_perf']       = result_dict
                AgentLogger.log(AgentLogger.DATABASE, 'DUMMY PERF DATA OBTAINED :: {} - {}'.format(result_dict['instance'], AgentConstants.DATABASE_PREVIOUS_DATA['mysql'][result_dict['instance']+'_perf']))
            else:
                AgentConstants.DATABASE_PREVIOUS_DATA['mysql'][result_dict['instance']+'_child_data'] = {}
                AgentConstants.DATABASE_PREVIOUS_DATA['mysql'][result_dict['instance']+'_perf']       = {}
                AgentLogger.log(AgentLogger.DATABASE, "Dummy DataCollection Failed [MySQL Connection Failed] :: {}".format(result_dict['err_msg']))

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while saving startup data :: {}'.format(e))
        traceback.print_exc()


# # Database List discovered and sent for child register
# def save_database_discovery_data(result_dict):
#     try:
#         monitor_type="MYSQLDB"
#         child_type="MYSQL_DATABASE"
#         if result_dict['availability'] == "1":
#             AgentLogger.debug(AgentLogger.DATABASE, '[DEBUG] DATABASE DISCOVERY DATA OBTAINED :: {} - {}'.format(result_dict['instance'],result_dict))
#             body_list_dict = DatabaseUtil.register_database_child(AgentConstants.MYSQL_DB,result_dict,monitor_type,child_type)
#             DatabaseUtil.post_child_data_buffers(body_list_dict)
#         else:
#             AgentLogger.log(AgentLogger.DATABASE, '====== database discovery failed [MySQL Connection Failed] ========= {}'.format(result_dict))
#     except Exception as e:
#         AgentLogger.log(AgentLogger.DATABASE,'Exception while saving database discovery data :: {}'.format(e))
#         traceback.print_exc()


# instance type [master/slave/standalone] onchange occurred data
def save_cluster_config_data(result_dict):
    try:
        if result_dict['availability'] == "1":
            AgentLogger.debug(AgentLogger.DATABASE, '[DEBUG] REPLICA CHANGE DATA OBTAINED :: {} - {}'.format(result_dict['instance'],result_dict))
            DatabaseUtil.upload_cluster_config('mysqldb',result_dict)
        else:
            AgentLogger.log(AgentLogger.DATABASE, '====== mysql cluster config data collection failed [MySQL Connection Failed] ========= {}'.format(result_dict))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while saving cluster config data :: {}'.format(e))
        traceback.print_exc()


# final data is consolidated for what type of data collection is done [basic/insight/replica change]
def data_save(result_dict):
    try:
        if result_dict:
            insight_data          = {}
            basic_data            = {}
            child_db_data_dict    = {}
            mid                   = None

            # store conf new metrics, during onchange occoured and get separate copy on conf metrics and writes in file for next poll
            if (result_dict['collection_type'] == "0") and ('conf' in result_dict) and (result_dict['conf']):
                # instnace type(instance_type) and conf(conf) metrics are stored in json format on <instnace_name>_conf.json file under mysql folder
                # read from here on every polling for conf metric onchange check
                conf_json_to_write                   = {}
                conf_json_to_write['conf']           = result_dict['conf']
                conf_json_to_write['instance_type']  = result_dict['instance_type']
                DatabaseUtil.write_data(conf_json_to_write,AgentConstants.DB_CONSTANTS[AgentConstants.MYSQL_DB]['CONF_FOLDER'],result_dict['instance'] + '_conf.json')
                AgentLogger.debug(AgentLogger.DATABASE, '[DEBUG] BASIC CONF DATA OBTAINED :: {} - {}'.format(result_dict['instance'],result_dict['conf']))

            # stores the current data in DATABASE_PREVIOUS_DATA for volatile metrics(counter), which will be used in next poll to calculate periodic volatile data by subtracting this value
            # basic current data are stored in key [ "<instnace_name>_perf" ]
            if (result_dict['collection_type'] == "0") and ('current_data' in result_dict) and (result_dict['current_data']):
                AgentConstants.DATABASE_PREVIOUS_DATA['mysql'][result_dict['instance']+'_perf'] = result_dict['current_data']
                result_dict.pop('current_data')
                AgentLogger.debug(AgentLogger.DATABASE, '[DEBUG] CURRENT DATA FROM BASIC DATA OBTAINED :: {} - {}'.format(result_dict['instance'],AgentConstants.DATABASE_PREVIOUS_DATA['mysql'][result_dict['instance']+'_perf']))
            elif (result_dict['collection_type'] == "0"):
                AgentConstants.DATABASE_PREVIOUS_DATA['mysql'][result_dict['instance']+'_perf'] = {}
                AgentLogger.log(AgentLogger.DATABASE, '============= No data for perf current poll found ============= :: {}'.format(result_dict['instance']))

            # stores the current data in DATABASE_PREVIOUS_DATA for volatile metrics(counter), which will be used in next poll to calculate periodic volatile data by subtracting this value
            # child database current data are stored in key [ "<instnace_name>_child_data" ]
            # List of database data are sent in list in key [ "Data" ]
            if (result_dict['collection_type'] == "6") and ('current_data' in result_dict) and (result_dict['current_data']):
                AgentConstants.DATABASE_PREVIOUS_DATA['mysql'][result_dict['instance']+'_child_data'] = result_dict['current_data']
                AgentLogger.debug(AgentLogger.DATABASE, '[DEBUG] CHILD DUMMY DATABASE DATA OBTAINED :: {} - {}'.format(result_dict['instance'],result_dict['current_data']))
            elif (result_dict['collection_type'] == "6"):
                AgentConstants.DATABASE_PREVIOUS_DATA['mysql'][result_dict['instance']+'_child_data'] = {}
                AgentLogger.log(AgentLogger.DATABASE, '============= No data for child database current poll found ============= :: {}'.format(result_dict['instance']))

            # if master/slave/standalone type changes, it is sent in key [ 'replication_onchange' ]
            # it is sent to cluster config serverlet
            if (result_dict['collection_type'] == "0") and ('replication_onchange' in result_dict) and (result_dict['replication_onchange']):
                replica_change_data    = result_dict['replication_onchange']
                replica_change_data['availability'] = '1'
                save_cluster_config_data(replica_change_data)
                result_dict.pop('replication_onchange')
                AgentLogger.log(AgentLogger.DATABASE, 'REPLICATION INSTANCE TYPE ONCHANGE OBTAINED :: {} - {}'.format(result_dict['instance'], replica_change_data))

            # after all possible data income check, main data of each data collection type is stored in separate variable and pushed to server
            if result_dict['collection_type'] == "0":
                basic_data             = result_dict
                mid                = result_dict['mid']
            elif result_dict['collection_type'] == "1":
                insight_data           = result_dict
            elif result_dict['collection_type'] == "6":
                child_db_data_dict = result_dict['Data']
                mid                = result_dict['mid']

            # basic data contains, perf and conf data od the overall mysql [basic monitor]
            if basic_data:
                #AgentLogger.log(AgentLogger.DATABASE, 'BASIC DATA OBTAINED :: {}'.format(basic_data))
                DatabaseUtil.persist_database_data('mysqldb',basic_data,"0",mid)
            # insight data conatains the overall insight data of the overall mysql [insight monitor]
            if insight_data:
                #AgentLogger.log(AgentLogger.DATABASE, 'INSIGHT DATA OBTAINED :: {}'.format(insight_data))
                DatabaseUtil.persist_database_data('mysqldb',insight_data,"1")
            # child db data contains the individual db data in list each list contains 50 database data dictionary [ to resolve 2mb size exception ]
            # child database are divieded into separate files in databae_monitoring agent istself
            # below code creates 5 files [5 set of 50 database nodes] to be uploaded to the server
            if child_db_data_dict:
                #AgentLogger.log(AgentLogger.DATABASE, 'CHILD DATABASE DATA OBTAINED :: {} - {}'.format(result_dict['instance'],child_db_data_dict))
                AgentLogger.debug(AgentLogger.DATABASE, '[DEBUG] CHILD DATABASE DATA OBTAINED :: {}'.format(child_db_data_dict))
                DatabaseUtil.persist_database_data('mysqldb',child_db_data_dict,"6",mid)
                #for each_list in AgentUtil.list_chunks(child_db_data_dict,5):
                #    AgentLogger.debug(AgentLogger.DATABASE, '[DEBUG] CHILD DATABASE DATA OBTAINED :: {}'.format(each_list))
                #    DatabaseUtil.persist_database_data('mysqldb',each_list,"6")
        else:
            AgentLogger.log(AgentLogger.DATABASE, 'no data found for upload')
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while saving obtained result data [dave_save] :: {}'.format(e))
        traceback.print_exc()


# database list discovery can be called in between like process [discover process]
# DMSHandler.execute_action() -> [AgentConstants.CCD (MYSQL_DATABASE)] -> DatabaseUtil.child_database_discover() -> mysql_monitoring.schedule_database_discovery()
# one time task
def schedule_database_discovery(instance):
    try:
        schedule_data_collection(instance,"3")
        AgentLogger.log(AgentLogger.DATABASE,'Received Database Discover Action :: Instance - {}'.format(instance))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while scheduling database discover task :: Error - {}'.format(e))
        traceback.print_exc()

# calls scheduler for the instance that are active and ready for data collection
def start_mysql_data_collection():
    try:
        DB_TYPE         =   AgentConstants.MYSQL_DB
        DB_CONSTANTS    =   AgentConstants.DB_CONSTANTS[DB_TYPE]
        xmlString       =   DatabaseUtil.read_data(DB_CONSTANTS['CONF_FOLDER'],DB_CONSTANTS['NDB_XML_QUERY_FILE_NAME'])

        # kills all previously scheduled mysql tasks [ DATABASE_OBJECT_MAPPER['mysql'] ]
        DatabaseUtil.stop_all_instance(AgentConstants.MYSQL_DB)
        # 0 - basic data
        # 1 - insight data
        # 2 - replica change conf update [one day once]
        # 3 - database child discovery
        # 5 - dummy data collection [basic and child db]
        # 6 - child db data collection
        DatabaseUtil.MYSQL_CONFIG = DatabaseUtil.get_config_parser(DB_CONSTANTS['CONF_FILE'])
        for instance in DatabaseUtil.MYSQL_CONFIG:
            if instance not in ['MYSQL', 'DEFAULT']:
                if DatabaseUtil.MYSQL_CONFIG.get(instance,'enabled') == 'true':
                    #AgentConstants.DATABASE_OBJECT_MAPPER['mysql'][instance] = {}
                    if '-insight' in instance and DatabaseUtil.MYSQL_CONFIG.get(instance,'status') == '0':
                        schedule_data_collection(instance,"1")   # ok   # insight moitor data collection
                    if '-insight' not in instance and DatabaseUtil.MYSQL_CONFIG.get(instance,'status') == '0':
                        schedule_data_collection(instance,"5")    # ok    # basic/child db dummy data collection
                        schedule_data_collection(instance,"0")    # ok    # basic perf monitor data collection
                        schedule_data_collection(instance,"6")    # ok    # child db monitor data collection
                        schedule_data_collection(instance,"2")    # ok    # cluster config data collection
                        pass
                    if '-insight' not in instance and DatabaseUtil.MYSQL_CONFIG.has_option(instance,'discover_database') and DatabaseUtil.MYSQL_CONFIG.get(instance,'discover_database') == 'true' and DatabaseUtil.MYSQL_CONFIG.get(instance,'status') == '0':
                        schedule_data_collection(instance,"3")    # ok    # database list discover task
                        DatabaseUtil.MYSQL_CONFIG.remove_option(instance,'discover_database')
                        pass
                    
                    if DatabaseUtil.MYSQL_CONFIG.has_option(instance,"NDB_status") and DatabaseUtil.MYSQL_CONFIG.get(instance,"NDB_status")=="0" and DatabaseUtil.MYSQL_CONFIG.get(instance,"NDB_enabled")=="true":
                        ndb_obj=NDBCluster.Initializer(instance,xmlString)
                        schedule_data_collection((ndb_obj,instance),"7")  # MySQL NDB Cluster child discovery
                        schedule_data_collection((ndb_obj,instance),"8")  # MySQL NDB Cluster perf data collection
                        schedule_data_collection((ndb_obj,instance),"9")  # MySQL NDB Cluster topology data collection

                else:
                    AgentLogger.log(AgentLogger.DATABASE,'Database - mysql :: Instance - {} not ready for data collection'.format(instance))
            # should check for failed registered instance
        DatabaseUtil.persist_config_parser(DB_CONSTANTS['CONF_FILE'], DatabaseUtil.MYSQL_CONFIG)
        if NDBCluster.getNodeDiscovery()[0]:
            schedule_data_collection(None,'10') # MySQL NDB Cluster node mapping discovery - sends all ipv4 and ipv6 of this machine to plus server. 
        # NDBCluster.initializeAfterAppRegistration()
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while starting all thread mysql data collection :: Error - {}'.format(e))
        traceback.print_exc()

# check mysql dir exist in app and create it, with default SQL configuration instance for discovery
def initialize(rediscover=False):
    try:
        if AgentConstants.PYMYSQL_MODULE!="1":
            AgentLogger.log(AgentLogger.DATABASE,'pymysql not found')
            return

        if DatabaseUtil.setup_config_file(AgentConstants.MYSQL_DB) != True:
            AgentLogger.log(AgentLogger.DATABASE,'config setup failed for mysql monitor')
            return
    
        start_mysql_data_collection()

        # used for file change notifier
        # AgentConstants.MYSQL_INIT = True
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while initializing mysql monitor :: {}'.format(e))
