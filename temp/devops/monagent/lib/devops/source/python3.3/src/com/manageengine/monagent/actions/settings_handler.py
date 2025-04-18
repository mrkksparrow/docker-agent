#$Id$
import traceback
import os
import json 
import com
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.util import AgentUtil, MetricsUtil, eBPFUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil
from com.manageengine.monagent.communication import UdpHandler

def initialize():
    try:
        if os.path.isfile(AgentConstants.AGENT_SETTINGS_FILE):
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(AgentConstants.AGENT_SETTINGS_FILE)
            fileObj.set_dataType('txt')
            fileObj.set_mode('r')
            fileObj.set_dataEncoding('UTF-8')
            bool_toReturn, settings_content = FileUtil.readData(fileObj)
            if bool_toReturn and  settings_content:
                settings_content = settings_content.split('\n')
                settings_str = "|".join(settings_content)
                AgentConstants.IPARAMS = settings_str
        for each,value in AgentConstants.SETTINGS_MAP.items():
            AgentConstants.AGENT_SETTINGS[value["k"]] = "1" if os.path.exists(value["check"]) else "0"
        AgentConstants.AGENT_SETTINGS["prometheus"] = "1" if check_prometheus_settings() else "0"
        AgentConstants.AGENT_SETTINGS["statsd"] = "1" if check_statsd_settings() else "0"
        AgentConstants.AGENT_SETTINGS["ebpf"] = "1" if os.path.exists(AgentConstants.EBPF_EXEC_PATH) else "0"
        AgentConstants.AGENT_SETTINGS["upgrade"] = "1" if not os.path.exists(AgentConstants.UPGRADE_DISABLE_FLAG_FILE) else "0"
        AgentLogger.log(AgentLogger.MAIN,'AGENT SETTINGS :: {}'.format(AgentConstants.AGENT_SETTINGS))
        if os.path.isfile(AgentConstants.PS_UTIL_FLOW_FILE):
            AgentConstants.PS_UTIL_FLOW = True
        FileUtil.deleteFile(AgentConstants.AGENT_SETTINGS_FILE)
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,"Exception while initializing agent settings")
        traceback.print_exc()

def check_prometheus_settings():
    enabled=False
    try:
        if os.path.exists(AgentConstants.PROMETHEUS_INPUT_FILE) or  os.path.exists(AgentConstants.ENABLE_PROMETHEUS_FLAG_FILE):
            enabled=True
        elif os.path.exists(AgentConstants.DISABLE_PROMETHEUS_FLAG_FILE):
            enabled=False
        else:
            if os.path.exists(AgentConstants.PROMETHEUS_CONF_FILE):
                PROMETHEUS_CONFIG=configparser.RawConfigParser()
                PROMETHEUS_CONFIG.read(AgentConstants.PROMETHEUS_CONF_FILE)
                if str(PROMETHEUS_CONFIG.get('PROMETHEUS', 'enabled'))=='true':
                    enabled=True
                elif str(PROMETHEUS_CONFIG.get('PROMETHEUS', 'enabled'))=='false':
                    enabled=False
    except Exception as e:
        traceback.print_exc()
    finally:
        return enabled

def check_statsd_settings():
    enabled=False
    try:
        if os.path.exists(AgentConstants.STATSD_INPUT_FILE) or os.path.exists(AgentConstants.ENABLE_STATSD_FLAG_FILE):
            enabled=True
        elif os.path.exists(AgentConstants.DISABLE_STATSD_FLAG_FILE):
            enabled=False
        else:
            if os.path.exists(AgentConstants.STATSD_CONF_FILE):
                STATSD_CONFIG=configparser.RawConfigParser()
                STATSD_CONFIG.read(AgentConstants.STATSD_CONF_FILE)
                if str(STATSD_CONFIG.get('STATSD', 'enabled'))=='true' or str(STATSD_CONFIG.get('STATSD', 'enabled'))=='1':
                    enabled=True
                elif str(STATSD_CONFIG.get('STATSD', 'enabled'))=='false' or str(STATSD_CONFIG.get('STATSD', 'enabled'))=='0':
                    enabled=False
    except Exception as e:
        traceback.print_exc()
    finally:
        return enabled

