# $Id$
import os
import sys
import shutil
import time
import threading
import traceback
import json
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser
from datetime import datetime

import com
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.security import AgentCrypt
from . import AgentUtil

statsd_util_obj = None

STATSD_CONFIG=configparser.RawConfigParser()
PROMETHEUS_CONFIG=configparser.RawConfigParser()

def initialize():
    try:
        if AgentUtil.is_module_enabled(AgentConstants.METRICS_SETTING):
            global statsd_util_obj
            statsd_util_obj=StatsDUtil()
            create_metric_config_files()
            STATSD_CONFIG.read(AgentConstants.STATSD_CONF_FILE)
            PROMETHEUS_CONFIG.read(AgentConstants.PROMETHEUS_CONF_FILE)
            if check_metrics_file(AgentConstants.PROMETHEUS_INPUT_FILE):
                write_prometheus_config_file()
            if check_metrics_file(AgentConstants.EDIT_PROMETHEUS_SCRAPE_INTERVAL):
                edit_prometheus_scrape_interval()
            if check_metrics_file(AgentConstants.STATSD_INPUT_FILE):
                statsd_util_obj.write_statsd_config_file()
            if check_metrics_file(AgentConstants.REMOVE_PROMETHEUS_INSTANCE):
                remove_prometheus_instance()
            check_metrics_flag_file()
            AgentConstants.METRICS_ENABLED=check_metric_enabled()
            if AgentConstants.METRICS_ENABLED:
                statsd_util_obj.executor(AgentConstants.METRICS_RESTART_COMMAND)
        AgentLogger.log(AgentLogger.MAIN,'Metrics Status :: {}'.format(AgentConstants.METRICS_ENABLED))
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Metrics enabling excepton {}'.format(e))
        AgentLogger.log(AgentLogger.STDOUT,' {}'.format(traceback.print_exc()))

def terminate_agent():
    try:
        if AgentConstants.METRICS_ENABLED:
            statsd_util_obj.kill()
            statsd_util_obj.statsd_command_executor(AgentConstants.METRICS_STOP_COMMAND)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, "Error while terminating metrics agent :: {}".format(e))
        traceback.print_exc()

def create_metric_config_files():
    try:
        if not os.path.exists(AgentConstants.METRICS_WORKING_DIRECTORY):
            os.mkdir(AgentConstants.METRICS_WORKING_DIRECTORY)
            shutil.copyfile(AgentConstants.METRICS_AGENT_TEMP_CONF_FILE,AgentConstants.METRICS_AGENT_CONF_FILE)
        for (application, config) in AgentConstants.METRICS_APPLICATIONS.items():
            if not os.path.exists(config['working_dir']):
                os.mkdir(config['working_dir'])
                shutil.copyfile(config['temp_conf_file'],config['conf_file'])
    except Exception as e:
        traceback.print_exc()
    
def check_metric_enabled():
    is_active=False
    try:
        for (application, config) in AgentConstants.METRICS_APPLICATIONS.items():
            CONFIG_PARSER = configparser.RawConfigParser()
            CONFIG_PARSER.read(config['conf_file'])
            if str(CONFIG_PARSER.get(application,'enabled'))=='true' or str(CONFIG_PARSER.get(application,'enabled'))=='1':
                is_active=True
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, "Error while getting metric check :: {}".format(e))
        traceback.print_exc()
    finally:
        return is_active

def delete_prometheus_instance(instance):
    try:
        PROMETHEUS_CONFIG.set(instance, 'status', '3')
        persit_prometheus_info()
        statsd_util_obj.executor(AgentConstants.METRICS_RESTART_COMMAND)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, "Error while deleting prometheus instance :: {}".format(e))
        traceback.print_exc()

def suspend_prometheus_instance(instance):
    try:
        PROMETHEUS_CONFIG.set(instance, 'status', '5')
        persit_prometheus_info()
        statsd_util_obj.executor(AgentConstants.METRICS_RESTART_COMMAND)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, "Error while suspend prometheus instance :: {}".format(e))
        traceback.print_exc()

def remove_dc_zips():
    try:
        for the_file in os.listdir(AgentConstants.METRICS_DATA_ZIP_DIRECTORY):
            file_path = os.path.join(AgentConstants.METRICS_DATA_ZIP_DIRECTORY, the_file)
            try:
                if os.path.isfile(file_path):
                    AgentLogger.log(AgentLogger.STDOUT,"Deleting metrics DC zips :: {}".format(file_path))
                    os.remove(file_path)
            except Exception as e:
                AgentLogger.log(AgentLogger.STDOUT,"Exception while deleting metrics DC zips :: {}".format(e))
                traceback.print_exc()
    except Exception as e:
        traceback.print_exc()

