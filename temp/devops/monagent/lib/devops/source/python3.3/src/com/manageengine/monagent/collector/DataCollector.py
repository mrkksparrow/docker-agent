#$Id$
import os
import sys
import time
import traceback
import threading
import errno
import ssl
import shutil
import re
import json
import collections
import socket
import random
from collections import deque, OrderedDict
import copy
from six.moves.urllib.parse import urlencode
from operator import itemgetter

from com.manageengine.monagent import AgentConstants,module_object_holder
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util import AppUtil
from com.manageengine.monagent.util.AgentUtil import ZipUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil
from com.manageengine.monagent.util.AgentUtil import FileZipAndUploadInfo
from com.manageengine.monagent.util.rca.RcaHandler import RcaUtil, RcaInfo
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.docker_old.DockerAgent import DockerDataCollector
from com.manageengine.monagent.scheduler import AgentScheduler
from com.manageengine.monagent.util import AgentBuffer
from com.manageengine.monagent.util import AgentParser
import com.manageengine.monagent.network
from com.manageengine.monagent.actions import ScriptHandler

from com.manageengine.monagent.communication import UdpHandler
from com.manageengine.monagent.communication import BasicClientHandler
from com.manageengine.monagent.actions import ScriptMonitoring

from com.manageengine.monagent.collector import DataConsolidator , server_inventory , ps_util_metric_collector
from com.manageengine.monagent.docker_agent import collector as da_collector

import platform

if platform.system() in [ AgentConstants.LINUX_OS,AgentConstants.FREEBSD_OS, AgentConstants.DARWIN_OS]:
    from com.manageengine.monagent.hardware import HardwareMonitoring
    from com.manageengine.monagent.hadoop import hadoop_monitoring
    from com.manageengine.monagent.hadoop import zookeeper_monitoring
    from com.manageengine.monagent.container import container_monitoring
    from com.manageengine.monagent.kubernetes_monitoring import KubernetesExecutor
else:
    AgentLogger.log(AgentLogger.MAIN,'OS is not Linux :: {}'.format(platform.system()))

from com.manageengine.monagent.database_executor.mysql import mysql_monitoring
from com.manageengine.monagent.addm import DataCollector as addm_datacollector
#from com.manageengine.monagent.database_executor.mongodb import mongodb_monitoring
from com.manageengine.monagent.database_executor.postgres import postgres_monitoring
from com.manageengine.monagent.database_executor.oracle     import oracledb_monitoring

COLLECTOR = None
SCHEDULED_THREAD_DICT = {}
CPU_UTIL_VALUES = deque([])
PROCESS_LIST = []
FREE_PROCESS_LIST = []
MONITORS_INFO = None
CUSTOM_MONITORS_INFO = None
PREVIOUS_COUNTER_VALUES = {}
COLLECTOR_IMPL = None
APP_IMPL = None

FILES_TO_ZIP_BUFFER = None
FILES_TO_UPLOAD_BUFFER = None
FILE_UPLOADER = None
FILE_ZIPPER = None
ACTIVATOR = None
UPLOAD_DETAILS = None
LIST_UPLOAD_CATEGORIES = None
UPLOAD_DATA_DIR_IMPL = None
FILES_UPLOADED = 0
LAST_UPLOADED_TIME = 0
UPLOAD_PAUSE_FLAG = False
UPLOAD_PAUSE_TIME = 0

def initialize():
    global FILES_TO_ZIP_BUFFER, FILE_UPLOADER, FILE_ZIPPER, COLLECTOR_IMPL, APP_IMPL, LIST_UPLOAD_CATEGORIES, UPLOAD_DATA_DIR_IMPL, ACTIVATOR
    LIST_UPLOAD_CATEGORIES = ['Upload','Statistics','Plugins']
    FILES_TO_ZIP_BUFFER = AgentBuffer.getBuffer(AgentConstants.FILES_TO_ZIP_BUFFER,AgentConstants.MAX_SIZE_ZIP_BUFFER)
    FILES_TO_UPLOAD_BUFFER = AgentBuffer.getBuffer(AgentConstants.FILES_TO_UPLOAD_BUFFER, AgentConstants.MAX_SIZE_UPLOAD_BUFFER )
    initializeFileAndZipIds()
    FILE_ZIPPER = ZipUtil
    FILE_ZIPPER.start()
    UPLOADER = UploaderCycleHandler()
    UPLOADER.setDaemon(True)
    UPLOADER.name = 'UPLOADER'
    UPLOADER.start()
    AgentUtil.UploadUtil = UPLOADER
    ACTIVATOR = Activator()

    UPLOAD_DATA_DIR_IMPL = {
    #                        'Upload':UPLOADER.addFilesinDataDirectory,
    #                        'Plugins':UPLOADER.addPluginsFilesinDataDirectory,
    #                        'Statistics':UdpHandler.SysLogStatsUtil.addFilesinDataDirectory
                           }
    if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS,AgentConstants.FREEBSD_OS, AgentConstants.OS_X]:
        COLLECTOR_IMPL = {
                       'ChecksMonitoring': BasicClientHandler.checksMonitor,
                       'EventLogMonitoring': UdpHandler.SysLogStatsUtil.collectSysLogData,
                       'RootCauseAnalysis': RcaUtil.generateRca,
                       'ProcessMonitoring': ProcessUtil.processMonitor,
                       'PluginMonitoring': executePlugins,
                       'TopProcessMonitoring': AgentUtil.get_top_process_data,  # if top command check failed, old flow
                       'server_inventory': server_inventory.inventory_data_collector,
                       'HardwareMonitoring':HardwareMonitoring.initialize,
                       'kubernetes_dc' : KubernetesExecutor.schedule,
                       'hadoop_monitoring': hadoop_monitoring.initialize,
                       'mysql_monitoring': mysql_monitoring.initialize,
                       #'mongodb_monitoring': mongodb_monitoring.initialize,
                       'postgres_monitoring': postgres_monitoring.initialize,
                       'oracledb_monitoring': oracledb_monitoring.initialize,
                       'dc_bottlenecks': AgentUtil.check_dc_bottlenecks,
                       'zookeeper_monitoring':zookeeper_monitoring.initialize,
                       'docker_monitoring':container_monitoring.initialize,
                       'SelfMonitoring':DataConsolidator.agentSelfMetrics,
                       'ADDM': addm_datacollector.collect_metrics
                      }
    
        APP_IMPL = {
                    'Docker':collectDockerData
                   }
    
        DOCKER_AGENT_APPS_IMPL = {'docker': {'path':'com.manageengine.monagent.container.container_monitoring','method_name':'initialize'},'kubernetes': {'path':'com.manageengine.monagent.kubernetes_monitoring.KubernetesExecutor','method_name':'schedule'}}

    if AgentConstants.OS_NAME in [AgentConstants.SUN_OS, AgentConstants.AIX_OS_LOWERCASE]:
        COLLECTOR_IMPL = {
                            'TopProcessMonitoring': AgentUtil.get_top_process_data,
                            'server_inventory': server_inventory.inventory_data_collector
                        }
    
    if AgentConstants.IS_DOCKER_AGENT=="1":
        if AgentUtil.is_module_enabled(AgentConstants.APPS_SETTING):
            AppUtil.do_app_discovery(DOCKER_AGENT_APPS_IMPL)
        server_inventory.start_inventory()
        da_collector.schedule_agentSelfMetrics()
        
        
    if AgentConstants.OS_NAME in AgentConstants.BIN_SUPPORTED_OS and not AgentConstants.IS_DOCKER_AGENT == "1" and not AgentConstants.PS_UTIL_FLOW:
        AgentLogger.log(AgentLogger.MAIN, "SCRIPT DATA COLLECTION INITIALIZED  \n")
        DataConsolidator.initialize()
        loadProcessList()
        ProcessUtil.loadProcessStatusList()
        ProcessUtil.loadProcessDetailsList()
        COLLECTOR.scheduleDataCollection(True)
    elif AgentConstants.PSUTIL_OBJECT and AgentConstants.OS_NAME in [AgentConstants.FREEBSD_OS, AgentConstants.OS_X]:
        AgentLogger.log(AgentLogger.MAIN, "PS UTIL METRIC COLLECTION INITIALIZED  \n")
        AgentUtil.create_file(AgentConstants.PS_UTIL_CHECK_FILE)
        ps_util_metric_collector.schedule_dc()
        AgentConstants.PS_UTIL_DC = True
    else:
        AgentLogger.log(AgentLogger.MAIN, "MAIN AGENT DATA COLLECTION AND CONSOLIDATION IGNORED \n")
    return True


def changeMonitoringInterval(dictData):
    AgentLogger.log(AgentLogger.STDOUT,'update dc monitoring interval \n')
    try:
        if 'INTERVAL' in dictData and dictData['INTERVAL']:
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(AgentConstants.AGENT_MONITORS_GROUP_FILE)
            fileObj.set_dataType('json')
            fileObj.set_mode('rb')
            fileObj.set_dataEncoding('UTF-8')
            fileObj.set_loggerName(AgentLogger.COLLECTOR)
            fileObj.set_logging(False)
            bool_toReturn, dictCustomMonitors = FileUtil.readData(fileObj)
            dictCustomMonitors['MonitorGroup']['Monitoring']['Interval'] = dictData['INTERVAL']
            if 'dc_bottlenecks' in dictCustomMonitors['MonitorGroup']:
                dictCustomMonitors['MonitorGroup']['dc_bottlenecks']['Interval'] = dictData['INTERVAL']
            AgentLogger.log(AgentLogger.COLLECTOR,' updated monitoring configuraton -- '+repr(dictCustomMonitors)+'\n')
            fileObj.set_data(dictCustomMonitors)
            fileObj.set_mode('wb')
            bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
            COLLECTOR.loadMonitors()
            if COLLECTOR_IMPL != None:
                COLLECTOR.scheduleDataCollection(True)
        else:
            AgentLogger.log([AgentLogger.MAIN,AgentLogger.CRITICAL],' interval parameter not found in the dictionary -- {0}'.format(json.dumps(dictData)))
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,' ************************** Exception while changing monitoring interval **************************** ')
        traceback.print_exc()
        
def init_hardware_monitor(dictData):
    try:
        AgentLogger.log(AgentLogger.HARDWARE,'Add Hardware monitoring in monitors group \n')
        fileObj = AgentUtil.FileObject()
        fileObj.set_filePath(AgentConstants.AGENT_MONITORS_GROUP_FILE)
        fileObj.set_dataType('json')
        fileObj.set_mode('rb')
        fileObj.set_dataEncoding('UTF-8')
        fileObj.set_loggerName(AgentLogger.HARDWARE)
        fileObj.set_logging(False)
        bool_toReturn, dictCustomMonitors = FileUtil.readData(fileObj)
        if 'HardwareMonitoring' not in dictCustomMonitors['MonitorGroup']:
            dictCustomMonitors['MonitorGroup']["HardwareMonitoring"]={"GroupName": "HardwareMonitoring","Impl": "true"}
            AgentLogger.log(AgentLogger.HARDWARE,' updated monitoring configuraton -- '+repr(dictCustomMonitors)+'\n')
            fileObj.set_data(dictCustomMonitors)
            fileObj.set_mode('wb')
            bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
            COLLECTOR.loadMonitors()
            COLLECTOR.scheduleDataCollection(True)
    except Exception as e:
        AgentLogger.log(AgentLogger.HARDWARE,' ************************** Exception while Inserting Hardware monitor **************************** ')
        traceback.print_exc()
        
def stop_hardware_monitor(dictData):
    try:
        AgentLogger.log(AgentLogger.HARDWARE,'Delete Hardware monitoring in monitors group \n')
        HardwareMonitoring.reregister_hardware_monitoring(True)
        fileObj = AgentUtil.FileObject()
        fileObj.set_filePath(AgentConstants.AGENT_MONITORS_GROUP_FILE)
        fileObj.set_dataType('json')
        fileObj.set_mode('rb')
        fileObj.set_dataEncoding('UTF-8')
        fileObj.set_loggerName(AgentLogger.HARDWARE)
        fileObj.set_logging(False)
        bool_toReturn, dictCustomMonitors = FileUtil.readData(fileObj)
        if 'HardwareMonitoring' in dictCustomMonitors['MonitorGroup']:
            dictCustomMonitors['MonitorGroup'].pop("HardwareMonitoring",None)
            AgentLogger.log(AgentLogger.HARDWARE,' updated monitoring configuraton -- '+repr(dictCustomMonitors)+'\n')
            fileObj.set_data(dictCustomMonitors)
            fileObj.set_mode('wb')
            bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
            COLLECTOR.loadMonitors()
            COLLECTOR.scheduleDataCollection(True)
    except Exception as e:
        AgentLogger.log(AgentLogger.HARDWARE,' ************************** Exception while Deleting Hardware monitor **************************** ')
        traceback.print_exc()


def changeCPU(dictData):
    try:
        AgentLogger.log(AgentLogger.STDOUT,'change dc monitoring interval \n')
        fileObj = AgentUtil.FileObject()
        fileObj.set_filePath(AgentConstants.AGENT_CUSTOM_MONITORS_GROUP_FILE)
        fileObj.set_dataType('json')
        fileObj.set_mode('rb')
        fileObj.set_dataEncoding('UTF-8')
        fileObj.set_loggerName(AgentLogger.COLLECTOR)
        fileObj.set_logging(False)
        bool_toReturn, dictCustomMonitors = FileUtil.readData(fileObj)
        if 'CPUMonitoring' in dictCustomMonitors['MonitorGroup']:
            dictCustomMonitors['MonitorGroup']['CPUMonitoring']['Schedule'] = "True"
            dictCustomMonitors['MonitorGroup']['CPUMonitoring']['Interval'] = dictData['CPU_INTERVAL']
        else:
            dictCustomMonitors['MonitorGroup'].setdefault('CPUMonitoring',{})
            dictCustomMonitors['MonitorGroup']['CPUMonitoring']['Schedule'] = "True"
            dictCustomMonitors['MonitorGroup']['CPUMonitoring']['Interval'] = dictData['CPU_INTERVAL']
            dictCustomMonitors['MonitorGroup']['CPUMonitoring']['SaveFile'] = "False"
            listData = []
            listData.append('CPU Utilization')
            dictCustomMonitors['MonitorGroup']['CPUMonitoring'].setdefault('Monitors',listData)
        AgentLogger.log(AgentLogger.STDOUT,' final json -- {0}'.format(json.dumps(dictCustomMonitors)))
        fileObj.set_data(dictCustomMonitors)
        fileObj.set_mode('wb')
        bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
        COLLECTOR.loadMonitors()
        COLLECTOR.scheduleDataCollection(True)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],' ************************** Exception while changing CPU utilization details **************************** ')
        traceback.print_exc()

def addAndFindAverage(float_cpu):
    floatAvgCPU = None
    try:
        if CPU_UTIL_VALUES:
            AgentLogger.log(AgentLogger.COLLECTOR,' Current CPU values : ' + str(CPU_UTIL_VALUES)) 
        else:
            AgentLogger.log(AgentLogger.COLLECTOR,' No current CPU values ')
        if len(CPU_UTIL_VALUES) >= AgentConstants.CPU_SAMPLE_VALUES:
            popped_cpu = CPU_UTIL_VALUES.popleft()
            AgentLogger.debug(AgentLogger.COLLECTOR,' Popped oldest CPU value : ' + str(popped_cpu))
            CPU_UTIL_VALUES.append(float_cpu)
            AgentLogger.debug(AgentLogger.COLLECTOR,' Appended new CPU value : ' + str(float_cpu))
        elif len(CPU_UTIL_VALUES) < AgentConstants.CPU_SAMPLE_VALUES:
            CPU_UTIL_VALUES.append(float_cpu)
            AgentLogger.debug(AgentLogger.COLLECTOR,' Added new CPU value : ' + str(float_cpu))
        floatAvgCPU = round(sum(CPU_UTIL_VALUES)/float(len(CPU_UTIL_VALUES)),1)
        AgentLogger.log(AgentLogger.COLLECTOR,' Calculated Average CPU Value : ' + str(floatAvgCPU))
    except ZeroDivisionError as e:
        AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR],' ************************** Divide by zero Exception occured in avg cpu values **************************** \n')
        floatAvgCPU = float_cpu
    except Exception as e:
        AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR],' ************************** Exception while finding avg CPU utilization **************************** \n')
        traceback.print_exc()
        floatAvgCPU = float_cpu
    finally:
        return floatAvgCPU


def collectDockerData():
    dictDataToSave = None
    if ((AgentConstants.AGENT_DOCKER_INSTALLED == 1) and (AgentConstants.AGENT_DOCKER_ENABLED == 1)):
        dictDataToSave = DockerDataCollector().collectDockerData()
        if ((dictDataToSave) and ('DOCKER' in dictDataToSave)):
            dictDataToSave['DOCKER'].setdefault('availability',1)
        else:
            tempDict = {}
            tempDict.setdefault('DOCKER',{}).setdefault('availability',0)
            tempDict['DOCKER'].setdefault('error_code', 19002)
            return tempDict
    return dictDataToSave

def executePlugins():
    AgentLogger.log(AgentLogger.PLUGINS,'plugin obj :: {}'.format(module_object_holder.plugins_obj))
    try:
        if AgentConstants.UPTIME_MONITORING=="false":
            if AgentUtil.is_module_enabled(AgentConstants.PLUGINS_SECTION.lower()):
                module_object_holder.plugins_obj.loadPluginTask()
            else:
                AgentLogger.log(AgentLogger.PLUGINS,'#### plugins disabled ####')
        else:
            AgentLogger.log(AgentLogger.PLUGINS,'#### plugins disabled - up time monitoring ####')
    except Exception as e:
        AgentLogger.log(AgentLogger.CRITICAL,' Exception in plugin DC execution \n')
        traceback.print_exc()

