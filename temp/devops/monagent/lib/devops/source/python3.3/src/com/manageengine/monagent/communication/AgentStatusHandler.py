 # $Id$
import traceback
import threading
import platform
import com
import ssl
from six.moves.urllib.parse import urlencode
import time, os, re, json
from datetime import datetime
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil
from com.manageengine.monagent.util.rca.RcaHandler import RcaUtil, RcaInfo
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.util import DesignUtils
from com.manageengine.monagent.util import AgentBuffer

STATUS_THREAD = None
WMS_THREAD = None
WMS_INTERVAL = -1
HEART_BEAT_THREAD = None
STATUS_UTIL = None
TRACE_THREAD = None
LAST_TRACE_ROUTE_TIME = None
CLEAR_TRACE_ROUTE_REPORT = False
STATUS_UPDATE_SERVER_LIST = []

def initialize():
    global STATUS_THREAD, HEART_BEAT_THREAD, WMS_THREAD, TRACE_THREAD, CLEAR_TRACE_ROUTE_REPORT, STATUS_UPDATE_SERVER_LIST
    bool_toReturn = True
    try:
        STATUS_THREAD = StatusThread()
        STATUS_THREAD.setDaemon(True)
        STATUS_THREAD.start()
        (bool_status, list_dict) = AgentUtil.loadDataFromFile(AgentConstants.AGENT_STATUS_UPDATE_SERVER_LIST_FILE)
        if bool_status:
            STATUS_UPDATE_SERVER_LIST = list_dict['servers_list']
        if STATUS_UPDATE_SERVER_LIST:
            AgentLogger.log(AgentLogger.MAIN, 'Servers List for Status Update : ' + repr(STATUS_UPDATE_SERVER_LIST) + '\n')
    except Exception as e:
        AgentLogger.log([AgentLogger.CRITICAL, AgentLogger.STDERR], '*************************** Exception while initialising AgentStatusHandler  *************************** ' + repr(e))
        traceback.print_exc()
        bool_toReturn = False
    return bool_toReturn

def init_wms_thread():
    global WMS_THREAD
    try:
        WMS_THREAD = WMSThread()
        WMS_THREAD.setDaemon(True)
        WMS_THREAD.start()
    except Exception as e:
        traceback.print_exc()

def setStatusUpdateInterval(dict_task):
    try:  
        str_statusUpdateInterval = dict_task['INTERVAL']
        str_statusUpdateInterval = int(str_statusUpdateInterval) * 60
        AgentConstants.STATUS_UPDATE_INTERVAL = str_statusUpdateInterval
        AgentUtil.persistAgentInfo()
    except Exception as e:
        AgentLogger.log([AgentLogger.MAIN, AgentLogger.CRITICAL], '*************************** Exception while changing status update interval  *************************** ' + repr(e))
        traceback.print_exc()

def setRealTimeUpdateInterval():
    try:  
        str_statusUpdateInterval = 5
        AgentConstants.STATUS_UPDATE_INTERVAL = str_statusUpdateInterval
        AgentUtil.persistAgentInfo()
    except Exception as e:
        AgentLogger.log([AgentLogger.MAIN, AgentLogger.CRITICAL], '*************************** Exception while changing real time messaging update interval  *************************** ' + repr(e))
        traceback.print_exc()
        