def activate_prometheus_instance(instance):
    try:
        PROMETHEUS_CONFIG.set(instance, 'status', '0')
        persit_prometheus_info()
        statsd_util_obj.executor(AgentConstants.METRICS_RESTART_COMMAND)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, "Error while avtivating prometheus instance :: {}".format(e))
        traceback.print_exc()

def persit_prometheus_info():
    try:
        with open(AgentConstants.PROMETHEUS_CONF_FILE, 'w') as prom_configfile:
            PROMETHEUS_CONFIG.write(prom_configfile)
        prom_configfile.close()
        AgentLogger.log(AgentLogger.STDOUT,'Prometheus Info persisted')
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, "Error while persisting PROMETHEUS_CONFIG info in prometheus.cfg :: {}".format(e))
        traceback.print_exc()

def check_metrics_flag_file():
    is_prom=False
    is_stat=False
    try:
        if check_metrics_file(AgentConstants.ENABLE_PROMETHEUS_FLAG_FILE):
            PROMETHEUS_CONFIG.set('PROMETHEUS', 'enabled', 'true')
            os.remove(AgentConstants.ENABLE_PROMETHEUS_FLAG_FILE)
            is_prom=True
        if check_metrics_file(AgentConstants.DISABLE_PROMETHEUS_FLAG_FILE):
            PROMETHEUS_CONFIG.set('PROMETHEUS', 'enabled', 'false')
            os.remove(AgentConstants.DISABLE_PROMETHEUS_FLAG_FILE)
            is_prom=True
        if check_metrics_file(AgentConstants.ENABLE_STATSD_FLAG_FILE):
            STATSD_CONFIG.set('STATSD', 'enabled', 'true')
            os.remove(AgentConstants.ENABLE_STATSD_FLAG_FILE)
            is_stat=True
        if check_metrics_file(AgentConstants.DISABLE_STATSD_FLAG_FILE):
            STATSD_CONFIG.set('STATSD', 'enabled', 'false')
            os.remove(AgentConstants.DISABLE_STATSD_FLAG_FILE)
            is_stat=True
        if is_prom:
            persit_prometheus_info()
        if is_stat:
            statsd_util_obj.persist_statsd_info()
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, "Error while checking metrics flag file :: {}".format(e))
        traceback.print_exc()

def check_metrics_file(input_file):
    is_present=False
    try:
        if os.path.exists(input_file):
            is_present=True
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, "Error while checking file :: {0} :: {1}".format(input_file, e))
        traceback.print_exc()
    finally:
        return is_present

def remove_prometheus_instance ():
    try:
        bool_FileLoaded, prometheus_instance = AgentUtil.loadDataFromFile(AgentConstants.REMOVE_PROMETHEUS_INSTANCE)
        if prometheus_instance:
            for instance in prometheus_instance:
                PROMETHEUS_CONFIG.remove_section(instance['instance_name'])
            persit_prometheus_info()
        os.remove(AgentConstants.REMOVE_PROMETHEUS_INSTANCE)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, "Error while removing instance in prometheus.cfg :: {}".format(e))
        traceback.print_exc()

def edit_prometheus_scrape_interval ():
    try:
        bool_FileLoaded, prometheus_instance = AgentUtil.loadRawDataFromFile(AgentConstants.EDIT_PROMETHEUS_SCRAPE_INTERVAL)
        if prometheus_instance:
            if ":" in str(prometheus_instance):
                instance = (prometheus_instance.split(":")[0]).strip()
                value = (prometheus_instance.split(":")[1]).strip()
            else:
                instance = "PROMETHEUS"
                value = str(prometheus_instance).strip()
            AgentLogger.log(AgentLogger.STDOUT, "Scrape Interval input for change :: {} : {}".format(instance, value))
            if PROMETHEUS_CONFIG.has_section(instance):
                if PROMETHEUS_CONFIG.has_option(instance, "scrape_interval"):
                    scrap_interval = PROMETHEUS_CONFIG.get(instance,'scrape_interval')
                    if str(scrap_interval) != str(value):
                        PROMETHEUS_CONFIG.set(instance, 'scrape_interval', str(value))
                        persit_prometheus_info()
                    else:
                        AgentLogger.log(AgentLogger.STDOUT, "Scrape Interval already :: {}".format(scrap_interval))
                else:
                    PROMETHEUS_CONFIG.set(instance, 'scrape_interval', str(value))
                    persit_prometheus_info()
            else:
                AgentLogger.log(AgentLogger.STDOUT, "Prometheus does not have an Instance :: {}".format(instance))
        os.remove(AgentConstants.EDIT_PROMETHEUS_SCRAPE_INTERVAL)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, "Error while changing scrape interval in prometheus.cfg :: {}".format(e))
        traceback.print_exc()