def discover_process():
    str_jsonData=''
    str_servlet = AgentConstants.DISCOVERY_SERVLET
    request_params = {} 
    str_url = None
    try:
        if AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key') == "0":
            AgentLogger.log(AgentLogger.STDOUT, 'agent key :: 0 | not proceeding with process discovery')
            return
        dict_processData = ProcessUtil.discoverProcessForRegisterAgent() if AgentConstants.IS_DOCKER_AGENT == "0" else None
        if dict_processData:
            str_jsonData = json.dumps(dict_processData)
        AgentLogger.debug(AgentLogger.STDOUT, 'Process details collected :: {}'.format(str_jsonData)+'\n')
        request_params['custID'] = AgentConstants.CUSTOMER_ID
        request_params['bno'] = AgentConstants.AGENT_VERSION
        request_params['agentKey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        request_params['action'] = "RA_DPS"
        str_requestParameters = urlencode(request_params)
        str_url = str_servlet + str_requestParameters
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.STDOUT)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.set_data(str_jsonData)
        requestInfo.add_header("Content-Type", 'application/json')
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        (isSuccess, int_errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
    except Exception as e:
        traceback.print_exc()
        
def persistProcessList():
    if not PROCESS_LIST == None:  
        AgentLogger.log(AgentLogger.COLLECTOR,'================================= PERSISTING PROCESS LIST =================================')
        AgentLogger.log(AgentLogger.COLLECTOR,repr(PROCESS_LIST))      
        if not AgentUtil.writeDataToFile(AgentConstants.AGENT_PROCESS_LIST_FILE, PROCESS_LIST):
            AgentLogger.log(AgentLogger.CRITICAL,'************************* Problem while persisting process list ************************* \n') 
    else:
        AgentLogger.log(AgentLogger.CRITICAL,'************************* Process list to be persisted is empty ************************** \n')
        
def loadProcessList():
    global PROCESS_LIST
    AgentLogger.log(AgentLogger.COLLECTOR,'Loading process list')
    if os.path.exists(AgentConstants.AGENT_PROCESS_LIST_FILE):
        (bool_status, PROCESS_LIST) = AgentUtil.loadDataFromFile(AgentConstants.AGENT_PROCESS_LIST_FILE)
        if bool_status:        
            AgentLogger.log(AgentLogger.COLLECTOR,'Process list Loaded From '+AgentConstants.AGENT_PROCESS_LIST_FILE+' : '+repr(PROCESS_LIST))
        else:
            AgentLogger.log(AgentLogger.CRITICAL,'*********************** Problem while loading process list ************************ \n')
        if FREE_PROCESS_LIST:
            updateProcessList(FREE_PROCESS_LIST)
    else:
        if FREE_PROCESS_LIST:
            updateProcessList(FREE_PROCESS_LIST)
    
def updateProcessList(list_processDetails):
    AgentLogger.log(AgentLogger.COLLECTOR,'Process list to be updated : '+repr(list_processDetails))
    if list_processDetails:
        for processDetail in list_processDetails:
            #AgentLogger.log(AgentLogger.COLLECTOR,'Process detail : '+repr(processDetail))
            #AgentLogger.log(AgentLogger.COLLECTOR,'Process Name : '+repr(processDetail['Name']))
            if len(PROCESS_LIST) == 0:
                AgentLogger.debug(AgentLogger.COLLECTOR,'Appending the following process details for monitoring 1 : '+repr(processDetail))
                PROCESS_LIST.append(processDetail)
            else:
                for index, processMap in enumerate(PROCESS_LIST):
                    AgentLogger.debug(AgentLogger.COLLECTOR,'Index : '+repr(index)+' Length : '+repr(len(PROCESS_LIST)))
                    if 'PathName' in processDetail:
                        if len(PROCESS_LIST)-1 == index:
                            if 'PathName' not in processMap:                                
                                AgentLogger.debug(AgentLogger.COLLECTOR,'Appending the following process details for monitoring 2 : '+repr(processDetail))
                                PROCESS_LIST.append(processDetail)
                            elif processDetail['Name'] != processMap['Name'] or processDetail['PathName'] != processMap['PathName'] or processDetail['Arguments'] != processMap['Arguments']:
                                AgentLogger.debug(AgentLogger.COLLECTOR,'Appending the following process details for monitoring 3 : '+repr(processDetail))
                                PROCESS_LIST.append(processDetail)
                        else:
                            if 'PathName' not in processMap:
                                AgentLogger.debug(AgentLogger.COLLECTOR,'2 continue : '+repr(processMap))
                                continue
                            if processDetail['Name'] == processMap['Name'] and processDetail['PathName'] == processMap['PathName'] and processDetail['Arguments'] == processMap['Arguments']:
                                AgentLogger.debug(AgentLogger.COLLECTOR,'2 break : '+repr(processMap))
                                break
                    else:
                        if len(PROCESS_LIST)-1 == index:
                            if 'PathName' in processMap:                                
                                AgentLogger.debug(AgentLogger.COLLECTOR,'Appending the following process details for monitoring 4 : '+repr(processDetail))
                                PROCESS_LIST.append(processDetail)
                            elif not processDetail['Name'] == processMap['Name']:
                                AgentLogger.debug(AgentLogger.COLLECTOR,'Appending the following process details for monitoring 5 : '+repr(processDetail))
                                PROCESS_LIST.append(processDetail)
                        else:
                            if 'PathName' in processMap:
                                AgentLogger.debug(AgentLogger.COLLECTOR,'3 continue : '+repr(processMap))
                                continue
                            if processDetail['Name'] == processMap['Name']:
                                AgentLogger.debug(AgentLogger.COLLECTOR,'3 break : '+repr(processMap))
                                break
        persistProcessList()
        
def filterProcess(dict_processData):
    processList = dict_processData['Process Details']
    filteredProcessList = []
    for index, processMap in enumerate(PROCESS_LIST):
        if 'PathName' in processMap:
            for processDetail in processList:
                if processMap['Name'] ==  processDetail['PROCESS_NAME'] and processMap['PathName'] ==  processDetail['EXEUTABLE_PATH'] and processMap['Arguments'] ==  processDetail['COMMANDLINE']:
                    filteredProcessList.append(processDetail)
        else:
            for processDetail in processList:
                if processMap['Name'] ==  processDetail['PROCESS_NAME']:
                    filteredProcessList.append(processDetail)
    AgentLogger.log(AgentLogger.COLLECTOR,'Filtered process list : '+repr(filteredProcessList))
    dict_processData['Process Details'] = filteredProcessList
            
def getProcessNameList():
    list_toReturn = []
    if AgentConstants.OS_NAME == AgentConstants.LINUX_OS:
        AgentLogger.log(AgentLogger.COLLECTOR,'PROCESS_LIST 1 : '+repr(PROCESS_LIST))
        for dict_processDetails in PROCESS_LIST:
            list_toReturn.append(dict_processDetails['Name'])
    else:
        list_toReturn = AgentConstants.PROCESS_NAMES_TO_BE_MONITORED
    return list_toReturn

def synchronized(func):    
    func.__lock__ = threading.Lock()        
    def synced_func(*args, **kws):
        with func.__lock__:
            func(*args, **kws)
    return synced_func

class ProcessUtil:
    list_downNotifiedProcess = [] # Static variable
    dict_totalProcessDetails = {'Process Details':[]} # Static variable
    process_status_dict = {}    
    #process_details_dict = {'Process Details':[]}
    def __init__(self):
        pass
    
    @staticmethod
    def getRawProcessData(filePath=None):
        dict_processData = None
        str_agentDataCollFilePath = None
        try:
            if filePath:
                str_agentDataCollFilePath = filePath
            else:
                str_agentDataCollFileName = FileUtil.getUniqueFileName(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),'Temp_Raw_Data')
                str_agentDataCollFilePath = AgentConstants.AGENT_TEMP_RAW_DATA_DIR +'/'+str_agentDataCollFileName
                str_commandToExecute = '"'+AgentConstants.SCRIPTS_FILE_PATH+'" topCommand,psCommand'
                str_commandToExecute += ' > "'+str_agentDataCollFilePath+'"'
                isSuccess, str_output = AgentUtil.executeCommand(str_commandToExecute,AgentLogger.STDOUT, 14)
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(str_agentDataCollFilePath)
            fileObj.set_dataType('text')
            fileObj.set_mode('r')
            fileObj.set_loggerName(AgentLogger.COLLECTOR)
            fileObj.set_logging(False)
            bool_toReturn, str_collectedData = FileUtil.readData(fileObj)
            if not bool_toReturn:
                AgentLogger.log(AgentLogger.CRITICAL,'Exception while reading collected process data from the file : '+repr(str_agentDataCollFilePath) + '\n')
                return None
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], ' *************************** Exception while fetching raw process data by executing the command : '+repr(str_commandToExecute)+' *************************** '+ repr(e) + '\n')
            traceback.print_exc()
        return str_collectedData
    
    @staticmethod
    def discoverProcessForRegisterAgent():
        dict_processData = None
        try:
            dict_processData, list_psCommandOutput = ProcessUtil.getProcessDetails(AgentConstants.REGISTER_AGENT_DISCOVER_PROCESSES_AND_SERVICES)
            dict_processData['AGENT_REQUEST_ID'] = '1'
            dict_processData['REQUEST_TYPE'] = AgentConstants.DISCOVER_PROCESSES_AND_SERVICES
            dict_processData['DATACOLLECTTIME'] = str(AgentUtil.getTimeInMillis())
            dict_processData['ERRORMSG'] = 'NO ERROR'
            dict_processData['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.CRITICAL], ' *************************** Exception while discovering processes for register agent *************************** '+ repr(e) + '\n')
            traceback.print_exc()
        return dict_processData
    
    @staticmethod
    def updateProcessDetailsForAgentVersionsBelow11_0_0():
        dict_processData = None
        try:
            str_servlet = AgentConstants.DATA_AGENT_HANDLER_SERVLET
            dict_requestParameters      =   {
            'agentKey'  :   AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),
            'action'  :   AgentConstants.UPDATE_PROCESS_DETAILS,
            'bno' : AgentConstants.AGENT_VERSION,
            'custID'  :   AgentConstants.CUSTOMER_ID        
            }
            dict_processData, list_psCommandOutput = ProcessUtil.getProcessDetails(AgentConstants.UPDATE_PROCESS_DETAILS)
            dict_processData['AGENT_REQUEST_ID'] = '1'
            dict_processData['REQUEST_TYPE'] = AgentConstants.UPDATE_PROCESS_DETAILS
            dict_processData['DATACOLLECTTIME'] = str(AgentUtil.getTimeInMillis())
            dict_processData['ERRORMSG'] = 'NO ERROR'
            dict_processData['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
            str_jsonData = json.dumps(dict_processData)#python dictionary to json string
            AgentLogger.debug(AgentLogger.COLLECTOR, 'Process details collected : '+repr(str_jsonData))
            str_url = None
            if not dict_requestParameters == None:
                str_requestParameters = urlencode(dict_requestParameters)
                str_url = str_servlet + str_requestParameters
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.COLLECTOR)
            requestInfo.set_method(AgentConstants.HTTP_POST)
            requestInfo.set_url(str_url)
            requestInfo.set_data(str_jsonData)
            requestInfo.add_header("Content-Type", 'application/json')
            requestInfo.add_header("Accept", "text/plain")
            requestInfo.add_header("Connection", 'close')
            (isSuccess, int_errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
        except Exception as e:
            AgentLogger.log([AgentLogger.STDERR], ' *************************** Exception while discovering processes for updating agents below version 11.0.0 *************************** '+ repr(e))
            traceback.print_exc()
        return dict_processData

    @staticmethod
    def discoverAndUploadProcess(dict_task, str_loggerName = AgentLogger.STDOUT):
        bool_isSuccess = True
        str_agentDataCollFileName = None
        str_agentDataCollFilePath = None
        file_obj = None
        str_dataToSend = None
        try:
            if AgentUtil.is_module_enabled(AgentConstants.PROCESS_DISCOVERY):
                if os.path.exists(AgentConstants.PS_UTIL_CHECK_FILE):
                    AgentLogger.log(AgentLogger.CHECKS,' process discovery using ps util ')
                    dict_processData = ProcessUtil.get_processes_using_psutil()
                else:
                    if AgentConstants.OS_NAME==AgentConstants.AIX_OS_LOWERCASE:
                        dict_processData = ProcessUtil.get_aix_process_data()
                    elif AgentConstants.OS_NAME.lower()==AgentConstants.SUN_OS.lower():
                        dict_processData = ProcessUtil.get_aix_process_data(AgentConstants.SUNOS_PROCESS_COMMAND)
                    else:
                        dict_processData, list_psCommandOutput = ProcessUtil.getProcessDetails(dict_task['REQUEST_TYPE'])
                if dict_task['REQUEST_TYPE'] == AgentConstants.TEST_MONITOR:
                    dict_processData['NAME'] = dict_task['REQUEST_TYPE']
                    dict_processData['ACTION_TO_CALL'] = 'false'
                else:
                    dict_processData['REQUEST_TYPE'] = dict_task['REQUEST_TYPE']
                dict_processData['AGENT_REQUEST_ID'] = dict_task['AGENT_REQUEST_ID']
                dict_processData['DATACOLLECTTIME'] = str(AgentUtil.getTimeInMillis())
                dict_processData['ERRORMSG'] = 'NO ERROR'
                dict_processData['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
                str_jsonData = json.dumps(dict_processData)#python dictionary to json string
                AgentLogger.debug(str_loggerName, 'Process details collected')
                AgentLogger.debug(str_loggerName,str_jsonData)
                str_url = None
                str_servlet = AgentConstants.DATA_AGENT_HANDLER_SERVLET
                dict_requestParameters      =   {
                'action'   :   dict_task['REQUEST_TYPE'],
                'agentKey'  :   AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),
                'bno' : AgentConstants.AGENT_VERSION,
                'requestId'   :  str(dict_task['AGENT_REQUEST_ID']),
                'custID' : AgentConstants.CUSTOMER_ID           
                }
                if not dict_requestParameters == None:
                    str_requestParameters = urlencode(dict_requestParameters)
                    str_url = str_servlet + str_requestParameters
                requestInfo = CommunicationHandler.RequestInfo()
                requestInfo.set_loggerName(str_loggerName)
                requestInfo.set_method(AgentConstants.HTTP_POST)
                requestInfo.set_url(str_url)
                requestInfo.set_data(str_jsonData)
                requestInfo.add_header("Content-Type", 'application/json')
                requestInfo.add_header("Accept", "text/plain")
                requestInfo.add_header("Connection", 'close')
                bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
                dict_requestParameters.pop('custID')
                AgentLogger.log(AgentLogger.CHECKS,' response of process discovery -- {0} and {1}'.format(dict_requestParameters,dict_responseData))
            else:
                AgentLogger.log(AgentLogger.CHECKS,'Process Discovery Disabled for this agent')      
        except Exception as e:
            AgentLogger.log([str_loggerName,AgentLogger.CRITICAL], ' *************************** Exception while discovering processes *************************** '+ repr(e))
            traceback.print_exc()
            bool_isSuccess = False
        return bool_isSuccess
    
    @staticmethod
    def getProcessDetails(action=AgentConstants.DISCOVER_PROCESSES_AND_SERVICES, str_rawProcessData = None, str_loggerName = AgentLogger.COLLECTOR):
        dict_toReturn = None
        list_psCommandOutput = None
        try:
            if action != AgentConstants.PROCESS_AND_SERVICE_DETAILS:
                if AgentConstants.OS_NAME ==  AgentConstants.SUN_OS:
                    dict_toReturn = ProcessUtil.get_aix_process_data(AgentConstants.SUNOS_PROCESS_COMMAND)
                else:
                    str_rawProcessData = ProcessUtil.getRawProcessData()
                if not str_rawProcessData and not dict_toReturn:
                    AgentLogger.log(AgentLogger.COLLECTOR,'*************************** Unable to get raw process data for the action : '+ repr(action) + '***************************')
            if str_rawProcessData:
                if AgentConstants.OS_NAME == AgentConstants.FREEBSD_OS:
                    dict_toReturn, list_psCommandOutput = ProcessUtil.parseBSDRawProcessData(str_rawProcessData, action)
                elif AgentConstants.OS_NAME == AgentConstants.OS_X:
                    dict_toReturn, list_psCommandOutput = ProcessUtil.parseOSXRawProcessData(str_rawProcessData, action)
                else:
                    dict_toReturn, list_psCommandOutput = ProcessUtil.parseRawProcessData(str_rawProcessData, action)
        except Exception as e:
            AgentLogger.log([str_loggerName, AgentLogger.STDERR],' *************************** Exception while fetching process details *************************** '+ repr(e))
            traceback.print_exc()
        return dict_toReturn, list_psCommandOutput
    
    
    @staticmethod
    def get_aix_process_data(process_command=AgentConstants.AIX_PROCESS_COMMAND):
        dict_to_return={}
        list_of_process=[]
        dict_to_return.setdefault('PROCESS_LOG_DATA',[])
        try:
            executorObj = AgentUtil.Executor()
            executorObj.setLogger(AgentLogger.COLLECTOR)
            executorObj.setTimeout(30)
            executorObj.setCommand(process_command)
            executorObj.executeCommand()
            retVal    = executorObj.getReturnCode()
            stdOutput = executorObj.getStdOut()
            stdErr    = executorObj.getStdErr()
            if stdOutput:
                processes = stdOutput.split('\n')
                for each_process in processes:
                    if not each_process or each_process.strip().startswith('PID'):
                        continue
                    inner_process_dict = {}
                    process_metrics = each_process.split()
                    if len(process_metrics) < 8:
                        continue
                    inner_process_dict['Name'] = str(process_metrics[6])
                    inner_process_dict['ProcessId'] = str(process_metrics[0])
                    inner_process_dict['User'] = str(process_metrics[1])
                    inner_process_dict['Priority'] = process_metrics[2]
                    inner_process_dict['CPU_UTILIZATION'] = str(process_metrics[3])
                    inner_process_dict['MEMORY_UTILIZATION'] = str(process_metrics[4])
                    inner_process_dict['ThreadCount'] = str(process_metrics[5])
                    inner_process_dict['ExecutablePath'] = str(process_metrics[6])
                    inner_process_dict['HandleCount']='0'
                    inner_process_dict['CommandLine']=process_metrics[7]
                    for i , val in enumerate(process_metrics):
                        if i > 7:
                            inner_process_dict['CommandLine']+= " "+val
                    inner_process_dict['CommandLine']=inner_process_dict['CommandLine'].strip()
                    list_of_process.append(inner_process_dict)
                dict_to_return['PROCESS_LOG_DATA']=list_of_process
            AgentLogger.log(AgentLogger.COLLECTOR,' process command output -- {0}'.format(dict_to_return)+'\n')
        except Exception as e:
            traceback.print_exc()
        return dict_to_return
    
    @staticmethod
    def get_processes_using_psutil(process_list=None):
        dict_to_return = None
        try:
            import psutil
            list_of_process=[]
            dict_to_return = {}
            dict_to_return.setdefault('PROCESS_LOG_DATA',[])
            for proc in psutil.process_iter():
                inner_process_dict = {}
                try:
                    pinfo = proc.as_dict(attrs=['pid', 'name', 'username','num_threads','cpu_percent','memory_percent','cmdline','open_files','nice','create_time','memory_info'])
                    process_name = pinfo['name']
                    if process_list:
                        if process_name not in process_list:
                            continue
                    inner_process_dict['CPU_UTILIZATION'] = str(pinfo['cpu_percent'])
                    inner_process_dict['User'] = str(pinfo['username'])
                    inner_process_dict['MEMORY_UTILIZATION'] = str(pinfo['memory_percent'])
                    inner_process_dict['ProcessId']= str(pinfo['pid'])
                    inner_process_dict['ThreadCount'] = str(pinfo['num_threads'])
                    inner_process_dict['Name'] = pinfo['name']
                    inner_process_dict['Priority'] = str(pinfo['nice']+20) if pinfo['nice'] != None else '0'
                    inner_process_dict['uptime'] = AgentUtil.process_uptime_in_secs(pinfo['create_time'], True)
                    inner_process_dict['size'] = pinfo['memory_info'].rss #Bytes
                    handle_count = pinfo['open_files']
                    if type(handle_count) is list:
                        inner_process_dict['HandleCount'] = str(len(handle_count))
                    command_line_args = None
                    command_line_args = pinfo['cmdline']
                    process_args=''
                    if command_line_args:
                        cmd = ' '.join(command_line_args)
                        process_args = cmd
                    else:
                        process_args = '['+pinfo['name']+']'
                    inner_process_dict['CommandLine'] = process_args
                    #AgentLogger.log(AgentLogger.COLLECTOR,' process arguments -- {0}'.format(process_args))
                    if process_args:
                        inner_process_dict['ExecutablePath'] = process_args.split()[0]
                    else:
                        inner_process_dict['ExecutablePath'] = 'check'
                        AgentLogger.debug(AgentLogger.CHECKS,' ##### aix check #####')
                        continue
                    list_of_process.append(inner_process_dict)
                except psutil.NoSuchProcess:
                    AgentLogger.log(AgentLogger.STDERR,' no such process using psutil')
                    traceback.print_exc()
        except Exception as e:
            traceback.print_exc()
            AgentLogger.log(AgentLogger.COLLECTOR,' process arguments 2 -- {0}'.format(process_args))
        dict_to_return['PROCESS_LOG_DATA'] = list_of_process
        return dict_to_return
        
    @staticmethod
    def getProcessMonitoringData(str_rawProcessData):
        dict_toReturn = None
        list_psCommandOutput = None
        try:
            dict_toReturn, list_psCommandOutput = ProcessUtil.parseProcessMonitoringData(str_rawProcessData)
        except Exception as e:
            AgentLogger.log([str_loggerName, AgentLogger.STDERR],' *************************** Exception while fetching process details *************************** '+ repr(e))
            traceback.print_exc()
        return dict_toReturn, list_psCommandOutput
    
    # psCommandList = [pid, processName, psCpu, psMem, nlwp, handleCount, path, CommandArgs]
    # psCommandListAfterMergingTopResults = [pid, processName, psCpu, psMem, nlwp, handleCount, path, CommandArgs, topCpu, topMem]
    
    @staticmethod
    def processMonitor():
        str_rawProcessData = None
        dict_toReturn = {}
        list_psCommandOutput = []
        dict_processStatus = {}
        try:
            AgentLogger.log(AgentLogger.COLLECTOR,"============================ Process Monitoring ============================")
            str_rawProcessData = ProcessUtil.getRawProcessData()
            AgentLogger.debug(AgentLogger.COLLECTOR,'String of raw processed data : '+str(str_rawProcessData))
            dict_toReturn, list_psCommandOutput = ProcessUtil.getProcessDetails(AgentConstants.PROCESS_AND_SERVICE_DETAILS,str_rawProcessData)
            AgentLogger.debug(AgentLogger.COLLECTOR,"Dictionary of process to monitor : "+str(dict_toReturn))
            ProcessUtil.updateProcessMonitorDictionary(dict_toReturn)
            dict_processStatus = ProcessUtil.processMonitorStatus(str_rawProcessData)
            AgentLogger.debug(AgentLogger.COLLECTOR,'Updated status of processes being monitored : '+str(dict_processStatus))
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL, AgentLogger.STDERR],' *************************** Exception while fetching process monitor details *************************** '+ repr(e) + '\n')
            traceback.print_exc()            
        return dict_processStatus,dict_toReturn
        
    @staticmethod
    def updateProcessMonitorDictionary(dict_processDetailsToMonitor):
        #bool_scheduleProcessMonitor = False
        try:
            #ProcessUtil.dict_totalProcessDetails = ProcessUtil.process_details_dict
            AgentLogger.log(AgentLogger.COLLECTOR,' ============================ Checking for any additions in list of processes to be monitored =========================')
            AgentLogger.log(AgentLogger.COLLECTOR,'PROCESS_LIST : '+str(PROCESS_LIST))
            if 'Process Details' in dict_processDetailsToMonitor:
                for eachProcessDetailToMonitor in dict_processDetailsToMonitor['Process Details']:
                    for  eachProcessAlreadyExisting in ProcessUtil.dict_totalProcessDetails['Process Details']:
                        #if re.sub(r' --channel=.*','',eachProcessDetailToMonitor['COMMANDLINE']) == re.sub(r' --channel=.*','',eachProcessAlreadyExisting['COMMANDLINE']):
                        if eachProcessDetailToMonitor['PROCESS_NAME'] == eachProcessAlreadyExisting['PROCESS_NAME']:
                            #eachProcessAlreadyExisting['COMMANDLINE'] = eachProcessDetailToMonitor['COMMANDLINE']  #Updating to latest parameters if there is a change
                            #AgentLogger.debug(AgentLogger.COLLECTOR,'Modified %s To %s :' %(str(eachProcessAlreadyExisting['COMMANDLINE']),str(eachProcessDetailToMonitor['COMMANDLINE'])))
                            AgentLogger.debug(AgentLogger.COLLECTOR," ==================== The process %s is already under monitor ======================" %(str(eachProcessAlreadyExisting['PROCESS_NAME'])))
                            break
                    else:
                        #if not ProcessUtil.dict_totalProcessDetails['Process Details']:
                            #bool_scheduleProcessMonitor = True
                        ProcessUtil.dict_totalProcessDetails['Process Details'].append(eachProcessDetailToMonitor)
                        AgentLogger.log(AgentLogger.COLLECTOR,"Incoming new process details to monitor: "+str(eachProcessDetailToMonitor))
            AgentLogger.debug(AgentLogger.COLLECTOR,"Updated details of processes to be monitored: "+str(ProcessUtil.dict_totalProcessDetails))
            #ProcessUtil.persistProcessDetailsList()
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR],' ************************** Exception while checking for any new additions in processes to be monitored **************************** \n')
            traceback.print_exc()
        #return bool_scheduleProcessMonitor
        
    @staticmethod
    def processMonitorStatus(str_rawProcessData):
        list_processDetails = None
        dict_processStatus = {}
        try:
            list_processDetails = []
            AgentLogger.log(AgentLogger.COLLECTOR,' ==================================== PROCESS MONITOR STATUS ==================================')
            AgentLogger.log(AgentLogger.COLLECTOR,"List of processes already down notified: "+str(ProcessUtil.list_downNotifiedProcess))
            AgentLogger.debug(AgentLogger.COLLECTOR,"Details of processes/process monitored : "+str(ProcessUtil.dict_totalProcessDetails['Process Details']))
            for eachProcessArgs in ProcessUtil.dict_totalProcessDetails['Process Details']:
                AgentLogger.debug(AgentLogger.COLLECTOR,"Command line argument of process %s is %s :" %(str(eachProcessArgs['PROCESS_NAME']),str(eachProcessArgs['COMMANDLINE'])))
                #list_processDetails.append(eachProcessArgs['COMMANDLINE'])
                if eachProcessArgs['PROCESS_NAME'] in str_rawProcessData:
                    AgentLogger.debug(AgentLogger.COLLECTOR,'Status of process/processes being monitored : '+str(ProcessUtil.process_status_dict))
                    if ProcessUtil.process_status_dict :
                        AgentLogger.debug(AgentLogger.COLLECTOR,'Process name : '+str(eachProcessArgs['PROCESS_NAME']))
                        if eachProcessArgs['PROCESS_NAME'] in ProcessUtil.process_status_dict.keys():
                            if ProcessUtil.process_status_dict[eachProcessArgs['PROCESS_NAME']] == 'false':
                                if eachProcessArgs['PROCESS_NAME'] not in ProcessUtil.list_downNotifiedProcess:
                                    ProcessUtil.list_downNotifiedProcess.append(eachProcessArgs['PROCESS_NAME'])
                                    #ProcessUtil.list_downNotifiedProcess.remove(eachProcessArgs['PROCESS_NAME'])
                                    AgentLogger.log(AgentLogger.COLLECTOR,"List of processes already down notified: "+str(ProcessUtil.list_downNotifiedProcess))
                    dict_processStatus[eachProcessArgs['PROCESS_NAME']] = 'true'
                else:
                    if ProcessUtil.process_status_dict:
                        if eachProcessArgs['PROCESS_NAME'] in ProcessUtil.process_status_dict.keys():
                            if ProcessUtil.process_status_dict[eachProcessArgs['PROCESS_NAME']] == 'false': 
                                if eachProcessArgs['PROCESS_NAME'] not in ProcessUtil.list_downNotifiedProcess:
                                    ProcessUtil.list_downNotifiedProcess.append(eachProcessArgs['PROCESS_NAME'])
                                AgentLogger.debug(AgentLogger.COLLECTOR,'List of processes already down notified : '+str(ProcessUtil.list_downNotifiedProcess))                                                
                    dict_processStatus[eachProcessArgs['PROCESS_NAME']] = 'false'
            ProcessUtil.persistProcessStatusList(dict_processStatus)
            ProcessUtil.persistProcessDetailsList()                   
            #dict_processStatus = ProcessUtil.checkProcessStatus(list_processDetails)
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR,'************************************* Exception while extracting process details from dictionary ***********************')
            traceback.print_exc()
        return dict_processStatus
    
    @staticmethod
    def checkProcessStatus(list_procDetails):
        dict_processStatus = {}
        try:
            AgentLogger.log(AgentLogger.COLLECTOR,'============================== Checking process status ==============================')
            AgentLogger.log(AgentLogger.COLLECTOR,"List of process arguments :"+str(list_procDetails))
            for processargs in list_procDetails:
                escapedProcessargs = processargs.replace("/","\/").replace(".","\.").replace("*","\*").replace("[","\[").replace("]","\]").replace("(","\(").replace(")","\)").replace(":","\:").replace(";","\;").replace("@","\@").replace("#","\#").replace("$","\$")
                escapedProcessargs = '"{}"' .format(escapedProcessargs)
                AgentLogger.log(AgentLogger.COLLECTOR,"Command-line argument of process after escaping special characters: "+escapedProcessargs)
                command = AgentConstants.VIEW_PROCESSES_RUNNING_COMMAND+' '+escapedProcessargs
                AgentLogger.log(AgentLogger.COLLECTOR,"COMMAND: "+str(command))
                executorObj = AgentUtil.Executor()
                executorObj.setLogger(AgentLogger.COLLECTOR)
                executorObj.setTimeout(7)
                executorObj.setCommand(command)
                #executorObj.redirectToFile(True)
                executorObj.executeCommand()
                AgentLogger.log(AgentLogger.COLLECTOR,"Standard output from command-line executor: "+str(executorObj.getStdOut()))
                #AgentLogger.log(AgentLogger.COLLECTOR,"std_error: "+str(executorObj.getStdErr()))
                if executorObj.getStdOut():
                    dict_processStatus[processargs] = 'true'
                else:
                    dict_processStatus[processargs] = 'false'
            AgentLogger.debug(AgentLogger.COLLECTOR,"Process status dictionary: "+str(dict_processStatus))
        except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],' *********************** Exception while checking for process status ************************')
            traceback.print_exc()
        return dict_processStatus
    
    @staticmethod
    def processCallback(tupleArgs):
        dict_processStatus = None
        dict_processTobeSentToServer = None
        toNotify = False
        boolToUpdate = True
        try:
            listSuspectedDown = []
            dict_processStatus,dict_processTobeSentToServer = tupleArgs
            AgentLogger.log(AgentLogger.COLLECTOR,"Status of process/processes monitored: "+str(dict_processStatus))
            for processArgs in dict_processStatus.keys():
                if ((dict_processStatus[processArgs] == 'false') and (processArgs in ProcessUtil.list_downNotifiedProcess)):
                    AgentLogger.log(AgentLogger.COLLECTOR,"The process %s is already notified to be down" %(processArgs))
                elif ((dict_processStatus[processArgs] == 'false') and (processArgs not in ProcessUtil.list_downNotifiedProcess)):
                    AgentLogger.log(AgentLogger.COLLECTOR,"The process %s is down and hence notifying to server" %(processArgs))
                    #ADDITIONAL CHECK STARTS HERE
                    AgentLogger.log(AgentLogger.COLLECTOR,"Will do Additional check for suspected down process: " + str(processArgs))
                    listSuspectedDown.append(str(processArgs))
                    toNotify = True
                    '''str_command = AgentConstants.PROCESS_STATUS_COMMAND + " \"" + processArgs + "\" | wc -l"
                    isSuccess, str_output = AgentUtil.executeCommand(str_command)
                    AgentLogger.log(AgentLogger.COLLECTOR," Printing output from additional check command " + str_command + " : " + str_output)
                    if isSuccess:
                        try:
                            if int(str_output) > 0:
                                AgentLogger.log(AgentLogger.COLLECTOR," Suspected down process is up. Hence skipping instant notification " )
                            else:
                                AgentLogger.log(AgentLogger.COLLECTOR," Suspected down process is confirmed. Hence uploading instant notification " )
                                toNotify = True
                                ProcessUtil.list_downNotifiedProcess.append(processArgs)
                        except Exception as e:
                            AgentLogger.log(AgentLogger.COLLECTOR," Exception in confirming down process status. Hence skipping instant notification " )'''
                    #ADDITIONAL CHECK ENDS HERE
                elif ((dict_processStatus[processArgs] == 'true') and (processArgs in ProcessUtil.list_downNotifiedProcess)):
                    AgentLogger.log(AgentLogger.COLLECTOR,"The down notified process %s just went up and hence notifying to server" %(processArgs))
                    #AgentLogger.log(AgentLogger.COLLECTOR,"Down notified process list : "+str(ProcessUtil.list_downNotifiedProcess))
                    ProcessUtil.list_downNotifiedProcess.remove(processArgs)
                    #AgentLogger.log(AgentLogger.COLLECTOR,"Down notified process list : "+str(ProcessUtil.list_downNotifiedProcess))
                    toNotify = True
                elif ((dict_processStatus[processArgs] == 'true') and (processArgs not in ProcessUtil.list_downNotifiedProcess)):
                    AgentLogger.debug(AgentLogger.COLLECTOR,"The process %s is running" %(processArgs))
            if toNotify:
                AgentLogger.debug(AgentLogger.COLLECTOR,'The dictionary of processes that are up and running : %s '%(str(dict_processTobeSentToServer)))
                dictProcessData = DataConsolidator.updateID(dict_processTobeSentToServer)
                if listSuspectedDown:
                    AgentLogger.log(AgentLogger.COLLECTOR,"Additional check for suspected down process: " + str(listSuspectedDown))
                    boolToUpdate = DataConsolidator.addDownProcCheck(listSuspectedDown)
                if boolToUpdate:
                    ProcessUtil.notfiyProcessStatus(AgentConstants.PROCESS_NOTIFY, dict_processTobeSentToServer)
            #AgentLogger.log(AgentLogger.COLLECTOR,'============================== Process Monitoring Ends ==============================')
        except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],'*********************** Exception while executing process callback ****************************')
            traceback.print_exc()
            
    @staticmethod
    def deleteProcessSchedule(action=AgentConstants.PROCESS_AND_SERVICE_DETAILS):
        AgentLogger.log(AgentLogger.COLLECTOR,"Deleting schedule of action type: "+str(action))
        scheduleInfo = AgentScheduler.ScheduleInfo()
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName(AgentConstants.PROCESS_MONITOR)
        AgentScheduler.deleteSchedule(scheduleInfo)
        
    @staticmethod   
    def notfiyProcessStatus(action, dict_processInfo):
        bool_isSuccess = True
        AgentLogger.log(AgentLogger.CRITICAL, '================================= NOTIFYING PROCESS STATUS CHANGE =================================')
        AgentLogger.log(AgentLogger.CRITICAL,str(dict_processInfo)+' : '+str(action))
        try:
            str_url = None
            str_servlet = AgentConstants.SERVER_INSTANT_NOTIFIER_SERVLET
            dict_requestParameters = {
                                        'action'    :   action,
                                        'agentKey'  :   AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),
                                        'custID'    :   AgentConstants.CUSTOMER_ID,
                                        'dc'        :   str(AgentUtil.getTimeInMillis()),
                                        'bno' : AgentConstants.AGENT_VERSION
                                     }
            if not dict_requestParameters == None:
                str_requestParameters = urlencode(dict_requestParameters)
                str_url = str_servlet + str_requestParameters
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.COLLECTOR)
            requestInfo.set_method(AgentConstants.HTTP_POST)
            requestInfo.set_url(str_url)
            requestInfo.set_timeout(30)
            str_jsonData = json.dumps(dict_processInfo)#python dictionary to json string
            AgentLogger.log(AgentLogger.COLLECTOR,'Json data to be sent : '+str(str_jsonData))
            requestInfo.set_data(str_jsonData)            
            requestInfo.add_header("Content-Type", 'application/json')
            requestInfo.add_header("Accept", "text/plain")
            requestInfo.add_header("Connection", 'close')
            bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], ' *************************** Exception while notifying process status *************************** '+ repr(e) + '\n')
            traceback.print_exc()
            bool_isSuccess = False
        return bool_isSuccess
    
    @staticmethod    
    def persistProcessStatusList(dict_processStatus):
        if not PROCESS_LIST == None:
            ProcessUtil.process_status_dict = dict_processStatus  
            AgentLogger.debug(AgentLogger.COLLECTOR,'================================= PERSISTING PROCESS STATUS LIST =================================')
            AgentLogger.debug(AgentLogger.COLLECTOR,"Modified process status dictionary being persisted to file : "+str(ProcessUtil.process_status_dict))      
            if not AgentUtil.writeDataToFile(AgentConstants.AGENT_PROCESS_STATUS_LIST_FILE, dict_processStatus):
                AgentLogger.log(AgentLogger.COLLECTOR,'************************* Problem while persisting process status list *************************') 
        else:
            AgentLogger.log(AgentLogger.COLLECTOR,'************************* Process status list to be persisted is empty **************************')
    
    @staticmethod    
    def persistProcessDetailsList():
        if not PROCESS_LIST == None:  
            AgentLogger.debug(AgentLogger.COLLECTOR,'================================= PERSISTING PROCESS DETAILS LIST =================================')
            AgentLogger.debug(AgentLogger.COLLECTOR,str(ProcessUtil.dict_totalProcessDetails))      
            if not AgentUtil.writeDataToFile(AgentConstants.AGENT_PROCESS_DETAILS_LIST_FILE, ProcessUtil.dict_totalProcessDetails):
                AgentLogger.log(AgentLogger.COLLECTOR,'************************* Problem while persisting process details list *************************') 
        else:
            AgentLogger.log(AgentLogger.COLLECTOR,'************************* Process details list to be persisted is empty **************************')
    
    @staticmethod
    def loadProcessStatusList():
        AgentLogger.log(AgentLogger.COLLECTOR,'Loading process status list')
        if os.path.exists(AgentConstants.AGENT_PROCESS_STATUS_LIST_FILE):
            (bool_status, ProcessUtil.process_status_dict) = AgentUtil.loadDataFromFile(AgentConstants.AGENT_PROCESS_STATUS_LIST_FILE)
            if bool_status:        
                AgentLogger.log(AgentLogger.COLLECTOR,'Process status list Loaded From '+AgentConstants.AGENT_PROCESS_STATUS_LIST_FILE+' : '+str(ProcessUtil.process_status_dict))
            else:
                AgentLogger.log(AgentLogger.COLLECTOR,'*********************** Problem while loading process list ************************')
         
    @staticmethod
    def loadProcessDetailsList():
        AgentLogger.log(AgentLogger.COLLECTOR,'Loading process details list')
        if os.path.exists(AgentConstants.AGENT_PROCESS_DETAILS_LIST_FILE):
            (bool_status, ProcessUtil.dict_totalProcessDetails) = AgentUtil.loadDataFromFile(AgentConstants.AGENT_PROCESS_DETAILS_LIST_FILE)
            if bool_status:        
                AgentLogger.log(AgentLogger.COLLECTOR,'Process details list Loaded From '+AgentConstants.AGENT_PROCESS_DETAILS_LIST_FILE+' : '+str(ProcessUtil.dict_totalProcessDetails))
            else:
                AgentLogger.log(AgentLogger.COLLECTOR,'*********************** Problem while loading process list ************************')
    
    @staticmethod
    def parseOSXRawProcessData(str_rawProcessData, action = AgentConstants.DISCOVER_PROCESSES_AND_SERVICES):
        dict_toReturn = None
        try:
            int_topFirstSampleIndex = str_rawProcessData.find('Processes: ') + len('Processes: ')
            int_topSecondSampleIndex = str_rawProcessData.find('Processes: ', int_topFirstSampleIndex)
            
            int_topCommandIndex = str_rawProcessData.find('PID    %CPU', int_topSecondSampleIndex)
            int_psCommandIndex = str_rawProcessData.find('PID USER PRIORITY', int_topSecondSampleIndex)
            
            str_topCommandOutput = str_rawProcessData[int_topCommandIndex:int_psCommandIndex]
            str_psCommandOutput = str_rawProcessData[int_psCommandIndex:]
            
            #tuple_topCommand = (pid, cpu, mem, time, command)
            #tuple_psCommand = (PID, PName, CPU, MEM, NLWP, HC, exe, args)

            dict_topCommandOutput = {}
            for topCommandline in str_topCommandOutput.split('\n'):
                list_topCommandLine = topCommandline.split()
                #some machines have unusual '*' in PID of top hence,
                if list_topCommandLine:
                    list_topCommandLine[0] = list_topCommandLine[0].strip('*')
                    tuple_topCommandLine = tuple(list_topCommandLine)
                if tuple_topCommandLine:
                    dict_topCommandOutput[tuple_topCommandLine[0]] = tuple_topCommandLine
            
            list_psCommandOutput = []
            for psCommandline in str_psCommandOutput.split('\n'):
                list_psCommandLine = list(psCommandline.split(' :: '))
                if len(list_psCommandLine) < 11:
                    continue
                list_psCommandOutput.append(list_psCommandLine)

            if list_psCommandOutput:
                list_psCommandOutput.pop(0)


            list_site24x7ScriptProcessToBeDeleted = []
            for int_index, list_psCommandLine in enumerate(list_psCommandOutput):
                str_commandArgs = list_psCommandLine[10]
                if list_psCommandLine[0] in dict_topCommandOutput:
                    if str_commandArgs.find('/scripts/osx_script.sh') > 0:
                        list_site24x7ScriptProcessToBeDeleted.append(int_index)
                        continue
                    tuple_topCommand = dict_topCommandOutput[list_psCommandLine[0]]
                    psCommandOldProcessArg = list_psCommandLine[10]
                    #converting process uptime from dd-hh:mm:ss into seconds
                    list_psCommandLine[3] = AgentUtil.process_uptime_in_secs(list_psCommandLine[3], False)
                    list_psCommandLine[4] = ' '.join(tuple_topCommand[4:])
                    list_psCommandLine.append(tuple_topCommand[1]) #appending top cpu
                    list_psCommandLine.append(list_psCommandLine[6]) #appending mem of ps as topmem as we cant get top mem
                else:
                    AgentLogger.log(AgentLogger.COLLECTOR,'Deleting the following process missing in top command : '+repr(list_psCommandLine))
                    list_site24x7ScriptProcessToBeDeleted.append(int_index)

            for index, item in enumerate(list_site24x7ScriptProcessToBeDeleted):
                popItem = list_psCommandOutput.pop(item-index)
            #AgentLogger.log(AgentLogger.MAIN,'Final OSX command output list : \n'+repr(len(list_psCommandOutput))+ ' :: ' + repr(list_psCommandOutput)+ " :: "+action)
            dict_toReturn = ProcessUtil.convertProcessListToDictionary(list_psCommandOutput, action)
            
            # Save temp data for RCA
            dict_processIdVsProcessDetails = {}
            dict_tempRCADataToSave = {}
            for list_process in list_psCommandOutput:
                dict_processIdVsProcessDetails[list_process[0]] = list_process
            dict_tempRCADataToSave['Process Details'] = dict_processIdVsProcessDetails
            
            rcaInfo = RcaInfo()
            rcaInfo.action = AgentConstants.SAVE_RCA_RAW
            rcaInfo.data = dict_tempRCADataToSave
            RcaUtil.saveRca(rcaInfo)
        except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],' *************************** Exception while parsing OSX raw process data : '+str(str_rawProcessData)+' *************************** '+ repr(e))
            traceback.print_exc()

        return dict_toReturn, list_psCommandOutput
    
    @staticmethod
    def parseBSDRawProcessData(str_rawProcessData, action = AgentConstants.DISCOVER_PROCESSES_AND_SERVICES):
        dict_toReturn = None
        try:
            int_topFirstSampleIndex = str_rawProcessData.find('last pid:') + len('last pid:')
            int_topSecondSampleIndex = str_rawProcessData.find('last pid:', int_topFirstSampleIndex)
            int_topCommandIndex = str_rawProcessData.find('PID USER', int_topSecondSampleIndex)
            int_psCommandIndex = str_rawProcessData.find('PID USER PRIORITY')
            str_psCommandOutput = str_rawProcessData[int_psCommandIndex:]
            str_topCommandOutput = str_rawProcessData[int_topCommandIndex:int_psCommandIndex]
            dict_topCommandOutput = {}
            list_psCommandOutput = []
            list_site24x7ScriptProcessToBeDeleted = []
            for topCommandline in str_topCommandOutput.split('\n'):
                tuple_topCommandLine = tuple(topCommandline.split())
                if tuple_topCommandLine:
                    dict_topCommandOutput[tuple_topCommandLine[0]] = tuple_topCommandLine
            if dict_topCommandOutput:
                AgentLogger.debug(AgentLogger.COLLECTOR,'FreeBSD top command output dict : ' + repr(dict_topCommandOutput))
            for psCommandline in str_psCommandOutput.split('\n'):
                list_psCommandLine = list(psCommandline.split(' :: '))
                if len(list_psCommandLine) < 11:
                    continue
                list_psCommandOutput.append(list_psCommandLine)

            if list_psCommandOutput:
                list_psCommandOutput.pop(0)

            AgentLogger.debug(AgentLogger.COLLECTOR,'FreeBSD PS command output list : '+repr(len(list_psCommandOutput))+'  '+repr(list_psCommandOutput))
            for int_index, list_psCommandLine in enumerate(list_psCommandOutput):
                str_commandArgs = list_psCommandLine[10]
                if list_psCommandLine[0] in dict_topCommandOutput:
                    if str_commandArgs.find(AgentConstants.SCRIPTS_FILE_PATH) > 0:
                        list_site24x7ScriptProcessToBeDeleted.append(int_index)
                        continue
                    tuple_topCommand = dict_topCommandOutput[list_psCommandLine[0]]
                    # not converting process uptime since its already in seconds
                    str_topCpu = list_psCommandLine[5]
                    str_topMem = list_psCommandLine[6]
                    list_psCommandLine.append(str_topCpu) #appending pscpu as topcpu as we cant get topcpu
                    list_psCommandLine.append(str_topMem) #appending  psmem as topmem as we cant get topmem
                else:
                    AgentLogger.log(AgentLogger.COLLECTOR,'Deleting the following process missing in top command : '+repr(list_psCommandLine))
                    list_site24x7ScriptProcessToBeDeleted.append(int_index)


            for index, item in enumerate(list_site24x7ScriptProcessToBeDeleted):
                popItem = list_psCommandOutput.pop(item-index)

            #AgentLogger.log(AgentLogger.MAIN,'Final FreeBSD PS command output list : \n'+repr(len(list_psCommandOutput))+ ' :: ' + repr(list_psCommandOutput)+ " :: "+action)
            dict_toReturn = ProcessUtil.convertProcessListToDictionary(list_psCommandOutput, action)

            # Save temp data for RCA
            dict_processIdVsProcessDetails = {}
            dict_tempRCADataToSave = {}
            for list_process in list_psCommandOutput:
                dict_processIdVsProcessDetails[list_process[0]] = list_process
            dict_tempRCADataToSave['Process Details'] = dict_processIdVsProcessDetails
            rcaInfo = RcaInfo()
            rcaInfo.action = AgentConstants.SAVE_RCA_RAW
            rcaInfo.data = dict_tempRCADataToSave
            RcaUtil.saveRca(rcaInfo)
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR],' *************************** Exception while parsing raw process data : '+str(str_rawProcessData)+' *************************** '+ repr(e))
            traceback.print_exc()
        return dict_toReturn, list_psCommandOutput
            
    
    @staticmethod
    def parseRawProcessData(str_rawProcessData, action = AgentConstants.DISCOVER_PROCESSES_AND_SERVICES):
        dict_toReturn = None
        try:
            int_topFirstSampleIndex = str_rawProcessData.find('top -') + len('top -')
            int_topSecondSampleIndex = str_rawProcessData.find('top -', int_topFirstSampleIndex)
            int_topCommandIndex = str_rawProcessData.find('PID USER', int_topSecondSampleIndex)
            int_psCommandIndex = str_rawProcessData.find('PID  USER   PRI', int_topSecondSampleIndex)
            str_cpuMetricsInTopOutput = str_rawProcessData[int_topSecondSampleIndex:int_topCommandIndex]
            str_topCommandOutput = str_rawProcessData[int_topCommandIndex:int_psCommandIndex]
            str_psCommandOutput = str_rawProcessData[int_psCommandIndex:]
            dict_topCommandOutput = {}
            list_psCommandOutput = []
            list_site24x7ScriptProcessToBeDeleted = []
            for topCommandline in str_topCommandOutput.split('\n'):
                tuple_topCommandLine = tuple(topCommandline.split())
                if tuple_topCommandLine:
                    dict_topCommandOutput[tuple_topCommandLine[0]] = tuple_topCommandLine
            for psCommandline in str_psCommandOutput.split('\n'):
                list_psCommandLine = list(psCommandline.split(' :: '))
                if len(list_psCommandLine) < 12:
                    continue
                list_psCommandOutput.append(list_psCommandLine)
            if list_psCommandOutput:
                list_psCommandOutput.pop(0)
            
            for int_index, list_psCommandLine in enumerate(list_psCommandOutput):
                #AgentLogger.log(AgentLogger.COLLECTOR,'PS command line list : '+repr(list_psCommandLine))
                str_commandArgs = list_psCommandLine[10]
                #AgentLogger.debug(AgentLogger.COLLECTOR,repr(int_index)+'   str_commandArgs : '+repr(len(list_psCommandLine))+'  '+repr(str_commandArgs))
                if list_psCommandLine[0] in dict_topCommandOutput:
                    if str_commandArgs.find(AgentConstants.SCRIPTS_FILE_PATH) > 0:
                        #AgentLogger.debug(AgentLogger.COLLECTOR,'str_commandArgssssssssssssssssss : '+repr(list_psCommandLine[0])+repr(int_index)+'   '+'    '+repr(str_commandArgs)+repr(str_commandArgs.find('/opt/site24x7/monagent/scripts/script.sh')))
                        list_site24x7ScriptProcessToBeDeleted.append(int_index)
                        continue
                    tuple_topCommand = dict_topCommandOutput[list_psCommandLine[0]]
                    psCommandOldProcessArg = list_psCommandLine[11]
                    #converting process uptime from dd-hh:mm:ss into seconds
                    list_psCommandLine[3] = AgentUtil.process_uptime_in_secs(list_psCommandLine[3], False)
                    list_psCommandLine[11] = tuple_topCommand[8] #appending top CPU
                    list_psCommandLine.append(tuple_topCommand[9]) #appending top memory
                    list_psCommandLine.append(psCommandOldProcessArg)
                else:
                    AgentLogger.log(AgentLogger.COLLECTOR,'Deleting the following process missing in top command : '+repr(list_psCommandLine))
                    list_site24x7ScriptProcessToBeDeleted.append(int_index)
                    #AgentLogger.debug(AgentLogger.COLLECTOR,'PS command output list : \n'+repr(list_psCommandLine)+'\n'+repr(tuple_topCommand))
            for index, item in enumerate(list_site24x7ScriptProcessToBeDeleted):
                popItem = list_psCommandOutput.pop(item-index)
            dict_toReturn = ProcessUtil.convertProcessListToDictionary(list_psCommandOutput, action)
            # Save temp data for RCA
            dict_processIdVsProcessDetails = {}
            dict_tempRCADataToSave = {}
            for list_process in list_psCommandOutput:
                dict_processIdVsProcessDetails[list_process[0]] = list_process
            dict_tempRCADataToSave['Process Details'] = dict_processIdVsProcessDetails
            rcaInfo = RcaInfo()
            rcaInfo.action = AgentConstants.SAVE_RCA_RAW
            rcaInfo.data = dict_tempRCADataToSave
            RcaUtil.saveRca(rcaInfo)
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR],' *************************** Exception while parsing raw process data : '+str(str_rawProcessData)+' *************************** '+ repr(e) + '\n')
            traceback.print_exc()
        return dict_toReturn, list_psCommandOutput
    
    @staticmethod
    def parseProcessMonitoringData(str_rawProcessData):
        dict_toReturn = {}
        try:
            list_psCommandOutput = []
            list_psCommandLine=[]
            for psCommandline in str_rawProcessData.split('\n'):
                if psCommandline.strip()=='' or psCommandline.startswith('PID'):
                    continue
                else:
                    list_psCommandLine = list(psCommandline.split(' :: '))
                    if len(list_psCommandLine) < 13:
                        continue
                    list_psCommandOutput.append(list_psCommandLine)
            
            finaleProcessList = []
            #AgentLogger.log(AgentLogger.COLLECTOR,' ps command output --- {0}'.format(list_psCommandLine))
            for int_index, ps_list in enumerate(list_psCommandOutput):
                #AgentLogger.log(AgentLogger.COLLECTOR,' list and ps == {0}{1}'.format(int_index,ps_list))
                processDict = {}

                processDict['pid'] = ps_list[0]
                processDict['user'] = ps_list[1]
                processDict['priority'] = ps_list[2]
                if ':' in ps_list[3]:
                    processDict['uptime'] = AgentUtil.process_uptime_in_secs(ps_list[3], False)
                else:
                    processDict['uptime'] = ps_list[3]
                processDict['size'] = int(ps_list[4])*1024 #size is the memory used by process, KB to Bytes
                processDict['pname'] = ps_list[5]
                processDict['pcpu'] = ps_list[6]
                processDict['pmem'] = ps_list[7]
                processDict['pthread'] = ps_list[8]
                processDict['phandle'] = ps_list[9]
                processDict['path'] = ps_list[10]
                processDict['pargs'] = ps_list[11]
                processDict['AVAILABILITY'] = 1

                if processDict['pargs'].find(AgentConstants.SCRIPTS_FILE_PATH) > 0:
                    continue
                finaleProcessList.append(processDict)
            
            dict_toReturn['Process Details'] = finaleProcessList
            #AgentLogger.log(AgentLogger.COLLECTOR,' process dict -- {0}'.format(json.dumps(dict_toReturn)))