def notifyShutdown(notifyShutdownTime=None):
    try:
        AgentLogger.log(AgentLogger.MAIN, 'Notifying Agent Shut down : \n')
        str_url = None
        str_servlet = AgentConstants.AGENT_STATUS_UPDATE_SERVLET
        if notifyShutdownTime==None:
            float_shutDownTime = AgentUtil.getCurrentTimeInMillis()
        else:
            float_shutDownTime = notifyShutdownTime
        if HEART_BEAT_THREAD:
            HEART_BEAT_THREAD.stop()
            #float_shutDownTime = HEART_BEAT_THREAD.getLastHeartBeatTime()
            #AgentLogger.log(AgentLogger.MAIN, 'HEART_BEAT_THREAD is initialised hence assigning Shutdown time  = LastHeartBeatTime : ' + repr(float_shutDownTime) + '\n')
        else:
            #AgentLogger.log(AgentLogger.MAIN, 'HEART_BEAT_THREAD is not initialised hence updating HeartBeat with the current time : ' + repr(float_shutDownTime) + '\n')
            HeartBeatThread.updateHeartBeat(float_shutDownTime)
        AgentLogger.log(AgentLogger.MAIN, 'Agent Shut down time : ' + repr(AgentUtil.getFormattedTime(float_shutDownTime)) + ' --> ' + repr(float_shutDownTime) + '\n')
        AgentLogger.log(AgentLogger.MAIN, 'Agent Shut down time - diff based : ' + repr(AgentUtil.getFormattedTime(AgentUtil.getTimeInMillis(float_shutDownTime))) + ' --> ' + repr(AgentUtil.getTimeInMillis(float_shutDownTime)) + '\n')
        dict_requestParameters = {
        'agentStatus'   :   AgentConstants.AGENT_DOWN,
        'bno'  :  AgentConstants.AGENT_VERSION,
        'agentKey'  :   AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),
        'serviceName'   :   AgentConstants.AGENT_NAME,
        'AGENTUNIQUEID':    AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_unique_id'),
        'timeStamp' : str(AgentUtil.getTimeInMillis(float_shutDownTime))
        }
        AgentLogger.log(AgentLogger.MAIN,'shut down notification parameters -- {0}'.format(json.dumps(dict_requestParameters))+'\n')
        dict_requestParameters['CUSTOMERID'] = AgentConstants.CUSTOMER_ID
        if not dict_requestParameters == None:
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.MAIN)
        requestInfo.set_method(AgentConstants.HTTP_GET)
        requestInfo.set_timeout(AgentConstants.AGENT_SHUTDOWN_NOTIFICATION_TIMEOUT)
        requestInfo.set_url(str_url)
        CommunicationHandler.sendRequest(requestInfo)
    except Exception as e:
        AgentLogger.log([AgentLogger.MAIN, AgentLogger.CRITICAL], ' ************************* Exception while notifying agent shutdown ************************* ' + repr(e))
        traceback.print_exc()

def updateServerList(dict_list):
    global STATUS_UPDATE_SERVER_LIST
    dict_servers = {}
    AgentLogger.log(AgentLogger.MAIN, 'DATA RECEIVED FROM SERVER : ' + repr(dict_list))
    fileObj = AgentUtil.FileObject()
    fileObj.set_filePath(AgentConstants.AGENT_STATUS_UPDATE_SERVER_LIST_FILE)
    fileObj.set_dataType('json')
    fileObj.set_mode('rb')
    fileObj.set_dataEncoding('UTF-8')
    fileObj.set_loggerName(AgentLogger.MAIN)
    fileObj.set_logging(False)
    bool_toReturn, dict_monitorsInfo = FileUtil.readData(fileObj)
    dict_monitorsInfo['servers_list'] = dict_list
    fileObj.set_data(dict_monitorsInfo)
    fileObj.set_mode('wb')
    bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
    if bool_toReturn:
        AgentLogger.log(AgentLogger.MAIN, 'File updated successfully. ' + repr(str_filePath))
    else:
        AgentLogger.log(AgentLogger.MAIN, 'File update failed. ' + repr(str_filePath))
    STATUS_UPDATE_SERVER_LIST = dict_list
        