def write_prometheus_config_file():
    try:
        bool_FileLoaded, prometheus_instance = AgentUtil.loadDataFromFile(AgentConstants.PROMETHEUS_INPUT_FILE)
        if prometheus_instance:
            PROMETHEUS_CONFIG.set('PROMETHEUS', 'enabled', 'true')
            AgentLogger.log(AgentLogger.PLUGINS,'Prometheus Enabled for Data Collection ')
            for instance in prometheus_instance:
                PROMETHEUS_CONFIG.add_section(instance['instance_name'])
                if 'prometheus_url' in instance.keys():
                    PROMETHEUS_CONFIG.set(instance['instance_name'], 'prometheus_url', instance['prometheus_url'])
                elif all(each in instance for each in ['target_hostname', 'target_port', 'target_metrics_api', 'target_protocol']):
                    url=str(instance['target_protocol']+"://"+instance['target_hostname']+":"+instance['target_port']+"/"+instance['target_metrics_api'])
                    PROMETHEUS_CONFIG.set(instance['instance_name'], 'prometheus_url', url)
                else:
                    AgentLogger.log(AgentLogger.MAIN, "========================== Prometheus Input Param is not given Properly for instance ========================== :: {}".format(instance))
                    PROMETHEUS_CONFIG.remove_section(instance['instance_name'])
                    continue
                if 'scrape_interval' in instance.keys():
                    PROMETHEUS_CONFIG.set(instance['instance_name'], 'scrape_interval', instance['scrape_interval'])
                if 'timeout' in instance.keys():
                    PROMETHEUS_CONFIG.set(instance['instance_name'], 'timeout', instance['timeout'])
                PROMETHEUS_CONFIG.set(instance['instance_name'], 'include_pattern', instance['include_pattern'])
            persit_prometheus_info()
        os.remove(AgentConstants.PROMETHEUS_INPUT_FILE)

    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, "Error while writing config in prometheus.cfg :: {}".format(e))
        traceback.print_exc()

def stop_prometheus_monitoring():
    try:
        PROMETHEUS_CONFIG.read(AgentConstants.PROMETHEUS_CONF_FILE)
        if PROMETHEUS_CONFIG.has_option('PROMETHEUS', 'enabled') and str(PROMETHEUS_CONFIG.get('PROMETHEUS', 'enabled'))=='true':
            PROMETHEUS_CONFIG.set('PROMETHEUS', 'enabled','false')
            persit_prometheus_info()
        if not check_metric_enabled():
            statsd_util_obj.executor(AgentConstants.METRICS_STOP_COMMAND)
        else:
            statsd_util_obj.statsd_command_executor(AgentConstants.METRICS_RESTART_COMMAND)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Stoping Prometheus exception {}'.format(e))
        traceback.print_exc()

def start_prometheus_monitoring():
    try:
        PROMETHEUS_CONFIG.read(AgentConstants.PROMETHEUS_CONF_FILE)
        if PROMETHEUS_CONFIG.has_option('PROMETHEUS', 'enabled') and str(PROMETHEUS_CONFIG.get('PROMETHEUS', 'enabled'))=='false':
            PROMETHEUS_CONFIG.set('PROMETHEUS', 'enabled','true')
            persit_prometheus_info()
            statsd_util_obj.statsd_command_executor(AgentConstants.METRICS_RESTART_COMMAND)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'starting Prometheus exception {}'.format(e))
        traceback.print_exc()


