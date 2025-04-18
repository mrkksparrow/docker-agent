#$Id$
import os
import json
import copy
import time
import shutil
import traceback
import threading
import hashlib
import re
import math
import sys
import platform
import multiprocessing
try:
    import psutil
except Exception as e:
    pass

from six.moves.urllib.parse import urlencode
import com
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.util import AgentUtil , AppUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil
from com.manageengine.monagent.communication import BasicClientHandler
from com.manageengine.monagent.communication import UdpHandler
from com.manageengine.monagent.util.rca import RcaHandler
from com.manageengine.monagent.util.rca.RcaHandler import RcaUtil
from com.manageengine.monagent.collector import aix_data_consolidator,sunos_data_consolidator
from com.manageengine.monagent.actions import settings_handler

customFileLock = threading.Lock()
CONFIG_OBJECTS = None
PARSE_IMPL = None
ACTIVE_PROCESS_DICT = None
PROCESS_WATCHER_DICT = None
THRESHOLD_DICT = None
DISABLED_CHILD_ALERTS_DICT = None
SELF_MONITOR_DICT = {}

def getHashID(strArgs):
    try:
        return hashlib.md5(strArgs.encode()).hexdigest()
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],'*************************** Exception While getting hash ID for process args :'  +  str(strArgs) +'*************************** '+ repr(e))
        traceback.print_exc()

def initialize():
    global PARSE_IMPL,CONFIG_OBJECTS,ACTIVE_PROCESS_DICT,PROCESS_WATCHER_DICT
    PARSE_IMPL = {'ROOT_IMPL': getRootData,
                  'ASSET_IMPL': getAssetData,
                  'MEMORY_IMPL': getMemoryData,
                  'MEMORY_STATS_IMPL':get_memory_statistics,
                  'DISK_IMPL': getDiskData,
                  'LINUX_DISK_IMPL': get_linux_disk_data,
                  'DISK_INODE_IMPL': get_disk_inode,
                  'DISK_IO_IMPL':get_disk_io,
                  'SOURCE_DISK_IO_IMPL':source_disk_io,
                  'NETWORK_IMPL': getNetworkData,
                  'CPU_IMPL' : getCPUData,
                  'PROCESS_IMPL' : getProcessData, # freebsd, osx
                  'PROCESS_IMPLEMENTATION':getProcessMonitoring,   # linux
                  'SYSTEM_IMPL':getSystemData,
                  'PSUTIL_IMPL':get_ps_util_cpu_stats,
                  'CPU_SAR_IMPL': get_sar_cpu, 
                  'CPU_STATS_IMPL':getCpuMonitoringStats, # if top command failed during initialization, old flow
                  'TOP_CPU_PROCESS': getTopCpuProcessData, # if top command passed during initialization, new flow
                  'TOP_MEM_PROCESS': getTopMemProcessData, # if top command passed during initialization, new flow
                  'CPU_LOAD_IMPL' : getCPULoadData,
                  'CPU_AIX_IMPL' : aix_data_consolidator.get_aix_cpu,
                  'DISK_AIX_IMPL': aix_data_consolidator.get_aix_disk,
                  'Ps_Util_Stats_Impl': aix_data_consolidator.collect_metrics,
                  'DIRECT_IMPL':aix_data_consolidator.get_metrics,
                  'MEM_AIX_IMPL':aix_data_consolidator.get_aix_mem,
                  'DISK_SUN_IMPL':sunos_data_consolidator.get_sunos_disk,
                  'CPU_SUN_IMPL' :sunos_data_consolidator.get_sunos_cpu,
                  'MEM_SUN_IMPL':sunos_data_consolidator.get_sunos_mem
                }
    PROCESS_WATCHER_DICT = {}
    
def updateAgentConfig(restart=False,app_config=False):
    ''' To sync the config objects in data consolidator'''
    str_servlet = AgentConstants.AGENT_CONFIG_SERVLET
    dictRequestParameters = {}
    try:
        dictRequestParameters['CUSTOMERID'] = AgentConstants.CUSTOMER_ID
        dictRequestParameters['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        dictRequestParameters['bno'] = AgentConstants.AGENT_VERSION
        dictRequestParameters['apps'] = True
        if not dictRequestParameters == None:
            str_requestParameters = urlencode(dictRequestParameters)
            str_url = str_servlet + str_requestParameters
        AgentLogger.log(AgentLogger.STDOUT,'================================= UPDATING AGENT CONFIG DATA =================================\n')
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.STDOUT)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.add_header("Content-Type", 'application/json')
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        (isSuccess, int_errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
        if isSuccess and dict_responseData:
            dictParsedData = json.loads(dict_responseData)
            dict_parsed_data_copy = dictParsedData.copy()
            AgentLogger.log(AgentLogger.MAIN,'Configuration Update from Server - Success \n')
            AgentLogger.debug(AgentLogger.MAIN,'config data from server -- {0}'.format(dictParsedData))
            if 'process' in dict_parsed_data_copy:
                del dict_parsed_data_copy['process']
            AgentLogger.log(AgentLogger.STDOUT,'Server returned the config data : {}'.format(json.dumps(dict_parsed_data_copy)))
            updateConfigObjects(dictParsedData,restart)
            if AgentConstants.IS_DOCKER_AGENT == "1":
                AgentConstants.DOCKER_HELPER_OBJECT.handle_new_configurations(dictParsedData, restart)
        else:
            AgentLogger.log([AgentLogger.STDOUT, AgentLogger.MAIN],'Server returned no config data or connection failure \n')
        CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'CONFIG DATA')
    except Exception as e:
        AgentLogger.log([AgentLogger.MAIN,AgentLogger.STDERR],'*************************** Exception While loading agent config data from server *************************** {}'.format(e))
        traceback.print_exc()

def updateConfigObjects(dictConfigData,restart):
    '''To update the global config object '''
    #traceback.print_stack()
    global CONFIG_OBJECTS,ACTIVE_PROCESS_DICT,THRESHOLD_DICT,DISABLED_CHILD_ALERTS_DICT
    CONFIG_OBJECTS={}
    PROCESS_NAMES=[]
    ACTIVE_PROCESS_DICT={}
    try:
        if 'plugins' in dictConfigData:
            CONFIG_OBJECTS['plugins']={}
            plugin_config_list = dictConfigData['plugins']
            for each in plugin_config_list:
                plugin_name = each['plugin_name']
                CONFIG_OBJECTS['plugins'][plugin_name]={}
                CONFIG_OBJECTS['plugins'][plugin_name]['timeout']= each['timeout']
                CONFIG_OBJECTS['plugins'][plugin_name]['poll_interval']= each['poll_interval']
        if 'threshold' in dictConfigData:
            THRESHOLD_DICT={}               
            THRESHOLD_DICT=dictConfigData['threshold']
            AgentLogger.log([AgentLogger.COLLECTOR],"threshold configuration -- {0} ".format(json.dumps(THRESHOLD_DICT)))
        if 'disabled_alerts' in dictConfigData:
            DISABLED_CHILD_ALERTS_DICT = {}
            DISABLED_CHILD_ALERTS_DICT = dictConfigData['disabled_alerts']
            AgentLogger.log([AgentLogger.COLLECTOR],"disabled alerts configuration -- {0} ".format(json.dumps(DISABLED_CHILD_ALERTS_DICT)))
        if 'process' in dictConfigData:
            ACTIVE_PROCESS_DICT = {}
            CONFIG_OBJECTS['Processes'] = {}
            listProcess = dictConfigData['process']
            for each_process in listProcess:
                CONFIG_OBJECTS['Processes'][each_process['args']] = each_process['id']
                if (AgentConstants.OS_NAME == AgentConstants.LINUX_OS or AgentConstants.OS_NAME == AgentConstants.AIX_OS_LOWERCASE or AgentConstants.OS_NAME.lower()==AgentConstants.SUN_OS.lower()):
                    processid = each_process['id']
                    process_name=each_process['pn'].split()[0]
                    PROCESS_NAMES.append(process_name)
                    ACTIVE_PROCESS_DICT.setdefault(processid,{})
                    ACTIVE_PROCESS_DICT[processid]['pn'] = process_name
                    ACTIVE_PROCESS_DICT[processid]['args'] = each_process['args']
                    ACTIVE_PROCESS_DICT[processid]['pth'] = each_process['pth']
                    ACTIVE_PROCESS_DICT[processid]['id'] = each_process['id']
                    ACTIVE_PROCESS_DICT[processid]['regex']=False
                    if 'regex' in each_process and each_process['regex']=="true":
                        regex_obj = AgentUtil.get_regex_expression(each_process['args'])
                        if regex_obj:
                            ACTIVE_PROCESS_DICT[processid]['regex_exp'] = regex_obj
                            ACTIVE_PROCESS_DICT[processid]['regex']=True
                else:
                    if AgentConstants.PS_UTIL_DC==True:
                        HId = each_process['id']
                    else:
                        HId = getHashID(each_process['args'])
                    ACTIVE_PROCESS_DICT.setdefault(HId,{})
                    ACTIVE_PROCESS_DICT[HId]['pn'] = each_process['pn']
                    ACTIVE_PROCESS_DICT[HId]['args'] = each_process['args']
                    ACTIVE_PROCESS_DICT[HId]['pth'] = each_process['pth']
                    ACTIVE_PROCESS_DICT[HId]['id'] = each_process['id']
                    if each_process['pn'] not in AgentConstants.PROCESS_NAMES_TO_BE_MONITORED:
                        AgentConstants.PROCESS_NAMES_TO_BE_MONITORED.append(each_process['pn'])
        AgentLogger.debug(AgentLogger.CHECKS,'process monitoring configuration --- {0}'.format(ACTIVE_PROCESS_DICT))
        if 'apps' in dictConfigData:
            AppUtil.update_app_config_data(dictConfigData)
        if  'BONDING_STATUS' in dictConfigData:
            if dictConfigData['BONDING_STATUS'] == 'true':
                AgentConstants.BONDING_INTERFACE_STATUS = True
        if 'nw' in dictConfigData:
            CONFIG_OBJECTS['NICS'] = {}
            listNICs = dictConfigData['nw']
            for each_NIC in listNICs:
                CONFIG_OBJECTS['NICS'][each_NIC['ma']] = each_NIC['id']
        if 'disks' in dictConfigData:
            CONFIG_OBJECTS['DISKS'] = {}
            listDisks = dictConfigData['disks']
            for each_disk in listDisks:
                CONFIG_OBJECTS['DISKS'][each_disk['dn']] = each_disk['id']
        AgentConstants.PROCESS_MONITORING_NAMES='|'.join(PROCESS_NAMES)
        if AgentConstants.PROCESS_NAMES_TO_BE_MONITORED:
            AgentConstants.PROCESS_MONITORING_NAMES='|'.join(AgentConstants.PROCESS_NAMES_TO_BE_MONITORED)
        AgentLogger.log(AgentLogger.CHECKS,'list of process to be monitored--- '+repr(AgentConstants.PROCESS_MONITORING_NAMES)+'\n')
        if 'settings' in dictConfigData:
            settings_handler.update_settings(dictConfigData)
        if (('reloadNotRequired' not in dictConfigData) or (dictConfigData['reloadNotRequired'] != True) or (restart)):
            if 'url' in dictConfigData:
                CONFIG_OBJECTS['URL'] = {}
                listURLs = dictConfigData['url']
                for each_URL in listURLs:
                    CONFIG_OBJECTS['URL'][each_URL['id']] = each_URL['id']
            if 'port' in dictConfigData:
                CONFIG_OBJECTS['PORT'] = {}
                listPorts = dictConfigData['port']
                for each_port in listPorts:
                    CONFIG_OBJECTS['PORT'][each_port['id']] = each_port['id']
            if 'ntp' in dictConfigData:
                CONFIG_OBJECTS['NTP'] = {}
                listNTP = dictConfigData['ntp']
                for each_port in listNTP:
                    CONFIG_OBJECTS['NTP'][each_port['id']] = each_port['id']
            if 'script' in dictConfigData:
                CONFIG_OBJECTS['SCRIPT'] = {}
                listScripts = dictConfigData['script']
                for each_script in listScripts:
                    CONFIG_OBJECTS['SCRIPT'][each_script['PATH']] = each_script['id']
            if (('nfs' in dictConfigData) and  (AgentConstants.OS_NAME in AgentConstants.NFS_MON_SUPPORTED)):
                CONFIG_OBJECTS['NFS'] = {}
                listNFS = dictConfigData['nfs']
                for each_nfs in listNFS:
                    CONFIG_OBJECTS['NFS'][each_nfs['id']] = each_nfs['id']
            if ((('file' in dictConfigData) or ('dir' in dictConfigData)) and  (AgentConstants.OS_NAME in AgentConstants.NFS_MON_SUPPORTED)):
                CONFIG_OBJECTS['FILE'] = {}
                if 'file' in dictConfigData:
                    listFiles = dictConfigData['file']
                    for each_file in listFiles:
                        CONFIG_OBJECTS['FILE'][each_file['id']] = each_file['id']
                if 'dir' in dictConfigData:
                    listDirs = dictConfigData['dir']
                    for each_dir in listDirs:
                        CONFIG_OBJECTS['FILE'][each_dir['id']] = each_dir['id']
            if 'logrule' in dictConfigData:
                CONFIG_OBJECTS['logrule'] = {}
                listFilters = dictConfigData['logrule']
                if listFilters:
                    UdpHandler.SysLogUtil.reloadCustomFilters(listFilters)
                for each_filter in listFilters:
                    CONFIG_OBJECTS['logrule'][each_filter['filter_name']] = each_filter['id']
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(AgentConstants.AGENT_CUSTOM_MONITORS_GROUP_FILE)
            fileObj.set_dataType('json')
            fileObj.set_mode('rb')
            fileObj.set_dataEncoding('UTF-8')
            fileObj.set_loggerName(AgentLogger.CHECKS)
            fileObj.set_logging(False)
            bool_toReturn, dict_monitorsInfo = FileUtil.readData(fileObj)
            dict_monitorsInfo['MonitorGroup']['ChecksMonitoring']['Port'] = dictConfigData['port']
            dict_monitorsInfo['MonitorGroup']['ChecksMonitoring']['URL'] = dictConfigData['url']
            dict_monitorsInfo['MonitorGroup']['ChecksMonitoring']['NTP'] = dictConfigData['ntp']
            if 'nfs' in dictConfigData:
                dict_monitorsInfo['MonitorGroup']['ChecksMonitoring']['NFSMonitoring'] = dictConfigData['nfs']
            dict_monitorsInfo['MonitorGroup']['ChecksMonitoring']['FileDirectory'] = dictConfigData['file']+dictConfigData['dir']
            fileObj.set_data(dict_monitorsInfo)
            fileObj.set_mode('wb')
            with customFileLock:
                bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
            BasicClientHandler.reload()
        else:
            AgentLogger.log([AgentLogger.STDOUT],'=============== Skipped Updating resource configuration values =======')
        CONFIG_OBJECTS_COPY = CONFIG_OBJECTS.copy()
        AgentLogger.debug([AgentLogger.STDOUT],' config object original ' + json.dumps(CONFIG_OBJECTS_COPY))
        if 'Processes' in CONFIG_OBJECTS_COPY:
            del CONFIG_OBJECTS_COPY['Processes']
        AgentLogger.log([AgentLogger.STDOUT],' Updated configuration values ' + json.dumps(CONFIG_OBJECTS_COPY))
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],'*************************** Exception While loading agent config data from server *************************** '+ repr(e))
        traceback.print_exc()

