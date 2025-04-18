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

from com.manageengine.monagent.util import AgentUtil,AppUtil,DatabaseUtil
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants,AppConstants,DatabaseConstants
#from com.manageengine.monagent.database.mysql.DataCollector import MongoDBCollector
from com.manageengine.monagent.scheduler import AgentScheduler

MONGODB_CONFIG = configparser.RawConfigParser()

def register_mongodb_monitor(instance,config,instance_name):
    register_status = False
    app_key = None
    try:
        request_params = AgentUtil.get_default_reg_params()
        request_params.update(instance)
        #AgentLogger.log(AgentLogger.MAIN,'check request param for registering mysql instance monitor :: {}'.format(request_params))
        register_status , app_key = DatabaseUtil.apps_registration(AgentConstants.MONGODB_DB,instance_name,instance,AgentConstants.MONGODB_CONF_FILE,config,request_params)
        AgentLogger.log(AgentLogger.DATABASE,'$$$$$$$$$$$$$$ registration successfull :: App key - {}'.format(app_key))
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while registering postgres monitor :: {} : {}'.format(instance,e))
        traceback.print_exc()
    finally:
        return register_status, app_key

def create_instance_section_from_process(instance_name, mongodb_instance, config):
    try:
        config.add_section(instance_name)
        config.set(instance_name,'host',mongodb_instance['host'])
        config.set(instance_name,'port',mongodb_instance['port'])
        config.set(instance_name,'user','0')
        config.set(instance_name,'password','0')
        config.set(instance_name,'mid','0')
        config.set(instance_name,'enabled','false')

        register_status,app_key = register_mongodb_monitor(mongodb_instance,config,instance_name)

        if register_status and not app_key in ['0', None]:
            AgentLogger.log(AgentLogger.DATABASE,'Database - mongodb :: Instance - {} registered successfully :: App key - {}'.format(instance_name,app_key))
            config.set(instance_name,'mid',app_key)
        else:
            AgentLogger.log(AgentLogger.DATABASE,'Database - mongodb :: Instance - {} not registered from process, hence removing instance :: Process - {}'.format(instance_name,mongodb_instance))
            #config.set(instance_name,'mid','1234')
            config.remove_section(instance_name)
        DatabaseUtil.persist_config_parser(AgentConstants.MONGODB_CONF_FILE, config)

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception mysql monitor not registered :: {}'.format(e))

def discover_mongodb_db():
    try:
        discover_op_list = []
        version = None
        output=subprocess.Popen(AgentConstants.MONGODB_VERSION_COMMAND, shell=True, stdout=subprocess.PIPE).stdout.read().decode("utf-8").splitlines()[0].split()
        pattern = re.compile(r'\d+\.\d+\.\d')
        for each in output:
            if pattern.search(each):
                if "v" in each:
                    version = each.split('v')[1]
                else:
                    version = each
        #output = subprocess.Popen(AgentConstants.MYSQL_PID_COMMAND, shell=True, stdout=subprocess.PIPE).stdout.read().decode("utf-8").splitlines()
        discover_op_list = DatabaseUtil.discover_db_from_process(AgentConstants.MONGODB_DB,AgentConstants.MONGODB_PID_COMMAND,version)
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception in discover_mysql_db initialize :: {}'.format(e))
    finally:
        return discover_op_list

def update_instance_config_data(instance_name, mysql_instance, config):
    try:
        for each in mysql_instance:
            if each in ['user', 'password', 'database_metrics', 'session', 'replication', 'top_query', 'slow_query', 'innodb', 'binlog', 'poll_interval']:
                config.set(instance_name,each,mysql_instance[each])
        DatabaseUtil.persist_config_parser(AgentConstants.MYSQL_CONF_FILE, config)

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while updating instance configurations :: Database - mysql :: Instance -{} :: Error - {}'.format(instance_name,e))
        traceback.print_exc()

    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while updating mysql input data Instance - {} :: Error - {}'.format(instance_name,e))
        traceback.print_exc()

def initialize(rediscover=False):
    try:
        if not os.path.exists(AgentConstants.MONGODB_CONF_FILE) or rediscover:
            AgentLogger.log(AgentLogger.DATABASE,'MongoDB configuration folder not found, Hence creating mongodb config folder')
            DatabaseUtil.create_db_monitoring_dir(AgentConstants.MONGODB_DB,AgentConstants.MONGODB_CONF_FILE)

        global MONGODB_CONFIG
        MONGODB_CONFIG = DatabaseUtil.get_config_parser(AgentConstants.MONGODB_CONF_FILE)
        bool_status, mongodb_instance = DatabaseUtil.check_input_data_file(AgentConstants.MYSQL_INPUT_FILE)
        if mongodb_instance:
            AgentLogger.log(AgentLogger.DATABASE,'mongodb_input file found, adding input configurations to mongodb.cfg')
            mongodb_instance = json.loads(mongodb_instance)
            for single_instance in mongodb_instance:
                send_registration = False
                instance_name = str(single_instance['host'])+'-'+str(single_instance['port'])
                # instance not present [ add configurations and registering directly as basic monitor ]
                if not MONGODB_CONFIG.has_section(instance_name):
                    MONGODB_CONFIG.add_section(instance_name)
                    send_registration = True
                else:
                    # instance already registered, possible actions : [ update configurations / convert free to basic monitor ]
                    if MONGODB_CONFIG.get(instance_name, 'mid') not in ['0', None]:
                        # instance already registered as basic monitor [ update user/password/other options ]
                        if MONGODB_CONFIG.get(instance_name, 'user') not in ['0', None] and MONGODB_CONFIG.get(instance_name, 'password') not in ['0', None]:
                            update_instance_config_data(instance_name, single_instance, MONGODB_CONFIG)
                        # instance registered as free monitor [ updating configurations and converting to basic monitor ]
                        else:
                            send_registration = True
            os.remove(AgentConstants.MYSQL_INPUT_FILE)

        mongodb_instance_list = discover_mongodb_db() if DatabaseUtil.is_discovery_enabled(AgentConstants.MONGODB_DB.upper(), MONGODB_CONFIG) else "disabled"
        AgentLogger.log(AgentLogger.DATABASE,'mongodb check 3')
        if mongodb_instance_list != "disabled":
            for single_instance in mongodb_instance_list:
                instance_name = single_instance['host']+'-'+str(single_instance['port'])
                if not MONGODB_CONFIG.has_section(instance_name):
                    create_instance_section_from_process(instance_name, single_instance, MONGODB_CONFIG)
        else:
            AgentLogger.log(AgentLogger.DATABASE,'auto discover mongodb instance from process running is disabled')
        bool_FileLoaded, mysql_instance = DatabaseUtil.check_input_data_file(AgentConstants.MONGODB_INPUT_FILE)
        DatabaseUtil.persist_config_parser(AgentConstants.MONGODB_CONF_FILE, MONGODB_CONFIG)
    except Exception as e:
        AgentLogger.log(AgentLogger.DATABASE,'Exception while initialize mongodb_monitoring :: {}'.format(e))
        traceback.print_exc()