#                 if list_psCommandLine[0] in dict_topCommandOutput:
#                     psCommandOldProcessArg = list_psCommandLine[8]
#                     list_psCommandLine[8] = tuple_topCommand[8]
#                     list_psCommandLine.append(tuple_topCommand[9]) #appending top cpu
#                     list_psCommandLine.append(psCommandOldProcessArg) #appending top memory
#                 else:
#                     AgentLogger.log(AgentLogger.COLLECTOR,'Deleting the following process missing in top command : '+repr(list_psCommandLine))
#                     list_site24x7ScriptProcessToBeDeleted.append(int_index)
#             for index, item in enumerate(list_site24x7ScriptProcessToBeDeleted):
#                 popItem = list_psCommandOutput.pop(item-index)
#                
#             dict_toReturn = ProcessUtil.convertProcessListToDictionary(list_psCommandOutput, action)
#             # Save temp data for RCA
#             dict_processIdVsProcessDetails = {}
#             dict_tempRCADataToSave = {}
#             for list_process in list_psCommandOutput:
#                 dict_processIdVsProcessDetails[list_process[0]] = list_process
#             dict_tempRCADataToSave['Process Details'] = dict_processIdVsProcessDetails
#             rcaInfo = RcaInfo()
#             rcaInfo.action = AgentConstants.SAVE_RCA_RAW
#             rcaInfo.data = dict_tempRCADataToSave
#             RcaUtil.saveRca(rcaInfo)
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR],' *************************** Exception while parsing raw process data : '+str(str_rawProcessData)+' *************************** '+ repr(e) + '\n')
            traceback.print_exc()
        return dict_toReturn, list_psCommandOutput
    
    #used in linux only for TEST_MONITOR action
    @staticmethod
    def convertProcessListToDictionary(list_psCommandOutput, action):
        #AgentLogger.log(AgentLogger.MAIN,'\n\nAction --- '+action)
        dict_toReturn = {}
        list_processDetails = []
        list_processNamesToBeFiltered = []
        dict_processNamesToBeFiltered = {}
        try:
            if action == AgentConstants.PROCESS_AND_SERVICE_DETAILS or action == AgentConstants.UPDATE_PROCESS_DETAILS:
                #dict_processMonDetails = COLLECTOR.getMonitors()[AgentConstants.PROCESS_AND_SERVICE_DETAILS]['Attributes']
                # 'searchValues' value will be present when at least one process is monitored in the server.
                # Below check just prevents huge process data from being sent to the server when no process is being monitored.
                list_processNamesToBeFiltered = getProcessNameList()
                '''for each_proc in list_processNamesToBeFiltered:
                    dict_processNamesToBeFiltered[each_proc] = False
                    AgentLogger.debug(AgentLogger.COLLECTOR,' Set all Process List as False ')'''
                #AgentLogger.debug(AgentLogger.COLLECTOR,'Action : '+repr(action)+', List of process names to be filtered : '+repr(list_processNamesToBeFiltered))
                AgentLogger.debug(AgentLogger.COLLECTOR,'Process list collected : \n')
                AgentLogger.debug(AgentLogger.COLLECTOR,list_psCommandOutput)
            for list_process in list_psCommandOutput:
                dict_processMap = {}
                AgentLogger.debug(AgentLogger.COLLECTOR,'Process list : '+repr(list_process))
                if (action == AgentConstants.PROCESS_AND_SERVICE_DETAILS or action == AgentConstants.UPDATE_PROCESS_DETAILS) and list_process[4] not in list_processNamesToBeFiltered:
                    AgentLogger.debug(AgentLogger.COLLECTOR,'Process name : '+repr(list_process[4]))
                    AgentLogger.debug(AgentLogger.COLLECTOR,'continue : '+repr(list_process[4] not in list_processNamesToBeFiltered))
                    continue

                #AgentLogger.log(AgentLogger.MAIN,'\n\n### Process List : '+repr(list_process))
                # Process List : ['1052364', 'root', '19', '04:34', 'Site24x7', '1.8', '0.6', '5', '10', '/opt/site24x7/monagent/lib/', ' /opt/site24x7/monagent/lib/applog/Site24x7Applog', '0.0', '0.7', '/opt/site24x7/monagent/lib/applog/Site24x7Applog']
                if action == AgentConstants.UPDATE_PROCESS_DETAILS:
                    dict_processMap['PROCESS_ID'] = list_process[0]
                    dict_processMap['Name'] = list_process[4] if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['PathName'] = list_process[9] if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['Arguments'] = list_process[10]  if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['OldPath'] = list_process[9]
                    dict_processMap['OldArguments'] = list_process[10]
                elif action == AgentConstants.REGISTER_AGENT_DISCOVER_PROCESSES_AND_SERVICES:
                    dict_processMap['PROCESS_ID'] = list_process[0]
                    dict_processMap['Name'] = list_process[4]  if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['PathName'] = list_process[9]  if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['Arguments'] = list_process[10]  if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                elif action == AgentConstants.TEST_MONITOR:
                    dict_processMap['ProcessId'] = list_process[0]
                    dict_processMap['User'] = list_process[1]  if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['Name'] = list_process[4]  if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['ExecutablePath'] = list_process[9]  if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['CommandLine'] = list_process[10]  if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                else:
                    dict_processMap['ProcessId'] = list_process[0]
                    dict_processMap['USER'] = list_process[1]  if AgentConstants.OS_NAME in [AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['PRIORITY'] =list_process[2] if AgentConstants.OS_NAME in [AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['UPTIME'] = list_process[3] if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['PROCESS_NAME'] = list_process[4]  if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['EXEUTABLE_PATH'] = list_process[9]  if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['COMMANDLINE'] = list_process[10]  if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""

                if action == AgentConstants.PROCESS_AND_SERVICE_DETAILS:
                    dict_processMap['CPU_UTILIZATION'] = list_process[11] if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['MEMORY_UTILIZATION'] = list_process[12] if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['THREAD_COUNT'] = list_process[7] if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['HANDLE_COUNT'] = list_process[8] if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['PS_CPU_UTILIZATION'] = list_process[5] if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['PS_MEMORY_UTILIZATION'] = list_process[6] if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['AVAILABILITY'] = 1
                    '''dict_processNamesToBeFiltered[list_process[1]] = True
                    AgentLogger.debug(AgentLogger.COLLECTOR,' Set dict as true for process : ' + str(list_process[1]))'''
                elif action == AgentConstants.TEST_MONITOR:
                    dict_processMap['CPU_UTILIZATION'] = list_process[5] if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    regex_out = re.search('[a-zA-Z]+',dict_processMap['CPU_UTILIZATION'])
                    if regex_out:
                        AgentLogger.log(AgentLogger.COLLECTOR,'incorrect cpu utilization value found so skipping -- {0} | {1}'.format(dict_processMap['Name'],dict_processMap['CPU_UTILIZATION']))
                        continue
                    dict_processMap['MEMORY_UTILIZATION'] = list_process[6] if AgentConstants.OS_NAME == AgentConstants.LINUX_OS else list_process[11] if AgentConstants.OS_NAME in [AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['ThreadCount'] = list_process[7] if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                    dict_processMap['HandleCount'] = list_process[8] if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                list_processDetails.append(dict_processMap)
            if action == AgentConstants.TEST_MONITOR:
                #AgentLogger.log(AgentLogger.CHECKS,"Discovered processes data-- {0}".format(list_processDetails))
                dict_toReturn['PROCESS_LOG_DATA'] = list_processDetails
            else:
                dict_toReturn['Process Details'] = list_processDetails
            #AgentLogger.log(AgentLogger.MAIN,"\n\n\n CONVERT processes data-- {0}".format(list_processDetails))
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR],' *************************** Exception while converting process list to dictionary for action : '+repr(action)+' \n'+repr(list_psCommandOutput)+' *************************** '+ repr(e) + '\n')
            traceback.print_exc()
        return dict_toReturn
    
    @staticmethod
    def sortProcessListAndConvertToDict(list_processDetails, sortKey='cpu', noOfSamples=5):
        list_sortedProcessMetrics = []
        try:
            #AgentLogger.log(AgentLogger.COLLECTOR,' list process -- {0}'.format(list_processDetails))
            if sortKey == 'cpu':
                list_sortedProcessDetails = sorted(list_processDetails, key=itemgetter(8,2), reverse=True)[:noOfSamples]
            elif sortKey == 'mem':
                list_sortedProcessDetails = sorted(list_processDetails, key=itemgetter(9,3), reverse=True)[:noOfSamples]
            for list_processDet in list_sortedProcessDetails:
                #AgentLogger.log(AgentLogger.COLLECTOR,' sorted process -- {0}'.format(list_processDet))
               # ['2214', 'sriram-+', '19', 'upstart-', '0.0', '0.0', '1', '10', 'upstart-file-bridge', 'upstart-file-bridge --daemon --user', '0.0', '0.0', '--daemo']
                dict_processDetail = OrderedDict()
                dict_processDetail['Process Id'] = list_processDet[0]
                dict_processDetail['Process Name'] = list_processDet[3] if AgentConstants.OS_NAME == AgentConstants.LINUX_OS else list_processDet[1] if AgentConstants.OS_NAME in [AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                dict_processDetail['CPU Usage(%)'] = list_processDet[4] if AgentConstants.OS_NAME == AgentConstants.LINUX_OS else list_processDet[8] if AgentConstants.OS_NAME in [AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                dict_processDetail['Avg. CPU Usage(%)'] = list_processDet[10] if AgentConstants.OS_NAME == AgentConstants.LINUX_OS else list_processDet[2] if AgentConstants.OS_NAME in [AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                dict_processDetail['Memory Usage(MB)'] = list_processDet[5] if AgentConstants.OS_NAME == AgentConstants.LINUX_OS else list_processDet[9] if AgentConstants.OS_NAME in [AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                dict_processDetail['Avg. Memory Usage(MB)'] = list_processDet[11]  if AgentConstants.OS_NAME == AgentConstants.LINUX_OS else list_processDet[3] if AgentConstants.OS_NAME in [AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                dict_processDetail['Thread Count'] = list_processDet[6]  if AgentConstants.OS_NAME == AgentConstants.LINUX_OS else list_processDet[4] if AgentConstants.OS_NAME in [AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                dict_processDetail['Handle Count'] = list_processDet[7]  if AgentConstants.OS_NAME == AgentConstants.LINUX_OS else list_processDet[5] if AgentConstants.OS_NAME in [AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                dict_processDetail['Path'] = list_processDet[8]  if AgentConstants.OS_NAME == AgentConstants.LINUX_OS else list_processDet[6] if AgentConstants.OS_NAME in [AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                dict_processDetail['Command Line Arguments'] = list_processDet[9]  if AgentConstants.OS_NAME == AgentConstants.LINUX_OS else list_processDet[7] if AgentConstants.OS_NAME in [AgentConstants.OS_X, AgentConstants.FREEBSD_OS] else ""
                if len(str(dict_processDetail['Command Line Arguments'])) > AgentConstants.TOP_PROCESS_ARGUMENT_LENGTH:
                    dict_processDetail['Command Line Arguments'] = str(dict_processDetail['Command Line Arguments'])[0:AgentConstants.TOP_PROCESS_ARGUMENT_LENGTH]
                list_sortedProcessMetrics.append(dict_processDetail)
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' *************************** Exception while sorting process metrics for RCA : '+repr(list_processDetails)+' *************************** '+ repr(e))
            traceback.print_exc()
        return list_sortedProcessMetrics

class MonitorInfo:
    def __init__(self):
        self.__str_name = None
        self.__dict_monitorInfo = None
        self.__logger = AgentLogger.STDOUT
        self.__func_monitorImpl = self.setMonitorImpl()
    def __str__(self):
        str_monitorInfo = ''
        str_monitorInfo += 'MONITOR NAME : '+repr(self.__str_name)
        str_monitorInfo += ' MONITOR LOGGER : '+repr(self.__logger)
        str_monitorInfo += ' MONITOR IMPL : '+repr(self.__func_monitorImpl)
        str_monitorInfo += ' MONITOR INFO : '+repr(self.__dict_monitorInfo)
        return str_monitorInfo
    def setName(self, str_monitorName):
        self.__str_name = str_monitorName
    def getName(self):
        return self.__str_name
    def setProps(self, dict_props):
        self.__dict_monitorInfo = dict_props
    def getProps(self):
        return self.__dict_monitorInfo
    def setMonitorImpl(self, func_monitorImpl = None):
        if func_monitorImpl:
            self.__monitorImpl = func_monitorImpl
        else:
            pass
    def getMonitorImpl(self):
        return self.__func_monitorImpl
        
class Activator:
    def __init__(self):
        self.state = False
        self.name = 'Activatormodule'
    
    def getActivatorState(self):
        return self.state
    
    def setActivatorState(self,boolState):
        self.state = boolState
    
    def scheduleActivator(self):
        try:
            if self.state == False:
                AgentLogger.log(AgentLogger.COLLECTOR,'================================= SCHEDULING FOR ACTIVATION LISTENER =================================')
                scheduleInfo = AgentScheduler.ScheduleInfo()
                scheduleInfo.setSchedulerName('AgentScheduler')
                scheduleInfo.setTaskName('ListenAct')
                scheduleInfo.setTime(time.time())
                task = self.listenActivation
                scheduleInfo.setTask(task)
                scheduleInfo.setIsPeriodic(True)
                scheduleInfo.setInterval(180)
                scheduleInfo.setLogger(AgentLogger.COLLECTOR)
                AgentScheduler.schedule(scheduleInfo)
                self.setActivatorState(True)
            else:
                AgentLogger.log(AgentLogger.COLLECTOR,'******************************** Activator Listener already scheduled *********************************')
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' *************************** Exception while scheduling activator for stop_monitoring *************************** '+ repr(e))
            traceback.print_exc()

    def listenActivation(self):
        dictRequestParameters = {}
        str_servlet = AgentConstants.AGENT_LISTEN_ACTIVATION_SERVLET
        try:
            AgentLogger.log(AgentLogger.COLLECTOR,'================ Contacting Activation servlet =================' )
            dictRequestParameters['bno'] = AgentConstants.AGENT_VERSION
            dictRequestParameters['custID'] = AgentConstants.CUSTOMER_ID
            dictRequestParameters['agentKey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
            dictRequestParameters['auid'] = AgentConstants.AUID
            dictRequestParameters['auid_old'] = AgentConstants.AUID_OLD
            str_url = None
            if not dictRequestParameters == None:
                str_requestParameters = urlencode(dictRequestParameters)
                str_url = str_servlet + str_requestParameters
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.COLLECTOR)
            requestInfo.set_method(AgentConstants.HTTP_POST)
            requestInfo.set_url(str_url)
            requestInfo.set_timeout(10)
            bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
            if bool_toReturn:
                CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'ACTIVATOR LISTENER MODULE')
            elif int_errorCode == 404:
                AgentLogger.log([AgentLogger.COLLECTOR],' ACTIVATOR LISTENER SERVLET Servlet not found ' ) 
            else:
                AgentLogger.log([AgentLogger.COLLECTOR],' Failed to receive response from ACTIVATOR LISTENER SERVLET ' )
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' *************************** Exception while listening for activation response from server *************************** '+ repr(e))
            traceback.print_exc()
    
    def stopActivator(self):
        try:
            if self.state == True:
                AgentLogger.log([AgentLogger.COLLECTOR],'================================= STOPPING SCHEDULE FOR ACTIVATION LISTENER =================================')
                scheduleInfo = AgentScheduler.ScheduleInfo()
                scheduleInfo.setSchedulerName('AgentScheduler')
                scheduleInfo.setTaskName('ListenAct')
                AgentScheduler.deleteSchedule(scheduleInfo)
                self.setActivatorState(False)
            else:
                AgentLogger.log([AgentLogger.COLLECTOR],'******************************** Activator Listener already stopped *********************************')
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' *************************** Exception while stopping activator in start_monitoring *************************** '+ repr(e))
            traceback.print_exc()

class Collector:
    def __init__(self, name = 'Collector'):
        self.__name = name
        self.__bool_dataCollectionStopped = True
        self.__dict_monitors = None
        self.__dict_customMonitors = None
        self.__dict_monitorsgroup = None
        self.__dict_customMonitorsGroup = None
        self.__scheduler = None
        self.__colDataBuffer = {}
        self.loadMonitors()
    
    def loadMonitors(self):
        try:
            AgentLogger.log(AgentLogger.COLLECTOR,'======================================= INITIALIZING COLLECTOR =======================================')
            AgentLogger.log(AgentLogger.STDOUT, "data collector config files : {} | {}".format(AgentConstants.AGENT_MONITORS_FILE, AgentConstants.AGENT_CUSTOM_MONITORS_FILE)+'\n')
            dict_monitorsInfo = AgentUtil.loadMonitorsXml(AgentConstants.AGENT_MONITORS_FILE)
            dict_customMonitorsInfo = AgentUtil.loadMonitorsXml(AgentConstants.AGENT_CUSTOM_MONITORS_FILE)
            (bool_isSuccess, dict_monitorsGroup) = AgentUtil.loadDataFromFile(AgentConstants.AGENT_MONITORS_GROUP_FILE)
            (bool_isSuccess2, dict_customMonitorsGroup) = AgentUtil.loadDataFromFile(AgentConstants.AGENT_CUSTOM_MONITORS_GROUP_FILE)
            if bool_isSuccess:
                self.__dict_monitorsgroup = collections.OrderedDict(dict_monitorsGroup)
                AgentLogger.log(AgentLogger.COLLECTOR,'Monitor group Loaded From '+AgentConstants.AGENT_MONITORS_GROUP_FILE+' : '+json.dumps(dict_monitorsGroup))
            else:
                AgentLogger.log(AgentLogger.CRITICAL,' ********************** Failed to load the monitor group conf file : '+AgentConstants.AGENT_MONITORS_GROUP_FILE+' ********************** \n')
                raise Exception
            if bool_isSuccess2:
                self.__dict_customMonitorsGroup = collections.OrderedDict(dict_customMonitorsGroup)
                AgentLogger.debug(AgentLogger.COLLECTOR,'Custom Monitor group Loaded From '+AgentConstants.AGENT_CUSTOM_MONITORS_GROUP_FILE+' : '+repr(dict_customMonitorsGroup))
            else:
                AgentLogger.log(AgentLogger.CRITICAL,' ********************** Failed to load the custom monitor group conf file : '+AgentConstants.AGENT_CUSTOM_MONITORS_GROUP_FILE+' ********************** \n')
                raise Exception
            if dict_monitorsInfo:
                strDictKey = AgentConstants.OS_NAME + 'Monitors'
                self.__dict_monitors = dict_monitorsInfo['MonitorsXml'][strDictKey] if strDictKey in dict_monitorsInfo['MonitorsXml'] else {}
                #AgentLogger.log(AgentLogger.COLLECTOR,'Monitors Info Loaded From '+AgentConstants.AGENT_MONITORS_FILE+' : '+repr(dict_monitorsInfo))
            else:
                AgentLogger.log(AgentLogger.CRITICAL,' ********************** Failed To Load The Monitors Conf File : '+AgentConstants.AGENT_MONITORS_FILE+' ********************** \n')
                if not AgentConstants.OS_NAME == AgentConstants.AIX_OS:
                    raise Exception
            AgentLogger.log(AgentLogger.COLLECTOR,'Custom monitors Info Loaded From '+AgentConstants.AGENT_CUSTOM_MONITORS_FILE+' : '+repr(dict_customMonitorsInfo))         
            if dict_customMonitorsInfo and 'MonitorsXml' in dict_customMonitorsInfo and 'LinuxMonitors' in dict_customMonitorsInfo['MonitorsXml']:
                self.__dict_customMonitors = dict_customMonitorsInfo['MonitorsXml']['LinuxMonitors']
            if dict_monitorsGroup and 'Monitoring' in dict_monitorsGroup['MonitorGroup']:
                AgentConstants.POLL_INTERVAL = dict_monitorsGroup['MonitorGroup']['Monitoring']['Interval']
                AgentLogger.log(AgentLogger.COLLECTOR,'monitoring poll interval frequency from monitorsgroup.json - {0}'.format(dict_monitorsGroup['MonitorGroup']['Monitoring']['Interval']))
        except Exception as e:
            AgentLogger.log(AgentLogger.MAIN, "Error while loading monitors {}".format(AgentConstants.OS_NAME+'Monitors'))
            AgentLogger.log(AgentLogger.MAIN, "DataCollector initialization error")
            traceback.print_exc()

    def setDataCollectionStopped(self, bool_dataCollectionStopped):
        self.__bool_dataCollectionStopped = bool_dataCollectionStopped
    
    def isDataCollectionStopped(self):
        return self.__bool_dataCollectionStopped
    
    def addMonitor(self):
        pass
    
    def removeMonitor(self):
        pass
    
    def updateMonitor(self):
        pass
    
    def getMonitors(self):
        return self.__dict_monitors
    
    def getMonitorsGroup(self):
        return self.__dict_monitorsgroup
    
    def getCustomMonitors(self):
        return self.__dict_customMonitors
    
    def __getCommandsToExecute(self, dict_groupVsMonitorList):
        dict_scriptVsArgs = {}
        list_scriptCommandsToExecute = []
        AgentLogger.debug(AgentLogger.COLLECTOR,'Collecting data for the group : '+repr(dict_groupVsMonitorList['GroupName'])+' with details : '+repr(dict_groupVsMonitorList))
        for monitorName in dict_groupVsMonitorList['Monitors']:
            #AgentLogger.log(AgentLogger.COLLECTOR,'Collecting data for the monitor : '+repr(monitorName))
            str_commandArgs = self.__dict_monitors[monitorName]['Attributes']['commandArgs']
            if monitorName == "Network Data":
                if AgentConstants.BONDING_INTERFACE_STATUS == True and AgentConstants.OS_NAME in [AgentConstants.LINUX_OS]:
                    str_commandArgs = 'if_bond_data'
            if monitorName == "Process_Monitoring":
                if AgentConstants.PROCESS_MONITORING_NAMES==None or AgentConstants.PROCESS_MONITORING_NAMES=='':
                    continue
                else:
                    commandArgs = 'pcheck::'+AgentConstants.PROCESS_MONITORING_NAMES
                    str_commandArgs = "'{}'".format(commandArgs)
                    AgentLogger.log(AgentLogger.COLLECTOR,'command args :: {}'.format(str_commandArgs))
            if self.__dict_monitors[monitorName]['Attributes']['command'] not in dict_scriptVsArgs:
                list_commandArgs = []
                for commandArg in str_commandArgs.split(','):
                    if commandArg not in list_commandArgs:
                        list_commandArgs.append(commandArg)
                dict_scriptVsArgs[self.__dict_monitors[monitorName]['Attributes']['command']] = list_commandArgs
            elif self.__dict_monitors[monitorName]['Attributes']['commandArgs'] not in dict_scriptVsArgs[self.__dict_monitors[monitorName]['Attributes']['command']]:
                list_commandArgs = dict_scriptVsArgs[self.__dict_monitors[monitorName]['Attributes']['command']]
                for commandArg in str_commandArgs.split(','):
                    if commandArg not in list_commandArgs:
                        list_commandArgs.append(commandArg)
        AgentLogger.debug(AgentLogger.COLLECTOR,'Script vs argument map for group : '+repr(dict_groupVsMonitorList['GroupName'])+' are : '+repr(dict_scriptVsArgs))
        for key in dict_scriptVsArgs.keys():
            #str_agentDataCollFilePath = AgentConstants.AGENT_TEMP_DIR +'/'+str_agentDataCollFileName
            str_commandToExecute = '"'+AgentConstants.AGENT_SCRIPTS_DIR+'/'+key+'" '
            str_commandToExecute += ','.join(dict_scriptVsArgs[key])
            list_scriptCommandsToExecute.append(str_commandToExecute)
        return list_scriptCommandsToExecute
    
    def collectData(self, dict_groupVsMonitorList):
        dict_collectedData = {}
        try:
            AgentLogger.log(AgentLogger.COLLECTOR,'================================= COLLECTING DATA FOR THE GROUP : '+repr(dict_groupVsMonitorList['GroupName'])+'=================================')
            dict_collectedData = copy.deepcopy(dict_groupVsMonitorList)
            list_scriptCommandsToExecute = self.__getCommandsToExecute(dict_groupVsMonitorList)
            AgentLogger.debug(AgentLogger.COLLECTOR,'Script command(s) to be executed for group : '+repr(dict_groupVsMonitorList['GroupName'])+' are : '+repr(list_scriptCommandsToExecute))
            for command in list_scriptCommandsToExecute:
                executorObj = AgentUtil.Executor()
                executorObj.setLogger(AgentLogger.COLLECTOR)
                executorObj.setTimeout(int(AgentConstants.DC_SCRIPT_TIMEOUT))
                executorObj.setCommand(command)
                executorObj.redirectToFile(True)
                executorObj.executeCommand()
                #AgentUtil.executeCommand(command, AgentLogger.COLLECTOR, 7)
                dict_collectedData['CollectedData'] = self.__parseCollectedData(executorObj.getOutputFilePath(), dict_groupVsMonitorList)
                #AgentLogger.log(AgentLogger.MAIN,'\n\ndict_collectedData[CollectedData] contains :: {}'.format(dict_collectedData['CollectedData']['Process_Monitoring']))
            if 'AppMonitors' in dict_groupVsMonitorList:
                appList = dict_groupVsMonitorList['AppMonitors']
                dict_collectedData.setdefault('AppData',{})
                for each_app in appList:
                    task = APP_IMPL[each_app]
                    appData = task()
                    #AgentLogger.debug(AgentLogger.COLLECTOR,' APP data for : ' + each_app + ' is \n' + repr(appData))
                    dict_collectedData['AppData'].setdefault(each_app,appData)
            #AgentLogger.debug(AgentLogger.COLLECTOR,' COLLECTED DATA IN CD : ' + repr(dict_collectedData))
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], ' *************************** Exception while collecting data for the group : '+repr(dict_groupVsMonitorList['GroupName'])+'*************************** '+ repr(e) + '\n')
            traceback.print_exc()
            bool_isSuccess = False
        return dict_collectedData
    
    def __parseCollectedData(self, str_agentDataCollFilePath, dict_groupVsMonitorList):
        dict_collectedData = OrderedDict()
        file_obj = None
        try:
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(str_agentDataCollFilePath)
            fileObj.set_dataType('text')
            fileObj.set_mode('r')
            fileObj.set_loggerName(AgentLogger.COLLECTOR)
            fileObj.set_logging(False)
            bool_toReturn, str_collectedData = FileUtil.readData(fileObj)
            if not bool_toReturn:
                AgentLogger.log(AgentLogger.CRITICAL,'Exception while reading collected data from the file : '+repr(str_agentDataCollFilePath) + '\n')
                return None
            #AgentLogger.log(AgentLogger.COLLECTOR,'Collected data from the file '+str_agentDataCollFilePath+' is '+str_agentDataCollFilePath+str(str_collectedData))
            for monitorName in dict_groupVsMonitorList['Monitors']:
                bool_isSuccess = True
                list_parseTags = self.__dict_monitors[monitorName]['Attributes']['parseTag'].split(',')
                AgentLogger.debug(AgentLogger.COLLECTOR,'================================= '+str(monitorName)+' =================================')
                #AgentLogger.log(AgentLogger.COLLECTOR,'Parse tag for the monitor '+monitorName+' is '+repr(list_parseTags))
                str_data = self.__getData(list_parseTags, str_collectedData) 
                if str_data == None or str_data == '':
                    bool_isSuccess = False
                    AgentLogger.debug(AgentLogger.CRITICAL,'No data from script - for the monitor : '+repr(monitorName)+' in the group : '+repr(dict_groupVsMonitorList['GroupName']) + '\n')
                else:
                    bool_isSuccess = True
                if 'logOutput' in self.__dict_monitors[monitorName]['Attributes'] and self.__dict_monitors[monitorName]['Attributes']['logOutput'] == "false":
                    pass
                else:
                    AgentLogger.log(AgentLogger.COLLECTOR,'Data collected for the monitor : '+repr(monitorName)+' in the group : '+repr(dict_groupVsMonitorList['GroupName']))
                    AgentLogger.log(AgentLogger.COLLECTOR,str(str_data))
                dict_parsedData = AgentParser.parse(self.__dict_monitors[monitorName]['Attributes'], (bool_isSuccess, str_data))
                dict_collectedData[monitorName] = dict_parsedData
                AgentLogger.debug(AgentLogger.COLLECTOR,'Parsed data : '+repr(dict_parsedData))
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR],' ************************* Exception while reading collected data from the file '+str_agentDataCollFilePath+' ************************* '+repr(e) + '\n')
            traceback.print_exc()
        finally:
            if not file_obj == None:
                file_obj.close()
        return dict_collectedData
    
    def __getData(self, list_parseTags, str_collectedData):
        str_data = None
        for parseTag in list_parseTags:
            try:
                str_searchString = '<<'+parseTag+'>>'
                int_tagIndex = str_collectedData.find(str_searchString) + len(str_searchString)
                int_nextTagIndex = str_collectedData.find('<<', int_tagIndex)
                AgentLogger.debug(AgentLogger.COLLECTOR,'Parse tag : '+repr(str_searchString)+' Tag index : '+repr(int_tagIndex)+' Next tag index : '+repr(int_nextTagIndex))
                if str_data:
                    str_data += '\n'
                    str_data += str_collectedData[int_tagIndex:int_nextTagIndex].strip()
                else:
                    str_data = str_collectedData[int_tagIndex:int_nextTagIndex].strip()
            except Exception as e:
                AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR],' ************************* Exception while searching collected data using parseTags '+repr(list_parseTags)+' ************************* '+ repr(e) + '\n')
                traceback.print_exc()
        return str_data

    # This method can be called multiple times. It just adds the schedule and the scheduler removes existing
    # schedules for a task and replaces them with the new one based on schedule creation time.
    def scheduleDataCollection(self,restartDC=False):
        global SCHEDULED_THREAD_DICT
        if AgentConstants.IS_DOCKER_AGENT != '1' and (self.isDataCollectionStopped() or restartDC):
            AgentLogger.log(AgentLogger.COLLECTOR,'================================= SCHEDULING FOR DATA COLLECTION =================================')
            self.setDataCollectionStopped(False)
            if not self.__dict_monitorsgroup == None:
                dict_monitorsGroup = self.__dict_monitorsgroup['MonitorGroup']
                if AgentConstants.OS_NAME == AgentConstants.AIX_OS_LOWERCASE:
                    dict_customMonitorsGroup = {}
                else:
                    dict_customMonitorsGroup = self.__dict_customMonitorsGroup['MonitorGroup']
                for key in list(dict_monitorsGroup.keys()):
                    try:
                        if 'Schedule' in dict_monitorsGroup[key] and dict_monitorsGroup[key]['Schedule'] == 'false':
                            AgentLogger.log([AgentLogger.COLLECTOR],'SKIPPING DATA COLLECTION FOR : '+repr(key)+' : '+ json.dumps(dict_monitorsGroup[key]))
                            continue
                        elif ((key in dict_customMonitorsGroup) and ('Schedule' in dict_customMonitorsGroup[key]) and (dict_customMonitorsGroup[key]['Schedule'] == 'false')):
                            AgentLogger.log([AgentLogger.COLLECTOR],'SKIPPING DATA COLLECTION FOR : '+repr(key)+' : '+ repr(dict_customMonitorsGroup[key]))
                            continue
                        elif ((key == 'TopProcessMonitoring') and AgentConstants.TOP_COMMAND_CHECK):
                            AgentLogger.log([AgentLogger.COLLECTOR],'===== TOP Command Check Passed, New TOP/CPU dc Flow : '+repr(key) + ' =====')
                            continue
                        AgentLogger.log([AgentLogger.COLLECTOR],'SCHEDULE FOR DATA COLLECTION : '+repr(key)+' : '+ json.dumps(dict_monitorsGroup[key]))
                        scheduleInfo = AgentScheduler.ScheduleInfo()
                        if not AgentScheduler.SCHEDULERS:
                            continue
                        if key == 'Monitoring' and not AgentUtil.is_module_enabled(AgentConstants.DC_SETTING):
                            continue
                        if key in ['kubernetes_dc','hadoop_monitoring','zookeeper_monitoring','docker_monitoring'] and not AgentUtil.is_module_enabled(AgentConstants.APPS_SETTING):
                            continue
                        if key == "TopProcessMonitoring" and not AgentUtil.is_module_enabled(AgentConstants.PROCESS_DISCOVERY):
                            continue
                        task = self.collectData
                        callback = self.processCollectedData
                        taskArgs = dict_monitorsGroup[key]
                        if 'Interval' in dict_monitorsGroup[key]:
                            interval = int(dict_monitorsGroup[key]['Interval'])
                            scheduleInfo.setIsPeriodic(True)
                        elif key in dict_customMonitorsGroup and 'Interval' in dict_customMonitorsGroup[key]:
                            interval = int(dict_customMonitorsGroup[key]['Interval'])
                            if key == 'CPUMonitoring':
                                AgentConstants.CPU_SAMPLE_VALUES = int(300/interval)
                            scheduleInfo.setIsPeriodic(True)
                        else:
                            interval = 0
                            scheduleInfo.setIsPeriodic(False)
                        if 'Delay' in dict_monitorsGroup[key]:
                            scheduleInfo.setTime(time.time() + float(dict_monitorsGroup[key]['Delay']))
                        else:
                            scheduleInfo.setTime(time.time())
                        if 'Impl' in dict_monitorsGroup[key]:
                            #AgentLogger.log(AgentLogger.COLLECTOR,'Impl found in ' + str(COLLECTOR_IMPL[key]))
                            task = COLLECTOR_IMPL[key]
                            callback = None
                            if key == 'RootCauseAnalysis' :
                                rcaInfo = RcaInfo()
                                rcaInfo.requestType = AgentConstants.GENERATE_RCA
                                rcaInfo.action = AgentConstants.SAVE_RCA_REPORT
                                AgentLogger.log(AgentLogger.COLLECTOR, 'RootCauseAnalysis')
                                taskArgs = rcaInfo
                            elif key == 'ProcessMonitoring':
                                callback = ProcessUtil.processCallback
                                taskArgs = None
                            else:
                                taskArgs = None
                        scheduleInfo.setSchedulerName('AgentScheduler')
                        scheduleInfo.setTaskName(key)
                        scheduleInfo.setTask(task)
                        scheduleInfo.setTaskArgs(taskArgs)
                        scheduleInfo.setCallback(callback)
                        #scheduleInfo.setCallbackArgs(dict_monitorsGroup[key]
                        scheduleInfo.setInterval(interval)
                        scheduleInfo.setLogger(AgentLogger.COLLECTOR)
                        AgentScheduler.schedule(scheduleInfo)
                        SCHEDULED_THREAD_DICT[key] = scheduleInfo
                    except Exception as e:
                        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while scheduling '+repr(key)+' for data collection : *************************** '+ repr(e))
                        traceback.print_exc()
            else:
                AgentLogger.log(AgentLogger.CRITICAL, '*************************** Unable to schedule monitors for data collection since monitors group is empty : '+repr(self.__dict_monitorsgroup)+' *************************** \n')
        else:
            AgentLogger.log([AgentLogger.COLLECTOR],'Data collection is already running')
        
    def processCollectedData(self, dict_groupVsMonitorList):
        list_fileNames = []
        list_appFileNames = []
        bool_thresholdCheck= False
        bool_dcTimeCheck=False
        try:
            AgentLogger.log(AgentLogger.COLLECTOR,'Processing collected data : ')
            dict_collectedData = dict_groupVsMonitorList['CollectedData']
            if dict_groupVsMonitorList['GroupName'] == 'Monitoring':
                fh = DataConsolidator.DataHandler()
                dictDataToSave = fh.createUploadData(dict_collectedData)
                if AgentConstants.POLL_INTERVAL != AgentConstants.FIVE_MIN_POLLING_INTERVAL:
                    bool_ThresholdViolated,violated_Param = self.checkForThresholdViolation(dictDataToSave)
                    if bool_ThresholdViolated:
                        AgentLogger.log(AgentLogger.COLLECTOR,'threshold violated  -- {0} attribute -- {1}'.format(bool_ThresholdViolated,violated_Param))
                        bool_thresholdCheck=True
                bool_isSuccess, str_fileName = saveCollectedServerData(dictDataToSave, AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['001'], "SMData")
                if bool_isSuccess:
                    list_fileNames.append(str_fileName)
            if 'AppData' in dict_groupVsMonitorList:
                dict_appData = dict_groupVsMonitorList['AppData']
                for key in dict_appData.keys():
                    dict_dataToSave = dict_appData[key]
                    if dict_groupVsMonitorList['GroupName'] == 'Realtime':
                        dict_dataToSave['REAL_TIME'] = 'True'
                    AgentLogger.debug(AgentLogger.COLLECTOR,'Saving app data : '+ repr(dict_dataToSave))
                    if dict_dataToSave:
                        bool_isSuccess, str_fileName = saveCollectedData(dict_dataToSave,key)
                        if bool_isSuccess:
                            list_appFileNames.append(str_fileName)
            if dict_groupVsMonitorList['SaveFile'] != 'False':
                for key in dict_collectedData.keys():
                    dict_dataToSave = dict_collectedData[key]
                    if dict_groupVsMonitorList['GroupName'] == 'Realtime':
                        dict_dataToSave['REAL_TIME'] = 'True'
                    AgentLogger.debug(AgentLogger.COLLECTOR,'Saving collected data : '+ repr(dict_dataToSave))
                    if dict_dataToSave:
                        bool_isSuccess, str_fileName = saveCollectedData(dict_dataToSave)
                        if bool_isSuccess:
                            list_fileNames.append(str_fileName)
                #FILES_TO_ZIP_BUFFER.add(list_fileNames)
            
            # Agent_5983972240318813010_Upload_1501061459566.zip
            if list_appFileNames:
                    self.setAppUploadInfo(list_appFileNames)

            if dict_groupVsMonitorList['GroupName'] == 'Monitoring':
                if list_fileNames and (bool_thresholdCheck or AgentConstants.CURRENT_DC_TIME == None):
                    ZipUtil.zipFilesAtInstance([list_fileNames],AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['001'])
                    AgentConstants.CURRENT_DC_TIME = time.time()

            
            if AgentConstants.UPDATE_PLUGIN_INVENTORY:
                module_object_holder.plugins_obj.updateInventoryToServer()
                AgentConstants.UPDATE_PLUGIN_INVENTORY=False
                AgentLogger.log(AgentLogger.PLUGINS, 'Plugin Inventory Reset -- {0}'.format(AgentConstants.UPDATE_PLUGIN_INVENTORY))
            
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], '*************************** Exception while processing collected data : '+repr(dict_groupVsMonitorList)+' *************************** '+ repr(e))
            traceback.print_exc()

    
    def evaluateThreshold(self,perf_Value,condition,threshold):
        eval_Check = False
        try:
            perf_Value=str(perf_Value)
            condition=str(condition)
            threshold=str(threshold)
            math_String = perf_Value+condition+threshold
            eval_Check = eval(math_String)
        except Exception as e:
            traceback.print_exc()
        return eval_Check
    
    def checkForThresholdViolation(self,dictDataToSave):
        bool_ToReturn=False
        violated_Param=None
        try:
            if DataConsolidator.THRESHOLD_DICT:
                for metric in DataConsolidator.THRESHOLD_DICT.keys():
                    dictValue = DataConsolidator.THRESHOLD_DICT[metric]
                    condition=None
                    threshold=None
                    if 'con' in dictValue:
                        condition = dictValue['con']
                        threshold = dictValue['val']
                        if metric in dictDataToSave:
                            perf_Value = dictDataToSave[metric]
                            eval_Check = self.evaluateThreshold(perf_Value,condition,threshold)
                        if eval_Check==True and (AgentConstants.S_V_DICT is not None and metric not in AgentConstants.S_V_DICT):
                            AgentLogger.log(AgentLogger.COLLECTOR,'threshold violated  -- metric  - {0}'.format(metric))
                            bool_ToReturn=True
                            violated_Param=metric
                            break
                    elif ((metric in dictDataToSave) and type(dictDataToSave[metric]) is list):
                        for innerkey , innerval in dictValue.items():
                            if innerkey=="global":
                                for key in innerval:
                                    perf_check = key
                                    perf_criteria = innerval[key]
                                    condition = perf_criteria['con']
                                    threshold = perf_criteria['val']
                                    list_Values=dictDataToSave[metric]
                                    for item in list_Values:
                                        id =item['id']
                                        if perf_check not in item:
                                            continue                                            
                                        perf_Value = str(item[perf_check])
                                        eval_Check = self.evaluateThreshold(perf_Value,condition,threshold)
                                        if DataConsolidator.DISABLED_CHILD_ALERTS_DICT and id in DataConsolidator.DISABLED_CHILD_ALERTS_DICT:
                                            AgentLogger.log(AgentLogger.COLLECTOR,'skip alert chosen for -- metric  - {0}, resource id - {1}'.format(metric,id))
                                            continue
                                        if eval_Check:
                                            if (AgentConstants.S_V_DICT is not None) and ((metric not in AgentConstants.S_V_DICT) or (id not in AgentConstants.S_V_DICT[metric]) or (perf_check not in AgentConstants.S_V_DICT[metric][id])):
                                                AgentLogger.log(AgentLogger.COLLECTOR,'threshold violated -- metric  - {0}, child key - {1}, resource id - {2}'.format(metric,perf_check,id))
                                                bool_ToReturn=True
                                                violated_Param=perf_check
                                                return bool_ToReturn,violated_Param
                            else:
                                list_Values=dictDataToSave[metric]
                                for item in list_Values:
                                    id = item['id']
                                    if id == innerkey:
                                        child_Dict = dictValue[id]
                                        for innerChildKey,innerChildVal in child_Dict.items():
                                            if innerChildKey in item:
                                                perf_Value = item[innerChildKey]
                                                condition = dictValue[id][innerChildKey]['con']
                                                threshold = dictValue[id][innerChildKey]['val']
                                                if isinstance(perf_Value, int):
                                                    perf_Value = str(perf_Value)
                                                eval_Check = self.evaluateThreshold(perf_Value,condition,threshold)
                                                if eval_Check:
                                                    if (AgentConstants.S_V_DICT is not None) and ( (metric not in AgentConstants.S_V_DICT) or (id not in AgentConstants.S_V_DICT[metric]) or (innerChildKey not in AgentConstants.S_V_DICT[metric][id])):
                                                        AgentLogger.log(AgentLogger.COLLECTOR,'threshold violated -- metric  - {0}, child key - {1}, resource id - {2}'.format(metric,innerChildKey,id))
                                                        bool_ToReturn=True
                                                        violated_Param=innerChildKey
                                                        return bool_ToReturn,violated_Param
                                                else:
                                                    AgentLogger.debug(AgentLogger.COLLECTOR,' eval check failed :: {0}{1}'.format(violated_Param,innerChildKey))
                    else:
                        for secondLevelKey in dictValue.keys():
                            if metric in dictDataToSave and secondLevelKey in dictDataToSave[metric]:
                                if 'con' in DataConsolidator.THRESHOLD_DICT[metric][secondLevelKey]:
                                    condition = DataConsolidator.THRESHOLD_DICT[metric][secondLevelKey]['con']
                                    threshold = DataConsolidator.THRESHOLD_DICT[metric][secondLevelKey]['val']
                                    perf_Value = dictDataToSave[metric][secondLevelKey]
                                    perf_Value = str(perf_Value)
                                    eval_Check = self.evaluateThreshold(perf_Value,condition,threshold)
                                    if eval_Check==True:
                                        if AgentConstants.S_V_DICT is not None and ( ( metric not in AgentConstants.S_V_DICT ) or ( metric in AgentConstants.S_V_DICT and secondLevelKey not in AgentConstants.S_V_DICT[metric])):
                                            AgentLogger.log(AgentLogger.COLLECTOR,'threshold violated -- metric  - {0}, child key - {1}'.format(metric,secondLevelKey))
                                            bool_ToReturn=True
                                            violated_Param=secondLevelKey
                                            return bool_ToReturn,violated_Param
            else:
                bool_ToReturn=False
        except Exception as e:
            traceback.print_exc()
        
        return bool_ToReturn,violated_Param
            
    #Setting the upload and zipping parameters of application metrics
    def setAppUploadInfo(self, listOfFiles):
        dict_requestParameters = {}
        try:
            zipAndUploadInfo = FileZipAndUploadInfo()
            zipAndUploadInfo.filesToZip = listOfFiles
            zipAndUploadInfo.zipFileName = ZipUtil.getUniqueZipFileName(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'), 'Application_' +str(AgentUtil.getTimeInMillis()))
            zipAndUploadInfo.zipFilePath = AgentConstants.AGENT_UPLOAD_DIR+'/' + zipAndUploadInfo.zipFileName
            dict_requestParameters['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
            dict_requestParameters['CUSTOMERID'] = AgentConstants.CUSTOMER_ID
            dict_requestParameters['AGENTUNIQUEID'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_unique_id')
            dict_requestParameters['FILENAME'] = zipAndUploadInfo.zipFilePath if len(zipAndUploadInfo.zipFilePath)<200 else zipAndUploadInfo.zipFilePath[0:199]
            dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
            zipAndUploadInfo.uploadRequestParameters = dict_requestParameters
            zipAndUploadInfo.uploadServlet = AgentConstants.APPLICATION_COLLECTOR_SERVLET
            FILES_TO_ZIP_BUFFER.add(zipAndUploadInfo)
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], '*************************** Exception while setting zipanduploadinfo in collector *************************** '+ repr(e) + '\n')
            traceback.print_exc()

    def stopDataCollection(self):
        try:
            if not self.isDataCollectionStopped():
                AgentLogger.log([ AgentLogger.COLLECTOR],'================================= STOPPING DATA COLLECTION =================================')
                dict_monitorsGroup = self.__dict_monitorsgroup['MonitorGroup']
                AgentLogger.log([ AgentLogger.COLLECTOR],'Deleting schedules for : '+ repr(list(dict_monitorsGroup.keys())))
                for key in list(dict_monitorsGroup.keys()):
                    try:  
                        scheduleInfo = AgentScheduler.ScheduleInfo()
                        scheduleInfo.setSchedulerName('AgentScheduler')
                        scheduleInfo.setTaskName(key)
                        AgentScheduler.deleteSchedule(scheduleInfo)
                    except Exception as e:
                        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while stopping data collection *************************** '+ repr(e))
                        traceback.print_exc()
                self.setDataCollectionStopped(True)
                ACTIVATOR.scheduleActivator()
            else:
                AgentLogger.log([ AgentLogger.COLLECTOR],'Data collection is already stopped')
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], '*************************** Exception while setting zipanduploadinfo in collector *************************** '+ repr(e) + '\n')
            traceback.print_exc()

    def startDataCollection(self):
        try:
            AgentLogger.log([ AgentLogger.COLLECTOR],'================================= RE-STARTING DATA COLLECTION =================================')
            COLLECTOR.scheduleDataCollection(True)
            ACTIVATOR.stopActivator()
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], '*************************** Exception while starting data collection *************************** '+ repr(e) + '\n')
            traceback.print_exc()
    
    