def updateID(dictProcessData):
    try:
        for eachProcess in dictProcessData['Process Details']:
            if "COMMANDLINE" in eachProcess:
                if eachProcess['COMMANDLINE'] in CONFIG_OBJECTS['Processes']:
                    id  = CONFIG_OBJECTS['Processes'][eachProcess['COMMANDLINE']]
                    eachProcess['id'] = id
                    eachProcess['status'] = '1'
                else:
                    eachProcess['id'] = '-9'
                    eachProcess['status'] = '1'
            else:
                eachProcess['id'] = '-1'
                eachProcess['status'] = '0'
        return dictProcessData
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],'*************************** Exception While updating IDs in process data *************************** '+ repr(e))
        traceback.print_exc()

def getRootData(dictData, dictKeyData, dictConfig):
    try:
        if 'CPU Utilization' in dictKeyData:
            dictData['cper'] = dictKeyData['CPU Utilization'][0]['LoadPercentage']
            if AgentConstants.OS_NAME == AgentConstants.FREEBSD_OS:
                if AgentConstants.PSUTIL_OBJECT:
                    get_ps_util_cpu_stats(dictData)
            if AgentConstants.OS_NAME == AgentConstants.LINUX_OS:
                idle_time = dictKeyData['CPU Utilization'][0]['CPU_Idle_Percentage']
                wait_time = dictKeyData['CPU Utilization'][0]['CPU_Wait_Percentage']
                idle_time=float(idle_time)
                wait_time=float(wait_time)
                dictData['cper'] = eval(AgentConstants.CPU_FORMULA)
        elif 'Context Switches' in dictKeyData:
            dictData['ctxtsw'] = dictKeyData['Context Switches'][0]['ContextSwitchesPersec']
        elif 'Number of Interrupts' in dictKeyData:
            dictData['interrupts'] = dictKeyData['Number of Interrupts'][0]['InterruptsPersec']
        if AgentConstants.OS_NAME is AgentConstants.LINUX_OS:
            dictData['entropy'] = AgentUtil.entropy_avail()
    except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for root node *********************************')
            traceback.print_exc()

def getCpuMonitoringStats(dictData,dictKeyData,dictConfig):
    try:
        if not AgentConstants.TOP_COMMAND_CHECK:
            cpu_data = dictKeyData['CPU_Monitoring'][0]['Output']
            cpu_values = cpu_data.split(',')
            for each in cpu_values:
                each=each.strip()
                x=re.split('%|\s',each)
                dictData[x[1]]=x[0]
            idle_time=float(dictData['id'])
            steal_time=float(dictData['st'])
            if idle_time > 100 or steal_time < 0:
                get_ps_util_cpu_stats(dictData)
            else:
                wait_time=float(dictData['wa'])
                user_time=float(dictData['us'])
                system_time=float(dictData['sy'])
                steal_time=float(dictData['st'])
                hardware_interrupt=float(dictData['hi'])
                software_interrupt=float(dictData['si'])
                dictData['cper']=eval(AgentConstants.CPU_FORMULA)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for cpu stats *********************************')
        traceback.print_exc()
        AgentLogger.log(AgentLogger.COLLECTOR,' data obtained -- {0}'.format(dictKeyData))
        get_ps_util_cpu_stats(dictData)

def parseTopProcessData(dict_key, parse_arg, dictKeyData, dictData):
    try:
        cpu_count = multiprocessing.cpu_count()
        AgentConstants.PS_UTIL_PROCESS_DICT[dict_key] = []
        top_process = []
        list_top_cpu_data = dictKeyData[parse_arg] if parse_arg in dictKeyData else []
        for each in list_top_cpu_data:
            if each:
                if each['PID'] == 'CPU_UTIL' and each['thread_count'] == 'xxx':
                    cpu_data = each['cmd_line_arg']
                    cpu_data_list = cpu_data.split(": ")[1].split(",")
                    for each in cpu_data_list:
                        each=each.strip()
                        x=re.split('%|\s',each)
                        dictData[x[1]]=x[0]
                    try:
                        idle_time=float(dictData['id'])
                        steal_time=float(dictData['st'])
                        dictData['cper']=eval(AgentConstants.CPU_FORMULA)
                    except Exception as e:
                        traceback.print_exc()
                    if "cper" not in dictData:
                        dictData["cper"] = each["CPU"]
                else:
                    process_data = {}
                    for key, value in AgentConstants.TOP_PROCESS_METRICS.items():
                        if each[key] is None:
                            process_data[value] = '0'
                        elif type(each[key]) is list:
                            process_data[value] = ' '.join(each[key]).strip()
                        elif key in ('CPU', 'MEM'):
                            if ":" in str(each[key]):
                                each[key] = str(each[key]).replace(":","")
                            process_data[value] = str(round(float(each[key]), 2))
                        else:
                            process_data[value] = str(each[key]) if type(each[key]) is not float else str(round(each[key], 2))

                    process_data['Avg. CPU Usage(%)'] = round(float(process_data['CPU Usage(%)']), 2)
                    process_data['CPU Usage(%)'] = round(float(process_data['CPU Usage(%)']) / cpu_count, 2)
                    process_data['Avg. Memory Usage(MB)'] = process_data['Memory Usage(MB)']
                    if process_data['Command Line Arguments'] == '':
                        process_data['Command Line Arguments'] = process_data['Process Name']
                    if len(process_data['Command Line Arguments']) > AgentConstants.TOP_PROCESS_ARGUMENT_LENGTH:
                        process_data['Command Line Arguments'] = str(process_data['Command Line Arguments'])[0:AgentConstants.TOP_PROCESS_ARGUMENT_LENGTH]
                    if process_data['Path'] in (None, '', '0'):
                        process_data['Path'] = process_data['Process Name']
                    top_process.append(process_data)
                    continue

        AgentConstants.PS_UTIL_PROCESS_DICT[dict_key] = copy.deepcopy(top_process)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR, AgentLogger.STDERR], '*************************** Exception while parsing top process data *********************************')
        traceback.print_exc()

def getTopCpuProcessData(dictData, dictKeyData, dictConfig):
    try:
        if AgentConstants.TOP_COMMAND_CHECK:
            parseTopProcessData('TOPCPUPROCESS', 'Top CPU Process', dictKeyData, dictData)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR, AgentLogger.STDERR], '*************************** Exception while getting top process data *********************************')
        traceback.print_exc()

def getTopMemProcessData(dictData, dictKeyData, dictConfig):
    try:
        if AgentConstants.TOP_COMMAND_CHECK:
            parseTopProcessData('TOPMEMORYPROCESS', 'Top MEM Process', dictKeyData, dictData)
            file_desc = 0
            if AgentConstants.DOCKER_PSUTIL:
                for proc in AgentConstants.DOCKER_PSUTIL.process_iter():
                    if AgentConstants.ISROOT_AGENT:
                        try:
                            file_desc += proc.num_fds()
                        except:
                            AgentLogger.log(AgentLogger.CRITICAL, 'Exception on summation of file desc of all process during access of /proc/{}/fd'.format(proc['pid']))
                            traceback.print_exc()

                        continue

            AgentConstants.PS_UTIL_PROCESS_DICT['fd'] = file_desc
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR, AgentLogger.STDERR], '*************************** Exception while getting top mem process data *********************************')
        traceback.print_exc()

