# $Id$

import traceback
import threading
import time, os
import zipfile
from six.moves.urllib.parse import urlencode
import json,sys
import socket
import platform
import com
from com.manageengine.monagent import AgentConstants,AppConstants,module_object_holder
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil, AgentBuffer, AppUtil, MetricsUtil, DatabaseUtil, eBPFUtil
from com.manageengine.monagent.database_executor.mysql import mysql_monitoring
from com.manageengine.monagent.util.rca.RcaHandler import RcaUtil 
from com.manageengine.monagent.communication import applog as applog_communication
from com.manageengine.monagent.util.AgentUtil import FileUtil
from com.manageengine.monagent.communication import CommunicationHandler, AgentStatusHandler, UdpHandler, BasicClientHandler , RealTimeMonitoring
from com.manageengine.monagent.collector import DataCollector, DataConsolidator , server_inventory
from com.manageengine.monagent.docker_old import DockerAgent
from com.manageengine.monagent.scheduler import AgentScheduler 
from com.manageengine.monagent.upgrade import AgentUpgrader
from com.manageengine.monagent.network.AgentPingHandler import PingUtil
from com.manageengine.monagent.communication.UdpHandler import SysLogUtil
from com.manageengine.monagent.actions import AgentAction,checksum_validator
from com.manageengine.monagent.module_controller import installer
from com.manageengine.monagent.framework.worker import worker_v1 as framework_worker

from com.manageengine.monagent.database_executor.mysql import NDBCluster
from com.manageengine.monagent.database_executor.postgres import postgres_monitoring
from com.manageengine.monagent.database_executor.oracle import oracledb_monitoring
from com.manageengine.monagent.container import container_monitoring

if platform.system() == AgentConstants.LINUX_OS:
    from com.manageengine.monagent.hardware import HardwareMonitoring
    from com.manageengine.monagent.kubernetes.SettingsHandler import KubeActions as KubeActionsHandler
    from com.manageengine.monagent.kubernetes import KubeGlobal
    from com.manageengine.monagent.container import container_management
    if AgentConstants.WEBSOCKET_MODULE:
        from . import dms_websocket
else:
    AgentLogger.log(AgentLogger.MAIN,'OS is not Linux :: {}'.format(platform.system()))
    
DMS = None
WMS_REQID_SERVED_BUFFER = AgentBuffer.getBuffer(AgentConstants.WMS_REQID_SERVED_BUFFER,AgentConstants.MAX_WMS_REQID_BUFFER)

def initialize():    
    global DMS
    DMS = DMSThread()
    DMS.setDaemon(True)
    DMS.start()

class DMSThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.name = 'DMSThread'
        self.isRegisteredWithDMS = False
        self.int_exceptionWait = 60
        self.int_requestEventsExceptionWait = 30
        self.__kill = False
    def stop(self):
        self.__kill=True
    def run(self):
        try:
            while not AgentUtil.TERMINATE_AGENT and not self.__kill:
                try:
                    if self.isRegisteredWithDMS:
                        if not self.requestEvents():
                            AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(self.int_requestEventsExceptionWait)#Just a temporary wait for preventing infinite exception loop.
                    else:
                        if not self.registerWithDMS():
                            AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(self.int_exceptionWait)
                except Exception as e:                                        
                    AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(self.int_exceptionWait)#Just a temporary wait for preventing infinite exception loop. 
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.MAIN], ' *************************** Exception while executing the DMS thread. Exiting DMS thread!!! *************************** '+ repr(e) + '\n')
            traceback.print_exc()
    def registerWithDMS(self):   
        bool_toReturn = True    
        try:
            AgentLogger.debug(AgentLogger.MAIN, '================================= REAL TIME MESSAGING REGISTRATION =================================')
            str_url = None
            str_servlet = AgentConstants.DMS_REGISTER_SERVLET
            dict_requestParameters      =   {
            'prd'   :   AgentConstants.DMS_PRODUCT_CODE,
            'zuid'  :   AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),
            'key'   :   AgentConstants.CUSTOMER_ID,
            'config':   AgentConstants.DMS_CONFIG_VALUE,
            }
            if not dict_requestParameters == None:
                str_requestParameters = urlencode(dict_requestParameters)
                str_url = str_servlet + str_requestParameters  
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.STDOUT)
            requestInfo.set_host(AgentConstants.DMS_SERVER)
            requestInfo.set_port(AgentConstants.DMS_PORT)
            requestInfo.set_method(AgentConstants.HTTP_GET)
            requestInfo.set_responseAction(self.parseDMSResponse)
            requestInfo.set_timeout(AgentConstants.REQUEST_DMS_TIMEOUT)
            requestInfo.add_header('Host', AgentConstants.DMS_SERVER)
            requestInfo.set_url(str_url)
            bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
            AgentLogger.debug(AgentLogger.MAIN,'DMS Response -- {0}'.format(bool_toReturn))
            AgentLogger.debug(AgentLogger.MAIN,'DMS Error Code -- {0}'.format(int_errorCode))
            AgentLogger.debug(AgentLogger.MAIN,'DMS Response Data -- {0}'.format(dict_responseData))
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.MAIN,AgentLogger.CRITICAL], 'REAL TIME MESSAGING REGISTRATION : *************************** Exception - DMS Registration ************************** '+ repr(e) + '\n')
            traceback.print_exc()
            raise e
        return bool_toReturn
            
    def requestEvents(self):
        bool_toReturn = True
        try:
            AgentLogger.debug(AgentLogger.MAIN, '================================= REQUESTING DMS FOR EVENTS =================================')
            str_url = None
            str_servlet = AgentConstants.DMS_REQUEST_EVENTS_SERVLET
            dict_requestParameters      =   {
            'c'  :   AgentConstants.DMS_PRODUCT_CODE+':'+ AgentConstants.DMS_UID,
            'i'  :   AgentConstants.DMS_SID,
            'key':   AgentConstants.CUSTOMER_ID,
            'a'  :   str(int(time.time())),
            }
            if not dict_requestParameters == None:
                str_requestParameters = urlencode(dict_requestParameters)
                str_url = str_servlet + str_requestParameters  
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.STDOUT)
            requestInfo.set_host(AgentConstants.DMS_SERVER)
            requestInfo.set_port(AgentConstants.DMS_PORT)
            requestInfo.set_method(AgentConstants.HTTP_GET)
            requestInfo.set_responseAction(self.parseDMSResponse)
            requestInfo.set_timeout(AgentConstants.REQUEST_DMS_TIMEOUT)
            requestInfo.add_header('Host', AgentConstants.DMS_SERVER)
            requestInfo.set_url(str_url)
            bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
            AgentLogger.debug(AgentLogger.MAIN,'DMS Event Response -- {0}'.format(bool_toReturn))
            AgentLogger.debug(AgentLogger.MAIN,'DMS Event Error Code -- {0}'.format(int_errorCode))
            AgentLogger.debug(AgentLogger.MAIN,'DMS Event Response Data -- {0}'.format(dict_responseData))
            if isinstance(int_errorCode, socket.timeout):
                bool_toReturn = True
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.MAIN], 'DMS REQUEST EVENTS : *************************** Exception while requesting dms for events ************************** '+ repr(e) + '\n')
            traceback.print_exc()
            raise e
        return bool_toReturn
    
    def parseDMSResponse(self, requestInfo, str_responseData):        
        try:
            AgentLogger.debug(AgentLogger.MAIN, 'DMS RESPONSE : Response from DMS '+repr(str_responseData))
            msgs = json.loads(str_responseData,'UTF-8')
            for data in msgs:
                mtype = data.get("mtype")
                if mtype == "0": # ACKNOWLEDGEMENT
                    msg = data["msg"]
                    AgentConstants.DMS_UID = msg["uid"]
                    AgentConstants.DMS_SID = msg["sid"]
                    AgentConstants.DMS_NNAME   = msg["nname"]
                    AgentConstants.DMS_ZUID = msg["zuid"]
                    AgentLogger.log(AgentLogger.MAIN, 'Real Time Messaging Registration - Success\n')
                    AgentLogger.log(AgentLogger.STDOUT, '================================= REAL TIME MESSAGING REGISTRATION SUCCESS =================================\n')
                    self.isRegisteredWithDMS = True
                elif mtype == "-2": # AUTH FAILURE
                    AgentLogger.log([AgentLogger.MAIN,AgentLogger.CRITICAL], '************************** REAL TIME MESSAGING - AUTHENTICATION FAILURE **************************\n')
                elif mtype == "-5": # AUTH FAILURE
                    AgentLogger.log([AgentLogger.MAIN,AgentLogger.CRITICAL], '************************** REAL TIME MESSAGING - UNAUTHORIZED KEY **************************\n')
                elif mtype == "-1": # RECONNECT
                    AgentLogger.log([AgentLogger.MAIN,AgentLogger.CRITICAL], '************************** REAL TIME MESSAGING - RECONNECT SIGNAL **************************\n')
                    self.isRegisteredWithDMS = False
                    self.registerWithDMS()
                elif mtype == "650": # DEVICE MESG
                    try:
                        msg = data['msg']
                        operation = msg['opr']         
                        data = msg['data']
                        content = data['content']
                        AgentLogger.debug(AgentLogger.STDOUT, 'DMS - content type : '+repr(type(content))+' Content : '+repr(content))
                        if type(content) is not dict:
                            requestList = json.loads(content, 'UTF-8')['RequestList']
                        else:
                            requestList = content['RequestList']
                        processTasks(requestList)
                    except Exception as e:
                        AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], '************************** Exception while parsing DMS EVENT ************************** :' + repr(e))
                        traceback.print_exc()                        
                        continue                    
                else:
                    AgentLogger.log([AgentLogger.MAIN,AgentLogger.CRITICAL], '************************** DMS - UNKNOWN MTYPE **************************' + str(data))                    
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL], 'DMS REGISTRATION : *************************** Exception while parsing response from the DMS ************************** '+ repr(e))
            traceback.print_exc()
            bool_isSuccess = False
        finally:
            str_responseData = None