class StatsDUtil():
    __instance = None
    def __init__(self):
        pass
    
    def init(self):
        self.__instance = statsd.StatsClient('localhost', 8125)
        AgentLogger.log(AgentLogger.PLUGINS,'StatsD Client init :{}\n'.format(self.__instance))
    
    def kill(self):
        try:
            if self.__instance:
                AgentLogger.log(AgentLogger.PLUGINS,'Killing StatsD Client :{}\n'.format(self.__instance))
                self.__instance.close()
        except Exception as e:
            traceback.print_exc()
    
    def get_statsd_instance(self):
        return self.__instance
    
    def enable_statsd_monitoring(self):
        try:
            if STATSD_CONFIG.has_option('STATSD', 'enabled') and str(STATSD_CONFIG.get('STATSD', 'enabled'))!='true':
                STATSD_CONFIG.set('STATSD', 'enabled', 'true')
                self.persist_statsd_info()
                self.executor(AgentConstants.METRICS_RESTART_COMMAND)
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,'Exception while Enabling statsd  {} \n'.format(e))
            traceback.print_exc()
            
    def disable_statsd_monitoring(self):
        try:
            if STATSD_CONFIG.has_option('STATSD', 'enabled') and str(STATSD_CONFIG.get('STATSD', 'enabled'))=='true':
                STATSD_CONFIG.set('STATSD', 'enabled','false')
                self.persist_statsd_info()
                self.executor(AgentConstants.METRICS_RESTART_COMMAND)
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,'Exception while Disabling statsd  {} \n'.format(e))
            traceback.print_exc()
    
    def write_statsd_config_file(self):
        try:
            bool_FileLoaded, statsd_instance = AgentUtil.loadDataFromFile(AgentConstants.STATSD_INPUT_FILE)
            if statsd_instance:
                STATSD_CONFIG.set('STATSD', 'enabled', 'true')
                AgentLogger.log(AgentLogger.PLUGINS,'Statsd Enabled for Data Collection ')
                for instance in statsd_instance:
                    if all(each in instance for each in ['hostname', 'port']):
                        STATSD_CONFIG.set('STATSD', 'hostname', instance['hostname'])
                        STATSD_CONFIG.set('STATSD', 'port', instance['port'])
                    else:
                        AgentLogger.log(AgentLogger.MAIN, "========================== Hostaname and Port not given for Statsd ========================== :: {}".format(instance))
                        continue
                    if 'push_interval' in instance.keys():
                        STATSD_CONFIG.set('STATSD', 'push_interval', instance['push_interval'])
                    if 'flush_interval' in instance.keys():
                        STATSD_CONFIG.set('STATSD', 'flush_interval', instance['flush_interval'])
                    if 'metrics_limit' in instance.keys():
                        STATSD_CONFIG.set('STATSD', 'metrics_limit', instance['metrics_limit'])
                    if 'zip_metrics_limit' in instance.keys():
                        STATSD_CONFIG.set('STATSD', 'zip_metrics_limit', instance['zip_metrics_limit'])
                    if 'gauge_reset' in instance.keys():
                        STATSD_CONFIG.set('STATSD', 'gauge_reset', instance['gauge_reset'])
                self.persist_statsd_info()
            os.remove(AgentConstants.STATSD_INPUT_FILE)

        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT, "Error while writing config in statsd.cfg :: {}".format(e))
            traceback.print_exc()

    def start_statsd(self):
        self.executor(AgentConstants.METRICS_START_COMMAND)
    
    def stop_statsd(self):
        self.executor(AgentConstants.METRICS_STOP_COMMAND)
    
    def update_statsd_config(self,statsd_config):
        try:
            self.stop_statsd()
            time.sleep(2)
            for section_name , section_map in statsd_config.items():
                for k , v in section_map.items():
                    STATSD_CONFIG.set(section_name,k,v)
            with open(AgentConstants.STATSD_CONF_FILE,'w') as config:
                STATSD_CONFIG.write(config)            
            self.start_statsd()
        except Exception as e:
            traceback.print_exc()
    
    def statsd_command_executor(self,command):
        tuple_command_status='Failed'
        try:
            executorobj = AgentUtil.Executor()
            executorobj.setTimeout(30)
            executorobj.setLogger(AgentLogger.STDOUT)
            executorobj.setCommand(command)
            if AgentConstants.PYTHON_VERSION < 3 or os.path.exists(AgentConstants.USE_DC_CMD_EXECUTOR):
                AgentLogger.debug(AgentLogger.STDOUT,' using dc command executor')
                executorobj.executeCommand()
            else:
                executorobj.execute_cmd_with_tmp_file_buffer()
            tuple_command_status = executorobj.isSuccess()
            stdout = executorobj.getStdOut()
            stderr = executorobj.getStdErr()
            retVal = executorobj.getReturnCode()
            AgentLogger.log(AgentLogger.STDOUT,'out stream -- {}'.format(stdout))
            AgentLogger.log(AgentLogger.STDOUT,'err stream -- {}'.format(stderr))
            AgentLogger.log(AgentLogger.STDOUT,'exit code -- {}'.format(retVal))
            AgentLogger.log(AgentLogger.STDOUT,'command for execution -- {} --- command Status -- {}'.format(command.split(),tuple_command_status))                                  
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,'Exception while handling statsd_command_executor   --- command  {} --- command Status {} \n'.format(command,tuple_command_status))
            traceback.print_exc()
            
    def executor(self,str_command):
        try:
            obj=threading.Thread(target=self.statsd_command_executor,args=(str_command,))
            obj.start()
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,'Exception while executing command in executor %s',e)
            traceback.print_exc()
    
    def persist_statsd_info(self):
        ispersists_success=False
        try:
            STATSD_CONFIG.set('STATSD','source', AgentConstants.HOST_NAME)
            with open(AgentConstants.STATSD_CONF_FILE,'w') as config:
                STATSD_CONFIG.write(config)
            AgentLogger.log(AgentLogger.STDOUT,'Statsd Info persisted')
            ispersists_success=True
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,'Exception while persisting statsd info  {} \n'.format(e))
            traceback.print_exc()
        finally:
             return ispersists_success
            
#initialize()