def getCpuMetrics(dictData,top_command_data):
    try:
        cpu_data = top_command_data['cpu_values']
        cpu_values = cpu_data.split(',')
        for each in cpu_values:
            each=each.strip()
            x=re.split('%|\s',each)
            dictData[x[1]]=x[0]
        idle_time=float(dictData['id'])
        steal_time=float(dictData['st'])
        if idle_time > 100 or steal_time < 0:
            get_ps_util_cpu_stats(dictData)
        else:    
            wait_time=float(dictData['wa'])
            user_time=float(dictData['us'])
            system_time=float(dictData['sy'])
            steal_time=float(dictData['st'])
            hardware_interrupt=float(dictData['hi'])
            software_interrupt=float(dictData['si'])    
            dictData['cper']=eval(AgentConstants.CPU_FORMULA)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for cpu stats *********************************')
        traceback.print_exc()
        AgentLogger.log(AgentLogger.COLLECTOR,' data obtained -- {0}'.format(dictData))
        get_ps_util_cpu_stats(dictData)

def get_ps_util_cpu_stats(dictData):
    try:
        AgentLogger.log(AgentLogger.COLLECTOR,' -- CPU metrics collected using get_ps_util_cpu_stats -- ')
        import psutil
        cpu = psutil.cpu_times_percent(interval=2)
        idle_time=cpu.idle
        if AgentConstants.OS_NAME==AgentConstants.FREEBSD_OS:
            dictData['cper']=eval(AgentConstants.CPU_FORMULA)
            return
        wait_time=cpu.iowait
        steal_time=cpu.steal
        #kernel version 4.9 bug results in negative steal time
        if steal_time < 0:
            steal_time = 0
            AgentLogger.log(AgentLogger.COLLECTOR,'found negative steal time so setting it to 0 \n')
            AgentLogger.log(AgentLogger.COLLECTOR,'value obtained - {0}'.format(cpu.steal)+'\n')
        dictData['id']=idle_time
        dictData['wa']=wait_time
        dictData['us']=cpu.user
        dictData['sy']=cpu.system
        dictData['st']=steal_time
        dictData['si']=cpu.softirq
        dictData['hi']=cpu.irq
        dictData['cper']=eval(AgentConstants.CPU_FORMULA)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for ps util stats *********************************')
        traceback.print_exc()

#To get cpu data from sar 
def get_sar_cpu(dictData, dictKeyData, dictConfig):
    try:
        command = "sar -u ALL 2 2 | awk 'END{print}'"
        executorObj = AgentUtil.Executor()
        executorObj.setTimeout(30)
        executorObj.setCommand(command)
        executorObj.executeCommand()
        stdout = executorObj.getStdOut()
        if stdout:
            parsedList = stdout.strip('\n').split()
            idle_time = float(parsedList[11])
            dictData['id'] = idle_time
            dictData['us'] = parsedList[2]
            dictData['sy'] = parsedList[4]
            dictData['wa'] = parsedList[5]
            dictData['hi'] = parsedList[7]
            dictData['si'] = parsedList[8]
            dictData['cper'] = eval(AgentConstants.CPU_FORMULA)
            steal_time = float(parsedList[6])
            if steal_time < 0:
                steal_time = 0
                AgentLogger.log(AgentLogger.COLLECTOR, 'Found negative steal time so setting it to 0 \n')
                AgentLogger.log(AgentLogger.COLLECTOR, 'value obtained - {0}'.format(steal_time) + '\n')
            dictData['st'] = steal_time
        else:
            AgentLogger.log([AgentLogger.COLLECTOR, AgentLogger.STDERR], '*************************** No values for SAR cpu stats *********************************')
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR, AgentLogger.STDERR], '*************************** Exception while setting consolidated values for SAR cpu stats *********************************')
        traceback.print_exc()

def getAssetData(dictData, dictKeyData, dictConfig):
    try:
        if 'Number Of Cores' in dictKeyData:
            dictData['asset']['core'] = dictKeyData['Number Of Cores'][0]['NumberOfCores']
        elif 'Memory Utilization' in dictKeyData:
            dictData['asset']['os'] = dictKeyData['Memory Utilization'][0]['Caption'] if not re.match(r'^[_\W]+$',dictKeyData['Memory Utilization'][0]['Caption']) else platform.system()
            if not AgentConstants.EXACT_OS:
               AgentConstants.EXACT_OS = dictData['asset']['os']
        elif 'OS Architecture' in dictKeyData:
            dictData['asset']['arch'] = dictKeyData['OS Architecture'][0]['OSArchitecture']
        elif 'CPU Utilization' in dictKeyData:
            dictData['asset']['cpu'] = dictKeyData['CPU Utilization'][0]['Name']
        dictData['asset']['instance'] = AgentConstants.AGENT_INSTANCE_TYPE
        if AgentConstants.PROCESSOR_NAME:
            dictData['asset']['cpu'] = AgentConstants.PROCESSOR_NAME
    except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for asset node*********************************')
            traceback.print_exc()

def getMemoryData(dictData, dictKeyData, dictConfig):
    defMemPercent = 0
    defMemory = 0
    free_cmd_available_check = False
    try:
        if 'Memory Utilization' in dictKeyData:
            if ('AvailablePhysicalMemory' in dictKeyData['Memory Utilization'][0]):
                availPhy = round(int(dictKeyData['Memory Utilization'][0]['AvailablePhysicalMemory'])/1024)
            else:
                availPhy = defMemory
            if ('FreePhysicalMemory' in dictKeyData['Memory Utilization'][0]):
                freePhy = round(int(dictKeyData['Memory Utilization'][0]['FreePhysicalMemory'])/1024)
            else:
                freePhy = defMemory
            if ('UsedPhysicalMemory' in dictKeyData['Memory Utilization'][0]):
                usedPhy = round(int(dictKeyData['Memory Utilization'][0]['UsedPhysicalMemory'])/1024)
            else:
                usedPhy = defMemory
            if ('TotalVisibleMemorySize' in dictKeyData['Memory Utilization'][0]):
                totPhy = round(int(dictKeyData['Memory Utilization' ][0]['TotalVisibleMemorySize'])/1024)
            else:
                totPhy = defMemory
            if ('BufferMemory' in dictKeyData['Memory Utilization'][0]):
                bufferMemory = round(int(dictKeyData['Memory Utilization' ][0]['BufferMemory'])/1024)
            else:
                bufferMemory = defMemory
            if ('CacheMemory' in dictKeyData['Memory Utilization'][0]):
                if dictKeyData['Memory Utilization' ][0]['CacheMemory'] == "-1":
                    cacheMemory = defMemory
                    free_cmd_available_check = True
                else:
                    cacheMemory = round(int(dictKeyData['Memory Utilization' ][0]['CacheMemory'])/1024)
            else:
                cacheMemory = defMemory
            if not free_cmd_available_check:
                if not AgentUtil.is_module_enabled(AgentConstants.EXCLUDE_BUFFER_VALUE) :
                    AgentLogger.log(AgentLogger.COLLECTOR, '[totPhy - usedPhy + bufferMemory + cacheMemory] :: TotalMemory - {} :: UsedMemory - {} :: BufferMemory - {} :: CacheMemory - {}'.format(totPhy, usedPhy, bufferMemory, cacheMemory))
                    resfreePhy = totPhy - usedPhy + bufferMemory + cacheMemory
                else:
                    AgentLogger.log(AgentLogger.COLLECTOR, '[totPhy - usedPhy] :: TotalMemory - {} :: UsedMemory - {}'.format(totPhy, usedPhy))
                    resfreePhy = totPhy - usedPhy
            else:
                if not AgentUtil.is_module_enabled(AgentConstants.EXCLUDE_BUFFER_VALUE):
                    AgentLogger.log(AgentLogger.COLLECTOR, '[AvailableMemory] - {}'.format(availPhy))
                    resfreePhy = availPhy
                else:
                    AgentLogger.log(AgentLogger.COLLECTOR, '[freePhy  + bufferMemory + cacheMemory] :: FreeMemory - {} :: BufferMemory - {} :: CacheMemory - {}'.format(freePhy, bufferMemory, cacheMemory))
                    resfreePhy = freePhy  + bufferMemory + cacheMemory
            if ('FreeVirtualMemory' in dictKeyData['Memory Utilization'][0]):
                freeVir = round(int(dictKeyData['Memory Utilization' ][0]['FreeVirtualMemory'])/1024)
            else:
                freeVir = defMemory
            if ('TotalVirtualMemorySize' in dictKeyData['Memory Utilization'][0]):
                totVir = round(int(dictKeyData['Memory Utilization' ][0]['TotalVirtualMemorySize'])/1024)
            else:
                totVir = defMemory
            dictData['memory']['fvirm'] = freeVir
            dictData['memory']['fvism'] = resfreePhy
            dictData['memory']['tvirm'] = totVir
            dictData['memory']['tvism'] = totPhy
            dictData['memory']['uvism'] = totPhy - resfreePhy
            dictData['memory']['uvirm'] = totVir - freeVir
            try:
                memUsedPercent = round((((totPhy - resfreePhy)/totPhy)*100),2)
            except ZeroDivisionError as e:
                memUsedPercent = defMemPercent
            dictData['mper'] = str(memUsedPercent)
            dictData['asset']['ram'] = totPhy
            if totVir!=0:
                dictData['memory']['swpmemper'] = ((totVir - freeVir)/totVir)*100
            else:
                dictData['memory']['swpmemper'] = 0
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for memory node *********************************')
        traceback.print_exc()
        get_ps_util_memory_info(dictData)

def get_memory_statistics(dictData,dictKeyData,dictConfig):
    try:
        if 'Memory Statistics' in dictKeyData:
            dictData['memory']['pfaults'] = int(dictKeyData['Memory Statistics'][0]['PageFaultsPersec'])
            dictData['memory']['pin'] = int(dictKeyData['Memory Statistics'][0]['PagesInputPersec'])
            dictData['memory']['pout'] = int(dictKeyData['Memory Statistics'][0]['PagesOutputPersec'])
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for memory statistics node *********************************')
        traceback.print_exc()

def get_ps_util_memory_info(dictData):
    try:
        if AgentConstants.PSUTIL_OBJECT:
            virtual_memory = psutil.virtual_memory()
            if virtual_memory:
                dictData['memory']['tvirm'] = virtual_memory.total/1024/1024
                dictData['memory']['fvirm'] = virtual_memory.free/1024/1024
                dictData['memory']['uvirm'] = virtual_memory.used/1024/1024
                dictData['asset']['ram']=virtual_memory.total/1024/1024
                dictData['mper'] = virtual_memory.percent
            swap_memory = psutil.swap_memory()
            if swap_memory:
                dictData['memory']['swpmemper']=swap_memory.percent
                dictData['memory']['fvism'] = swap_memory.free /1024/1024
                dictData['memory']['tvism'] = swap_memory.total/1024/1024
                dictData['memory']['uvism'] = swap_memory.used/1024/1024
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception is psutil memory block ')
        traceback.print_exc()