class LinuxCollector(Collector):
    def __init__(self, name = 'Linux Collector', distro = None):
        Collector.__init__(self, name)
        self.__distro = distro
        
class UbuntuCollector(LinuxCollector):
    def __init__(self, name = 'Ubuntu Collector', distro = None):
        LinuxCollector.__init__(self, name, distro)

class CommonCollector(Collector):
    def __init__(self, os_name):
        Collector.__init__(self, os_name+" Collector")

class UploaderCycleHandler(threading.Thread):
    __serverNotReachableStartTime = 0
    def __init__(self):
        threading.Thread.__init__(self)
        self.task_name = 'Zip Upload Cycle'
        self.cycle_min_timer = None
        self.prev_file_cleanup_time = time.time()

    def uploadCycleIntervalCheck(self,dir_prop):
        upload_zip = False
        try:
            if dir_prop['instant_upload']:
                upload_zip = False
            else:
                upload_interval = dir_prop['upload_interval']
                upload_modulo = dir_prop['upload_modulo']
                if int(upload_modulo) == int(upload_interval):
                    upload_zip = True
                    dir_prop['upload_modulo'] = int(self.cycle_min_timer)
                else:
                    dir_prop['upload_modulo'] = int(upload_modulo) + int(self.cycle_min_timer)
            return upload_zip
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while checking upload Cycle time ************************* '+ repr(e))
            traceback.print_exc()

    def getUploadData(self,zipFilePath,dictData=False):
        str_dataToReturn = None
        file_obj = None
        try:
            bool_zipFileCorrupted = False
            if zipFilePath and os.path.isfile(zipFilePath):
                try:
                    file_obj = open(zipFilePath,'rb')
                    str_dataToReturn = file_obj.read()
                    #zipAndUploadInfo.isZipFile = True
                except Exception as e:
                    AgentLogger.log(AgentLogger.CRITICAL,' ************************* Exception while reading the zip file '+repr(zipFilePath)+' ************************* '+ repr(e) + '\n')
                    traceback.print_exc()
                    bool_zipFileCorrupted = True
                finally:
                    if file_obj:
                        file_obj.close()
                if bool_zipFileCorrupted:
                    os.remove(zipFilePath)
            elif dictData: # if folder contains json data to send, case should be handled
                str_dataToReturn = zipFilePath
                #isZipFile = False
        except Exception as e:
            AgentLogger.log(AgentLogger.CRITICAL, ' *************************** Exception while fetching data for uploading *************************** '+ repr(e) + '\n')
            traceback.print_exc()
        return str_dataToReturn

    def uploadInstantJsonData(self,dir_prop, dictData, str_action=None):
        dict_requestParameters = {}
        try:
            str_servlet = dir_prop['uri']
            str_contentType = 'application/json'
            str_dataToSend = json.dumps(dictData)
            AgentUtil.get_default_param(dir_prop,dict_requestParameters,str_action)
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.STDOUT)
            requestInfo.set_method(AgentConstants.HTTP_POST)
            requestInfo.set_url(str_url)
            requestInfo.set_data(str_dataToSend)
            requestInfo.set_dataType(str_contentType)
            requestInfo.add_header("Content-Type", str_contentType)
            requestInfo.add_header("Accept", "text/plain")
            requestInfo.add_header("Connection", 'close')
            (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
            CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'FILE UPLOADER')
            AgentLogger.debug([AgentLogger.CRITICAL,AgentLogger.STDOUT], '###################### INSTANT UPLOAD CHECK = \n{}\n{}\n{}\n{}\n{}'.format(bool_isSuccess,str_url,str_dataToSend,dict_responseHeaders,dict_responseData))
            if bool_isSuccess:
                if ((dict_responseHeaders) and ('UPLOAD_FAILED' in dict_responseHeaders) and (str(dict_responseHeaders['UPLOAD_FAILED'] == "True"))):
                    #buffer_UploadInfoObjects.appendleft(zipAndUploadInfo)
                    AgentLogger.log(AgentLogger.STDOUT,'Server side issue cannot upload instant json data: {}'.format(str(dictData)))
                else:
                    AgentLogger.log([AgentLogger.STDOUT], 'Successfully posted the instant JSON data to the server')
                    dictUploadedData = json.loads(str_dataToSend)
                    if AgentConstants.CHECKS_VERIFY_TEXT in dictUploadedData:
                        AgentLogger.debug(AgentLogger.STDOUT, 'Changing status after instant notification')
                        BasicClientHandler.URLUtil.updateURLStatus(dictUploadedData)
                        BasicClientHandler.PortUtil.updatePortStatus(dictUploadedData)
                        BasicClientHandler.NTPUtil.updateNTPStatus(dictUploadedData)
                        if 'logrule' in dictUploadedData:
                            UdpHandler.SysLogUtil.updateSyslogData(dictUploadedData)
            else:
                AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDOUT], '************************* Unable to post the instant JSON data to the server. ************************* \n')
                CommunicationHandler.checkNetworkStatus(AgentLogger.STDOUT)
                #AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(AgentConstants.FILE_UPLOAD_EXCEPTION_INTERVAL)

        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while uploading json data to server ************************* '+ repr(e))
            traceback.print_exc()

    def uploadZipsInUploadDirCycle(self):
        try:
            global FILES_UPLOADED, LAST_UPLOADED_TIME
            zipFileList = None
            bufferOfZipList = None
            latestZipDirPath = None
            str_contentType = None
            buffer_with_latest_zip = None
            current_node_buffer = None
            object_current_index = None
            latest_grouped_dir_obj = None

            for dir, dir_prop in AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER.items():
                if self.uploadCycleIntervalCheck(dir_prop):
                    current_node_buffer = dir_prop['buffer']
                    latest_grouped_dir_obj = None
                    if len(current_node_buffer[0]) > 0:
                        bufferOfZipList = current_node_buffer[0]
                        latest_grouped_dir_obj = current_node_buffer[0].pop()
                    elif len(current_node_buffer[1]) > 0:
                        bufferOfZipList = current_node_buffer[1]
                        latest_grouped_dir_obj = current_node_buffer[1].pop()
                        AgentLogger.log(AgentLogger.STDOUT,'==== Latest Current Data Buffer empty, Hence sending from Failed buffer ====')
                    elif len(current_node_buffer[0]) == 0 and len(current_node_buffer[1]) == 0:
                        #AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],'No object found in both buffer {} 0-[{}] and 1-[{}]'.format(dir_prop['code'],len(current_node_buffer[0]),len(current_node_buffer[1])))
                        #AgentLogger.log(AgentLogger.STDOUT,'Latest/Failed buffer empty, Hence sending skipping to next buffer {} : {}-{}'.format(dir_prop['code'],len(AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[dir_prop['code']]['buffer'][0]),len(AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[dir_prop['code']]['buffer'][1])))
                        continue

                    object_current_index = len(bufferOfZipList)+1
                    latestZipDirPath = latest_grouped_dir_obj.getGroupedZipDirPath()
                    zipFileList = latest_grouped_dir_obj.getZipFilesPathInGroup()
                    zipFileListCopy = copy.deepcopy(zipFileList)
                    if zipFileList:
                        dict_requestParameters = {}
                        str_contentType = dir_prop['content_type']
                        isZipFile = True if str_contentType == 'application/zip' else False
                        AgentLogger.log(AgentLogger.STDOUT,'One Grouped Dir removed from ==[{}]== containing ==[{}]== zips'.format(dir,len(zipFileList)))
                        for zipFilePath in zipFileList:
                            try:
                                AgentUtil.get_default_param(dir_prop,dict_requestParameters,zipFilePath)
                                str_dataToSend = self.getUploadData(zipFilePath,isZipFile)
                                if not str_dataToSend:
                                    AgentLogger.log(AgentLogger.CRITICAL,'Unable to get data for the zip : '+repr(zipFilePath)+' hence skipping upload\n')
                                    continue
                                str_servlet = dir_prop['uri']
                                if not dict_requestParameters == None:
                                    str_requestParameters = urlencode(dict_requestParameters)
                                    str_url = str_servlet + str_requestParameters
                                requestInfo = CommunicationHandler.RequestInfo()
                                requestInfo.set_loggerName(AgentLogger.STDOUT)
                                requestInfo.set_method(AgentConstants.HTTP_POST)
                                requestInfo.set_url(str_url)
                                requestInfo.set_data(str_dataToSend)
                                requestInfo.set_dataType(str_contentType)
                                requestInfo.add_header("Content-Type", str_contentType)
                                requestInfo.add_header("Accept", "text/plain")
                                requestInfo.add_header("Connection", 'close')
                                (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
                                AgentLogger.log([AgentLogger.STDOUT], 'Upload Status for {} :: {}-{}'.format(dir,bool_isSuccess,errorCode))
                                CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'FILE UPLOADER',str(dir))
                                if bool_isSuccess:
                                    if ((dict_responseHeaders) and ('UPLOAD_FAILED' in dict_responseHeaders) and (str(dict_responseHeaders['UPLOAD_FAILED'] == "True"))):
                                        pass
                                        pass
                                        continue
                                    LAST_UPLOADED_TIME = time.time()
                                    FILES_UPLOADED += 1
                                    if dir_prop['content_type'] == 'application/zip':
                                        AgentLogger.log(AgentLogger.STDOUT, 'Successfully posted the zip file : ['+ zipFilePath +'] to the server \n')
                                    else:
                                        AgentLogger.log([AgentLogger.STDOUT], 'Successfully posted the JSON data to the server \n')
                                        dictUploadedData = json.loads(str_dataToSend)
                                        if AgentConstants.CHECKS_VERIFY_TEXT in dictUploadedData:
                                            AgentLogger.debug(AgentLogger.STDOUT, 'Changing status after instant notification')
                                            BasicClientHandler.URLUtil.updateURLStatus(dictUploadedData)
                                            BasicClientHandler.PortUtil.updatePortStatus(dictUploadedData)
                                            BasicClientHandler.NTPUtil.updateNTPStatus(dictUploadedData)
                                            if 'logrule' in dictUploadedData:
                                                UdpHandler.SysLogUtil.updateSyslogData(dictUploadedData)
                                    if self.__serverNotReachableStartTime != 0:
                                        self.__serverNotReachableStartTime = 0
                                        if (time.time() - self.__serverNotReachableStartTime) > AgentConstants.STOP_DATA_COLLECTION_INTERVAL:
                                            COLLECTOR.scheduleDataCollection()
                                    if dir_prop['content_type'] == 'application/zip':
                                        os.remove(zipFilePath)
                                        zipFileListCopy.remove(zipFilePath)
                                elif not bool_isSuccess and "no_backlog" in dir_prop and dir_prop["no_backlog"] == True:
                                    AgentLogger.log(AgentLogger.STDOUT, 'Failed to post the zip file : ['+ zipFilePath +'] to the server, Deleting the zip file due to no_backlog \n')
                                    if dir_prop['content_type'] == 'application/zip':
                                        os.remove(zipFilePath)
                                        zipFileListCopy.remove(zipFilePath)
                                else:
                                    AgentLogger.log(AgentLogger.STDOUT,'Zip readded to upload buffer because upload did not recieve successful flag. Total zips in GroupedZipList : ' + str(len(zipFileListCopy)))
                                    if dir_prop['content_type'] == 'application/zip':
                                        AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDOUT], '************************* Unable to post the zip file :'+zipFilePath+' to the server. Added its zipfilelist and object to upload buffer ************************* \n')
                                    else:
                                        AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDOUT], '************************* Unable to post the JSON data to the server. Added its uploadinfo object to upload buffer ************************* \n')
                                    CommunicationHandler.checkNetworkStatus(AgentLogger.STDOUT)
                                    if dir == "001" and (isinstance(errorCode, ssl.SSLCertVerificationError) or isinstance(errorCode, ssl.SSLError)):
                                        AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDOUT], '**** reinitializing ca-cert path from : {} ***** '.format(errorCode))
                                        CommunicationHandler.getCaCertPath()
                                    AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(AgentConstants.FILE_UPLOAD_EXCEPTION_INTERVAL) #300 seconds
                                    if isinstance(errorCode, OSError):
                                        if self.__serverNotReachableStartTime == 0:
                                            self.__serverNotReachableStartTime = time.time()
                                            break
                                        elif (time.time() - self.__serverNotReachableStartTime) > AgentConstants.STOP_DATA_COLLECTION_INTERVAL:
                                            #stop dc for 5 hours
                                            AgentLogger.log([ AgentLogger.CRITICAL],'Agent is not able to reach server for '+repr(time.time() - self.__serverNotReachableStartTime)+' seconds > STOP_DATA_COLLECTION_INTERVAL = '+repr(AgentConstants.STOP_DATA_COLLECTION_INTERVAL)+'\n')
                                            COLLECTOR.stopDataCollection()
                                            break
                                        else:
                                            break
                            except Exception as e:
                                AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], ' *************************** Exception while uploading files/JSON data *************************** {}'.format(e))
                                traceback.print_exc()
                                AgentLogger.log(AgentLogger.STDOUT,'Zip [{}] readded to upload buffer due to exception. Total zips not posted from current group : [{}] zips'.format(zipFilePath, len(zipFileListCopy)))
                            finally:
                                time.sleep(AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[dir]['grouped_zip_upload_interval'])

                        if len(zipFileListCopy) > 0:
                            group_dir_object = AgentUtil.ZipUploaderObject()
                            group_dir_object.setZipsInGroupedDir(len(zipFileListCopy))
                            group_dir_object.setGroupedZipDirPath(latestZipDirPath)
                            group_dir_object.setZipFilesPathInGroup(zipFileListCopy)
                            bufferOfZipList.insert(object_current_index, group_dir_object)
                            AgentLogger.log(AgentLogger.STDOUT,'Zips failed to upload : [{}] left in grouped Directory itself, buffer object readded with failed zipslist'.format(zipFileListCopy))
                        else:
                            os.rmdir(latestZipDirPath)
                        dir_prop['zips_in_buffer'] -= (len(zipFileList) - len(zipFileListCopy))
                    else:
                        AgentLogger.log(AgentLogger.STDOUT,'No Zips found in zipfile list [{}]'.format(zipFileList))
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while uploading zips to server ************************* '+ repr(e))
            traceback.print_exc()

    def getUploadCycleInterval(self):
        interval = None
        try:
            upload_zip_interval_list = []
            for dir, dir_props in AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER.items():
                if not dir_props['instant_upload']:
                    upload_zip_interval_list.append(int(dir_props['upload_interval']))
            interval = AgentUtil.get_gcd(upload_zip_interval_list)
            interval = 1 if not interval else interval
            if interval != self.cycle_min_timer:
                for dir, dir_props in AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER.items():
                    if not dir_props['instant_upload']:
                        dir_props['upload_modulo'] = interval
            return interval
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while getting Upload Cycle Interval ************************* '+ repr(e))
            traceback.print_exc()

    def updateUploadCycleInterval(self,dir_prop, new_interval):
        try:
            dir_prop['upload_interval'] = new_interval
            self.cycle_min_timer = self.getUploadCycleInterval()
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while updating Upload Cycle Interval for [{}] - New Value [{}] ************************* :: {} '.format(dir_prop['code'],new_interval,e))
            traceback.print_exc()

    def run(self):
        current_cycle_interval = None
        try:
            self.cycle_min_timer = self.getUploadCycleInterval()
            current_cycle_interval = self.cycle_min_timer
            AgentLogger.log([AgentLogger.STDOUT], "========= Upload Cycle Interval - {} ===========".format(self.cycle_min_timer))
            while not AgentUtil.TERMINATE_AGENT:
                int_currentTime = time.time()
                if (int_currentTime - self.prev_file_cleanup_time) >= AgentConstants.FILE_CLEAN_UP_INTERVAL:
                    FileUtil.cleanUpFiles()
                    self.prev_file_cleanup_time = int_currentTime
                self.cycle_min_timer = self.getUploadCycleInterval()
                if current_cycle_interval != self.cycle_min_timer:
                    current_cycle_interval = self.cycle_min_timer
                    AgentLogger.log([AgentLogger.STDOUT], "========= New Upload Cycle Interval - {} ===========".format(self.cycle_min_timer))
                self.uploadZipsInUploadDirCycle()
                time.sleep(self.cycle_min_timer)
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while starting UploaderCycleHandler ************************* '+ repr(e))
            traceback.print_exc()