def processTasks(list_tasks):
    for dict_task in list_tasks:
        perform_dms_task = True
        request_id = str(dict_task.get("AGENT_REQUEST_ID", ""))
        str_requestType = str(dict_task.get("REQUEST_TYPE", ""))
        if request_id not in AgentConstants.REQUEST_ID_VS_TIME_DICT:
            AgentConstants.REQUEST_ID_VS_TIME_DICT[request_id] = AgentUtil.getCurrentTimeInMillis()
        else:
            current_time = AgentUtil.getCurrentTimeInMillis()
            id_vs_dict_time = AgentConstants.REQUEST_ID_VS_TIME_DICT[request_id]
            if current_time - id_vs_dict_time < AgentConstants.DMS_TASK_IGNORE_TIME:
                perform_dms_task = False
            else:
                AgentConstants.REQUEST_ID_VS_TIME_DICT[request_id] = current_time
        boolPreAck = False
        try:
            agentKey = dict_task['AGENT_KEY']
            if agentKey==AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'):                
                if perform_dms_task:
                    str_requestType = str(dict_task['REQUEST_TYPE'])
                    WMS_REQID_SERVED_BUFFER.add(str(dict_task['AGENT_REQUEST_ID']))
                    AgentLogger.log(AgentLogger.MAIN,'Request Type :: {} | Request ID :: {}'.format(str_requestType,request_id))
                    execute_action(str_requestType,dict_task)
                else:
                    AgentLogger.log(AgentLogger.MAIN, 'same dms action received from server - {0} with request id - {1}'.format(str_requestType,request_id)+'\n')
            else:
                AgentLogger.log(AgentLogger.MAIN,'Mismatch in agent key received - '+agentKey+' key present in config - '+AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'))
        except Exception as e:
            AgentLogger.log([AgentLogger.MAIN,AgentLogger.STDERR], ' *************************** Exception while processing tasks from the server *************************** '+ repr(e) + '\n')
            traceback.print_exc()

def execute_action(str_requestType,dict_task=None):
    try:
        if 'AGENT_REQUEST_ID' in dict_task:
            sendACK(dict_task['AGENT_REQUEST_ID'])
        if str_requestType == AgentConstants.INITIATE_PATCH_UPGRADE:
            upgrade_props = {}
            if 'up_params' in dict_task:
                upgrade_props = dict_task['up_params']
            if not AgentConstants.IS_VENV_ACTIVATED:
                AgentUpgrader.handleUpgrade(upgrade_props,True)
            else:
                AgentLogger.log(AgentLogger.MAIN, "Upgrade module initialized for hybrid agent")
                AgentUpgrader.handle_venv_upgrade(True,upgrade_props)
        elif str_requestType == AgentConstants.INITIATE_AGENT_UPGRADE:
            upgrade_props = {}
            if 'up_params' in dict_task:
                upgrade_props = dict_task['up_params']
            if not AgentConstants.IS_VENV_ACTIVATED: 
                AgentUpgrader.handleUpgrade(upgrade_props)
            else:
                AgentLogger.log(AgentLogger.MAIN, "Upgrade module initialized for hybrid agent")
                AgentUpgrader.handle_venv_upgrade(False,upgrade_props)
        elif str_requestType == AgentConstants.APPLOG_INSTALL_AGENT:
            applog_communication.install(dict_task)
        elif str_requestType == AgentConstants.APPLOG_UPGRADE_AGENT:
            applog_communication.upgrade(dict_task)
        elif str_requestType == AgentConstants.INSTALL_EBPF_AGENT:
            eBPFUtil.upgrade_ebpf_agent(dict_task)
        elif str_requestType == AgentConstants.UPGRADE_EBPF_AGENT:
            eBPFUtil.upgrade_ebpf_agent(dict_task)
        elif str_requestType == AgentConstants.STOP_EBPF_AGENT:
            eBPFUtil.stop()
        elif str_requestType == AgentConstants.START_EBPF_AGENT:
            eBPFUtil.initialize()
        elif str_requestType == AgentConstants.UNINSTALL_EBPF_AGENT:
            eBPFUtil.remove_ebpf_agent()
        elif str_requestType == AgentConstants.APPLOG_START:
            applog_communication.start()
        elif str_requestType == AgentConstants.APPLOG_STOP:
            applog_communication.stop()
        elif str_requestType == AgentConstants.APPLOG_RESTART:
            applog_communication.restart()
        elif str_requestType == AgentConstants.APPLOG_ENABLE:
            applog_communication.enable()
            applog_communication.start()
        elif str_requestType == AgentConstants.APPLOG_DISABLE:
            applog_communication.disable()
            applog_communication.stop()
        elif str_requestType.startswith('APPLOG_'):
            applog_communication.configure(dict_task)
        elif str_requestType == AgentConstants.SUSPEND_MONITOR:
            app_type = dict_task.get("APP_NAME", None)
            instance_name = dict_task.get("instance_name", None)
            AgentLogger.log(AgentLogger.STDOUT, "Suspend Monitor :: {} : {}".format(app_type,instance_name))
            if app_type == AgentConstants.STATSD:
                MetricsUtil.statsd_util_obj.disable_statsd_monitoring()
            elif app_type == AgentConstants.PROMETHEUS:
                if instance_name:
                    MetricsUtil.suspend_prometheus_instance(instance_name)
        elif str_requestType == AgentConstants.ACTIVATE_MONITOR:
            app_type = dict_task.get("APP_NAME", None)
            instance_name = dict_task.get("instance_name", None)
            AgentLogger.log(AgentLogger.STDOUT, "Activate Monitor :: {} : {}".format(app_type,instance_name))
            if app_type == AgentConstants.STATSD:
                MetricsUtil.statsd_util_obj.enable_statsd_monitoring()
            elif app_type == AgentConstants.PROMETHEUS:
                if instance_name:
                    MetricsUtil.activate_prometheus_instance(instance_name)
        elif str_requestType == AgentConstants.DELETE_MONITOR:
            app_type = dict_task.get("APP_NAME", None)
            instance_name = dict_task.get("instance_name", None)
            AgentLogger.log(AgentLogger.STDOUT, "Delete Monitor :: {} : {}".format(app_type,instance_name))
            if app_type == AgentConstants.STATSD:
                MetricsUtil.statsd_util_obj.disable_statsd_monitoring()
            elif app_type == AgentConstants.PROMETHEUS:
                if instance_name:
                    MetricsUtil.delete_prometheus_instance(instance_name)
        elif str_requestType == AgentConstants.START_WATCHDOG:
            AgentAction.startWatchdog(dict_task)
        elif str_requestType == AgentConstants.PLUGIN_DEPLOY:
            AgentAction.deployPlugin(dict_task)
        elif str_requestType == AgentConstants.PLUGIN_DISABLE:
            module_object_holder.plugins_util.disablePlugins(dict_task)
        elif str_requestType == AgentConstants.PLUGIN_ENABLE:
            module_object_holder.plugins_util.enablePlugins(dict_task)
        elif str_requestType == AgentConstants.DELETE_PLUGIN:
            module_object_holder.plugins_util.CleanPluginFolder(dict_task)
        elif str_requestType == AgentConstants.PLUGIN_COUNT_CONFIGURE:
            module_object_holder.plugins_util.configurePluginCount(dict_task)
        elif str_requestType == AgentConstants.INITIATE_PEER_SERVICE:
            PingUtil.getPeerCheck()
        elif str_requestType == AgentConstants.PEER_STOP:
            PingUtil.deletePeerSchedule(AgentConstants.PEER_SCHEDULE)
        elif str_requestType == AgentConstants.UPDATE_AGENT_CONFIG:
            DataConsolidator.updateAgentConfig()
        elif str_requestType == AgentConstants.EDIT_SYSLOG_SERVICE:
            UdpHandler.SysLogUtil.editSyslogConfiguration()
        elif str_requestType == AgentConstants.DELETE_SYSLOG_SERVICE:
            UdpHandler.SysLogUtil.deleteSyslogConfiguration()
        elif str_requestType == AgentConstants.FAILOVER:
            AgentStatusHandler.updateServerList(dict_task['servers'])
        elif str_requestType == AgentConstants.UPDATE_METADATA_URL:
            AgentUtil.writeDataToFile(AgentConstants.AGENT_INSTANCE_METADATA_CONF_FILE,dict_task['urls'])
        elif str_requestType == AgentConstants.UPDATE_FILES_FROM_PATCH:
            AgentUpgrader.updatefilesfrompatch()
        # UPLOAD_PLUGIN unused DMS request removed [Bug Bounty]
        elif str_requestType == AgentConstants.UPDATE_DEVICE_KEY:
            AgentUtil.updateKeys(dict_task)
        elif str_requestType == AgentConstants.UPDATE_AGENT_KEY:
            AgentUtil.updateKeys(dict_task)
        elif str_requestType == AgentConstants.UTM:
            AgentLogger.log(AgentLogger.STDOUT,'Uptime Monitoring Request Received From Server'+'\n')
            AgentLogger.log(AgentLogger.STDOUT,'Uptime Monitoring Before Server Request : '+repr(AgentConstants.UPTIME_MONITORING)+'\n')
            AgentConstants.UPTIME_MONITORING=dict_task['UPTIME_MONITORING']
            AgentLogger.log(AgentLogger.STDOUT,'Uptime Monitoring After Server Request : '+repr(AgentConstants.UPTIME_MONITORING)+'\n')
        elif str_requestType == AgentConstants.RE_REGISTER_PLUGINS:
            module_object_holder.plugins_obj.refresh_ignored_plugins_list(dict_task)
        elif str_requestType == AgentConstants.UPDATE_CONF_JSON_FILE:
            AgentUtil.writeDataToFile(dict_task['fileName'],dict_task['data'])
        elif str_requestType == AgentConstants.UPDATE_TASK_INFO:
            AgentUtil.updateTaskInfo(dict_task)
        elif str_requestType == AgentConstants.REBOOT_ACTION:
            AgentAction.triggerReboot(dict_task)
        elif str_requestType == AgentConstants.ACTION_SCRIPT_CLEANUP:
            AgentAction.CleanUpActionScript(dict_task)
        elif str_requestType == AgentConstants.REAL_TIME_MONITORING:
            AgentStatusHandler.setRealTimeUpdateInterval()
        elif str_requestType == AgentConstants.GET_REAL_TIME_ATTRIBUTE:
            RealTimeMonitoring.initiate_real_time_monitoring(dict_task)
        elif str_requestType == AgentConstants.STOP_REAL_TIME_MONITORING:
            RealTimeMonitoring.stop_real_time_monitoring()
        elif str_requestType == AgentConstants.ENABLE_PS_UTIL_PROCESS_DISCOVERY:
            AgentUtil.create_file(AgentConstants.PS_UTIL_CHECK_FILE)
        elif str_requestType == AgentConstants.DISABLE_PS_UTIL_PROCESS_DISCOVERY:
            os.remove(AgentConstants.PS_UTIL_CHECK_FILE)
        elif str_requestType == AgentConstants.UPDATE_LOG_LEVEL:
            AgentUtil.change_agentlog_level(dict_task.get('LOG_LEVEL', '3'))
        elif str_requestType == AgentConstants.SECURITY_CHECK:
            AgentConstants.SECURITY_ENABLED = bool(dict_task['security_check'])
        elif str_requestType == AgentConstants.UPDATE_PLUGIN_CONFIG:
            module_object_holder.plugins_obj.update_plugin_config(dict_task)
            DataConsolidator.updateAgentConfig()
        elif str_requestType == AgentConstants.ENABLE_BONDING_INTERFACE:
            AgentConstants.BONDING_INTERFACE_STATUS = True
        elif str_requestType == AgentConstants.DISABLE_BONDING_INTERFACE:
            AgentConstants.BONDING_INTERFACE_STATUS = False
        elif str_requestType == AgentConstants.DISCOVER_PROCESSES_AND_SERVICES:
            DataCollector.ProcessUtil.discoverAndUploadProcess(dict_task, str_loggerName = AgentLogger.STDOUT)
        elif str_requestType == AgentConstants.SCRIPT_RUN or str_requestType == AgentConstants.SCRIPT_DEPLOY:
            taskList = []
            taskList.append(dict_task)
            module_object_holder.script_obj.scriptExecutor(taskList)
        elif str_requestType == AgentConstants.SHARE_LOGS_REQUEST:
            AgentAction.getLogFiles(dict_task)
        elif str_requestType == AgentConstants.TEST_MONITOR:
            getInstantData(dict_task)
            boolPreAck = True
        elif str_requestType == "ENABLE_MONITOR":
            monitor = dict_task["monitor"]
            AgentUtil.edit_monitorsgroup(monitor, 'enable')
            AgentLogger.log(AgentLogger.STDOUT,'{} dms action received for the monitor:: {}'.format(str_requestType, monitor))
        elif str_requestType == "DISABLE_MONITOR":
            monitor = dict_task["monitor"]
            AgentUtil.edit_monitorsgroup(monitor, 'disable')
            AgentLogger.log(AgentLogger.STDOUT,'{} dms action received for the monitor:: {}'.format(str_requestType, monitor))
        elif str_requestType == AgentConstants.CHANGE_CPU_SAMPLES:
            DataCollector.changeCPU(dict_task)
        elif str_requestType == AgentConstants.CHANGE_MONITORING_INTERVAL:
            if AgentConstants.IS_DOCKER_AGENT == "0":
                DataCollector.changeMonitoringInterval(dict_task)
            else:
                AgentConstants.MONITORING_INTERVAL = int(dict_task.get("INTERVAL", 60))
        elif str_requestType == AgentConstants.UPDATE_CONTAINER_INTERVAL:
            AppConstants.CONTAINER_DISCOVERY_INTERVAL = dict_task.get("DISCOVERY_INTERVAL", 1800)
            container_monitoring.initialize(True)
        elif str_requestType == AgentConstants.RESUME_UPLOAD_FLAG:
            AgentLogger.log(AgentLogger.STDOUT,' Resume upload flag received. Hence switching back to normal upload mode')
            com.manageengine.monagent.collector.DataCollector.UPLOAD_PAUSE_FLAG = False
            com.manageengine.monagent.collector.DataCollector.UPLOAD_PAUSE_TIME = 0
        elif str_requestType == AgentConstants.TEST_WMS:
            testWMS(dict_task)
            boolPreAck = True
        elif str_requestType == AgentConstants.CLEAR_TRACE_ROUTE:
            AgentUtil.deleteTraceRoute()
        elif str_requestType == AgentConstants.REDISCOVER_DOCKER:
            AppUtil.rediscover_application()
            HardwareMonitoring.rediscover_hardware_monitoring()
            # MetricsUtil.statsd_util_obj.enable_statsd_monitoring()
            DatabaseUtil.rediscover_database_monitoring()
        elif str_requestType == AgentConstants.RCA_REPORT or str_requestType == AgentConstants.GENERATE_NETWORK_RCA or str_requestType == AgentConstants.GENERATE_RCA:
            RcaUtil.handleWmsRequest(dict_task)
        elif str_requestType == AgentConstants.STOP_MONITORING:
            boolPreAck = True
            if not AgentConstants.IS_DOCKER_AGENT == "1":
                DataCollector.COLLECTOR.stopDataCollection()
                if AgentStatusHandler.STATUS_THREAD != None:
                    AgentStatusHandler.STATUS_THREAD.stop()
                    AgentStatusHandler.STATUS_THREAD = None
                else:
                    AgentLogger.log(AgentLogger.STDOUT, "Status Update thread already not running :: {}".format(AgentStatusHandler.STATUS_THREAD))
            else:
                AgentConstants.DOCKER_COLLECTOR_OBJECT.do_monitoring = False
            thread_obj = AgentConstants.thread_pool_handler.active["Apps"] if "Apps" in AgentConstants.thread_pool_handler.active else None
            if thread_obj:
                thread_obj.shutdown.set()
                AgentConstants.thread_pool_handler.make_inactive("Apps")
        elif str_requestType == AgentConstants.SUSPEND_PLUGIN or str_requestType == AgentConstants.DELETE_PLUGIN or str_requestType == AgentConstants.ACTIVATE_PLUGIN:
            module_object_holder.plugins_util.updatePluginStatus(dict_task['PLUGIN_NAME'],str_requestType)
        elif str_requestType == AgentConstants.RELOAD_PLUGIN:
            module_object_holder.plugins_util.reloadPlugins()
        elif str_requestType == AgentConstants.REDISCOVER_PLUGINS:
            module_object_holder.plugins_util.re_register_plugins(dict_task)
        elif str_requestType == AgentConstants.START_MONITORING:
            if not AgentConstants.IS_DOCKER_AGENT == "1":
                DataCollector.COLLECTOR.startDataCollection()
                if AgentStatusHandler.STATUS_THREAD == None:
                    AgentStatusHandler.initialize()
                else:
                    AgentLogger.log(AgentLogger.STDOUT, "Status Update thread already Running :: {}".format(AgentStatusHandler.STATUS_THREAD))
            else:
                AgentConstants.DOCKER_COLLECTOR_OBJECT.do_monitoring = True
        elif str_requestType == AgentConstants.EDIT_STATUS_SCHEDULE:
            AgentStatusHandler.setStatusUpdateInterval(dict_task)
        elif str_requestType == AgentConstants.RESTART_SERVICE:
            AgentUtil.RestartAgent()
        elif str_requestType == AgentConstants.UNINSTALL_AGENT or str_requestType == AgentConstants.DELETE_MONITORING:
            AgentUtil.UninstallAgent()
        elif str_requestType == AgentConstants.UPDATE_SERVICE_AND_PROCESS_DETAILS:
            updateQueryConf(dict_task)
            DataConsolidator.updateAgentConfig()
            DataCollector.COLLECTOR.scheduleDataCollection(True)
        elif str_requestType == AgentConstants.KUBE_INSTANT_DISCOVERY:
            if dict_task[AgentConstants.KUBE_INSTANT_DISCOVERY] == "1":
                AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER["018"]["uri"] = AgentConstants.KUBE_DATA_DISCOVERY_SERVLET
            else:
                AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER["018"]["uri"] = AgentConstants.KUBE_DATA_COLLECTOR_SERVLET
        elif str_requestType == AgentConstants.DAM:
            str_mtype=None
            if "mtype" in dict_task:
                str_mtype = dict_task['mtype']
            if str_mtype is None:
                AgentLogger.log(AgentLogger.MAIN, "monitor type empty cannot perform the request") 
            elif str_mtype == 'PLUGIN':
                module_object_holder.plugins_util.processDAM(dict_task)
            elif str_mtype =='SMARTDISK':
                HardwareMonitoring.delete_hardware_monitoring(dict_task)
            elif str_mtype in ['MYSQLDB','MYSQLNDB']:
                #AgentLogger.log(AgentLogger.MAIN, "Delete MySQL Monitor received :: {}".format(dict_task))
                DatabaseUtil.delete_database_monitoring(AgentConstants.MYSQL_DB,dict_task)
            elif str_mtype in ['POSTGRESQL']:
                AgentLogger.log(AgentLogger.MAIN, "Delete POSTGRESQL Monitor received :: {}".format(dict_task))
                DatabaseUtil.delete_database_monitoring(AgentConstants.POSTGRES_DB,dict_task)
            elif str_mtype in ['ORACLE_DB']:
                AgentLogger.log(AgentLogger.MAIN, "Delete ORACLE_DB Monitor received :: {}".format(dict_task))
                DatabaseUtil.delete_database_monitoring(AgentConstants.ORACLE_DB,dict_task)
            else:
                if str_mtype == 'HADOOP':
                    str_mtype = AppConstants.namenode_app.lower()
                    dict_task['mtype'] = str_mtype
                AppUtil.delete_application(dict_task)
        elif str_requestType == AgentConstants.SAM:
            str_mtype=None
            if "mtype" in dict_task:
                str_mtype = dict_task['mtype']
            if str_mtype is None:
                AgentLogger.log(AgentLogger.MAIN, "monitor type empty cannot perform the request") 
            elif str_mtype == 'PLUGIN':
                module_object_holder.plugins_util.processSAM(dict_task)
            elif str_mtype =='SMARTDISK':
                HardwareMonitoring.suspend_hardware_monitoring(dict_task)
            elif str_mtype =='MYSQLDB':
                #AgentLogger.log(AgentLogger.MAIN, "Suspend MySQL Monitor received :: {}".format(dict_task))
                DatabaseUtil.suspend_database_monitor(AgentConstants.MYSQL_DB,dict_task)
            elif str_mtype =='POSTGRESQL':
                AgentLogger.log(AgentLogger.MAIN, "Suspend POSTGRESQL Monitor received :: {}".format(dict_task))
                DatabaseUtil.suspend_database_monitor(AgentConstants.POSTGRES_DB,dict_task)
            elif str_mtype =='ORACLE_DB':
                AgentLogger.log(AgentLogger.MAIN, "Suspend ORACLE_DB Monitor received :: {}".format(dict_task))
                DatabaseUtil.suspend_database_monitor(AgentConstants.ORACLE_DB,dict_task)
            elif str_mtype =='STATSD':
                MetricsUtil.statsd_util_obj.disable_statsd_monitoring()
            elif str_mtype =='MYSQLNDB':
                NDBCluster.suspendNDBClusterMonitoring(dict_task)
            else:
                if str_mtype == 'HADOOP':
                    str_mtype = AppConstants.namenode_app.lower()
                    dict_task['mtype'] = str_mtype
                AppUtil.suspend_application(dict_task)
        elif str_requestType == AgentConstants.AAM:
            str_mtype=None
            if "mtype" in dict_task:
                str_mtype = dict_task['mtype']
            if str_mtype is None:
                AgentLogger.log(AgentLogger.MAIN, "monitor type empty cannot perform the request") 
            elif str_mtype == 'PLUGIN':
                module_object_holder.plugins_util.processAAM(dict_task)
            elif str_mtype =='SMARTDISK':
                HardwareMonitoring.activate_hardware_monitoring(dict_task)
            elif str_mtype=='STATSD':
                MetricsUtil.statsd_util_obj.enable_statsd_monitoring()
            elif str_mtype =='MYSQLDB':
                DatabaseUtil.activate_database_monitor(AgentConstants.MYSQL_DB,dict_task)
            elif str_mtype =='POSTGRESQL':
                DatabaseUtil.activate_database_monitor(AgentConstants.POSTGRES_DB,dict_task)
            elif str_mtype =='ORACLE_DB':
                DatabaseUtil.activate_database_monitor(AgentConstants.ORACLE_DB,dict_task)
            elif str_mtype == 'MYSQLNDB':
                NDBCluster.activateNDBClusterMonitoring(dict_task)
            else:
                if str_mtype == 'HADOOP':
                    str_mtype = AppConstants.namenode_app.lower()
                    dict_task['mtype'] = str_mtype
                AppUtil.activate_application(dict_task)
        elif str_requestType == AgentConstants.STOP_INVENTORY:
            server_inventory.stop_inventory()
        elif str_requestType == AgentConstants.START_INVENTORY:
            server_inventory.start_inventory()
        elif str_requestType == AgentConstants.PROXY_KEY:
            AgentUtil.update_proxy_settings(dict_task[str_requestType])
        elif str_requestType == AgentConstants.HADOOP_BULK_INSTALL:
            cluster_type = dict_task.get("CLUSTER", None)
            if cluster_type == "HADOOP":
                framework_worker.Worker.do_bulk_install(entire_cluster=True if not "NODES" in dict_task else False, host_names=dict_task.get("NODES", []))
        elif str_requestType == AgentConstants.STOP_DMS:
            if 'com.manageengine.monagent.communication.dms_websocket' in sys.modules:
                dms_websocket.stop_dms()
            else:
                AgentLogger.log(AgentLogger.STDOUT, "*************************** Unable to stop DMS since module not found ***************************")
        elif str_requestType == AgentConstants.START_DMS:
            if 'com.manageengine.monagent.communication.dms_websocket' in sys.modules: 
                dms_websocket.initialize()
            else:
                AgentLogger.log(AgentLogger.STDOUT, "*************************** Unable to start DMS since module not found ***************************")
        elif str_requestType == AgentConstants.UPDATE_MONAGENT_CONFIG:
            AgentUtil.update_monagent_config(dict_task)
        elif str_requestType == AgentConstants.REMOVE_DC_ZIPS:
            AgentUtil.remove_dc_zips(dict_task)
        elif str_requestType==AgentConstants.INIT_HARDWARE_MONITORING:
            DataCollector.init_hardware_monitor(dict_task)
        elif str_requestType==AgentConstants.STOP_HARDWARE_MONITORING:
            DataCollector.stop_hardware_monitor(dict_task)
        elif str_requestType==AgentConstants.SET_KUBE_SEND_CONFIG:
            AgentLogger.log(AgentLogger.KUBERNETES,'received wms - SET_KUBE_SEND_CONFIG')
            if AgentConstants.KUBE_SEND_CONFIG in dict_task:
                sendConfig = dict_task.get(AgentConstants.KUBE_SEND_CONFIG)
                KubeActionsHandler.set_send_config(sendConfig)
        elif str_requestType==AgentConstants.SET_KUBE_SEND_PERF:
            AgentLogger.log(AgentLogger.KUBERNETES,'received wms - SET_KUBE_SEND_PERF')
            if AgentConstants.KUBE_SEND_PERF in dict_task:
                sendPerf = dict_task.get(AgentConstants.KUBE_SEND_PERF)
                KubeActionsHandler.set_send_perf(sendPerf)
        elif str_requestType==AgentConstants.SET_KUBE_CONFIG_DC_INT:
            AgentLogger.log(AgentLogger.KUBERNETES,'received wms - SET_KUBE_CONFIG_DC_INT')
            if AgentConstants.KUBE_CONFIG_DC_INTERVAL in dict_task:
                confInt = dict_task.get(AgentConstants.KUBE_CONFIG_DC_INTERVAL)
                KubeActionsHandler.set_config_dc_interval(confInt)
        elif str_requestType==AgentConstants.SET_KUBE_CHILD_COUNT:
            AgentLogger.log(AgentLogger.KUBERNETES,'received wms - SET_KUBE_CHILD_COUNT')
            if AgentConstants.KUBE_CHILD_COUNT in dict_task:
                childCount = dict_task.get(AgentConstants.KUBE_CHILD_COUNT)
                KubeActionsHandler.set_child_write_count(childCount)
        elif str_requestType==AgentConstants.SET_KUBE_API_SERVER_ENDPOINT_URL:
            AgentLogger.log(AgentLogger.KUBERNETES,'received wms - SET_KUBE_API_SERVER_ENDPOINT_URL')
            if AgentConstants.KUBE_API_SERVER_ENDPOINT in dict_task:
                apiEndpoint = dict_task.get(AgentConstants.KUBE_API_SERVER_ENDPOINT)
                KubeActionsHandler.set_api_server_endpoint_url(apiEndpoint)
        elif str_requestType==AgentConstants.SET_KUBE_STATE_METRICS_URL:
            AgentLogger.log(AgentLogger.KUBERNETES,'received wms - SET_KUBE_STATE_METRICS_URL')
            if AgentConstants.KUBE_STATE_METRICS_URL in dict_task:
                kubeStateMetricsUrl = dict_task.get(AgentConstants.KUBE_STATE_METRICS_URL)
                KubeActionsHandler.set_kube_state_metrics_url(kubeStateMetricsUrl)
        elif str_requestType==AgentConstants.SET_KUBE_CLUSTER_DISPLAY_NAME:
            AgentLogger.log(AgentLogger.KUBERNETES,'received wms - SET_KUBE_CLUSTER_DISPLAY_NAME')
            if AgentConstants.KUBE_CLUSTER_DN in dict_task:
                clusterDN = dict_task.get(AgentConstants.KUBE_CLUSTER_DN)
                KubeActionsHandler.set_cluster_display_name(clusterDN)
        elif str_requestType==AgentConstants.REDISCOVER_KUBE_STATE_METRICS_URL:
            AgentLogger.log(AgentLogger.KUBERNETES,'received wms - REDISCOVER_KUBE_STATE_METRICS_URL')
            KubeGlobal.kubeStateMetricsUrl = None
        elif str_requestType==AgentConstants.STOP_METRICS_AGENT:
            MetricsUtil.statsd_util_obj.stop_statsd()
        elif str_requestType in [AgentConstants.RESTART_MYSQL_MONITORING,AgentConstants.RESTART_NDB_MONITORING]:
            mysql_monitoring.initialize()
        elif str_requestType == AgentConstants.RESTART_ORACLE_MONITORING:
            oracledb_monitoring.initialize()
        elif str_requestType == AgentConstants.RESTART_POSTGRESQL_MONITORING:
            postgres_monitoring.initialize()
        elif str_requestType==AgentConstants.PERF_NODE_UPDATE:
            NDBCluster.enableInstance(dict_task)
        elif str_requestType==AgentConstants.UPLOAD_MYSQL_CONF_DATA:
            AgentLogger.log(AgentLogger.DATABASE,'received wms - UPLOAD_MYSQL_CONF_DATA')
            AgentConstants.CONF_UPLOAD_FLAG = True
        elif str_requestType==AgentConstants.START_METRICS_AGENT:
            MetricsUtil.statsd_util_obj.start_statsd()
        elif str_requestType==AgentConstants.STOP_STATSD:
            MetricsUtil.statsd_util_obj.disable_statsd_monitoring()
        elif str_requestType==AgentConstants.START_STATSD:
            MetricsUtil.statsd_util_obj.enable_statsd_monitoring()
        elif str_requestType==AgentConstants.START_PROMETHEUS:
            MetricsUtil.start_prometheus_monitoring()
        elif str_requestType==AgentConstants.STOP_PROMETHEUS:
            MetricsUtil.stop_prometheus_monitoring()
        elif str_requestType==AgentConstants.REMOVE_METRICS_DC_ZIPS:
            MetricsUtil.remove_dc_zips()
        elif str_requestType==AgentConstants.INIT_STATSD_MONITORING:
            MetricsUtil.statsd_util_obj.enable_statsd_monitoring()
        elif str_requestType==AgentConstants.START_STATSD_MONITORING:
            MetricsUtil.statsd_util_obj.enable_statsd_monitoring()
        elif str_requestType==AgentConstants.STOP_STATSD_MONITORING:
            MetricsUtil.statsd_util_obj.disable_statsd_monitoring()
        elif str_requestType==AgentConstants.UPDATE_STATSD_CONFIG:
            MetricsUtil.statsd_util_obj.update_statsd_config(dict_task['config'])
        elif str_requestType == AgentConstants.UPDATE_AGENT_APPS_CONFIG:
            AppUtil.update_agent_apps_config()
        elif str_requestType == AgentConstants.CCD:
            str_mtype=None
            str_ctype = None
            if "MONITOR_TYPE" in dict_task and "CHILD_TYPE" in dict_task:
                str_mtype = dict_task['MONITOR_TYPE']
                str_ctype = dict_task['CHILD_TYPE']
            AgentLogger.log(AgentLogger.DATABASE, "received CHILD discovery action -> {}".format(dict_task))
            if str_mtype is None or str_ctype is None:
                AgentLogger.log(AgentLogger.MAIN, "monitor/child type empty cannot perform the request :: monitor-{} : child-{}".format(str_mtype,str_ctype))
            elif str_mtype == 'MYSQLDB' and str_ctype == 'MYSQL_DATABASE':
                DatabaseUtil.child_database_discover(dict_task)
            elif str_mtype == 'MYSQLNDB' and str_ctype=='MYSQLNDB_NODE':
                NDBCluster.child_rediscover(dict_task)
            elif str_mtype == 'POSTGRESQL' and str_ctype == 'POSTGRESQL_DATABASE':
                postgres_monitoring.child_database_discover(dict_task)
            elif str_mtype == 'ORACLE_DB' and str_ctype == 'ORACLE_PDB':
                oracledb_monitoring.discover_child(dict_task,"1")
            elif str_mtype in ['ORACLE_DB','ORACLE_PDB'] and str_ctype == 'ORACLE_TABLESPACE':
                oracledb_monitoring.discover_child(dict_task,"2")
            else: # first no if case was there, now adding for mysql child database discovery, hence else part is given for docker container to not to touch previous flow
                com.manageengine.monagent.container.container_monitoring.schedule_container_discovery(dict_task)
        elif str_requestType == AgentConstants.CONTAINER_MANAGEMENT_ACTION:
            container_management.execute(dict_task)
        elif str_requestType == AgentConstants.VALIDATE_CHECKSUM:
            checksum_validator.initialize(dict_task['agent_files_checksum'])
        elif str_requestType == AgentConstants.UPDATE_SETTINGS:
            com.manageengine.monagent.actions.settings_handler.update_settings(dict_task,False)
        elif str_requestType == AgentConstants.SET_EVENTS_ENABLED:
            AgentLogger.log(AgentLogger.KUBERNETES, "received EVENTS_ENABLED action -> {}".format(dict_task.get(AgentConstants.SET_EVENTS_ENABLED)))
            KubeActionsHandler.set_event_settings(str(dict_task.get(AgentConstants.SET_EVENTS_ENABLED)))
        elif str_requestType == "PERF_POLL_INTERVAL":   # to handle all k8s cluster level settings
            AgentLogger.log(AgentLogger.KUBERNETES, "received PERF_POLL_INTERVAL action -> {}".format(dict_task.get("PERF_POLL_INTERVAL")))
            KubeActionsHandler.change_kubernetes_perf_poll_interval(dict_task)
        elif str_requestType in ["KUBE_AGENT_OPS", "KUBE_YAML_CONFIG"] or str_requestType.startswith("KUBE_"):
            AgentLogger.log(AgentLogger.KUBERNETES, "received {} action -> {}".format(str_requestType, dict_task.get(str_requestType)))
            KubeActionsHandler.kube_agent_action_handler(dict_task)
        elif str_requestType == "INSTANT_RESOURCE_DISCOVERY_FLOW":
            AgentLogger.log(AgentLogger.KUBERNETES, "received INSTANT_RESOURCE_DISCOVERY action -> {}".format(dict_task.get("INSTANT_RESOURCE_DISCOVERY")))
            KubeActionsHandler.change_kubernetes_instant_resource_discovery(dict_task)
        elif str_requestType == "INITIATE_CLUSTER_AGENT_UPGRADE":
            com.manageengine.monagent.kubernetes.ClusterAgent.ClusterAgentUtil.upgrade_cluster_agent()
        else:
            AgentLogger.log(AgentLogger.MAIN,' request type not found -- {0}'.format(str_requestType))
    except Exception as e:
        traceback.print_exc()


def sendACK(strReqID):
    bool_isSuccess = False
    try:
        AgentLogger.log(AgentLogger.STDOUT, '================================= Send Ack =================================')
        str_url = None
        str_servlet = AgentConstants.WMS_ACK_SERVLET
        dict_requestParameters      =   {
        'REQID'   :   strReqID,
        'AGENTKEY'  :   AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        }
        if not dict_requestParameters == None:
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.STDOUT)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
        if bool_toReturn == True:
            bool_isSuccess = True
    except Exception as e:
        AgentLogger.log([AgentLogger.MAIN,AgentLogger.STDERR], ' *************************** Exception while sending WMS acknowledgment to server *************************** '+ repr(e))
        traceback.print_exc()
        bool_isSuccess = False
    return bool_isSuccess