def get_disk_data_from_config(collected_disk_data,dictConfig,dictData):
    disk_data = {}
    disk_data['totalDisk']=0
    disk_data['totalUsedDisk']=0
    disk_data['totalFreeDisk']=0
    defaultDiskPer = 0
    listDisks = []
    try:
        if collected_disk_data:
            disk_config_data = dictConfig['DISKS']
            for disk_name , disk_id in disk_config_data.items():
                temp_dict = {}
                temp_dict['id'] = disk_id
                temp_dict['name'] = disk_name
                if disk_name in collected_disk_data:
                    temp_dict['status'] = "1"
                    disk_values = collected_disk_data[disk_name]
                    get_disk_metric(disk_values,temp_dict,disk_data)
                else:
                    temp_dict['status'] = "0"
                listDisks.append(temp_dict)
            try:
                diskUsedPercent = int(round(((disk_data['totalUsedDisk']/disk_data['totalDisk'])*100),0))
                dictData['dused'] = int(round(disk_data['totalUsedDisk']))
                dictData['dfree'] = int(round(disk_data['totalFreeDisk']))
                dictData['dtotal'] = int(round(disk_data['totalDisk']))
            except ZeroDivisionError as e:
                diskUsedPercent = defaultDiskPer
            diskFreePercent = 100 - diskUsedPercent
            dictData['dfper'] = str(diskFreePercent)
            dictData['duper'] = str(diskUsedPercent)
        dictData.setdefault('disk',listDisks)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while getting disk data from config ********************************* :: {}'.format(e))
        traceback.print_exc()

def get_disk_metric(each_disk,temp_dict,disk_data):
    try:
        defaultDiskPer = 0
        try:
            freeSpace = float(each_disk['FreeSpace'])
        except:
            freeSpace = int(each_disk['FreeSpace'])
        try:
            totalSpace = float(each_disk['Size'])
        except:
            totalSpace = int(each_disk['Size'])
        totalSpace = totalSpace / ( 1024 * 1024 )
        freeSpace = freeSpace / ( 1024 * 1024 )
        usedSpace = totalSpace - freeSpace
        disk_data['totalDisk'] += totalSpace
        disk_data['totalUsedDisk'] += usedSpace
        disk_data['totalFreeDisk'] += freeSpace
        temp_dict['name'] = each_disk['Name']
        temp_dict['file_system'] = each_disk['FileSystem'].split()[0] #to strip unwanted values from fs
        temp_dict['filesystem'] = each_disk['Type']
        temp_dict['dfree'] = int(round(freeSpace,0))
        temp_dict['dtotal'] = int(round(totalSpace,0))
        try:
            temp_dict['dfper'] = int(round(((freeSpace/totalSpace)*100),0))
        except ZeroDivisionError as e:
            temp_dict['dfper'] = defaultDiskPer
        temp_dict['dused'] = int(round(usedSpace,0))
        try:
            temp_dict['duper'] = int(round(((usedSpace/totalSpace)*100),0))
        except ZeroDivisionError as e:
            temp_dict['duper'] = defaultDiskPer
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while getting dick metrics ********************************* :: {}'.format(e))
        traceback.print_exc()

def get_disk_io(dictData, dictKeyData, dictConfig):
    collected_disk_io_data = {}
    try:
        # data from script.sh disk_stats [Disk Statistics]
        dictData['dreads'] = 0
        dictData['dwrites'] = 0
        if 'Disk Statistics' in dictKeyData:
            for each in dictKeyData['Disk Statistics']:
                collected_disk_io_data[each['Name']]={}
                collected_disk_io_data[each['Name']]['Name']=each['Name']                                     # DiskReadBytesPersec/DiskWriteBytesPersec from the script output is subracted from previous output
                collected_disk_io_data[each['Name']]['DiskReadBytesPersec']=each['DiskReadBytesPersec']       # and divided by time diff in seconds
                collected_disk_io_data[each['Name']]['DiskWriteBytesPersec']=each['DiskWriteBytesPersec']     # to find the disk reads/writes per second
        # data from script.sh disk_details [Disk Utilization]
        if 'disk' in dictData:
            disk_data = dictData['disk']
            for each_disks in disk_data:
                if 'file_system' in each_disks:
                    disk_fs_list = each_disks['file_system'].split('/')
                    if len(disk_fs_list) > 2 and disk_fs_list[2] in collected_disk_io_data:
                        each_disks['dreads'] = collected_disk_io_data[disk_fs_list[2]]['DiskReadBytesPersec']
                        each_disks['dwrites'] = collected_disk_io_data[disk_fs_list[2]]['DiskWriteBytesPersec']
                        each_disks['diskio'] = str(float(each_disks['dreads'])+float(each_disks['dwrites']))
                    else:
                        each_disks['dreads'] = "NA"
                        each_disks['dwrites'] = "NA"
                        each_disks['diskio'] = "NA"
        # disk listed from "lsblk --noheadings --raw | grep -i disk" alone considered for overall disk read/write calculation
        for each_hdd in AgentConstants.HDD_NAMES:
            if each_hdd in collected_disk_io_data:
                 dictData['dreads'] += float(collected_disk_io_data[each_hdd]['DiskReadBytesPersec'])
                 dictData['dwrites'] += float(collected_disk_io_data[each_hdd]['DiskWriteBytesPersec'])
        dictData['diskio'] = dictData['dreads']+dictData['dwrites']
        dictData['dreads'] = str(dictData['dreads'])
        dictData['dwrites'] = str(dictData['dwrites'])
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for Disk IO *********************************')
        traceback.print_exc()

def source_disk_io(dictData, dictKeyData, dictConfig):
    try:
        dictData['dreads'] = 0.0
        dictData['dwrites'] = 0.0
        if 'Disk Statistics' in dictKeyData:
            for each in dictKeyData['Disk Statistics']:
                dictData['dreads'] += float(each['DiskReadBytesPersec'])
                dictData['dwrites'] += float(each['DiskWriteBytesPersec'])
        dictData['diskio'] = dictData['dreads'] + dictData['dwrites']
        dictData['dreads'] = str(dictData['dreads'])
        dictData['dwrites'] = str(dictData['dwrites'])
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for Disk IO *********************************')
        traceback.print_exc()

#for src agent disk
def getDiskData(dictData, dictKeyData, dictConfig):
    totalDisk = 0
    totalUsedDisk = 0
    defaultDiskPer = 0
    listDisks = []
    try:
        if 'Disk Utilization' in dictKeyData:
            listKeyDicts = dictKeyData['Disk Utilization']
            for each_disk in listKeyDicts:
                temp_dict = {}
                if dictConfig and'DISKS' in dictConfig and each_disk['Name'] in dictConfig['DISKS']:
                    temp_dict['id'] = dictConfig['DISKS'][each_disk['Name']]
                else:
                    temp_dict['id'] = "None"
                try:
                    freeSpace = float(each_disk['FreeSpace'])
                except:
                    freeSpace = int(each_disk['FreeSpace'])
                try:
                    totalSpace = float(each_disk['Size'])
                except:
                    totalSpace = int(each_disk['Size'])
                totalSpace = totalSpace / ( 1024 * 1024 )
                freeSpace = freeSpace / ( 1024 * 1024 )
                usedSpace = totalSpace - freeSpace
                totalDisk += totalSpace
                totalUsedDisk += usedSpace
                temp_dict['file_system'] = each_disk['FileSystem']
                temp_dict['filesystem'] = each_disk['Type']
                temp_dict['name'] = each_disk['Name']
                temp_dict['inodes'] = each_disk['Total_Inodes']
                temp_dict['iused'] = each_disk ['IUsed']
                temp_dict['ifree'] = each_disk ['IFree']
                temp_dict['iuper'] = each_disk ['IUsedPer'].strip('%') if each_disk['IUsedPer'] != '-' else '0' #IUsedPer will be - when total size itself 0
                temp_dict['dfree'] = int(round(freeSpace,0))
                temp_dict['dtotal'] = int(round(totalSpace,0))
                try:
                    temp_dict['dfper'] = int(round(((freeSpace/totalSpace)*100),0))
                except ZeroDivisionError as e:
                    temp_dict['dfper'] = defaultDiskPer
                temp_dict['dused'] = int(round(usedSpace,0))
                try:
                    temp_dict['duper'] = int(round(((usedSpace/totalSpace)*100),0))
                except ZeroDivisionError as e:
                    temp_dict['duper'] = defaultDiskPer
                listDisks.append(temp_dict)
                
            try:
                diskUsedPercent = int(round(((totalUsedDisk/totalDisk)*100),0))
            except ZeroDivisionError as e:
                diskUsedPercent = defaultDiskPer
            diskFreePercent = 100 - diskUsedPercent
            dictData['dfper'] = str(diskFreePercent)
            dictData['duper'] = str(diskUsedPercent)
        else:
            dictData['dfper'] = '0'
            dictData['duper'] = '0'
        dictData.setdefault('disk',listDisks)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for disk node *********************************')
        traceback.print_exc()

def get_linux_disk_data(dictData, dictKeyData, dictConfig):
    iterate_dc_data = True
    collected_disk_data = {}
    disk_config_data = {'DISKS':{}}
    try:
        if 'DISKS' in dictConfig and dictConfig['DISKS']:
            disk_config_data['DISKS'] = dictConfig['DISKS']
        list_disk_data = dictKeyData['Disk Utilization'] if 'Disk Utilization' in dictKeyData else []
        for each in list_disk_data:
            collected_disk_data[each['Name']]={}
            collected_disk_data[each['Name']]['Name']=each['Name']
            collected_disk_data[each['Name']]['Size']=each['Size']
            collected_disk_data[each['Name']]['FreeSpace']=each['FreeSpace']
            collected_disk_data[each['Name']]['FreeDiskPercent']=each['FreeDiskPercent']
            collected_disk_data[each['Name']]['FileSystem']=each['FileSystem']
            collected_disk_data[each['Name']]['Type']=each['Type']
            if each['Name'] not in disk_config_data['DISKS']:
                disk_config_data['DISKS'][each['Name']] = "None"
        get_disk_data_from_config(collected_disk_data,disk_config_data, dictData)
        if os.path.isfile('/proc/diskstats'):
            read_latency = 0
            write_latency = 0
            with open('/proc/diskstats', 'r') as file_obj:  #refer https://www.kernel.org/doc/Documentation/ABI/testing/procfs-diskstats
                diskstats = file_obj.readlines()
            for line in diskstats:
                if 'loop' not in line:
                    device = line.split()
                    read_latency += int(device[6]) / int(device[3])  if int(device[3]) != 0 else 0   # time spent on reads / total reads      in ms
                    write_latency += int(device[10]) / int(device[7]) if int(device[7]) != 0 else 0  # time spent on writes / total writes    in ms
            dictData['readlatency'] = str(round(read_latency, 2))
            dictData['writelatency'] = str(round(write_latency, 2))
        if AgentConstants.IOSTAT_UTILITY_PRESENT:
            dictData['dbusy'], dictData['didle'], dictData['readops'], dictData['writeops'], dictData['aql'] = AgentUtil.metrics_from_iostat()
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for disk node *********************************')
        traceback.print_exc()

def get_disk_inode(dictData, dictKeyData, dictConfig):
    collected_disk_data = {}
    try:
        for each in dictKeyData.get('Disk Inode',[]):
            collected_disk_data[each['Name']] = {}
            collected_disk_data[each['Name']]['Total_Inodes'] = each['Total_Inodes']
            collected_disk_data[each['Name']]['IUsed'] = each['IUsed']
            collected_disk_data[each['Name']]['IFree'] = each['IFree']
            collected_disk_data[each['Name']]['IUsedPer'] = each['IUsedPer'].strip('%') if each['IUsedPer'] != '-' else '0' #IUsedPer will be - when total size itself 0

        for each in dictData.get('disk',[]):
            if each['name'] in collected_disk_data.keys():
                each['inodes'] = collected_disk_data[each['name']]['Total_Inodes']
                each['iused'] = collected_disk_data[each['name']]['IUsed']
                each['ifree'] = collected_disk_data[each['name']]['IFree']
                each['iuper'] = collected_disk_data[each['name']]['IUsedPer']
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for disk_inode *********************************')
        traceback.print_exc()