'''
class Uploader(threading.Thread):
    __serverNotReachableStartTime = 0            
    def __init__(self):
        threading.Thread.__init__(self)
        self.name = 'UploaderThread'
    def run(self):
        try:
            int_prevFileCleanUpTime = time.time()
            # sleep for 7 seconds and upload files assuming data will be collected after scheduling.
            #time.sleep(7)
            self.__addFilesInUploadDirectoryToBuffer()
            #ZipUtil.zipFilesInDataDirectory()
            while not AgentUtil.TERMINATE_AGENT: 
                try:
                    int_currentTime = time.time()                          
                    Uploader.upload()
                    if (int_currentTime - int_prevFileCleanUpTime) >= AgentConstants.FILE_CLEAN_UP_INTERVAL:
                        FileUtil.cleanUpFiles()
                        int_prevFileCleanUpTime = int_currentTime
                    #Wait for a large interval if it is not the first data collection
                    if FILES_UPLOADED <= 5:
                        #AgentLogger.log(AgentLogger.STDOUT,'Value of files uploaded is : ' + str(FILES_UPLOADED) + '. Hence wait interval is default')
                        AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(AgentConstants.FILE_UPLOAD_INTERVAL)
                    else:
                        AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(AgentConstants.FILE_UPLOAD_NEW_INTERVAL)
                except Exception as e:
                    AgentLogger.log(AgentLogger.CRITICAL, ' *************************** Exception while executing the uploader thread *************************** '+ repr(e) + '\n')
                    traceback.print_exc()   
        except Exception as e:
            AgentLogger.log(AgentLogger.CRITICAL, ' *************************** Exception while executing the uploader thread *************************** '+ repr(e) + '\n')
            traceback.print_exc()
            
    def __addFilesInUploadDirectoryToBuffer(self):
        try:
            AgentLogger.log(AgentLogger.STDOUT,'===================== ADDING FILES IN UPLOAD DIRECTORY TO UPLOAD BUFFER ======================')
            for zipFileName in sorted(os.listdir(AgentConstants.AGENT_UPLOAD_DIR)):
                for upload_category in UPLOAD_DATA_DIR_IMPL:
                    if upload_category in zipFileName:
                        task = UPLOAD_DATA_DIR_IMPL[upload_category]
                        taskArgs =  zipFileName
                        #AgentLogger.log(AgentLogger.STDOUT, ' ***************************Executing task : ' + str(task) + '*****************************')
                        task(taskArgs)
                        AgentLogger.log(AgentLogger.STDOUT, ' *************************** Found upload_category : ' + upload_category + ' in upload directory file: ' +  zipFileName)
                        #self.setUploadInfo(zipFileName,upload_category)    
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT, ' *************************** Exception while adding files in upload directory to upload buffer *************************** '+ repr(e))
            traceback.print_exc()

    def addPluginsFilesinDataDirectory(self,zipFileName):
        dict_requestParameters = {}
        try:
            zipAndUploadInfo = FileZipAndUploadInfo()
            zipAndUploadInfo.zipFileName = zipFileName
            zipAndUploadInfo.zipFilePath = AgentConstants.AGENT_UPLOAD_DIR+'/' + zipAndUploadInfo.zipFileName
            dict_requestParameters['agentkey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
            dict_requestParameters['apikey'] = AgentConstants.CUSTOMER_ID
            dict_requestParameters['zipname'] = zipAndUploadInfo.zipFileName
            dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
            zipAndUploadInfo.uploadServlet = AgentConstants.PLUGIN_DATA_POST_SERVLET
            zipAndUploadInfo.uploadRequestParameters = dict_requestParameters
            AgentBuffer.getBuffer('FILES_TO_UPLOAD_BUFFER').add(zipAndUploadInfo)
        except Exception as e:
            AgentLogger.log(AgentLogger.CRITICAL, ' *************************** Exception while adding files in upload directory to upload buffer *************************** '+ repr(e) + '\n')
            traceback.print_exc()

    def addFilesinDataDirectory(self,zipFileName):
        dict_requestParameters = {}
        try:
            zipAndUploadInfo = FileZipAndUploadInfo()
            zipAndUploadInfo.zipFileName = zipFileName
            zipAndUploadInfo.zipFilePath = AgentConstants.AGENT_UPLOAD_DIR+'/' + zipAndUploadInfo.zipFileName
            dict_requestParameters['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
            dict_requestParameters['CUSTOMERID'] = AgentConstants.CUSTOMER_ID
            dict_requestParameters['AGENTUNIQUEID'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_unique_id')
            dict_requestParameters['FILENAME'] = zipAndUploadInfo.zipFilePath if len(zipAndUploadInfo.zipFilePath)<200 else zipAndUploadInfo.zipFilePath[0:199]
            dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
            zipAndUploadInfo.uploadServlet = AgentConstants.AGENT_FILE_COLLECTOR_SERVLET
            zipAndUploadInfo.uploadRequestParameters = dict_requestParameters
            AgentBuffer.getBuffer('FILES_TO_UPLOAD_BUFFER').add(zipAndUploadInfo)
        except Exception as e:
            AgentLogger.log(AgentLogger.CRITICAL, ' *************************** Exception while adding files in upload directory to upload buffer *************************** '+ repr(e) + '\n')
            traceback.print_exc()
            
    def addCustomFilesinDataDirectory(self,zipFileName):
        dict_requestParameters = {}
        try:
            zipAndUploadInfo = FileZipAndUploadInfo()
            zipAndUploadInfo.zipFileName = zipFileName
            zipAndUploadInfo.zipFilePath = AgentConstants.AGENT_UPLOAD_DIR+'/' + zipAndUploadInfo.zipFileName
            dict_requestParameters['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
            dict_requestParameters['CUSTOMERID'] = AgentConstants.CUSTOMER_ID
            dict_requestParameters['AGENTUNIQUEID'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_unique_id')
            dict_requestParameters['FILENAME'] = zipAndUploadInfo.zipFilePath if len(zipAndUploadInfo.zipFilePath)<200 else zipAndUploadInfo.zipFilePath[0:199]
            dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
            zipAndUploadInfo.uploadServlet = AgentConstants.AGENT_FILE_COLLECTOR_SERVLET # Change to custom metric later
            zipAndUploadInfo.uploadRequestParameters = dict_requestParameters
            AgentBuffer.getBuffer('FILES_TO_UPLOAD_BUFFER').add(zipAndUploadInfo)
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT, ' *************************** Exception while adding  custom files in upload directory to upload buffer *************************** '+ repr(e))
            traceback.print_exc()
    
    @staticmethod
    def getUploadData(zipAndUploadInfo):
        str_dataToReturn = None
        try:
            bool_zipFileCorrupted = False
            if zipAndUploadInfo.zipFilePath and os.path.isfile(zipAndUploadInfo.zipFilePath):
                try:
                    file_obj = open(zipAndUploadInfo.zipFilePath,'rb')
                    str_dataToReturn = file_obj.read()
                    zipAndUploadInfo.isZipFile = True
                except Exception as e:
                    AgentLogger.log(AgentLogger.CRITICAL,' ************************* Exception while reading the zip file '+repr(full_path)+' ************************* '+ repr(e) + '\n')
                    traceback.print_exc()
                    bool_zipFileCorrupted = True
                finally:
                    if file_obj:
                        file_obj.close()       
                if bool_zipFileCorrupted:
                    os.remove(full_path)
            elif zipAndUploadInfo.uploadData:
                str_dataToReturn = zipAndUploadInfo.uploadData
                zipAndUploadInfo.isZipFile = False
        except Exception as e:
            AgentLogger.log(AgentLogger.CRITICAL, ' *************************** Exception while fetching data for uploading *************************** '+ repr(e) + '\n')
            traceback.print_exc()
        return str_dataToReturn
    
    @staticmethod   
    @synchronized
    def upload():
        file_obj = None
        dict_requestParameters = {}
        global FILES_UPLOADED, LAST_UPLOADED_TIME, UPLOAD_PAUSE_TIME, UPLOAD_PAUSE_FLAG
        try:
            buffer_UploadInfoObjects = AgentBuffer.getBuffer('FILES_TO_UPLOAD_BUFFER')
            while buffer_UploadInfoObjects.size() > 0 and not AgentUtil.TERMINATE_AGENT:
                if UPLOAD_PAUSE_FLAG:
                    ct = time.time()
                    if ((ct - LAST_UPLOADED_TIME) > UPLOAD_PAUSE_TIME):
                        AgentLogger.log(AgentLogger.STDOUT,' Upload pause time requested by server completed. Hence switching to normal upload mode')
                        UPLOAD_PAUSE_FLAG = False
                        UPLOAD_PAUSE_TIME = 0
                    else:
                        break
                AgentLogger.log(AgentLogger.STDOUT,'================================= UPLOAD FILES AND DATA =================================')
                str_url = None
                str_dataToSend = None
                str_contentType = None
                zipAndUploadInfo = buffer_UploadInfoObjects.pop()
                AgentLogger.log(AgentLogger.STDOUT,'One object removed from the upload buffer with a total of : ' + str(len(buffer_UploadInfoObjects)) + 'zips')
                if AgentConstants.UPTIME_MONITORING=="true":
                    AgentLogger.log(AgentLogger.STDOUT,'##### Deleting collected data [uptime monitoring] #####')
                    os.remove(zipAndUploadInfo.zipFilePath)
                else:
                    try:
                        dict_requestParameters = zipAndUploadInfo.uploadRequestParameters
                        str_dataToSend = Uploader.getUploadData(zipAndUploadInfo)
                        if zipAndUploadInfo.isZipFile == True:
                            fileName = zipAndUploadInfo.zipFileName
                            str_contentType = 'application/zip'
                        else:
                            str_contentType = 'application/json'
                        if not str_dataToSend:
                            AgentLogger.log(AgentLogger.CRITICAL,'Unable to get data for the zipAndUploadInfo object : '+repr(zipAndUploadInfo)+' hence skipping upload\n')
                            continue
                        str_servlet = zipAndUploadInfo.uploadServlet
                        if not dict_requestParameters == None:
                            if str_servlet in [AgentConstants.PLUGIN_DATA_POST_SERVLET,AgentConstants.AGENT_FILE_COLLECTOR_SERVLET,AgentConstants.APPLICATION_COLLECTOR_SERVLET,AgentConstants.AGENT_SYSLOG_STATS_SERVLET]:
                                dict_requestParameters['ZIPS_IN_BUFFER'] = int(len(buffer_UploadInfoObjects))
                            if str_servlet in [AgentConstants.AGENT_FILE_COLLECTOR_SERVLET]:
                                dict_requestParameters['auid']=AgentConstants.AUID
                                dict_requestParameters['auid_old']=AgentConstants.AUID_OLD
                                dict_requestParameters['sct'] = AgentUtil.getTimeInMillis()
                                if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','installer') and not AgentUtil.AGENT_CONFIG.get('AGENT_INFO','installer')=='0':
                                    dict_requestParameters['installer'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','installer')
                            str_requestParameters = urlencode(dict_requestParameters)
                            str_url = str_servlet + str_requestParameters
                        requestInfo = CommunicationHandler.RequestInfo()
                        requestInfo.set_loggerName(AgentLogger.STDOUT)
                        requestInfo.set_method(AgentConstants.HTTP_POST)
                        requestInfo.set_url(str_url)
                        requestInfo.set_data(str_dataToSend)
                        requestInfo.set_dataType(str_contentType)
                        requestInfo.add_header("Content-Type", str_contentType)
                        requestInfo.add_header("Accept", "text/plain")
                        requestInfo.add_header("Connection", 'close')
                        (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
                        CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'FILE UPLOADER')
                        if bool_isSuccess:
                            if ((dict_responseHeaders) and ('UPLOAD_FAILED' in dict_responseHeaders) and (str(dict_responseHeaders['UPLOAD_FAILED'] == "True"))):
                                buffer_UploadInfoObjects.appendleft(zipAndUploadInfo)
                                AgentLogger.log(AgentLogger.STDOUT,'Zip readded to upload buffer due to server side error. Total zips in buffer : ' + str(len(buffer_UploadInfoObjects)))
                                continue
                            LAST_UPLOADED_TIME = time.time()
                            FILES_UPLOADED = FILES_UPLOADED + 1
                            if FILES_UPLOADED > 100 :
                                FILES_UPLOADED = int(FILES_UPLOADED/10)
                            AgentLogger.log(AgentLogger.STDOUT,'Value of files uploaded changed to : ' + str(FILES_UPLOADED))
                            if zipAndUploadInfo.isZipFile == True:
                                AgentLogger.log(AgentLogger.STDOUT, 'Successfully posted the zip file :'+fileName+' to the server \n')
                            else:
                                AgentLogger.log([AgentLogger.STDOUT], 'Successfully posted the JSON data to the server \n')
                                dictUploadedData = json.loads(str_dataToSend)
                                if AgentConstants.CHECKS_VERIFY_TEXT in dictUploadedData:
                                    AgentLogger.debug(AgentLogger.STDOUT, 'Changing status after instant notification')
                                    BasicClientHandler.URLUtil.updateURLStatus(dictUploadedData)
                                    BasicClientHandler.PortUtil.updatePortStatus(dictUploadedData)
                                    BasicClientHandler.NTPUtil.updateNTPStatus(dictUploadedData)
                                    if 'logrule' in dictUploadedData:
                                        UdpHandler.SysLogUtil.updateSyslogData(dictUploadedData)
                                #elif AgentConstants.PORT_VERIFY_TEXT in dictUploadedData:
                                #    BasicClientHandler.PortUtil.updatePortStatus(dictUploadedData)
                            if Uploader.__serverNotReachableStartTime != 0:
                                Uploader.__serverNotReachableStartTime = 0
                                COLLECTOR.scheduleDataCollection()
                            if zipAndUploadInfo.isZipFile == True:
                                os.remove(zipAndUploadInfo.zipFilePath)
                        else:
                            buffer_UploadInfoObjects.appendleft(zipAndUploadInfo)
                            AgentLogger.log(AgentLogger.STDOUT,'Zip readded to upload buffer because upload did not recieve successful flag. Total zips in buffer : ' + str(len(buffer_UploadInfoObjects)))
                            if zipAndUploadInfo.isZipFile == True:
                                AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDOUT], '************************* Unable to post the zip file :'+fileName+' to the server. Added its uploadinfo object to upload buffer ************************* \n')
                            else:
                                AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDOUT], '************************* Unable to post the JSON data to the server. Added its uploadinfo object to upload buffer ************************* \n')
                            CommunicationHandler.checkNetworkStatus(AgentLogger.STDOUT)
                            AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(AgentConstants.FILE_UPLOAD_EXCEPTION_INTERVAL)
                            if isinstance(errorCode, OSError):
                                if Uploader.__serverNotReachableStartTime == 0:
                                    Uploader.__serverNotReachableStartTime = time.time()
                                    break
                                elif (time.time() - Uploader.__serverNotReachableStartTime) > AgentConstants.STOP_DATA_COLLECTION_INTERVAL:
                                    AgentLogger.log([ AgentLogger.CRITICAL],'Agent is not able to reach server for '+repr(time.time() - Uploader.__serverNotReachableStartTime)+' seconds > STOP_DATA_COLLECTION_INTERVAL = '+repr(AgentConstants.STOP_DATA_COLLECTION_INTERVAL)+'\n')
                                    COLLECTOR.stopDataCollection()
                                    break
                                else:
                                    break
                    except Exception as e:
                        AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], ' *************************** Exception while uploading files/JSON data *************************** '+ repr(e) + '\n')
                        traceback.print_exc()
                        buffer_UploadInfoObjects.appendleft(zipAndUploadInfo) # Make sure that zipAndUploadInfo is back in buffer when exception occurs.
                        AgentLogger.log(AgentLogger.STDOUT,'Zip readded to upload buffer due to exception. Total memory occupied by it is now with a total of : ' + str(len(buffer_UploadInfoObjects)) + 'zips')
        except Exception as e:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], ' *************************** Exception while uploading files/JSON data *************************** '+ repr(e) + '\n')
            traceback.print_exc()

    @staticmethod
    def update_file_collector_time():
        try:
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(AgentConstants.FILE_COLLECTOR_UPLOAD_CHECK)
            fileObj.set_data(str(AgentUtil.getTimeInMillis()))
            fileObj.set_logging(False)
            fileObj.set_loggerName([AgentLogger.STDOUT])
            FileUtil.saveData(fileObj)
        except Exception as e:
            traceback.print_exc()
'''