def updateQueryConf(dict_task):
    try:
        str_unicodeUpdateQuery = dict_task['QUERY_STRING']
        DataCollector.updateQueryConf(json.loads(str_unicodeUpdateQuery), AgentLogger.STDOUT)
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR], ' *************************** Exception while updating query conf *************************** '+ repr(e))
        traceback.print_exc()

def getInstantData(dict_task):
    if AgentConstants.IS_DOCKER_AGENT == "0" or AgentConstants.OS_NAME.lower()==AgentConstants.SUN_OS.lower():
        bool_isSuccess = True
        try:
            monitorName = dict_task['MONITOR_NAME']
            if monitorName == 'PROCESS_LOG_DATA':
                DataCollector.ProcessUtil.discoverAndUploadProcess(dict_task, str_loggerName = AgentLogger.STDOUT)
        except Exception as e:
            AgentLogger.log([AgentLogger.MAIN,AgentLogger.STDERR], ' *************************** Exception While Processing TEST_MONITOR Request From The Server *************************** '+ repr(e))
            traceback.print_exc()
            bool_isSuccess = False
        return bool_isSuccess
    else:
        result_dict = AgentConstants.DOCKER_PROCESS_OBJECT.handle_process_discovery(dict_task)
        with AgentConstants.DOCKER_HELPER_OBJECT.post_process_data(result_dict, dict_task) as fp:
            pass

def testWMS(dict_task):
    bool_isSuccess = True
    AgentLogger.log(AgentLogger.STDOUT, '================================= TEST WMS =================================')
    try:
        str_url = None
        str_servlet = AgentConstants.DATA_AGENT_HANDLER_SERVLET
        dict_requestParameters      =   {
        'action'   :   dict_task['REQUEST_TYPE'],
        'agentKey'  :   AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),
        'bno' : AgentConstants.AGENT_VERSION,
        'requestId'   :  str(dict_task['AGENT_REQUEST_ID']),
        'custID'  :   AgentConstants.CUSTOMER_ID
        }
        if not dict_requestParameters == None:
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.STDOUT)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
    except Exception as e:
        AgentLogger.log([AgentLogger.MAIN,AgentLogger.STDERR], ' *************************** Exception while executing TEST_WMS request *************************** '+ repr(e))
        traceback.print_exc()
        bool_isSuccess = False
    return bool_isSuccess