def getCPULoadData(dictData, dictKeyData, dictConfig):
    dictLoadData = {}
    try:
        if 'Load Average Data' in dictKeyData:
            dictLoadData = dictKeyData['Load Average Data']
            dictData["load"] = {}
            dictData['load']['Last 1 Minute'] = dictLoadData[0]['Last 1']
            dictData['load']['Last 5 Minute'] = dictLoadData[0]['Last 5']
            dictData['load']['Last 15 Minute'] = dictLoadData[0]['Last 15']
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for CPU Load *********************************')
        traceback.print_exc()

def getNetworkData(dictData, dictKeyData, dictConfig):
    listNics = []
    dictNicData = {}
    ip_list= []
    ipv4_list=[]
    total_throughput = 0
    try:
        listKeyDict = dictKeyData['Network Data']
        #to include primary IP mandatorily            
        ipv4_list.append(AgentConstants.IP_ADDRESS)
        for each_nic in listKeyDict:
            if ((each_nic['MACAddress'] in dictNicData) and (int(each_nic['Status']) == 2)):
                AgentLogger.log( AgentLogger.COLLECTOR, '*********** MAC Address already exists and status is unknown. Hence skipping!! ****************')
                continue
            if (str(each_nic['AdapterDesc']).startswith('veth')):
                AgentLogger.log( AgentLogger.COLLECTOR, '*********** Network interface name starts with veth. Hence skipping!! ****************')
                continue
            if not each_nic['MACAddress']:
               AgentLogger.log( AgentLogger.COLLECTOR, '*********** MAC Address not found for interface :: {}. Hence skipping!! ****************'.format(each_nic['AdapterDesc']))
               continue 
            temp_dict = {}
            if dictConfig and 'NICS' in dictConfig and each_nic['MACAddress'] in dictConfig['NICS']:
                temp_dict['id'] = dictConfig['NICS'][each_nic['MACAddress']]
            else:
                temp_dict['id'] = "None"
            temp_dict['status'] = each_nic['Status']
            if int(each_nic['Status'])==2:
                temp_dict['status']=1
            temp_dict['name'] = each_nic['AdapterDesc']
            temp_dict['ipv4'] = each_nic['Ipv4Addrs']
            temp_dict['ipv6'] = each_nic['Ipv6Addrs']
            temp_dict['macadd'] = each_nic['MACAddress']
            temp_dict['bytesrcv'] = each_nic['BytesReceivedPersec']
            temp_dict['bytessent'] = each_nic['BytesSentPersec']
            temp_dict['bytesrcvkb'] = (int(each_nic['BytesReceivedPersec'])/1024)
            temp_dict['bytessentkb'] = (int(each_nic['BytesSentPersec'])/1024)
            temp_dict['totbyteskb'] = temp_dict['bytesrcvkb'] +  temp_dict['bytessentkb']
            temp_dict['discardpkts'] = each_nic['PacketsOutboundDiscarded']
            temp_dict['errorpkts'] = each_nic['PacketsOutboundErrors']
            temp_dict['pktrcv'] = each_nic['PacketsReceivedUnicastPersec']
            temp_dict['pktsent'] = each_nic['PacketsSentUnicastPersec']
            if temp_dict['ipv4'] not in ['-', '127.0.0.1', AgentConstants.IP_ADDRESS]:
                ipv4_list.append(temp_dict['ipv4'])

            temp_dict['bandwidth'] = AgentUtil.get_nicspeed(temp_dict['name']) #speed is being sent as bandwidth
            total_throughput += temp_dict['totbyteskb']
            dictNicData.setdefault(each_nic['MACAddress'],temp_dict)
        for (Macaddr,dictNic) in dictNicData.items():
            listNics.append(dictNic)
        dictData.setdefault('network',listNics)
        isempty_file = True
        if os.path.isfile('/sys/class/net/bonding_masters'):
            with open('/sys/class/net/bonding_masters', 'r') as bond_file:
                for line in bond_file:
                    if line.strip():
                        isempty_file = False
                        break
        if isempty_file is True:
            dictData.setdefault('bonding','false')
        else:
            dictData.setdefault('bonding','true')
        AgentConstants.NETWORKS_LIST = listNics
        AgentConstants.IP_LIST = ipv4_list
        dictData['asset'].setdefault('ip', ', '.join(AgentConstants.IP_LIST))
        #status, dictData['asset']['clock_delay'] = str(AgentUtil.offset_in_machine_clock()[1]) #in secs
        dictData['throughput'] = str(round(total_throughput,2)) #in KB
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for network node *********************************')
        traceback.print_exc()

def getCPUData(dictData, dictKeyData, dictConfig):
    listCores = []
    psutil_cpu = []
    try:
        listKeyDict = dictKeyData['CPU Cores Usage']
        if AgentConstants.PSUTIL_OBJECT:
            psutil_cpu = AgentConstants.PSUTIL_OBJECT.cpu_percent(percpu=True)
            for num , load in enumerate(psutil_cpu):
                temp_dict = {}
                temp_dict['core'] = num
                temp_dict['load'] = load
                listCores.append(temp_dict)
        else:
            for each_core in listKeyDict:
                temp_dict = {}
                temp_dict['core'] = each_core['Name']
                temp_dict['load'] = each_core['PercentProcessorTime']
                listCores.append(temp_dict)
        dictData.setdefault('cpu',listCores)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for CPU node *********************************')
        traceback.print_exc()

def getCpuInfo():
    processor_dict=None
    bool_toReturn=True
    cpuCoreInfo=[]
    try:
        if os.path.isfile('/proc/cpuinfo'):
            with open('/proc/cpuinfo', 'r') as fp:
                cpuinfo_list = fp.readlines()
            for line in cpuinfo_list:
                if line.startswith('processor'):
                    if processor_dict:
                        cpuCoreInfo.append(processor_dict)
                    processor_dict={}
                line = line.split(":")
                if len(line) > 1:
                    processor_dict[line[0].strip()]=line[1].strip()
            cpuCoreInfo.append(processor_dict)
            AgentLogger.debug(AgentLogger.COLLECTOR,' Final Output --- {0}'.format(cpuCoreInfo))
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while Reading CPU Info File *********************************')
        traceback.print_exc()
        bool_toReturn=False
    return bool_toReturn,cpuCoreInfo

def parse_top_command_data():
        top_data = {}
        try:
            top_data = {}
            textfile = open(AgentConstants.TOP_COMMAND_OUTPUT_FILE)
            lines = textfile.readlines()
            for line in reversed(lines):
                line = line.strip()
                if 'Tasks:' in line:
                    break
                if line.startswith(("KiB","PID")):
                    continue
                if line.startswith(('%Cpu','Cpu')):
                    cpu_line = line.strip().split(':')
                    cpu_data = cpu_line[1]
                    top_data['cpu_values'] = cpu_data.strip()
                else:
                    top_values = line.split()
                    if top_values:
                        top_data[top_values[0]] = top_values[8]
            if textfile:
                textfile.close()
        except Exception as e:
            traceback.print_exc()
        return top_data

def getProcessMonitoring(dictData, dictKeyData, dictConfig):
    try:
        listProcesses=[]
        VISITED_KEYS=[]
        dictProcessData={}
        processData = {}
        listKeyDict = dictKeyData['Process Details']   # script command output of param [pcheck::gnome-ca|ulaa]
        executorObj = AgentUtil.Executor()
        command = "/usr/bin/top -b -d2 -n2 > "+AgentConstants.TOP_COMMAND_OUTPUT_FILE
        executorObj.setCommand(command)
        executorObj.executeCommand()
        top_cmd_dict = parse_top_command_data()
        if not AgentConstants.PROCESS_MONITORING_NAMES:  # process to be monitored names [gnome-ca|ulaa]
            AgentLogger.debug(AgentLogger.CHECKS,'no process configured \n')
            return
        if not listKeyDict and AgentConstants.PROCESS_MONITORING_NAMES:  # not data from script.sh output but process name present for monitoring
            for key,value in ACTIVE_PROCESS_DICT.items():  # dict with child monitor id as key and process data as value (pid, pn, args, pth, rtc]
                process_id = key
                finalDict=processReCheck(value)
                processData.setdefault(process_id,finalDict)
        else:
            outputDict = {}
            ebpf_process_data = fetch_ebpf_process_data()
            for each_process in listKeyDict:  # for each process obtained from pcheck, a tempt dict is created
                process_name = each_process['pname']
                if process_name in outputDict:
                    list = outputDict.get(process_name)
                    temp_dict=getProcessTempDict(each_process)
                    list.append(temp_dict)
                else:
                    dictList = []
                    temp_dict=getProcessTempDict(each_process)
                    dictList.append(temp_dict)
                    outputDict.setdefault(process_name,dictList)
            for processid in ACTIVE_PROCESS_DICT.keys():
                process_config = ACTIVE_PROCESS_DICT[processid]
                process_id = process_config['id']
                regex_enaled = False
                pname = process_config['pn']
                process_args = process_config['args']
                regexEnabled = False
                if 'regex' in process_config:
                    regexEnabled = process_config['regex']
                processMonitoring = False
                if pname in outputDict:
                    processList = outputDict[pname]
                    retry_Once=False
                    for each_process_dict in processList:
                        args = each_process_dict['pargs']
                        if regexEnabled:
                            result = isRegexMatching(process_config,args)
                        else:
                            if os.path.exists(AgentConstants.PS_UTIL_CHECK_FILE):
                                result = isArgsMatching(process_config,args)
                            else:
                                result = check_for_arguments_match(process_config,args)
                        if result:
                            innerDict={}
                            innerDict['name']=each_process_dict['pname']
                            innerDict['status'] = 1
                            innerDict['args'] = each_process_dict['pargs']
                            innerDict['path'] = each_process_dict['path']
                            innerDict['cpu'] = each_process_dict['pcpu']
                            innerDict['memory'] = round(AgentUtil.custom_float(each_process_dict['pmem']),1)
                            innerDict['thread'] = each_process_dict['pthread']
                            innerDict['handle'] = each_process_dict['phandle']
                            innerDict['instance'] = 1
                            innerDict['priority'] = each_process_dict['priority']
                            innerDict['user'] = each_process_dict['user']
                            innerDict['id'] = process_id
                            innerDict['pid'] = each_process_dict['pid']
                            innerDict['uptime'] = each_process_dict['uptime']
                            innerDict['size'] = each_process_dict['size']
                            if each_process_dict["pid"] in ebpf_process_data:
                                innerDict['tx'] = ebpf_process_data[each_process_dict["pid"]]['tx']
                                innerDict['rx'] = ebpf_process_data[each_process_dict["pid"]]['rx']
                                innerDict['rt'] = ebpf_process_data[each_process_dict["pid"]]['rt']
                                AgentLogger.log(AgentLogger.CHECKS,"ebpf data found for process {}::{}".format(each_process_dict["pid"],each_process_dict['pname']))
                            if AgentConstants.PSUTIL_OBJECT:
                                get_ps_util_process_user_name(each_process_dict,innerDict)
                            if top_cmd_dict and each_process_dict['pid'] in top_cmd_dict:
                                innerDict['cpu'] = top_cmd_dict[each_process_dict['pid']]
                                if AgentConstants.NO_OF_CPU_CORES:
                                    innerDict['cpu'] = AgentUtil.custom_float(innerDict['cpu'])/AgentConstants.NO_OF_CPU_CORES
                            if ((process_id in processData) and (each_process_dict['AVAILABILITY'] == 1)):
                                innerDict['cpu'] = round(AgentUtil.custom_float(innerDict['cpu']) + AgentUtil.custom_float(processData[process_id]['cpu']),2)
                                innerDict['memory'] = round(AgentUtil.custom_float(innerDict['memory']) + AgentUtil.custom_float(processData[process_id]['memory']),2)
                                innerDict['instance'] = 1 + processData[process_id]['instance']
                                processData[process_id] = innerDict
                            elif process_id in processData:
                                innerDict['instance'] = 1 + processData[process_id]['instance']
                                processData[process_id] = innerDict
                            else:
                                processData.setdefault(process_id,innerDict)
                        else:
                            retry_Once=True
                    if process_id in processData:
                        retry_Once=False
                    if retry_Once:
                        finalDict = processReCheck(process_config)
                        processData.setdefault(process_id,finalDict)
                else:
                    finalDict = processReCheck(process_config)
                    processData.setdefault(process_id,finalDict)
        
        listProcesses=[]
        for key in processData:
            listProcesses.append(processData[key])
        dictData.setdefault('process',listProcesses)
        if processData:
            for k,v in processData.items():
                if k in ACTIVE_PROCESS_DICT:
                    if 'pid' in v:
                        ACTIVE_PROCESS_DICT[k]['pid'] = v['pid']
        # getCpuMetrics(dictData, top_cmd_dict) # ===>> cper collection no need for this flow #1846381
    except Exception as e:
        traceback.print_exc()