def update_settings(dict_from_server,update_settings=True):
    settings_from_server=None
    try:
        if 'settings' in dict_from_server:
            if type(dict_from_server['settings']) == str:
                settings_from_server = json.loads(dict_from_server['settings'])
            else:
                settings_from_server = dict_from_server['settings']
        if update_settings:
            AgentConstants.SERVER_SETTINGS = settings_from_server
        else:
            for setting,setting_val in settings_from_server.items():
                AgentConstants.SERVER_SETTINGS[setting] = setting_val
        AgentLogger.debug(AgentLogger.MAIN,' ######### server settings :: {}'.format(AgentConstants.SERVER_SETTINGS))
       
        if 'proc_dis' in AgentConstants.SERVER_SETTINGS and AgentConstants.SERVER_SETTINGS['proc_dis'] == "1":
            com.manageengine.monagent.collector.DataCollector.discover_process()
        
        if 'log_needed' in AgentConstants.SERVER_SETTINGS and AgentConstants.SERVER_SETTINGS['log_needed'] == '0':
            UdpHandler.SysLogUtil.deleteSyslogConfiguration()

        if 'agent_files_checksum' in dict_from_server:
            AgentConstants.AGENT_FILES_CHECKSUM_LIST = dict_from_server['agent_files_checksum']
            AgentLogger.log(AgentLogger.STDOUT,'list of files for validation check :: {}'.format(AgentConstants.AGENT_FILES_CHECKSUM_LIST))

        if 'w_int' in AgentConstants.SERVER_SETTINGS:
            if AgentUtil.WATCHDOGCONFIG.get('WATCHDOG_PARAMS','WATCHDOG_INTERVAL') != AgentConstants.SERVER_SETTINGS['w_int']:
                AgentLogger.log(AgentLogger.MAIN,'Agent threshold limit check interval change request received  {}'.format(AgentConstants.SERVER_SETTINGS['w_int']))
                with open(AgentConstants.WATCHDOG_CONF_FILE, "w") as conf:
                    AgentUtil.AGENT_CHECK_INTERVAL = int(AgentConstants.SERVER_SETTINGS['w_int'])
                    AgentUtil.WATCHDOGCONFIG.set('WATCHDOG_PARAMS','WATCHDOG_INTERVAL',AgentConstants.SERVER_SETTINGS['w_int'])
                    AgentUtil.WATCHDOGCONFIG.write(conf)
            else:
                AgentLogger.log(AgentLogger.STDOUT,'Agent memory threshold limit {} in the request is already same as the present config'.format(AgentConstants.SERVER_SETTINGS['w_mem']))

        if 'w_cpu' in AgentConstants.SERVER_SETTINGS:
            if AgentUtil.WATCHDOGCONFIG.get('AGENT_THRESHOLD','CPU') != AgentConstants.SERVER_SETTINGS['w_cpu']:
                AgentLogger.log(AgentLogger.MAIN,'Agent CPU threshold limit request received  {}'.format(AgentConstants.SERVER_SETTINGS['w_cpu']))
                with open(AgentConstants.WATCHDOG_CONF_FILE, "w") as conf:
                    AgentUtil.AGENT_CPU_THRESHOLD = float(AgentConstants.SERVER_SETTINGS['w_cpu'])
                    AgentUtil.WATCHDOGCONFIG.set('AGENT_THRESHOLD','CPU',AgentConstants.SERVER_SETTINGS['w_cpu'])
                    AgentUtil.WATCHDOGCONFIG.write(conf)
            else:
                AgentLogger.log(AgentLogger.STDOUT,'Agent CPU threshold limit {} in the request is already same as the present config'.format(AgentConstants.SERVER_SETTINGS['w_cpu']))

        if 'w_mem' in AgentConstants.SERVER_SETTINGS:
            if AgentUtil.WATCHDOGCONFIG.get('AGENT_THRESHOLD','MEMORY') != AgentConstants.SERVER_SETTINGS['w_mem']:
                AgentLogger.log(AgentLogger.MAIN,'Agent memory threshold limit request received  {}'.format(AgentConstants.SERVER_SETTINGS['w_mem']))
                with open(AgentConstants.WATCHDOG_CONF_FILE, "w") as conf:
                    AgentUtil.AGENT_MEMORY_THRESHOLD = float(AgentConstants.SERVER_SETTINGS['w_mem'])
                    AgentUtil.WATCHDOGCONFIG.set('AGENT_THRESHOLD','MEMORY',AgentConstants.SERVER_SETTINGS['w_mem'])
                    AgentUtil.WATCHDOGCONFIG.write(conf)
                AgentUtil.restartWatchdog()
            else:
                AgentLogger.log(AgentLogger.STDOUT,'Agent memory threshold limit {} in the request is already same as the present config'.format(AgentConstants.SERVER_SETTINGS['w_mem']))

        if 'addm_net' in AgentConstants.SERVER_SETTINGS:
            if AgentConstants.SERVER_SETTINGS['addm_net'] == "1":
                AgentUtil.edit_monitorsgroup('ADDM', 'enable')
            elif AgentConstants.SERVER_SETTINGS['addm_net'] == "0":
                AgentUtil.edit_monitorsgroup('ADDM', 'disable')

        if 'addm_ebpf' in AgentConstants.SERVER_SETTINGS:
            if AgentConstants.SERVER_SETTINGS['addm_ebpf'] == "1":
                eBPFUtil.initialize()
        
        if AgentConstants.DMS in AgentConstants.SERVER_SETTINGS:
            if AgentUtil.is_module_enabled(AgentConstants.DMS):
                dms_websocket.initialize()
            else:
                dms_websocket.stop_dms()
        
        if AgentConstants.UPT in AgentConstants.SERVER_SETTINGS:
            if AgentUtil.is_module_enabled("uptime"):
                AgentConstants.UPTIME_MONITORING="true"
            else:
                AgentConstants.UPTIME_MONITORING="false"
    except Exception as e:
        traceback.print_exc()
        
        
initialize()