def saveCollectedServerData(dict_dataToSave, dir_prop, custom=None):
    bool_toReturn = True
    str_fileName = None
    try:
        dict_dataToSave['MSPCUSTOMERID'] = AgentConstants.CUSTOMER_ID
        dict_dataToSave['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        custom=AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')+"_"+custom+"_"+"millis"+"_"+str(AgentUtil.getTimeInMillis())
        str_fileName = FileUtil.getUniqueFileName(dict_dataToSave['AGENTKEY'],custom,True)
        str_filePath = dir_prop['data_path'] +'/'+ str_fileName
        fileObj = AgentUtil.FileObject()
        fileObj.set_fileName(str_fileName)
        fileObj.set_filePath(str_filePath)
        fileObj.set_data(dict_dataToSave)
        fileObj.set_dataType('json')
        fileObj.set_mode('wb')
        fileObj.set_dataEncoding('UTF-16LE')
        fileObj.set_loggerName(AgentLogger.COLLECTOR)
        bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
    except Exception as e:
        AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], '*************************** Exception while saving collected server data : '+repr(dict_dataToSave)+'*************************** '+ repr(e) + '\n')
        traceback.print_exc()
        bool_toReturn = False
    return bool_toReturn, str_fileName

def saveCollectedData(dict_dataToSave, custom = None):
    bool_toReturn = True
    str_fileName = None
    try:
        dict_dataToSave['MSPCUSTOMERID'] = AgentConstants.CUSTOMER_ID
        dict_dataToSave['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        if custom and custom=="SMData":
            custom=AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')+"_"+custom+"_"+"millis"+"_"+str(AgentUtil.getTimeInMillis())
            str_fileName = FileUtil.getUniqueFileName(dict_dataToSave['AGENTKEY'],custom,True)
        else:
            dict_dataToSave['DATACOLLECTTIME'] = str(AgentUtil.getTimeInMillis())
            str_fileName = FileUtil.getUniqueFileName(dict_dataToSave['AGENTKEY'])
        str_filePath = AgentConstants.AGENT_DATA_DIR +'/'+ str_fileName
        fileObj = AgentUtil.FileObject()
        fileObj.set_fileName(str_fileName)
        fileObj.set_filePath(str_filePath)
        fileObj.set_data(dict_dataToSave)
        fileObj.set_dataType('json')
        fileObj.set_mode('wb')
        fileObj.set_dataEncoding('UTF-16LE')
        fileObj.set_loggerName(AgentLogger.COLLECTOR)
        bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
    except Exception as e:
        AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], '*************************** Exception while saving collected data : '+repr(dict_dataToSave)+'*************************** '+ repr(e) + '\n')
        traceback.print_exc()
        bool_toReturn = False
    return bool_toReturn, str_fileName

    