def get_ps_util_process_user_name(each_process_dict,innerDict):
        try:
            import psutil
            PID=each_process_dict['pid']
            p = psutil.Process(pid=int(PID))
            innerDict['user']=p.username()
        except Exception as e:
            traceback.print_exc()
            
def isRegexMatching(process_config,args):
    regexMatch = False
    try:
        if process_config['regex_exp'].search(args):
            AgentLogger.debug(AgentLogger.CHECKS," regex matched --- {0}".format(args))
            regexMatch = True
        else:
            AgentLogger.debug(AgentLogger.CHECKS," args not matched - from command  --- {0}".format(args))
            AgentLogger.debug(AgentLogger.CHECKS," args not matched - regex --- {0}".format(process_config['regex_exp']))
    except Exception as e:
        traceback.print_exc()
    return regexMatch
    
def isArgsMatching(process_config,args):
    argsMatch = False
    try:
        if  args.strip() in process_config['args']:
            AgentLogger.debug(AgentLogger.CHECKS," args matched --- {0}".format(args))
            argsMatch = True
        else:
            AgentLogger.debug(AgentLogger.CHECKS," args not matched - from command  --- {0}".format(args))
            AgentLogger.debug(AgentLogger.CHECKS," args not matched - from config --- {0}".format(process_config['args']))
    except Exception as e:
        traceback.print_exc()
    return argsMatch

def check_for_arguments_match(process_config,args):
    argsMatch = False
    try:
        if  args.strip() == process_config['args'].strip():
            AgentLogger.debug(AgentLogger.CHECKS," args matched --- {0}".format(args))
            argsMatch = True
        else:
            AgentLogger.debug(AgentLogger.CHECKS," args not matched - from command  --- {0}".format(args))
            AgentLogger.debug(AgentLogger.CHECKS," args not matched - from config --- {0}".format(process_config['args']))
    except Exception as e:
        traceback.print_exc()
    return argsMatch

def getProcessTempDict(process):
    temp_dict={}
    try:
        temp_dict['AVAILABILITY'] = process['AVAILABILITY']
        temp_dict['pargs'] = process['pargs']
        temp_dict['pname'] = process['pname']
        temp_dict['path'] = process['path']
        temp_dict['pcpu'] = process['pcpu']
        temp_dict['pmem'] = round(AgentUtil.custom_float(process['pmem']),1)
        temp_dict['pthread'] = process['pthread']
        temp_dict['phandle'] = process['phandle']
        temp_dict['uptime'] = process['uptime']
        temp_dict['size'] = process['size']
        if 'priority' in process:
            temp_dict['priority'] = process['priority']
        if 'user' in process:
            temp_dict['user'] = process['user']
        temp_dict['pid'] = process['pid']
        temp_dict['instance'] = 1
    except Exception as e:
        traceback.print_exc()
    finally:
        return temp_dict

def getProcessData(dictData, dictKeyData, dictConfig):
    listProcesses = []
    dictProcessData = {}
    AgentLogger.debug(AgentLogger.COLLECTOR,'process data -- {0}'.format(dictKeyData['Process Details']))
    try:
        listKeyDict = dictKeyData['Process Details']
        for each_process in listKeyDict:
            pHId = getHashID(each_process['COMMANDLINE'])
            if pHId in ACTIVE_PROCESS_DICT.keys():
                temp_dict = {}
                if dictConfig and 'Processes' in dictConfig and each_process['COMMANDLINE'] in dictConfig['Processes']:
                    temp_dict['id'] = dictConfig['Processes'][each_process['COMMANDLINE']]
                else:
                    temp_dict['id'] = "None"
                temp_dict['user'] = each_process['USER']
                temp_dict['priority'] = each_process['PRIORITY']
                temp_dict['uptime'] = each_process['UPTIME']
                if each_process['AVAILABILITY'] == 1:
                    temp_dict['status'] = 1
                    temp_dict['args'] = each_process['COMMANDLINE']
                    temp_dict['name'] = each_process['PROCESS_NAME']
                    temp_dict['path'] = each_process['EXEUTABLE_PATH']
                    #temp_dict['PID'] = each_process['PROCESS_ID']
                    #temp_dict['PS_CPU_UTILIZATION'] = each_process['PS_CPU_UTILIZATION']
                    temp_dict['cpu'] = round(AgentUtil.custom_float(each_process['CPU_UTILIZATION']),1)
                    #temp_dict['PS_MEMORY_UTILIZATION'] = each_process['PS_MEMORY_UTILIZATION']
                    temp_dict['memory'] = round(AgentUtil.custom_float(each_process['MEMORY_UTILIZATION']),1)
                    temp_dict['thread'] = each_process['THREAD_COUNT']
                    temp_dict['handle'] = each_process['HANDLE_COUNT']
                    temp_dict['instance'] = 1
                else:
                    temp_dict['status'] = 0
                    temp_dict['instance'] = 1
                    temp_dict['args'] = each_process['COMMANDLINE']
                if ((pHId in dictProcessData) and (each_process['AVAILABILITY'] == 1)):
                    temp_dict['cpu'] = round(float(temp_dict['cpu']) + float(dictProcessData[pHId]['cpu']),1)
                    temp_dict['memory'] = round(float(temp_dict['memory']) + float(dictProcessData[pHId]['memory']),1)
                    temp_dict['instance'] = 1 + dictProcessData[pHId]['instance']
                    dictProcessData[pHId] = temp_dict
                    AgentLogger.log(AgentLogger.COLLECTOR," PHID for up process: " + str(each_process['COMMANDLINE']) + " already exists as : " + str(dictProcessData[pHId])) 
                elif pHId in dictProcessData:
                    temp_dict['instance'] = 1 + dictProcessData[pHId]['instance']
                    dictProcessData[pHId] = temp_dict
                    AgentLogger.log(AgentLogger.COLLECTOR," PHID for down process : " + str(each_process['COMMANDLINE']) + " already exists as : " + str(dictProcessData[pHId]))
                else:
                    AgentLogger.log(AgentLogger.COLLECTOR," PHID for : " + str(each_process['COMMANDLINE']) + " is new and process data added now") 
                    dictProcessData.setdefault(pHId,temp_dict)
            else:
                AgentLogger.log(AgentLogger.COLLECTOR,"Process Command line does not match args of any process under monitor" + str(each_process['COMMANDLINE']) + " with HID : " +str(pHId))
        #findDownProcesses(dictProcessData)
        AgentLogger.debug(AgentLogger.COLLECTOR,'process data finale -- {0}'.format(dictProcessData))
        listProcesses = convertProcessDict(dictProcessData)
        dictData.setdefault('process',listProcesses)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for process node *********************************')
        traceback.print_exc()
        
def getSystemData(dictData,dictKeyData,dictConfig):
    outputDict = {}
    cpuCoreInfo = []
    try:
        if 'System Stats' in dictKeyData:
            dictData['systemstats']['1min'] = dictKeyData['System Stats'][0]['Last 1 min Avg']
            dictData['systemstats']['5min'] = dictKeyData['System Stats'][0]['Last 5 min Avg']
            dictData['systemstats']['15min'] = dictKeyData['System Stats'][0]['Last 15 min Avg']
            if dictKeyData['System Stats'][0]['Process Count']:
                counts=dictKeyData['System Stats'][0]['Process Count'].split('/')
                dictData['systemstats']['cr'] = counts[0]#cr - currently running
                dictData['systemstats']['totp'] = counts[1]#totp - total process in the system
            
            if AgentConstants.OS_NAME == AgentConstants.LINUX_OS and dictKeyData['System Stats'][0]['TotalProcessCount']:
                process_count = dictKeyData['System Stats'][0]['TotalProcessCount']
                dictData['systemstats']['totp'] = int(process_count)-1     # to minus the top line from word count command
            if AgentUtil.is_module_enabled(AgentConstants.NORMALIZED_LOAD_AVG):
                dictData['systemstats']['1min'] = float(dictData['systemstats']['1min']) / AgentConstants.NO_OF_CPU_CORES
                dictData['systemstats']['5min'] = float(dictData['systemstats']['5min'])  / AgentConstants.NO_OF_CPU_CORES
                dictData['systemstats']['15min'] = float(dictData['systemstats']['15min']) / AgentConstants.NO_OF_CPU_CORES
            dictData['systemstats']['opc'] = dictKeyData['System Stats'][0]['ListeningSocketCount']
        if 'System Uptime' in dictKeyData:
            no_of_cores = dictData['asset']['core']
            up_time=dictKeyData['System Uptime'][0]['Utime']
            idle_time=dictKeyData['System Uptime'][0]['IdleTime']
            idle_time = float(idle_time) / int(no_of_cores)
            busy_time=float(up_time)-float(idle_time)
            dictData['systemstats']['bt'] = busy_time
            dictData['systemstats']['it'] = idle_time
        time_in_sec = AgentUtil.getUptimeInChar()
        dictData['systemstats']['uttsec'] = str(time_in_sec)
        dictData['systemstats']['utt'] = AgentUtil.timeConversion(time_in_sec * 1000) if time_in_sec != '0' else time_in_sec
        if 'Process Queue' in dictKeyData:
            dictData['systemstats']['prun'] = dictKeyData['Process Queue'][0]['Procs Running']
            dictData['systemstats']['pblck'] = dictKeyData['Process Queue'][0]['Procs Blocked']
        if AgentConstants.PSUTIL_OBJECT:
            dictData['systemstats']['lc'] = len(AgentConstants.PSUTIL_OBJECT.users())
        if 'Login Count' in dictKeyData:
            if dictKeyData['Login Count']:
                str_loginCount = dictKeyData['Login Count'][0]['Login Count']
                dictData['systemstats']['lc'] = str_loginCount.strip().split(" ")[0]
    except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for System Stats node*********************************')
            traceback.print_exc()