class AgentStatusUtil(DesignUtils.Singleton):
    isUptimeParsed = False
    def __init__(self):
        self.__updateBootStatus()
        
    @classmethod
    def getLastUptime(cls):
        lastUptime = 0
        try:
            isSuccess, str_output = AgentUtil.executeCommand(AgentConstants.PREVIOUS_UPTIME_COMMAND)
            if isSuccess:
                AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : Last uptime command output : ' + repr(str_output))
                if str_output:
                    lastUptime = round(float(re.sub('\s+', '', str_output).strip()))
                AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : Last uptime : ' + repr(lastUptime))
            else:
                AgentLogger.log(AgentLogger.STDOUT, '********************* Unable to get lastUptime *********************')
        except Exception as e:
            AgentLogger.log([AgentLogger.STDERR], '************************* Exception while fetching last uptime ************************* ' + repr(e))
            traceback.print_exc()
        return lastUptime
    
    @staticmethod
    def get_da_host_uptime():
        _status, _uptime = False, "1"
        try:
            _boot_time = round(AgentConstants.DOCKER_PSUTIL.boot_time())
            _current_time = round(time.time())
            _uptime = _current_time - _boot_time
            _status = True
        except Exception as e:
            traceback.print_exc()
        finally:
            return _status, _uptime
        
    @classmethod
    def setMachineBootStatus(cls):
        lastUpTime = 0
        try:
            lastUpTime = cls.getLastUptime()
            isSuccess, str_output = AgentUtil.executeCommand(AgentConstants.UPTIME_COMMAND) if AgentConstants.IS_DOCKER_AGENT == "0" else AgentStatusUtil.get_da_host_uptime()
            if isSuccess:
                if AgentConstants.IS_DOCKER_AGENT == "0":
                    str_uptime = re.sub('\s+', '', str_output).strip()
                    AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : Uptime command output : ' + repr(str_output) + ' --> ' + repr(str_uptime))
                    AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : Last uptime : ' + repr(lastUpTime))
                    int_upTime = int(float(str_uptime))
                else:
                    int_upTime = int(str_output)
                if int_upTime > AgentConstants.APPROXIMATE_MACHINE_BOOT_TIME:
                    AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : Server uptime is greater than ' + str(AgentConstants.APPROXIMATE_MACHINE_BOOT_TIME / 60) + ' minutes, AGENT_MACHINE_REBOOT = False, setting AGENT_BOOT_STATUS : ' + repr(AgentConstants.AGENT_SERVICE_RESTART_MESSAGE))
                    AgentConstants.AGENT_MACHINE_START_TIME = AgentUtil.getCurrentTimeInMillis() - (int_upTime * 1000) if AgentConstants.IS_DOCKER_AGENT == "0" else round(AgentConstants.DOCKER_PSUTIL.boot_time()*1000)
                    AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_START_TIME = AgentUtil.getTimeInMillis(AgentConstants.AGENT_MACHINE_START_TIME)
                    AgentConstants.AGENT_BOOT_STATUS = AgentConstants.AGENT_SERVICE_RESTART_MESSAGE
                else:
                    AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : Server uptime is less than ' + str(AgentConstants.APPROXIMATE_MACHINE_BOOT_TIME / 60) + ' minutes, AGENT_MACHINE_REBOOT = True, setting AGENT_BOOT_STATUS : ' + repr(AgentConstants.AGENT_MACHINE_RESTART_MESSAGE))
                    if lastUpTime == 0 or (int_upTime < lastUpTime):
                        AgentConstants.AGENT_MACHINE_REBOOT = True
                        AgentConstants.AGENT_MACHINE_START_TIME = AgentUtil.getCurrentTimeInMillis() - (int_upTime * 1000) if AgentConstants.IS_DOCKER_AGENT == "0" else round(AgentConstants.DOCKER_PSUTIL.boot_time()*1000)
                        AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_START_TIME = AgentUtil.getTimeInMillis(AgentConstants.AGENT_MACHINE_START_TIME)
                        if not AgentConstants.AGENT_WARM_SHUTDOWN and AgentConstants.AGENT_MACHINE_REBOOT:
                            AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : Setting AGENT_BOOT_STATUS : ' + repr(AgentConstants.AGENT_MACHINE_CRASH_AND_REBOOT_MESSAGE))
                            AgentConstants.AGENT_BOOT_STATUS = AgentConstants.AGENT_MACHINE_CRASH_AND_REBOOT_MESSAGE
                        else:
                            AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : Setting AGENT_BOOT_STATUS : ' + repr(AgentConstants.AGENT_MACHINE_RESTART_MESSAGE))
                            AgentConstants.AGENT_BOOT_STATUS = AgentConstants.AGENT_MACHINE_RESTART_MESSAGE
                    else:
                        AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : Server uptime is greater than ' + str(AgentConstants.APPROXIMATE_MACHINE_BOOT_TIME / 60) + ' minutes, AGENT_MACHINE_REBOOT = False, setting AGENT_BOOT_STATUS : ' + repr(AgentConstants.AGENT_SERVICE_RESTART_MESSAGE))
                        AgentConstants.AGENT_MACHINE_START_TIME = AgentUtil.getCurrentTimeInMillis() - (int_upTime * 1000) if AgentConstants.IS_DOCKER_AGENT == "0" else round(AgentConstants.DOCKER_PSUTIL.boot_time()*1000)
                        AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_START_TIME = AgentUtil.getTimeInMillis(AgentConstants.AGENT_MACHINE_START_TIME)
                        AgentConstants.AGENT_BOOT_STATUS = AgentConstants.AGENT_SERVICE_RESTART_MESSAGE
                cls.isUptimeParsed = True
            else:
                AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : int_upTime > lastUpTime, setting AGENT_BOOT_STATUS : ' + repr(AgentConstants.AGENT_SERVICE_RESTART_MESSAGE))
                AgentConstants.AGENT_MACHINE_START_TIME = AgentUtil.getCurrentTimeInMillis() - (100 * 1000)
                AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_START_TIME = AgentUtil.getTimeInMillis(AgentConstants.AGENT_MACHINE_START_TIME)
                AgentConstants.AGENT_BOOT_STATUS = AgentConstants.AGENT_SERVICE_RESTART_MESSAGE
            
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT, '************************* Exception while checking whether agent machine is rebooted ************************* ' + repr(e))
            traceback.print_exc()
        finally:
            AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : AGENT_MACHINE_START_TIME : ' + repr(AgentUtil.getFormattedTime(AgentConstants.AGENT_MACHINE_START_TIME)) + ' --> ' + repr(AgentConstants.AGENT_MACHINE_START_TIME))
            AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : AGENT_MACHINE_TIME_DIFF_BASED_START_TIME : ' + repr(AgentUtil.getFormattedTime(AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_START_TIME)) + ' --> ' + repr(AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_START_TIME))
            AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : AGENT_BOOT_STATUS : ' + repr(AgentConstants.AGENT_BOOT_STATUS))
            
    @classmethod
    def setMachineShutdownTime(cls):
        if platform.system() == 'Darwin':
            str_shutDownTimeCommand = "cat " + AgentConstants.AGENT_HEART_BEAT_QUOTES_FILE + " | awk -F'--->' '{print $2;}'"
        else:
            str_shutDownTimeCommand = "cat " + AgentConstants.AGENT_HEART_BEAT_FILE + " | awk -F'--->' '{print $2;}'"        
        try:
            if not AgentConstants.AGENT_WARM_START:
                AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : Site24x7 monitoring agent cold start')
            else:
                AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : Site24x7 monitoring agent warm start')
                if not AgentConstants.AGENT_WARM_SHUTDOWN and AgentConstants.AGENT_MACHINE_REBOOT:
                    AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : Site24x7 monitoring agent warm start - Abnormal shutdown')
                else:
                    AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : Site24x7 monitoring agent warm start - Normal shutdown')
            if os.path.exists(AgentConstants.AGENT_HEART_BEAT_FILE):  
                isSuccess, str_output = AgentUtil.executeCommand(str_shutDownTimeCommand)
                if isSuccess:
                    str_shutdownTime = re.sub('\s+', '', str_output).strip()
                    AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : Shutdown time command output : ' + repr(str_output) + ' --> ' + repr(str_shutdownTime))
                    if '.' in str_shutdownTime:
                        str_shutdownTime = str_shutdownTime.strip("L")
                        str_shutdownTime = round((float(str_shutdownTime) * 1000))
                    AgentConstants.AGENT_MACHINE_SHUTDOWN_TIME = str_shutdownTime
                    AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_SHUTDOWN_TIME = AgentUtil.getTimeInMillis(float(str_shutdownTime), AgentConstants.AGENT_PREVIOUS_TIME_DIFF)
                else:
                    AgentLogger.log(AgentLogger.STDOUT, '********************* Unable to get shutdown time *********************')
                    AgentConstants.AGENT_MACHINE_SHUTDOWN_TIME = -1
                    AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_SHUTDOWN_TIME = -1
            else:
                AgentLogger.log(AgentLogger.STDOUT, '********************* Agent heartbeat file does not exist. Unable to get shutdown time. Setting AGENT_MACHINE_SHUTDOWN_TIME to -1. *********************')
                AgentConstants.AGENT_MACHINE_SHUTDOWN_TIME = -1
                AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_SHUTDOWN_TIME = -1
        except Exception as e:
            AgentLogger.log([AgentLogger.STDERR], ' ************************* Exception while updating boot status ************************* ' + repr(e))
            traceback.print_exc()
            AgentConstants.AGENT_MACHINE_SHUTDOWN_TIME = -1
            AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_SHUTDOWN_TIME = -1
        finally:
            AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : AGENT_MACHINE_SHUTDOWN_TIME : ' + repr(AgentUtil.getFormattedTime(AgentConstants.AGENT_MACHINE_SHUTDOWN_TIME)) + ' --> ' + repr(AgentConstants.AGENT_MACHINE_SHUTDOWN_TIME))
            AgentLogger.log(AgentLogger.STDOUT, 'BOOT STATUS : AGENT_MACHINE_TIME_DIFF_BASED_SHUTDOWN_TIME : ' + repr(AgentUtil.getFormattedTime(AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_SHUTDOWN_TIME)) + ' --> ' + repr(AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_SHUTDOWN_TIME))
            
    def __updateBootStatus(self):
        try:
            if AgentConstants.AGENT_MACHINE_REBOOT and AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_SHUTDOWN_TIME > 0:
                self.__postAgentShutdownInfo()
            else:
                AgentLogger.log([AgentLogger.STDOUT], 'AGENT_MACHINE_REBOOT : ' + repr(AgentConstants.AGENT_MACHINE_REBOOT) + ' AGENT_MACHINE_TIME_DIFF_BASED_SHUTDOWN_TIME : ' + repr(AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_SHUTDOWN_TIME) + ', Uptime correction ignored')
            if not AgentConstants.AGENT_WARM_SHUTDOWN and AgentConstants.AGENT_MACHINE_REBOOT:  # Machine crash
                AgentLogger.log([AgentLogger.STDOUT], 'AGENT_WARM_SHUTDOWN : ' + repr(AgentConstants.AGENT_WARM_SHUTDOWN) + ', AGENT_MACHINE_REBOOT : ' + repr(AgentConstants.AGENT_MACHINE_REBOOT) + ', Uploading RCA')
                # rcaInfo = RcaInfo()
                # RcaUtil.uploadRca(rcaInfo)
            elif AgentConstants.AGENT_MACHINE_REBOOT:  # Machine reboot
                AgentLogger.log([AgentLogger.STDOUT], 'AGENT_MACHINE_REBOOT : ' + repr(AgentConstants.AGENT_MACHINE_REBOOT) + ', Uploading RCA')
                # rcaInfo = RcaInfo()
                # RcaUtil.uploadRca(rcaInfo)
            else:
                AgentLogger.log([AgentLogger.STDOUT], 'AGENT_WARM_SHUTDOWN : ' + repr(AgentConstants.AGENT_WARM_SHUTDOWN) + ', AGENT_MACHINE_REBOOT : ' + repr(AgentConstants.AGENT_MACHINE_REBOOT) + ', Ignored RCA upload')
        except Exception as e:
            AgentLogger.log([ AgentLogger.STDERR], ' ************************* Exception while updating boot status ************************* ' + repr(e))
            traceback.print_exc()
            
    def __postAgentShutdownInfo(self):
        dict_dataToPost = {}
        try:
            AgentLogger.log(AgentLogger.STDOUT, '============================================= UPTIME CORRECTION =============================================')
            int_currentTimeWithTimeDiff = AgentUtil.getTimeInMillis()
            dict_dataToPost['SHUTDOWNTIME'] = str(AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_SHUTDOWN_TIME)
            dict_dataToPost['STARTUPTIME'] = str(AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_START_TIME)
            dict_dataToPost['MSPCUSTOMERID'] = AgentConstants.CUSTOMER_ID
            dict_dataToPost['DATACOLLECTTIME'] = str(int_currentTimeWithTimeDiff)
            dict_dataToPost['REASON'] = str(AgentConstants.AGENT_BOOT_STATUS)
            dict_dataToPost['AgentKey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
            str_jsonData = json.dumps(dict_dataToPost)  # python dictionary to json string
            AgentLogger.log(AgentLogger.STDOUT, 'Uptime correction data : ' + repr(str_jsonData))
            AgentLogger.log(AgentLogger.STDOUT, 'UPTIME CORRECTION : SHUTDOWNTIME : ' + repr(AgentUtil.getFormattedTime(AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_SHUTDOWN_TIME)))
            AgentLogger.log(AgentLogger.STDOUT, 'UPTIME CORRECTION : STARTUPTIME : ' + repr(AgentUtil.getFormattedTime(AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_START_TIME)))
            AgentLogger.log(AgentLogger.STDOUT, 'UPTIME CORRECTION : DATACOLLECTTIME : ' + repr(AgentUtil.getFormattedTime(int_currentTimeWithTimeDiff)))
            str_servlet = AgentConstants.DATA_AGENT_HANDLER_SERVLET
            dict_requestParameters = {
            'agentKey'  :   AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),
            'bno' : AgentConstants.AGENT_VERSION,
            'action'  :   AgentConstants.UPTIME_CORRECTION,
            'custID' : AgentConstants.CUSTOMER_ID
            }
            if not dict_requestParameters == None:
                str_requestParameters = urlencode(dict_requestParameters)
                str_url = str_servlet + str_requestParameters
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.STDOUT)
            requestInfo.set_method(AgentConstants.HTTP_POST)
            requestInfo.set_data(str_jsonData)
            requestInfo.set_url(str_url)
            requestInfo.add_header("Content-Type", 'application/json')
            requestInfo.add_header("Accept", "text/plain")
            requestInfo.add_header("Connection", 'close')
            requestInfo.set_timeout(5)
            CommunicationHandler.sendRequest(requestInfo)
        except Exception as e:
            AgentLogger.log([ AgentLogger.STDERR], ' ************************* Exception while posting agent shutdown info to server ************************* ' + repr(e))
            traceback.print_exc()

class WMSThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.name = 'WMS Thread'
        self.paused = False
        self.pause_cond = threading.Condition(threading.Lock())
        self.action = AgentConstants.TEST_PING

        
    def run(self):
        global WMS_INTERVAL
        while not AgentUtil.TERMINATE_AGENT:
            try:
                CommunicationHandler.getConsolidatedWMSData(self.action)
                if WMS_INTERVAL > 0:
                    time.sleep(WMS_INTERVAL)
                else:
                    self.pause()
            except Exception as e:
                AgentLogger.log([AgentLogger.STDOUT, AgentLogger.MAIN], ' *************************** Exception while executing WMSThread *************************** ' + repr(e))
                traceback.print_exc()
    
    def pause(self):
        try:
            self.paused = True
            self.pause_cond.acquire()
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT, AgentLogger.MAIN], ' *************************** Exception while suspending WMSThread *************************** ' + repr(e))
            traceback.print_exc()

    #should just resume the thread
    def resume(self):
        try:
            self.paused = False
            self.action=AgentConstants.GCR
            self.pause_cond.notify()
            self.pause_cond.release()
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT, AgentLogger.MAIN], ' *************************** Exception while resuming WMSThread *************************** ' + repr(e))
            traceback.print_exc()

class TraceRouteGenerator(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.name = 'Trace Route Thread'
        self.__kill = True
    
    def stop(self):
        self.__kill = True
        
    def activate(self):
        self.__kill = False
        
    def getThreadStatus(self):
        return self.__kill
        
    def run(self):
        global LAST_TRACE_ROUTE_TIME, CLEAR_TRACE_ROUTE_REPORT
        while not AgentUtil.TERMINATE_AGENT:
            time.sleep(1)
            if not self.__kill:
                try:
                    if CLEAR_TRACE_ROUTE_REPORT:
                        AgentUtil.deleteTraceRoute()
                        CLEAR_TRACE_ROUTE_REPORT = False
                    if LAST_TRACE_ROUTE_TIME == None or (time.time() - LAST_TRACE_ROUTE_TIME > 300):
                        fileCount = FileUtil.getFileCount(AgentConstants.AGENT_TEMP_RCA_DIR, 'trace_route')
                        if fileCount < 12:
                            LAST_TRACE_ROUTE_TIME = time.time() 
                            AgentUtil.generateTraceRoute()
                        else:
                            AgentLogger.log(AgentLogger.CHECKS, 'Trace Route File Count Exceeds So stopped generating trace')
                    else:
                        AgentLogger.log(AgentLogger.CHECKS, 'Trace Route Not generated because of polling difference ---->' + repr(time.time() - LAST_TRACE_ROUTE_TIME))
                    TRACE_THREAD.stop()
                    AgentLogger.log(AgentLogger.CHECKS, 'Deactivating the Trace Route Thread  ---->' + repr(self.__kill))
                except Exception as e:
                    traceback.print_exc()
            else:
                pass
                # AgentLogger.log(AgentLogger.CHECKS,'thread status ---->'+repr(self.__kill))
                
class StatusThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.name = 'Status Thread'
        self.networkStatus = True
        self.__kill = False
    def stop(self):
        self.__kill=True
    def run(self):      
        self.initializeStatusUtil()
        int_prevStatusUpdateTime = time.time()
        self.updateStatus()
        while not AgentUtil.TERMINATE_AGENT and not self.__kill:
            int_currentStatusUpdateTime = time.time()
            try:
                if AgentConstants.STATUS_UPDATE_INTERVAL > 0 and (int_currentStatusUpdateTime - int_prevStatusUpdateTime) >= AgentConstants.STATUS_UPDATE_INTERVAL:
                    self.updateStatus()
                    int_prevStatusUpdateTime = int_currentStatusUpdateTime
                AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(1)
            except Exception as e:
                AgentLogger.log([AgentLogger.STDOUT, AgentLogger.MAIN], ' *************************** Exception while executing StatusThread *************************** ' + repr(e))
                traceback.print_exc()
                AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(5)
    
    def updateStatus(self):   
        bool_toReturn = True
        global TRACE_THREAD, CLEAR_TRACE_ROUTE_REPORT, LAST_TRACE_ROUTE_TIME, STATUS_UPDATE_SERVER_LIST
        try:
            AgentLogger.debug(AgentLogger.STDOUT, '=============================================PRIMARY SERVER STATUS UPDATE =============================================')
            str_url = None
            str_servlet = AgentConstants.AGENT_STATUS_UPDATE_SERVLET
            dict_requestParameters = {
                'agentKey' : AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),
                'serviceName' : AgentConstants.AGENT_NAME,
                'CUSTOMERID' :  AgentConstants.CUSTOMER_ID,
                'AGENTUNIQUEID' : AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_unique_id'),
                'bno' : AgentConstants.AGENT_VERSION,
                'agentStatus' : 'AVAILABLE',
                'sct': AgentUtil.getTimeInMillis(),
                'auid':AgentConstants.AUID,
                'auid_old':AgentConstants.AUID_OLD
            }
            if AgentConstants.error_in_server:
                dict_requestParameters['err']=AgentConstants.error_in_server
            if not dict_requestParameters == None:
                str_requestParameters = urlencode(dict_requestParameters)
                str_url = str_servlet + str_requestParameters
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.STDOUT)
            requestInfo.set_method(AgentConstants.HTTP_POST)
            requestInfo.set_url(str_url)
            requestInfo.set_timeout(AgentConstants.STATUS_UPDATE_TIMEOUT)
            bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
            if not bool_toReturn:
                requestInfo.useSecondaryServer()   
                bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
                if bool_toReturn:
                    AgentLogger.log([AgentLogger.MAIN, AgentLogger.STDOUT, AgentLogger.CRITICAL],'Primary failed but reached secondary server successfully. Response data : '+repr(dict_responseData)+'\n')
                    bool_toReturn = True
                else:
                    if TRACE_THREAD == None:
                            AgentLogger.log(AgentLogger.CHECKS, 'Starting Trace Route Generator Thread')
                            TRACE_THREAD = TraceRouteGenerator()
                            TRACE_THREAD.setDaemon(True)
                            TRACE_THREAD.start()
                    else:
                        if TRACE_THREAD.getThreadStatus():
                            AgentLogger.log(AgentLogger.CHECKS, 'Trace Route thread not active So starting it')
                            TRACE_THREAD.activate()
                    AgentLogger.log([AgentLogger.MAIN, AgentLogger.STDOUT], 'Primary and secondary servers failed. Trying to reach servers from status update server list \n')
                    for hostname in STATUS_UPDATE_SERVER_LIST:
                        requestInfo.set_host(hostname)
                        bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
                        AgentLogger.log([AgentLogger.MAIN, AgentLogger.STDOUT], 'Trying to reach server : ' + str(requestInfo.get_host()) + ' : Reachability : ' + repr(bool_toReturn) + ' : Error code :' + repr(int_errorCode) + ' Response Data : ' + repr(dict_responseData) + '\n')
                        if bool_toReturn:
                            AgentLogger.log(AgentLogger.CRITICAL,'Primary and secondary servers failed. Reached Server ' + str(requestInfo.get_host()))
                            break
                    if isinstance(int_errorCode, ssl.SSLCertVerificationError) or isinstance(int_errorCode, ssl.SSLError):
                        AgentLogger.log([AgentLogger.MAIN, AgentLogger.STDOUT],'***** SSL Certificate Verification failed *****  ' + str(int_errorCode))
                        CommunicationHandler.getCaCertPath()
                    if not CommunicationHandler.checkNetworkStatus(AgentLogger.STDOUT) and self.networkStatus:
                        AgentLogger.log([AgentLogger.STDOUT, AgentLogger.MAIN], 'Unable to update agent status to server. Generate network rca. \n')
                        rcaInfo = RcaInfo()
                        rcaInfo.requestType = AgentConstants.GENERATE_NETWORK_RCA
                        rcaInfo.action = AgentConstants.SAVE_RCA_REPORT
                        RcaUtil.generateRca(rcaInfo)
                        self.networkStatus = False
                        com.manageengine.monagent.util.rca.RcaHandler.backupRCAReport(AgentConstants.AGENT_TEMP_RCA_REPORT_NETWORK_DIR)
            else:
                if not self.networkStatus:
                    AgentLogger.log(AgentLogger.CHECKS, 'Network Connectivity Resumed ')
                    self.networkStatus = True
                    LAST_TRACE_ROUTE_TIME = None
                    CLEAR_TRACE_ROUTE_REPORT = True
                    if AgentConstants.UPTIME_MONITORING == 'true':
                        AgentUtil.invokeUptimeMonitoringFC()
            CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'STATUS THREAD')
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT, AgentLogger.MAIN], '*************************** Exception while updating status ************************** ' + repr(e))
            traceback.print_exc()
            bool_toReturn = False
        return bool_toReturn
    
    def initializeStatusUtil(self):
        global STATUS_UTIL
        try:     
            while not AgentUtil.TERMINATE_AGENT:
                if not AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key') == '0':
                    STATUS_UTIL = AgentStatusUtil()
                    break
                else:
                    AgentLogger.log(AgentLogger.STDOUT, 'Agent Not Registered - Not Proceeding With Status Update')
                AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(2)
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT, AgentLogger.STDERR], '*************************** Exception while initialising AgentStatusUtil *************************** ' + repr(e))
            traceback.print_exc()
            