def loadQueryConf():    
    global PROCESS_LIST
    bool_isSuccess = True
    str_queryConfDir = AgentConstants.AGENT_QUERY_CONF_DIR+'/'+AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
    str_queryConfPath = str_queryConfDir+'/queryconf.txt'
    try:
        appendCustomMonitorsToMonitorsInfo()
        if not os.path.exists(str_queryConfDir):
            os.makedirs(str_queryConfDir)
        if not os.path.exists(str_queryConfPath):#copying default queryconf.txt
            shutil.copy(AgentConstants.AGENT_QUERY_CONF_DIR+'/queryconf.txt', str_queryConfPath)   
        if os.path.exists(str_queryConfPath):            
            isSuccess, dict_queryConfData = AgentUtil.loadUnicodeDataFromFile(str_queryConfPath)
            AgentLogger.debug(AgentLogger.STDOUT, 'LOAD QUERYCONF : Monitors Info Loaded From XML :'+repr(MONITORS_INFO))
            AgentLogger.debug(AgentLogger.STDOUT, 'LOAD QUERYCONF : Custom Monitors Info Loaded From XML :'+repr(CUSTOM_MONITORS_INFO))
            if isSuccess:
                list_dataCollParams = dict_queryConfData['WorkFlows']                
                for dict_dataCollParam in list_dataCollParams:
                    list_searchStrings = []
                    if 'Name' in dict_dataCollParam['recordSetName'][0]:
                        monitorDetails = dict_dataCollParam['recordSetName'][0]
                        monitorName = monitorDetails['Name']
                        monitoringInterval = dict_dataCollParam['interval']
                        AgentLogger.debug(AgentLogger.STDOUT, 'LOAD QUERYCONF : MONITOR :'+repr(monitorName)+repr(dict_dataCollParam)) 
                        #check for parsing search variables from wmiQuery for PROCESS_AND_SERVICE_DETAILS
                        if monitorName == 'PROCESS_AND_SERVICE_DETAILS':                            
                            params = monitorDetails['params']
                            AgentLogger.debug(AgentLogger.STDOUT, 'LOAD QUERYCONF : params :'+repr(params)+repr(type(params))) 
                            list_strings = re.findall(r'\'[\w\s\d,<\.\>\?\/\!\@\#\$\%\^\&\*\(\)\_\-\+\=\`\~\"\;\:]+\'',params)
                            for str_temp in list_strings:
                                list_searchStrings.append(str_temp[1:-1])                                                                                                      
                    if not COLLECTOR.getMonitors() == None and monitorName in COLLECTOR.getMonitors():     
                        dict_monitorAttributes = COLLECTOR.getMonitors()[monitorName]['Attributes']
                        if list_searchStrings:
                            dict_monitorAttributes['searchValues'] = list_searchStrings
                            AgentLogger.log(AgentLogger.STDOUT, 'Process to be filtered : '+repr(list_searchStrings))
                            dict_processToBeMonitored = {} 
                            list_processToBeMonitored = []
                            for processName in list_searchStrings:
                                dict_processToBeMonitored = {}
                                dict_processToBeMonitored['Name'] = processName
                                list_processToBeMonitored.append(dict_processToBeMonitored)
                            updateProcessList(list_processToBeMonitored)
                        AgentLogger.debug(AgentLogger.STDOUT, 'LOAD QUERYCONF : '+repr(monitorName)+' : Attributes : '+repr(dict_monitorAttributes))                 
            else:
                AgentLogger.log(AgentLogger.STDOUT, 'Failed To load the QueryConf.txt in the path :'+str_queryConfPath)
                bool_isSuccess = False
            AgentLogger.debug(AgentLogger.STDOUT,'MONITORS_INFO Data :'+repr(COLLECTOR.getMonitors()))
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, '*************************** Exception While loading Query Conf In The Path : '+str_queryConfPath+'*************************** '+ repr(e))
        traceback.print_exc()
        bool_isSuccess = False
    return bool_isSuccess