def convertProcessDict(dictProcessData):
    defPercent = 0
    listProcesses = []
    try:
        VISITED_KEYS = []
        if dictProcessData:
            for (key,eachProcDict) in dictProcessData.items():
                if ((eachProcDict['instance'] > 1) and (eachProcDict['status'] == 1)):
                    try:
                        eachProcDict['cpu'] = round(float(eachProcDict['cpu'])/int(eachProcDict['instance']),1)
                    except ZeroDivisionError as e:
                        eachProcDict['cpu'] = defPercent
                    try:
                        eachProcDict['memory'] = round(float(eachProcDict['memory'])/int(eachProcDict['instance']),1)
                    except ZeroDivisionError as e:
                        eachProcDict['memory'] = defPercent
                    AgentLogger.log(AgentLogger.COLLECTOR," Average Cpu util and Mem util found for the process with commandline : " + eachProcDict['args'] + " with values as : " + str(eachProcDict['cpu']) + " and " + str(eachProcDict['memory']))
                else:
                    AgentLogger.log(AgentLogger.COLLECTOR,"INSTANCE COUNT IS 1 or down process for : "  + str(eachProcDict['args']))
                VISITED_KEYS.append(key)
                listProcesses.append(eachProcDict)
        KEY_DIFF = list(set(ACTIVE_PROCESS_DICT.keys())-set(VISITED_KEYS))
        for each_key in KEY_DIFF:
            tempDict = {}
            #tempID = None
            if ((each_key in ACTIVE_PROCESS_DICT) and ('id' in ACTIVE_PROCESS_DICT[each_key])):
                tempID = ACTIVE_PROCESS_DICT[each_key]['id']
            else:
                tempID = "None"
            if ((each_key in ACTIVE_PROCESS_DICT) and ('pn' in ACTIVE_PROCESS_DICT[each_key])):
                tempPN = ACTIVE_PROCESS_DICT[each_key]['pn']
            else:
                tempPN = "None"
            if ((each_key in ACTIVE_PROCESS_DICT) and ('pth' in ACTIVE_PROCESS_DICT[each_key])):
                tempPath = ACTIVE_PROCESS_DICT[each_key]['pth']
            else:
                tempPath = "None"
            if ((each_key in ACTIVE_PROCESS_DICT) and ('args' in ACTIVE_PROCESS_DICT[each_key])):
                tempArgs = ACTIVE_PROCESS_DICT[each_key]['args']
                AgentLogger.log(AgentLogger.COLLECTOR," Suspected down process info for " + str(tempArgs))
            else:
                tempArgs = "None"
            tempDict['args'] = tempArgs
            tempDict['id'] = tempID
            tempDict['name'] = tempPN
            tempDict['path'] = tempPath
            if tempArgs != "None":
                AgentLogger.log(AgentLogger.COLLECTOR,"Additional check for suspected down process: " + str(tempPN))
                str_command = AgentConstants.PROCESS_STATUS_COMMAND + " \"" + tempArgs.strip() + "\" | wc -l"
                isSuccess, str_output = AgentUtil.executeCommand(str_command)
                AgentLogger.log(AgentLogger.COLLECTOR," Printing output from additional check command " + str_command + " : " + str_output)
                if isSuccess:
                    try:
                        if int(str_output) > 0:
                            tempDict['status'] = 1
                        else:
                            tempDict['status'] = 0
                    except Exception as e:
                        tempDict['status'] = 0
            else:
                tempDict['status'] = 0
            listProcesses.append(tempDict)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while converting process dict to list for process node *********************************')
        traceback.print_exc()
    finally:
        return listProcesses

def processReCheck(processDict):
    returnDict = {}
    str_args = str(processDict['args'])
    str_args = str_args.translate(str_args.maketrans({"]": r"\]","[":r"\[","*":r"\*"}))
    AgentLogger.debug(AgentLogger.CHECKS,"Retry Check for suspected down process : " + str(processDict['pn']) + " with args : " + str_args)
    str_command = AgentConstants.PROCESS_STATUS_COMMAND + " \"" + str_args.strip() + "\" | wc -l"
    AgentLogger.debug(AgentLogger.CHECKS,"Process Retry command : "+ str_command)
    executorObj = AgentUtil.Executor()
    executorObj.setLogger(AgentLogger.CHECKS)
    executorObj.setTimeout(7)
    executorObj.setCommand(str_command)
    executorObj.executeCommand()
    str_output = str(executorObj.getStdOut())
    isSuccess = executorObj.isSuccess()            
    AgentLogger.debug(AgentLogger.CHECKS,"Output of Process Retry command : " + str_output)
    if isSuccess:
        try:
            if 'pid' in processDict:
                returnDict['pid']=processDict['pid']
            if int(str_output) > 0:
                returnDict['status'] = 1
                returnDict['args'] = processDict['args']
                returnDict['id']=processDict['id']
            else:
                returnDict['status'] = 0
                returnDict['args'] = processDict['args']
                returnDict['id']=processDict['id']
        except Exception as e:
            AgentLogger.log(AgentLogger.CHECKS,"Exception Occured in process ReCheck ")
            traceback.print_exc()
    AgentLogger.debug(AgentLogger.CHECKS,"Final Recheck Output : " + str(returnDict))
    return returnDict


def parse_ebpf_process(data_dir, parsed_dict):
    try:
        dir_path = AgentConstants.EBPF_PROCESS_DATA_DIR+"/"+data_dir
        for each_file in os.listdir(dir_path):
            file_path = dir_path+"/"+each_file
            with open(file_path, 'r') as file:
                process_data = file.readlines()
            process_list = [process.strip() for process in process_data]
            for each_process in process_list:
                try:
                    process_data = each_process.split("|")
                    parsed_dict[process_data[0]] = {
                        "tx":  process_data[2],
                        "rx":  process_data[3],
                        "rt":  process_data[4]
                    }
                except Exception as e:
                    traceback.format_exc()
    except Exception as e:
        AgentLogger.log(AgentLogger.CHECKS,"*** Exception while parsing ebpf process data **** :: {}".format(traceback.format_exc()))

def fetch_ebpf_process_data():
    parsed_dict = {}
    try:
        current_time = time.time()
        ebpf_process_data_dir = sorted([data for data in os.listdir(AgentConstants.EBPF_PROCESS_DATA_DIR) if os.path.isdir(os.path.join(AgentConstants.EBPF_PROCESS_DATA_DIR, data))])
        if ebpf_process_data_dir:
            latest_polled_time = ebpf_process_data_dir[-1]
            if abs(int(current_time) - int(latest_polled_time)) <= 60:
                parse_ebpf_process(latest_polled_time, parsed_dict)
            for each_dir in ebpf_process_data_dir:
                shutil.rmtree(AgentConstants.EBPF_PROCESS_DATA_DIR+"/"+each_dir)
        AgentLogger.log(AgentLogger.CHECKS,"ebpf process data collected :: {}".format(parsed_dict))
    except Exception as e:
        AgentLogger.log(AgentLogger.CHECKS,"*** Exception while fetching process data from ebpf *** :: {}".format(traceback.format_exc()))
    finally:
        return parsed_dict


def addDownProcCheck(listProcessNames):
    bool_toUpdate = False
    for each_key in ACTIVE_PROCESS_DICT.keys():
        if ACTIVE_PROCESS_DICT[each_key]['pn'] in listProcessNames:
            str_args = str(ACTIVE_PROCESS_DICT[each_key]['args'])
            AgentLogger.log(AgentLogger.COLLECTOR,"Additional check for suspected down process : " + str(ACTIVE_PROCESS_DICT[each_key]['pn']) + " with args : " + str_args)
            str_command = AgentConstants.PROCESS_STATUS_COMMAND + " \"" + str_args.strip() + "\" | wc -l"
            #isSuccess, str_output = AgentUtil.executeCommand(str_command)
            AgentLogger.log(AgentLogger.COLLECTOR,"TEST_PROCESS_DOWN_COMMAND : "+ str_command)
            executorObj = AgentUtil.Executor()
            executorObj.setLogger(AgentLogger.COLLECTOR)
            executorObj.setTimeout(7)
            executorObj.setCommand(str_command)
            #executorObj.redirectToFile(True)
            executorObj.executeCommand()
            str_output = str(executorObj.getStdOut())
            isSuccess = executorObj.isSuccess()            
            AgentLogger.log(AgentLogger.COLLECTOR," Printing output from additional check command : " + str_output)
            if isSuccess:
                try:
                    if int(str_output) > 0:
                        pass
                    else:
                        bool_toUpdate = True
                except Exception as e:
                    bool_toUpdate = True
    AgentLogger.log(AgentLogger.COLLECTOR," Final value of boolean variable toUpdate is : " + str(bool_toUpdate))
    return bool_toUpdate

def agentSelfMetrics():
    try:
        global SELF_MONITOR_DICT
        #agent process
        proc_xml_map = {'Site24x7Agent':'a', 'Site24x7AgentWatchdog':'w', 'Site24x7Applog':'al','Site24x7MetricsAgent':'ma', 'MonitoringAgentWatchdog.py':'w', 'MonitoringAgent.py':'a', 'applog_starter.py':'al', 'metrics_agent.py':'ma'}
        metric_list = ['name','autt','_cpu','_mem','apmem','avmem','atu']
        outer_node = {}
        other_agent_list = []
        monagent_pid = str(os.getpid())

        if AgentConstants.OS_NAME == AgentConstants.OS_X:
            thread_param = 'wq'
        else:
            thread_param = 'nlwp'
        agent_process_cmd = "ps -eo comm,etime,pcpu,pmem,rss,vsz,"+thread_param+",pid,args | grep 'site24x7/monagent/lib' "
        executorObj = AgentUtil.Executor()
        executorObj.setTimeout(30)
        executorObj.setCommand(agent_process_cmd)
        executorObj.executeCommand()
        stdout = executorObj.getStdOut()
        stdout = stdout.strip().splitlines()

        for each_process in stdout:
            temp_dict = {}
            each_process = each_process.split()
            each_process[1] = AgentUtil.process_uptime_in_secs(each_process[1], False) #uptime conversion
            each_process[4] = str(float(each_process[4]) * 1024) #rss to bytes
            each_process[5] = str(float(each_process[5]) * 1024) #vsz to bytes
            handle_count_cmd = "ls /proc/{}/fd/ | wc -l".format(each_process[7])
            executorObj.setCommand(handle_count_cmd)
            executorObj.executeCommand() 
            hc_out = executorObj.getStdOut().strip()
            for value in each_process[::-1]:
                if '/' in value:
                    name = value.split('/')[-1]
                    break
            if each_process[0] not in ['grep', 'sh']:
                try:
                    proc_short_name = proc_xml_map[name]
                except Exception as e:
                    continue
                if each_process[7] == monagent_pid:
                    outer_node['ahc'] = hc_out if hc_out else '-1'
                    for metric, value in zip(metric_list, each_process):
                        if metric in ['_cpu', '_mem']:
                            outer_node[proc_short_name + metric] = value
                        elif metric not in ['name']:
                            outer_node[metric] = value
                else:
                    temp_dict['ahc'] = hc_out
                    for metric, value in zip(metric_list, each_process):
                        if metric in ['_cpu','_mem']:
                            temp_dict[proc_short_name + metric] = value
                            outer_node[proc_short_name + metric] = value
                        elif metric == 'name':
                            temp_dict[metric] = name
                        else:
                            temp_dict[metric] = value

                    other_agent_list.append(temp_dict)
            
        SELF_MONITOR_DICT = outer_node
        SELF_MONITOR_DICT['agent_proc'] = other_agent_list

        #total agent size
        SELF_MONITOR_DICT['ats'] = str(AgentUtil.get_file_size(AgentConstants.AGENT_WORKING_DIR))
        
        # agent upload dir size
        upload_size = AgentUtil.get_file_size(AgentConstants.AGENT_UPLOAD_DIR, depth = 1) 
        SELF_MONITOR_DICT['atus'] = str(upload_size.pop(AgentConstants.AGENT_UPLOAD_DIR.split('/')[-1]))
        SELF_MONITOR_DICT.update(self_monitor_mapper(upload_size, 'u'))
        
        # agent data dir size
        data_size = AgentUtil.get_file_size(AgentConstants.AGENT_DATA_DIR, depth = 1) 
        SELF_MONITOR_DICT['atds'] = str(data_size.pop(AgentConstants.AGENT_DATA_DIR.split('/')[-1]))
        SELF_MONITOR_DICT.update(self_monitor_mapper(data_size, 'd'))
        
        # agent temp dir size
        temp_size = AgentUtil.get_file_size(AgentConstants.AGENT_TEMP_DIR, depth = 1)
        temp_size = AgentUtil.convert_int_to_string(temp_size)
        SELF_MONITOR_DICT['atts'] = temp_size.pop(AgentConstants.AGENT_TEMP_DIR.split('/')[-1])
        SELF_MONITOR_DICT['u_al'] = temp_size.pop('applog', '0')
        SELF_MONITOR_DICT.update(temp_size)
        
        # agent upload zip count
        SELF_MONITOR_DICT.update(self_monitor_mapper(key = 'z', zipcounter=True))
        SELF_MONITOR_DICT['z_al'] = AgentUtil.count_dir_file(AgentConstants.AGENT_PLUGINS_DIR, 'dir','gz')
        
        #plugin folder count
        SELF_MONITOR_DICT['apfc'] = AgentUtil.count_dir_file(AgentConstants.AGENT_PLUGINS_DIR, 'dir')
        
        #metrics agent size
        SELF_MONITOR_DICT['mtds'] = str(AgentUtil.get_file_size(AgentConstants.METRIC_DATA_DIRECTORY))
        SELF_MONITOR_DICT['mtus'] = str(AgentUtil.get_file_size(AgentConstants.METRICS_DATA_ZIP_DIRECTORY))

        AgentLogger.log(AgentLogger.COLLECTOR, 'AGENT SELF METRICS COLLECTED\n')
        
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while collecting agent self metrics *********************************')
        traceback.print_exc()

