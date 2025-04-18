#$Id$


import json
import traceback
import os
import time
try:
    import psutil
except Exception as e:
    pass
import threading
from six.moves.urllib.parse import urlencode
import com
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.collector import DataConsolidator

REAL_TIME_MONITOR_THREAD = None
REAL_TIME_DATA_INTERVAL = 10

def initiate_real_time_monitoring(dict_task):
    global REAL_TIME_MONITOR_THREAD
    try:
        AgentLogger.log(AgentLogger.CHECKS,'real time monitoring configuration -- {0}'.format(json.dumps(dict_task)))
        if REAL_TIME_MONITOR_THREAD == None:
            init_rtm_thread(dict_task)
        else:
            AgentLogger.log(AgentLogger.CHECKS,'real time already in progress')
            AgentLogger.log(AgentLogger.CHECKS,'stopping real time monitoring ')
            REAL_TIME_MONITOR_THREAD.stop()
            time.sleep(10)
            init_rtm_thread(dict_task)
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.CHECKS,'exception while fetching real time attribute')
        
def init_rtm_thread(dict_task):
    global REAL_TIME_MONITOR_THREAD
    try:
        REAL_TIME_MONITOR_THREAD = RealTimeMonitor(dict_task)
        REAL_TIME_MONITOR_THREAD.setDaemon(True)
        REAL_TIME_MONITOR_THREAD.activate()
        REAL_TIME_MONITOR_THREAD.start()
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.CHECKS,'exception while fetching real time attribute')    

def stop_real_time_monitoring():
    global REAL_TIME_MONITOR_THREAD
    if REAL_TIME_MONITOR_THREAD is not None:
        AgentLogger.log(AgentLogger.CHECKS,'stopping the real time monitoring ')
        REAL_TIME_MONITOR_THREAD.stop()
        REAL_TIME_MONITOR_THREAD=None
    
def doRealTimeMonitoring(attribute):
    try:
        if attribute == "process":
            stop_real_time_monitoring()
        if attribute == "server":
            do_server_cpu_mem_monitoring(attribute)
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.CHECKS,'exception while fetching real time attribute')

def do_server_cpu_mem_monitoring(attribute):
    try:
        import psutil
        dict_to_return={}
        for x in range (REAL_TIME_DATA_INTERVAL):
            cpu_mem_dict=[]
            memory = psutil.virtual_memory().percent
            cpu = psutil.cpu_percent(interval=1)
            cpu_mem_dict.append(cpu)
            cpu_mem_dict.append(memory)
            dict_to_return[AgentUtil.getTimeInMillis()]=cpu_mem_dict
        send_real_time_data(dict_to_return,attribute)
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.CHECKS,'exception while fetching real time attribute in server cpu and memory')

def do_process_monitoring(attribute):
    try:
        dictToReturn = {}
        process_data = None
        pid_dict = {}
        AgentLogger.log(AgentLogger.CHECKS, 'process data -- {0}'.format(DataConsolidator.ACTIVE_PROCESS_DICT))
        if DataConsolidator.ACTIVE_PROCESS_DICT:
            for x in range (REAL_TIME_DATA_INTERVAL):
                ct = AgentUtil.getTimeInMillis()
                for key,value in DataConsolidator.ACTIVE_PROCESS_DICT.items():
                     innerDict = {}
                     innerList =[]
                     process_details = value
                     AgentLogger.log(AgentLogger.CHECKS, 'process value -- {0}'.format(value))
                     if 'pid' in process_details:
                         process_monitoring_pid = process_details['pid']
                         AgentLogger.log(AgentLogger.CHECKS, 'process monitoring pid -- {0}{1}'.format(process_monitoring_pid,int(process_monitoring_pid)))
                         if process_monitoring_pid not in pid_dict:
                             process_data = psutil.Process(pid = int(process_monitoring_pid))
                             pid_dict[process_monitoring_pid]=process_data
                             process_obj = process_data
                             cpu = process_obj.cpu_percent()
                         else:
                             process_obj = pid_dict[process_monitoring_pid]
                         cpu1  = process_obj.cpu_percent()
                         AgentLogger.log(AgentLogger.CHECKS, 'process monitoring cpu -- {0}{1}'.format(cpu,cpu1))
                         mem  = process_obj.memory_percent()
                         process_data = []
                         process_data.append(process_obj.name()+"_"+process_monitoring_pid)
                         process_data.append(cpu1)
                         process_data.append(mem)
                         if ct not in dictToReturn:
                             dictToReturn[ct]=[process_data]
                         else:
                            dictToReturn[ct].append(process_data)
                     else:
                        AgentLogger.log(AgentLogger.CHECKS, 'no process id found')
                if x < (REAL_TIME_DATA_INTERVAL-1):
                    time.sleep(1)
            #AgentLogger.log(AgentLogger.CHECKS, 'process monitoring  -- {0}'.format(json.dumps(dictToReturn)))
            send_real_time_data(dictToReturn,attribute)
        else:
            AgentLogger.log(AgentLogger.CHECKS, 'process monitoring not configured  -- {0}'.format(DataConsolidator.ACTIVE_PROCESS_DICT))
            REAL_TIME_MONITOR_THREAD.stop()
            AgentLogger.log(AgentLogger.CHECKS,'stopping the real time schedule ')
    except Exception as e:
        traceback.print_exc()
        time.sleep(10)
        
        
def send_real_time_data(dictToReturn,action_type=None):
    dict_requestParameters = {}
    requestInfo = com.manageengine.monagent.communication.CommunicationHandler.RequestInfo()
    try:
        dict_requestParameters['agentKey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        dict_requestParameters['custID'] = AgentConstants.CUSTOMER_ID
        dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
        if action_type:
            dict_requestParameters['actionType']=action_type
        AgentLogger.log(AgentLogger.CHECKS, ' uploading real time data =======> {0}'.format(json.dumps(dictToReturn)))
        str_servlet = AgentConstants.REAL_TIME_MONITORING_SERVLET
        if not dict_requestParameters == None:
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
        str_dataToSend = json.dumps(dictToReturn)
        str_contentType = 'application/json'
        requestInfo.set_loggerName(AgentLogger.CHECKS)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.set_data(str_dataToSend)
        requestInfo.set_dataType(str_contentType)
        requestInfo.add_header("Content-Type", str_contentType)
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = com.manageengine.monagent.communication.CommunicationHandler.sendRequest(requestInfo)
    except Exception as e:
        AgentLogger.log([AgentLogger.PLUGINS, AgentLogger.STDERR], ' *************************** Exception while registering Plugin to Server *************************** ' + repr(e))
        traceback.print_exc()
        
class RealTimeMonitor(threading.Thread):
    def __init__(self,dict_task):
        threading.Thread.__init__(self)
        AgentLogger.log(AgentLogger.CHECKS,'real time thread initializer')
        self.name = 'Real Time Monitor'
        self.__kill = False
        self.__dict = dict_task
    
    def stop(self):
        self.__kill = True
        
    def activate(self):
        self.__kill = False
        
    def getThreadStatus(self):
        return self.__kill
        
    def run(self):
        while not self.__kill:
            try:
                #AgentLogger.log(AgentLogger.CHECKS,'dict data -- {0}'.format(self.__dict))
                doRealTimeMonitoring(self.__dict['attribute'])
            except Exception as e:
                traceback.print_exc()
        else:
            pass
            # AgentLogger.log(AgentLogger.CHECKS,'thread status ---->'+repr(self.__kill))