def appendCustomMonitorsToMonitorsInfo():
    if COLLECTOR.getCustomMonitors():
        for monitorName in list(COLLECTOR.getCustomMonitors().keys()):            
            if not COLLECTOR.getMonitors() == None:     
                COLLECTOR.getMonitors()[monitorName] = COLLECTOR.getCustomMonitors()[monitorName]

def updateQueryConf(dict_updateQueryInfo, str_loggerName=AgentLogger.STDOUT):
    bool_isSuccess = True
    list_queryConf = []
    int_monitorCount = 0
    int_updateMonitorIndex = None
    str_agentQueryConfDir = AgentConstants.AGENT_QUERY_CONF_DIR+'/'+AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
    str_queryConfPath = str_agentQueryConfDir+'/queryconf.txt'
    try:
        if os.path.exists(str_queryConfPath):            
            isSuccess, dict_queryConfData = AgentUtil.loadUnicodeDataFromFile(str_queryConfPath)
            AgentLogger.log(str_loggerName, 'Monitor details to be updated in the query conf :'+repr(type(dict_updateQueryInfo))+repr(dict_updateQueryInfo))
            updateMonitorName = dict_updateQueryInfo['recordSetName'][0]['Name']#monitor details from server
            if isSuccess:
                list_dataCollParams = dict_queryConfData['WorkFlows']#list of monitors in query conf
                for dict_dataCollParam in list_dataCollParams:                                     
                    if 'Name' in dict_dataCollParam['recordSetName'][0]:
                        monitorName = dict_dataCollParam['recordSetName'][0]['Name']
                        if monitorName == 'PROCESS_AND_SERVICE_DETAILS':              
                            list_searchStrings = []              
                            params = dict_updateQueryInfo['recordSetName'][0]['params']
                            AgentLogger.log(str_loggerName, 'UPDATE QUERYCONF : params :'+repr(params)+repr(type(params))) 
                            list_strings = re.findall(r'\'[\w\s\d,<\.\>\?\/\!\@\#\$\%\^\&\*\(\)\_\-\+\=\`\~\"\;\:]+\'',params)
                            for str_temp in list_strings:
                                list_searchStrings.append(str_temp[1:-1])
                            AgentLogger.log(str_loggerName, 'Process to be filtered in update query conf : '+repr(list_searchStrings))
                            dict_processToBeMonitored = {} 
                            list_processToBeMonitored = []
                            for processName in list_searchStrings:
                                dict_processToBeMonitored = {}
                                dict_processToBeMonitored['Name'] = processName
                                list_processToBeMonitored.append(dict_processToBeMonitored)
                            updateProcessList(list_processToBeMonitored)
                        if updateMonitorName == monitorName:
                            int_updateMonitorIndex = int_monitorCount
                    int_monitorCount+=1
                if not int_updateMonitorIndex == None:
                    list_dataCollParams.pop(int_updateMonitorIndex)
                #by default append the monitor details from the server to the query conf list
                list_dataCollParams.append(dict_updateQueryInfo)    
                AgentLogger.log(str_loggerName, 'Query Conf data collection list :'+repr(list_dataCollParams))
                AgentUtil.writeUnicodeDataToFile(str_queryConfPath, json.dumps(dict_queryConfData))
                loadQueryConf()
                #COLLECTOR.scheduleDataCollection()
            else:
                AgentLogger.log(str_loggerName, 'Error while loading the QueryConf.txt in the path :'+str_queryConfPath)
                bool_isSuccess = False
        else:            
            AgentLogger.log(str_loggerName,'Failed to update query conf since '+repr(str_queryConfPath)+' does not exist!!')
            bool_isSuccess = False
    except Exception as e:
        AgentLogger.log(str_loggerName, '*************************** Exception while updating query conf in the path : '+str_queryConfPath+'*************************** '+ repr(e))
        traceback.print_exc()
        bool_isSuccess = False
    return bool_isSuccess    

def initializeFileAndZipIds():
    if int(AgentUtil.AGENT_PARAMS['AGENT_FILE_ID']) >= AgentConstants.MAX_FILE_ID - 100:
        AgentUtil.AGENT_PARAMS['AGENT_FILE_ID'] = 0
        AgentUtil.persistAgentParams()
    if int(AgentUtil.AGENT_PARAMS['AGENT_ZIP_ID']) >= AgentConstants.MAX_FILE_ID - 100:
        AgentUtil.AGENT_PARAMS['AGENT_ZIP_ID'] = 0
        AgentUtil.persistAgentParams()
    AgentUtil.AGENT_PARAMS['AGENT_FILE_ID'] = int(AgentUtil.AGENT_PARAMS['AGENT_FILE_ID']) +100
    AgentUtil.AGENT_PARAMS['AGENT_ZIP_ID'] = int(AgentUtil.AGENT_PARAMS['AGENT_ZIP_ID']) +100
    FileUtil.setFileId(AgentUtil.AGENT_PARAMS['AGENT_FILE_ID'])
    AgentUtil.persistAgentParams()