class HeartBeatThread(threading.Thread):
    __lastHeartBeatTime = None
    def __init__(self):
        threading.Thread.__init__(self)
        self.name = 'HeartBeatThread'
        self.__kill = False
        AgentStatusUtil.setMachineBootStatus()
        AgentStatusUtil.setMachineShutdownTime()
        
    @classmethod
    def __setLastHeartBeatTime(cls, lastHeartBeatTimeInMillis):
        cls.__lastHeartBeatTime = lastHeartBeatTimeInMillis
        
    @classmethod
    def getLastHeartBeatTime(cls):
        return cls.__lastHeartBeatTime
    
    def stop(self):
        self.__kill = True
        
    def run(self):
        int_prevHeartBeatTime = time.time()
        HeartBeatThread.updateHeartBeat()
        while not AgentUtil.TERMINATE_AGENT and not self.__kill:
            int_currentHeartBeatTime = time.time()
            try:     
                if (int_currentHeartBeatTime - int_prevHeartBeatTime) >= AgentConstants.AGENT_HEART_BEAT_INTERVAL:
                    HeartBeatThread.updateHeartBeat()  
                    int_prevHeartBeatTime = int_currentHeartBeatTime
                AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(1)
            except Exception as e:
                AgentLogger.log([AgentLogger.STDOUT, AgentLogger.MAIN], ' *************************** Exception while executing HeartBeatThread *************************** ' + repr(e))
                traceback.print_exc()
                AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(5)
                
    @classmethod
    def updateHeartBeat(cls, heartBeatTimeInMillis=None):
        upTime = 0
        try:  
            if not heartBeatTimeInMillis:
                heartBeatTimeInMillis = AgentUtil.getCurrentTimeInMillis()
            if AgentStatusUtil.isUptimeParsed:
                upTime = (AgentUtil.getCurrentTimeInMillis() - AgentConstants.AGENT_MACHINE_START_TIME) / 1000
            str_heartBeatTime = "Heart beat at " + str(datetime.fromtimestamp(heartBeatTimeInMillis / 1000).strftime("%Y-%m-%d %H:%M:%S") + " ---> " + repr(heartBeatTimeInMillis)) + " ---> uptime " + " ---> " + str(upTime)
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(AgentConstants.AGENT_HEART_BEAT_FILE)
            fileObj.set_data(str_heartBeatTime)
            fileObj.set_logging(False)
            fileObj.set_loggerName([AgentLogger.STDOUT])
            FileUtil.saveData(fileObj)
            cls.__setLastHeartBeatTime(heartBeatTimeInMillis)
        except Exception as e:
            AgentLogger.log([ AgentLogger.MAIN], '*************************** Exception while updating heart beat *************************** ' + repr(e))
            traceback.print_exc()
       
        