def self_monitor_mapper(src_dict={}, key='', zipcounter = False):
    return_dict = {}
    dict_key = ''
    total_zips = 0
    try:
        if not zipcounter:
            for code, value in AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER.items():
                dict_key = ''.join([key, '_', value['category']])
                if code in src_dict:
                    return_dict[dict_key] = return_dict.get(dict_key,0) + src_dict[code]
                elif dict_key not in return_dict and value['category']:
                    return_dict[dict_key] = 0
        else: 
            for each_code in AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER.values():
                if each_code['category']:
                    total_zips = total_zips + each_code['zips_in_buffer']
                    dict_key = ''.join([key, '_', each_code['category']])
                    return_dict[dict_key] = return_dict.get(dict_key,0) + each_code['zips_in_buffer']
            return_dict['azuc'] = total_zips

        return_dict = AgentUtil.convert_int_to_string(return_dict)
    except:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while mapping agent self metrics *********************************')
        traceback.print_exc()
    finally:
        return return_dict
    
class ConsolidatorCollector():
    dictData = None
    def __init__(self):
        self.dictData = {}
        self.setDefaultValues(self.dictData)
        self.setResourceValues(self.dictData,CONFIG_OBJECTS)
    def setDefaultValues(self,dictData):
        try:
            self.dictData.setdefault('avail', 1)
            self.dictData.setdefault('reason', "Server up")
            ctime = str(AgentUtil.getTimeInMillis())
            self.dictData.setdefault('dc' , ctime)
            self.dictData.setdefault('asset',{})
            self.dictData.setdefault('TOPCPUPROCESS',{})
            self.dictData.setdefault('TOPMEMORYPROCESS',{})
            self.dictData.setdefault('systemstats',{})
            self.dictData.setdefault('memorystats',{})
            self.dictData.setdefault('networkstats',{})
            self.dictData['asset'].setdefault('hostname', AgentConstants.HOST_NAME)
            self.dictData.setdefault('memory',{})
            ip_from_ifconfig = com.manageengine.monagent.discovery.HostHandler.get_ip_address()
            if ip_from_ifconfig and ip_from_ifconfig!= "127.0.0.1" and ip_from_ifconfig != AgentConstants.IP_ADDRESS:
                AgentLogger.log(AgentLogger.STDOUT,'ip address mismatch in-memory value :: {} | ifconfig command :: {}'.format(AgentConstants.IP_ADDRESS,ip_from_ifconfig))
                AgentConstants.IP_ADDRESS = ip_from_ifconfig
            self.dictData['asset'].setdefault('pri_ip', AgentConstants.IP_ADDRESS)
            if SELF_MONITOR_DICT:
                AgentLogger.log(AgentLogger.COLLECTOR, 'Agent self metrics added to FC\n')
                self.dictData.setdefault('agent', copy.deepcopy(SELF_MONITOR_DICT))
                SELF_MONITOR_DICT.clear()
            
        except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting default consolidated values *********************************')
            traceback.print_exc()
    def setResourceValues(self,dictData,dictConfig):
        listURLs = []
        listPorts = []
        listFiles = []
        listScripts = []
        listNFS = []
        listNTP = []
        listSysLogs = []
        dictURLData = None
        dictPortData = None
        dictFileData = None
        dictScriptData = None
        dictNFSData = None
        dictNTPData = None
        dictSysLogData = None
        try:
            with BasicClientHandler.globalDClock:
                if 'url' in BasicClientHandler.CHECKS_DATA:
                    dictURLData = BasicClientHandler.CHECKS_DATA['url']
                if 'port' in BasicClientHandler.CHECKS_DATA:
                    dictPortData = BasicClientHandler.CHECKS_DATA['port']
                if 'file' in BasicClientHandler.CHECKS_DATA:
                    dictFileData = BasicClientHandler.CHECKS_DATA['file']
                if 'logrule' in BasicClientHandler.CHECKS_DATA:
                    dictSysLogData = BasicClientHandler.CHECKS_DATA['logrule']
                if 'script' in BasicClientHandler.CHECKS_DATA:
                    dictScriptData = BasicClientHandler.CHECKS_DATA['script']
                if 'nfs' in BasicClientHandler.CHECKS_DATA:
                    dictNFSData = BasicClientHandler.CHECKS_DATA['nfs']
                if 'ntp' in BasicClientHandler.CHECKS_DATA:
                    dictNTPData = BasicClientHandler.CHECKS_DATA['ntp']
            if dictURLData:
                for each_check_id in dictURLData:
                    temp_dict = {}
                    temp_dict = dict(dictURLData[each_check_id])
                    if ((dictConfig) and ('URL' in dictConfig) and (str(each_check_id) in dictConfig['URL'])):
                        temp_dict['id'] = dictConfig['URL'][str(each_check_id)]
                    else:
                        temp_dict['id'] = "None"
                    listURLs.append(temp_dict)
            self.dictData.setdefault('url',listURLs)
            if dictPortData:
                for each_check_id in dictPortData:
                    temp_dict = {}
                    temp_dict = dict(dictPortData[each_check_id])
                    if ((dictConfig) and ('PORT' in dictConfig) and (str(each_check_id) in dictConfig['PORT'])):
                        temp_dict['id'] = dictConfig['PORT'][str(each_check_id)]
                    else:
                        temp_dict['id'] = "None"
                    listPorts.append(temp_dict)
            self.dictData.setdefault('port',listPorts)
            if dictFileData:
                for each_check_id in dictFileData:
                    temp_dict_file = {}
                    temp_dict_file = dict(dictFileData[each_check_id])
                    if (dictConfig and ('FILE' in dictConfig) and (str(each_check_id) in dictConfig['FILE'])):
                        temp_dict_file['id'] = dictConfig['FILE'][str(each_check_id)]
                    else:
                        temp_dict_file['id'] = "None"
                    listFiles.append(temp_dict_file)
            self.dictData.setdefault('file',listFiles)
            if dictScriptData:
                for each_check_id in dictScriptData:
                    temp_dict = {}
                    temp_dict = dict(dictScriptData[each_check_id])
                    if ((dictConfig) and ('SCRIPT' in dictConfig) and (str(each_check_id) in dictConfig['SCRIPT'])):
                        temp_dict['id'] = dictConfig['SCRIPT'][str(each_check_id)]
                    else:
                        temp_dict['id'] = "None"
                    listScripts.append(temp_dict)
            self.dictData.setdefault('script',listScripts)
            if dictNFSData:
                for each_check_id in dictNFSData:
                    temp_dict = {}
                    temp_dict = dict(dictNFSData[each_check_id])
                    if ((dictConfig) and ('NFS' in dictConfig) and (str(each_check_id) in dictConfig['NFS'])):
                        temp_dict['id'] = dictConfig['NFS'][str(each_check_id)]
                    else:
                        temp_dict['id'] = "None"
                    listNFS.append(temp_dict)
            self.dictData.setdefault('nfs',listNFS)
            if dictNTPData:
                for each_check_id in dictNTPData:
                    temp_dict = {}
                    temp_dict = dict(dictNTPData[each_check_id])
                    if ((dictConfig) and ('NTP' in dictConfig) and (str(each_check_id) in dictConfig['NTP'])):
                        temp_dict['id'] = dictConfig['NTP'][str(each_check_id)]
                    else:
                        temp_dict['id'] = "None"
                    listNTP.append(temp_dict)
            self.dictData.setdefault('ntp',listNTP)
            if dictSysLogData:
                for each_log in dictSysLogData:
                    temp_dict_syslog = {}
                    temp_dict_syslog = dictSysLogData[each_log]
                    listSysLogs.append(temp_dict_syslog)
            self.dictData.setdefault('logrule',listSysLogs)
        except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting default resource values *********************************')
            traceback.print_exc()
    def addAdditionalMetrics(self,dictCollectedData):
        try:
            for each_key in dictCollectedData:
                if 'parseTag' in dictCollectedData[each_key]:
                    AgentLogger.debug(AgentLogger.COLLECTOR,'Found parseTag : ' + str(dictCollectedData[each_key]['parseTag']) + ' in key : ' + str(each_key))
                    parseTag = dictCollectedData[each_key]['parseTag']
                    parseTags = parseTag.split(',')
                    for each_tag in parseTags:
                        task = PARSE_IMPL[each_tag]
                        # send CONFIG_OBJECTS globally is refrenced as address, and keep on adding dict [ copy() just copy one layer] [ deepcopy() copies entire dict tree ]
                        task(self.dictData, dictCollectedData[each_key], copy.deepcopy(CONFIG_OBJECTS))
            return self.dictData
        except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while adding metrics in consolidated data *********************************')
            traceback.print_exc()
    
class DataHandler():
    def __init__(self):
        pass
    def createUploadData(self,dictCollectedData):
        dictData = {}
        try:
            collector = ConsolidatorCollector()
            dictData = collector.addAdditionalMetrics(dictCollectedData)
            top_process_data = copy.deepcopy(AgentConstants.PS_UTIL_PROCESS_DICT)
            if top_process_data:
                dictData['TOPMEMORYPROCESS'] = top_process_data['TOPMEMORYPROCESS']
                dictData['TOPCPUPROCESS'] = top_process_data['TOPCPUPROCESS']
                dictData['fd'] = top_process_data['fd'] #file descriptor of total processes
                AgentConstants.PS_UTIL_PROCESS_DICT = {}
        except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while creating consolidated data *********************************')
            traceback.print_exc()
        finally:
            return dictData
