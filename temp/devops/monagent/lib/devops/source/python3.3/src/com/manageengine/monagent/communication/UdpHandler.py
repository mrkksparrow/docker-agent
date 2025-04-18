#$Id$
import socket, select, traceback
from threading import Thread
import os,re,json
import errno
from pyparsing import Word, alphas, Suppress, Combine, nums, string, Optional, Regex

import com
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.notify.AgentNotifier import NotificationUtil, Notifier, ShutdownListener
from com.manageengine.monagent.util import AgentBuffer
from com.manageengine.monagent.util import DesignUtils
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util.AgentUtil import ZipUtil, FileUtil, AGENT_CONFIG, FileZipAndUploadInfo
from com.manageengine.monagent.util.rca.RcaHandler import RcaUtil, RcaInfo
from collections import deque
import threading
#from com.manageengine.monagent.communication import UdpHandler
UDP_SERVER = None
SysLogUtil = None
SysLogStatsUtil = None

# Priority - The PRI part is a number that is enclosed in angle brackets. 
#            The Priority value is calculated by first multiplying the Facility number by 8 and then adding the numerical value of the Severity

LIST_FACILITY_LEVELS = ['kernel','user-level','mail','system','authorization','syslogd',
                        'line printer','network news','UUCP','clock daemon','authpriv','FTP',
                        'NTP','log audit','log alert','cron','local0','local1',
                        'local2','local3','local4','local5','local6','local7'
                       ]

LIST_SEVERITY_LEVELS = ['Emergency','Alert','Critical','Error','Warning','Notice','Informational','Debug']

FILTER_IMPL = {}

SYSLOGS_DATA = {}

syslogLock = threading.Lock()

def handleCustomFilters(filterName,count):
    customFilterObj = CustomFilters(filterName,count)
    return customFilterObj

class Server(Thread, ShutdownListener, Notifier):
    def __init__(self, address_family, socketType, addr, port, serverName = 'Server'):
        Thread.__init__(self)
        self._serverName = serverName
        ShutdownListener.__init__(self)
        self._socket = None
        self._address_family = address_family
        self._socketType = socketType
        self._serverAddress = addr
        self._serverPort = int(port)
        self._isRunning = False
      
    def isRunning(self):
        return self._isRunning
    
    def _bind(self):
        self._socket = socket.socket(self._address_family, self._socketType)
        self._socket.bind((self._serverAddress, self._serverPort))
        
    def __eq__(self, other): 
        return self is other
    
    def __hash__(self): 
        return hash(id(self))
    
    def fileno(self):
        return self._socket.fileno()


class UdpServer(Server):
    def __init__(self, addr, port):
        Server.__init__(self, socket.AF_INET, socket.SOCK_DGRAM, AgentConstants.UDP_SERVER_IP, AgentConstants.UDP_PORT, 'UdpServer')
        Notifier.__init__(self, AgentConstants.UDP_NOTIFIER)       
        self._maxPacketSize = 8192
        
    def run(self):
        try:
            self._isRunning = True
            self._bind()
            while not self._shutdown:
                r, w, e = select.select([self],[],[]) 
                if self in r:
                    self.handleRequest()
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while running '+str(self._serverName)+' *************************** '+ repr(e))
            traceback.print_exc()
        finally:
            self._isRunning = False
            
    def handleRequest(self):
        if not self._shutdown:
            data, client_addr = self._socket.recvfrom(self._maxPacketSize)
            self.process(data)
        else:
            data, client_addr = self._socket.recvfrom(self._maxPacketSize)
            AgentLogger.log(AgentLogger.UDP, 'Data received : '+repr(data))
            AgentLogger.log(AgentLogger.UDP, '======================================= SHUTTING DOWN UDP SERVER =======================================')
            
            #(data, self._socket), client_addr
    def process(self, data):
        try:
            decodedData = data.decode('utf-8')
            #AgentLogger.log(AgentLogger.UDPRAW, 'Udp ::: '+repr(AgentUtil.getCurrentTimeInMillis())+' ::: '+repr(decodedData))
            logMessage = SysLogMessage(decodedData)
            AgentLogger.debug(AgentLogger.UDPRAW,str(decodedData))
            filteredEvents = SysLogUtil.applyFilters(decodedData, None)
            filteredList = filteredEvents.toList()
            if filteredList:
                #SysLogUtil.handleAlertFilters(decodedData,['AlertFilters'])
                AgentLogger.debug(AgentLogger.UDPFILTERED,str(filteredList))
                SysLogUtil.addToBuffer(logMessage.toList())
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while processing the udp data : '+str(data)+' *************************** '+ repr(e))
            traceback.print_exc()
        finally:
            filteredEvents = None
            filteredList = None
            
    def update(self):
        try:
            self._shutdown = True
            self._socket.sendto(bytes('shutdown', 'UTF-8'), (self._serverAddress, self._serverPort))
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while sending shutdown notification to '+str(self._serverName)+' *************************** '+ repr(e))
            traceback.print_exc()
            
class SysLogFilter:
    
    def __init__(self, name, count=None):
        self.filterName = name
        self.priority = None
        self.facility = None
        self.severity = None
        self.hostname = None
        self.appname = None
        self.message = None
        self.time = None
        self.count = count
        self.impl = None
        #self.buffer = []
        
    def __str__(self):
        logMessage = ''
        logMessage += 'filterName : ' + repr(self.filterName)
        logMessage += ' impl : ' + repr(self.impl)
        logMessage += ' priority : ' + repr(self.priority)
        logMessage += ' facility : ' + repr(self.facility)
        logMessage += ' severity : ' + repr(self.severity)
        logMessage += ' time : ' + repr(self.time)
        logMessage += ' hostname : ' + repr(self.hostname)
        logMessage += ' appname : ' + repr(self.appname)
        logMessage += ' count : ' + repr(self.count)
        logMessage += ' message : ' + repr(self.message)
        return logMessage
    
    def __eq__(self, other): 
        return self is other
    
    def __hash__(self): 
        return hash(id(self))
        
    def filter(self, sysLogMessage, filteredEvents):
        try:
            AgentLogger.debug(AgentLogger.UDPFILTERED,'FILTERSTRING'+str(self.filterName)+' : '+str(self.facility)+' : '+str(sysLogMessage))
            if self.count:
                self.handleCount(sysLogMessage, filteredEvents)
            if self.time != None:
                self.handleTime(sysLogMessage, filteredEvents)
            if self.priority and self.priority in sysLogMessage.priority:
                filteredEvents.add(self, sysLogMessage)
            if self.severity:
                self.handleSeverity(sysLogMessage, filteredEvents)
            if self.facility:
                self.handleFacility(sysLogMessage, filteredEvents)
            if self.hostname and self.hostname in sysLogMessage.hostname:
                filteredEvents.add(self, sysLogMessage)
            if self.appname and self.appname in sysLogMessage.appname:
                filteredEvents.add(self, sysLogMessage)
            if self.message and self.message in sysLogMessage.message:
                filteredEvents.add(self, sysLogMessage)
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while applying the filter : '+str(self.filterName)+' for the log message : '+str(sysLogMessage)+' *************************** '+ repr(e))
            traceback.print_exc()
        
    def handleSeverity(self, sysLogMessage, filteredEvents):
        if sysLogMessage.severity in self.severity:
            filteredEvents.add(self, sysLogMessage)
    
    def handleFacility(self, sysLogMessage, filteredEvents):
        if sysLogMessage.facility in self.facility:
            filteredEvents.add(self, sysLogMessage)
            
    def handleCount(self, sysLogMessage, filteredEvents):
        if self in filteredEvents.filterVsTempParams and 'count' in filteredEvents.filterVsTempParams[self]:
            filteredEvents.filterVsTempParams[self]['count'] += 1
        else:
            filteredEvents.filterVsTempParams[self] = {'count' : 1}
        if filteredEvents.filterVsTempParams[self]['count'] <= self.count:
            filteredEvents.add(self, sysLogMessage)
    
    def handleTime(self, sysLogMessage, filteredEvents):
        if self not in filteredEvents.filterVsTempParams or 'time' not in filteredEvents.filterVsTempParams[self]:
            filteredEvents.filterVsTempParams[self]['time'] = AgentUtil.getCurrentTimeInMillis() + (self.time * 1000)
        if sysLogMessage.timestamp > filteredEvents.filterVsTempParams[self]['time']:
                filteredEvents.add(self, sysLogMessage)

class CustomFilters(SysLogFilter):
    
    def __init__(self,name,count):
        SysLogFilter.__init__(self, name, count)
        self.lastAlertedTime = None
        self.regex = None
        self.clearence = None
        self.timelimit = None
        if AgentConstants.ALERT_BUFFER + '_' + self.filterName in AgentBuffer.BUFFERS:
            AgentLogger.log(AgentLogger.CHECKS,'Buffer for filter '+ str(name) +' is already present. Hence deleting it!'+ str(AgentBuffer.BUFFERS[AgentConstants.ALERT_BUFFER + '_' + self.filterName]))
            AgentBuffer.BUFFERS.pop(AgentConstants.ALERT_BUFFER + '_' + self.filterName,None)
        self.alertBuffer = AgentBuffer.getBuffer(AgentConstants.ALERT_BUFFER + '_' + self.filterName , int(self.count))
        self.rCount = None
        self.counter = 0
        self.lastAlertedTime = None
        
    def filter(self, sysLogMessage, filteredEvents):
        list_messages = []
        #dict_filterDetails = {}
        try:
            isallowed = False #To check atleast one filter parameter is applied
            AgentLogger.debug(AgentLogger.UDP,' ========================= alertFilter'+str(self) + ' called for:'+ str(sysLogMessage)+'====================')
            if self.facility == None or str(sysLogMessage.facility) in self.facility:
                #AgentLogger.log(AgentLogger.UDP,' ========================= Facility matched :'+str(sysLogMessage.facility) + str(self.facility) + 'and appname is :' + str(self.appname))
                if self.facility:
                    isallowed = True
                if self.appname == None or str(sysLogMessage.appname) in self.appname :
                    #AgentLogger.log(AgentLogger.UDP,' ========================= Appname matched :'+str(sysLogMessage.appname) + str(self.appname))
                    if self.appname:
                        isallowed = True
                    if self.severity == None or str(sysLogMessage.severity) in self.severity:
                        if self.severity :
                            isallowed = True
                            
                        if self.message:
                            isallowed = True
                            is_valid = None
                            try:
                                re.compile(self.message)
                                is_valid = True
                            except re.error:
                                is_valid = False
                            if is_valid:
                                isMatch = re.search(self.message,str(sysLogMessage.message),re.I)
                                if isMatch:
                                    AgentLogger.log(AgentLogger.UDP,' ====Message strings matched ===' + self.message + '===' +str(sysLogMessage.message))
                                    self.uploadAlertServlet(sysLogMessage)
                                else:
                                    AgentLogger.debug(AgentLogger.UDP,' ====Message strings not matched for : '  + str(sysLogMessage.message) + ' ========')
                        else:
                            if isallowed == True :
                                AgentLogger.log(AgentLogger.UDP,' ====Message strings not found in filter ===' + str(self.filterName) + '===')
                                self.uploadAlertServlet(sysLogMessage)
                            else:
                                AgentLogger.log(AgentLogger.UDP,' ====Invalid filter details. So filter is ignored ========' + str(self.filterName))
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while applying the alert filter : '+str(self.filterName)+' for the log message : '+str(sysLogMessage)+' *************************** '+ repr(e))
            traceback.print_exc()
            
    def uploadAlertServlet(self,sysLogMessage):
        global SYSLOGS_DATA
        try:
            AgentLogger.log(AgentLogger.UDP,' ========================= Alert Servlet Upload code for :'+ str(sysLogMessage) + ' =====================')            
            countStatus = self.handleCount(int(sysLogMessage.timestamp),sysLogMessage.message)
            if countStatus:
                timeStatus,alertData = self.hadleAlertedTime()
                if timeStatus:
                    if ((not self.lastAlertedTime) or (AgentUtil.getCurrentTimeInMillis() > self.lastAlertedTime + AgentConstants.MIN_CHECK_ALERT_INTERVAL)):
                        AgentLogger.log(AgentLogger.UDP,' ======== Uploading alert to instant notifier servlet ==============')
                        with syslogLock:
                            SYSLOGS_DATA['logrule'][str(self.filterName)]['status'] = 0
                            SYSLOGS_DATA['logrule'][str(self.filterName)]['count'] = self.count
                            
                            if 'time' in SYSLOGS_DATA['logrule'][str(self.filterName)]:
                                SYSLOGS_DATA['logrule'][str(self.filterName)]['time'] = []
                            else:
                                SYSLOGS_DATA['logrule'][str(self.filterName)].setdefault('time',[])
                                
                            if 'msg' in SYSLOGS_DATA['logrule'][str(self.filterName)]:
                                SYSLOGS_DATA['logrule'][str(self.filterName)]['msg'] = []
                            else:
                                SYSLOGS_DATA['logrule'][str(self.filterName)].setdefault('msg',[])
                            
                            if alertData:
                                AgentLogger.log(AgentLogger.UDP, 'Alert data found' + str(alertData))              
                                for each_alert in alertData:
                                    SYSLOGS_DATA['logrule'][str(self.filterName)]['time'].append(each_alert['TIMESTAMP'])
                                    SYSLOGS_DATA['logrule'][str(self.filterName)]['msg'].append(each_alert['MESSAGE'])
                            else:
                                AgentLogger.log(AgentLogger.UDP, 'Alert data not found')
                                SYSLOGS_DATA['logrule'][str(self.filterName)]['time'] = [sysLogMessage.timestamp]
                                SYSLOGS_DATA['logrule'][str(self.filterName)]['msg'] = [sysLogMessage.message]
                        AgentLogger.log(AgentLogger.UDP,' ======== Added alert notification format to global object ====== \n' + str(SYSLOGS_DATA))
                        
                        com.manageengine.monagent.communication.BasicClientHandler.sendSysLogInstantNotif(SYSLOGS_DATA)
                        self.lastAlertedTime = AgentUtil.getCurrentTimeInMillis()
                    else:
                        AgentLogger.log(AgentLogger.UDP,' ********************* Syslog instant data not uploaded as it is a frequent alert ************************* ')
                else:
                    AgentLogger.debug(AgentLogger.UDP,' ========Can not upload because alert does not meet time limit ==============')
            else:
                AgentLogger.log(AgentLogger.UDP,' ========Can not upload because count ' + str(self.count) + ' not matched. ALERT BUFFER : ' + str(self.alertBuffer))
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception occured in uploadalertservlet: '+ repr(e))
            traceback.print_exc()
            
    def hadleAlertedTime(self):
        try:
            if (not self.timelimit):
                AgentLogger.log(AgentLogger.UDP,' ======== Timelimit condition not there for filtername: ' + str(self.filterName) + '===============')

                return True, None
            timediff = round((int(self.alertBuffer[self.count-1]['TIMESTAMP'])-int(self.alertBuffer[0]['TIMESTAMP']))/1000,0)
            if timediff <= int(self.timelimit):
                AgentLogger.log(AgentLogger.UDP,' ======== Timelimit condition also satisfied ========== diff: ' + str(timediff) + ' limit: ' + str(self.timelimit) + ' filtername: ' + str(self.filterName))
                listAlerts = list(self.alertBuffer)
                self.alertBuffer.clear()
                AgentLogger.log(AgentLogger.UDP, 'Returning Alert data found' + str(listAlerts))
                return True, listAlerts
            else:
                AgentLogger.log(AgentLogger.UDP,' ======== Timelimit condition not satisfied ========== diff: ' + str(timediff) + ' limit: ' + str(self.timelimit) + ' filtername: ' + str(self.filterName))
                return False, None
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception occured in handling alert times : '+ repr(e))
            traceback.print_exc()

    def handleCount(self,timestamp, message):
        countStatus = False
        dictAlertData = {}
        try:
            dictAlertData['TIMESTAMP'] = timestamp
            dictAlertData['MESSAGE'] = message
            self.alertBuffer.add(dictAlertData)
            if len(self.alertBuffer) == self.count:
                AgentLogger.log(AgentLogger.UDP,' ======== Max count limit ' + str(self.count) +  ' reached for : ' + str(self.filterName) + '============ ALERT BUFFER : ' + str(self.alertBuffer) )
                countStatus = True                
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception occured in handling alert count: '+ repr(e))
            traceback.print_exc()
        finally:
            return countStatus
        
    def handleClearance(self):
        pass
    
class SysLogFilterGroup:
    def __init__(self, name):
        self.filterGroupName = name
        self.filters = None
        
    def __str__(self):
        logMessage = ''
        logMessage += 'filterGroupName : ' + repr(self.filterGroupName)
        logMessage += ' filters : ' + repr(self.filters)
        return logMessage
    
    def __eq__(self, other): 
        return self is other
    
    def __hash__(self): 
        return hash(id(self))
    
            
class SysLogMessage:
    attributeCount = 11
    def __init__(self, rawMessage):
        self.raw = rawMessage
        self.time = AgentUtil.getCurrentTimeInMillis()
        self.priority = None
        self.facility = None
        self.severity = None
        self.timestamp = None
        self.hostname = None
        self.appname = None
        self.pid = None
        self.message = None
        self.__parse()
        
    def __str__(self):
        logMessage = ''
        logMessage += 'priority : ' + repr(self.priority)
        logMessage += ' facility : ' + repr(self.facility)
        logMessage += ' severity : ' + repr(self.severity)
        logMessage += ' timestamp : ' + repr(self.timestamp)
        logMessage += ' hostname : ' + repr(self.hostname)
        logMessage += ' appname : ' + repr(self.appname)
        logMessage += ' pid : ' + repr(self.pid)
        logMessage += ' message : ' + repr(self.message)
        return logMessage
    
    def __parse(self):
        try:
            if AgentConstants.MESSAGE_REPEATED_WARNING not in self.raw:
                parsed = SysLogUtil.pattern.parseString(self.raw)
                parsedListSize = len(parsed)
                AgentLogger.debug(AgentLogger.UDP, 'Size : '+repr(parsedListSize)+', Parsed List '+ repr(parsed))
                self.priority = parsed[0]
                self.facility = str((int(self.priority) // 8))
                self.severity = str((int(self.priority) % 8))
                self.timestamp = AgentUtil.getCurrentTimeInMillis()
                self.hostname = parsed[4]
                self.appname = parsed[5]
                if parsedListSize == 8:
                    self.pid       = parsed[6]
                    self.message   = parsed[7]
                else:
                    self.message   = parsed[6]
            #SysLogUtil.buffer.add(self)
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while parsing syslog message '+str(self.raw)+' *************************** '+ repr(e))
            
    def toList(self):
        toReturn = [None] * self.attributeCount
        toReturn[0] = self.time
        toReturn[1] = AgentUtil.getTimeInMillis(self.time)
        toReturn[2] = AgentUtil.getFormattedTime(self.time)
        toReturn[3] = self.priority
        toReturn[4] = self.facility
        toReturn[5] = self.severity
        toReturn[6] = self.timestamp
        toReturn[7] = self.hostname
        toReturn[8] = self.appname
        if self.pid:
            toReturn[9] = self.pid
        else:
            toReturn[9] = '-'
        toReturn[10] = self.message
        return toReturn
            
class SysLogQuery:
    def __init__(self):
        self.startTime = None
        self.endTime = None
        self.facility = None
        self.severity = None
        self.message = None       
            
class FilteredEvents:
    def __init__(self):
        self.__filterVsLogMessageList = {}
        self.filterVsTempParams = {}
        
    def add(self, filter, logMessage):
        AgentLogger.debug(AgentLogger.UDP, repr(filter.filterName)+repr(' : ')+str(logMessage))
        if filter in self.__filterVsLogMessageList:
            self.__filterVsLogMessageList[filter].append(logMessage)
        else:
            self.__filterVsLogMessageList[filter] = [logMessage]
        
    def toJson(self):
        toReturn = {}
        for key, messageList in self.__filterVsLogMessageList.items():
            for message in messageList:
                if key.filterName in toReturn:
                    toReturn[key.filterName].append(message.raw)
                else:
                    toReturn[key.filterName] = [message.raw]
        return toReturn
    
    def toList(self):
        toReturn = []
        for key, messageList in self.__filterVsLogMessageList.items():
            for message in messageList:
                toReturn.append(message.raw)
        return toReturn
    
class SysLogData:
    def __init__(self):
        self.data = None
    
    def setStats(self,dict_data):
        self.data = dict_data
        
    def getStats(self):
        return self.data
    
    def toJson(self):
        return json.dumps(self.data)
    
class SysLogStats:
    def __init__(self):
        self.stats = None
    
    def setStats(self,dict_stats):
        self.stats = dict_stats
        
    def getStats(self):
        return self.stats
    
    def toJson(self):
        return json.dumps(self.stats)
    
class SysLogCollector(DesignUtils.Singleton):
    def __init__(self):
        self.query = None
        self.setQuery()
        
    def setQuery(self):
        self.query = SysLogQuery()
        self.query.startTime = AgentUtil.getCurrentTimeInMillis() - AgentConstants.SYSLOG_FETCHING_INTERVAL*1000
        self.query.endTime = AgentUtil.getCurrentTimeInMillis()
    
    def getQuery(self):
        self.query.startTime = AgentUtil.getCurrentTimeInMillis() - AgentConstants.SYSLOG_FETCHING_INTERVAL*1000
        self.query.endTime = AgentUtil.getCurrentTimeInMillis()
        return self.query
        
    def collectSysLogData(self):
        try:
            syslogstats = SysLogStats()
            listToReturn = SysLogUtil.getLogMessages(self.getQuery())
            AgentLogger.debug(AgentLogger.UDP,'Collector_UDP_Log messages : '+repr(listToReturn))
            self.createStatisticsAndData(listToReturn,syslogstats)
            self.saveSysLogData(syslogstats, AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['004'])
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while collecting syslog stats *************************** '+ repr(e))
            traceback.print_exc()
        
    def saveSysLogData(self,syslogstats, dir_prop):
        try:
            dict_dataToSave = syslogstats.getStats()
            #dict_dataToSave['MSPCUSTOMERID'] = AgentConstants.CUSTOMER_ID
            #dict_dataToSave['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
            #dict_dataToSave['DATACOLLECTTIME'] = str(AgentUtil.getTimeInMillis()) 
            if "Statistics" in dict_dataToSave and dict_dataToSave["Statistics"]:
                AgentLogger.log(AgentLogger.UDP,'JSONdata to save : '+repr(syslogstats.toJson()))
                str_fileName = FileUtil.getUniqueFileName(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'), 'Statistics')
                str_filePath = dir_prop['data_path'] + '/' + str_fileName
                fileObj = AgentUtil.FileObject()
                fileObj.set_fileName(str_fileName)
                fileObj.set_filePath(str_filePath)
                fileObj.set_data(dict_dataToSave)
                fileObj.set_dataType('json')
                fileObj.set_mode('wb')
                fileObj.set_dataEncoding('UTF-16LE')
                fileObj.set_logging(False)
                fileObj.set_loggerName(AgentLogger.UDP)
                bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
                if bool_toReturn:
                    AgentLogger.log(AgentLogger.UDP,'Statistics file name and saved to : '+str_fileName + str_filePath)
                if dir_prop['instant_zip']:
                    ZipUtil.zipFilesAtInstance([[str_fileName]],dir_prop)
            else:
                AgentLogger.log(AgentLogger.UDP,'No Syslog Data found to upload : '+repr(syslogstats.toJson()))
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while saving syslog stats *************************** '+ repr(e))
            traceback.print_exc()
      
    def createStatisticsAndData(self,list_Messages,syslogstats):
        dict_statistics = {}
        list_Headers = []
        #json_listToReturn = json.dumps(listToReturn) 
        #AgentLogger.log(AgentLogger.UDP, 'Showing collectors logs : ' + repr(json_listToReturn))
        try:
            index=1
            temp_dict = {}
            dictTempData = {}
            for  index in range(len(list_Messages)):
                if index != 0 :
                    #int_facility = list_Messages[index][4] #facility value in the message
                    #AgentLogger.log(AgentLogger.UDP, 'ShowingUdpIndex: ' + list_Messages[index][4] + ' : ' + list_Messages[index][5])
                    facility_code = LIST_FACILITY_LEVELS[int(list_Messages[index][4])]
                    str_source = list_Messages[index][8] #source value in the message
                    #int_security = list_Messages[index][5] #security value in the message
                    severity_code = LIST_SEVERITY_LEVELS[int(list_Messages[index][5])]
                    if facility_code in temp_dict:
                        if str_source in temp_dict[facility_code] :
                            if severity_code in temp_dict[facility_code][str_source] :
                                temp_dict[facility_code][str_source][severity_code] += 1
                            else :
                                temp_dict.setdefault(facility_code,{}).setdefault(str_source,{}).setdefault(severity_code,1)
                        else :
                            temp_dict.setdefault(facility_code,{}).setdefault(str_source,{}).setdefault(severity_code,1)
                    else :
                        temp_dict.setdefault(facility_code,{}).setdefault(str_source,{}).setdefault(severity_code,1)
                        #temp_dict[listToReturn[index][4]][listToReturn[index][8]][listToReturn[index][5]] = 1
                else:
                    list_Headers.append(list_Messages[index][0])
                    list_Headers.append(list_Messages[index][3])
                    list_Headers.append(list_Messages[index][4])
                    list_Headers.append(list_Messages[index][5])
                    list_Headers.append(list_Messages[index][7])
                    list_Headers.append(list_Messages[index][8])
                    list_Headers.append(list_Messages[index][9])
                    list_Headers.append(list_Messages[index][10])
                index +=1
            #list_dataToSend.append(temp_dict)
            dict_statistics['HEADERS'] = list_Headers
            dict_statistics['ERRORMSG'] = 'NO ERROR'
            #dict_statistics['VALUES'] = listValues
            dict_statistics['Statistics'] = temp_dict
            #syslogstats = SysLogStats()
            syslogstats.setStats(dict_statistics)
            #AgentLogger.log(AgentLogger.UDP, 'Showing statistics dict: ' + repr(dict_statistics))

        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while creating statistics *************************** '+ repr(e))
            traceback.print_exc()
        return syslogstats
    


class SysLogParser(DesignUtils.Singleton):
    __pattern = None
    #__buffer = AgentBuffer.getBuffer(AgentConstants.SYS_LOG_BUFFER, AgentConstants.MAX_SIZE_OF_SYS_LOG_BUFFER)
    __buffer = []
    __defaultFilters = {}
    __customFilters = {}
    __filterGroups = {}
    def __init__(self):
        self.__setPattern()
        self.__loadFilters()
        
    def __setPattern(self):
        ints = Word(nums)
        # priority
        priority = Suppress("<") + ints + Suppress(">")
        # timestamp
        month = Word(string.ascii_uppercase, string.ascii_lowercase, exact=3)
        day   = ints
        hour  = Combine(ints + ":" + ints + ":" + ints)
        timestamp = month + day + hour
        # hostname
        hostname = Word(alphas + nums + "_" + "-" + ".")
        # appname
        appname = Word(alphas + nums + "/" + "-" + "_" + "." + ")" + "(" + "=") + Optional(Suppress("[") + ints + Suppress("]")) + Optional(Suppress(":"))
        # message
        message = Regex(".*")
        # pattern build
        self.__class__.__pattern = priority + timestamp + hostname + appname + message
    
    @property    
    def buffer(self):
        return self.__class__.__buffer
        
    @property
    def pattern(self):
        return self.__class__.__pattern
    
    def __loadFilters(self):
        try:
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(AgentConstants.AGENT_SYS_LOG_FILTERS_FILE)
            fileObj.set_dataType('json')
            fileObj.set_mode('rb')
            fileObj.set_dataEncoding('UTF-8')
            fileObj.set_loggerName(AgentLogger.UDP)
            fileObj.set_logging(False)
            bool_toReturn, dict_sysLogFilters = FileUtil.readData(fileObj)
            
            for filterName, value in dict_sysLogFilters['DefaultFilters'].items():
                filter = SysLogFilter(filterName)
                if 'priority' in value:
                    filter.priority = value['priority']
                if 'severity' in value:
                    filter.severity = value['severity'].split(',')
                if 'facility' in value:
                    filter.facility = value['facility'].split(',')
                if 'hostname' in value:
                    filter.hostname = value['hostname']
                if 'appname' in value:
                    filter.appname = value['appname']
                if 'message' in value:
                    filter.message = value['message']
                if 'time' in value:
                    filter.time = value['time']
                if 'count' in value:
                    filter.count = value['count']
                self.__class__.__defaultFilters[filterName] = filter
    
            for filterName, value in dict_sysLogFilters['CustomFilters'].items():
                if 'impl' in value:
                    dict_impl = self.getImpl()
                    if 'count' in value:
                        filter = dict_impl[value['impl']](filterName,value['count'])
                    else:
                        filter = dict_impl[value['impl']](filterName,1)
                    filter.impl = value['impl']
                else:
                    continue
                if 'priority' in value:
                    filter.priority = value['priority']
                if 'severity' in value:
                    filter.severity = value['severity'].split(',')
                if 'facility' in value:
                    filter.facility = value['facility'].split(',')
                if 'hostname' in value:
                    filter.hostname = value['hostname']
                if 'appname' in value:
                    filter.appname = value['appname']
                if 'message' in value:
                    filter.message = value['message']
                if 'time' in value:
                    filter.time = value['time']
                if 'count' in value:
                    filter.count = value['count']
                if 'rCount' in value:
                    filter.rCount = value['rCount']
                if 'lastAlertedTime' in value:
                    filter.lastAlertedTime = value['lastAlertedTime']
                if 'regex' in value:
                    filter.regex = value['regex']
                if 'clearence' in value:
                    filter.regex = int(value['clearence'])
                if 'timelimit' in value:
                    filter.timelimit = value['timelimit']
                self.__class__.__customFilters[filterName] = filter
            
            self.updateFilterGroups(dict_sysLogFilters)
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while loading syslog filters for first time *************************** '+ repr(e))
            traceback.print_exc()
    
    def checkSyslogData(self):
        return SYSLOGS_DATA
    
    def updateSyslogData(self,dictData):
        global SYSLOGS_DATA
        toDown = []
        try:
            if 'logrule' in SYSLOGS_DATA:
                for filterName, each_dict in SYSLOGS_DATA['logrule'].items():
                    if each_dict['status'] == 0:
                        each_dict['status'] = 1;
                        try:
                            del each_dict['msg']
                            del each_dict['time']
                            del each_dict['count']
                        except KeyError:
                            traceback.print_exc()
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while updating syslog checks data after upload *************************** '+ repr(e))
            traceback.print_exc()
    
    def reloadCustomFilters(self,listFilters):
        global SYSLOGS_DATA
        listFiltersToAdd = []
        listCustomFilters = []
        try:
            SYSLOGS_DATA = {}
            SYSLOGS_DATA.setdefault("logrule",{})
            for dict_filterDetails in listFilters:
                temp_dict = {}
                temp_dict['FilterName'] = dict_filterDetails['filter_name']
                SYSLOGS_DATA['logrule'].setdefault(str(dict_filterDetails['filter_name']),{"id":str(dict_filterDetails['id']),"status":1})
                if 'FACILITY' in dict_filterDetails:
                    str_facility = None
                    listFacilityLevels = dict_filterDetails['FACILITY']
                    for each_facilityLevel in listFacilityLevels :
                        if str_facility==None:
                            str_facility = str(each_facilityLevel)
                        else:
                            str_facility  += ',' + str(each_facilityLevel)
                    temp_dict['facility'] = str_facility
                    
                if 'SEVERITY' in dict_filterDetails:
                    str_severity = None
                    listSeverityLevels = dict_filterDetails['SEVERITY']
                    for each_severityLevel in listSeverityLevels :
                        if str_severity == None:
                            str_severity = str(each_severityLevel)
                        else:
                            str_severity  += ',' + str(each_severityLevel)
                    temp_dict['severity'] = str_severity
                
                if 'APPNAME' in dict_filterDetails:
                    temp_dict['appname'] = dict_filterDetails['APPNAME']
                
                if 'MESSAGE' in dict_filterDetails:
                    temp_dict['message'] =dict_filterDetails['MESSAGE']
                
                if'Count' in dict_filterDetails:
                    temp_dict['count'] = dict_filterDetails['Count']
                else:
                    temp_dict['count'] = 1
                    
                if 'regex' in temp_dict:
                    temp_dict['regex'] = dict_filterDetails['regex']
                
                if 'timelimit' in dict_filterDetails:
                    temp_dict['timelimit'] = dict_filterDetails['timelimit']
                
                if 'clearance' in dict_filterDetails:
                    temp_dict['clearance'] = dict_filterDetails['clearance']
                
                if 'rCount' in dict_filterDetails:
                    temp_dict['rCount'] = dict_filterDetails['rCount']
                    
                if 'lat' in dict_filterDetails:
                    temp_dict['lat'] = dict_filterDetails['lat']

                listFiltersToAdd.append(temp_dict)
                listCustomFilters.append(temp_dict['FilterName'])
                
            list_newFilterObjects = self.__toFilterObjectList(listFiltersToAdd)
            
            self.addAllFilters(list_newFilterObjects)
                
            self.updateSyslogFiltersFile(self.__filterObjectToDictionary(list_newFilterObjects),listCustomFilters)
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while creating list to reload checks as filters  *************************** '+ repr(e))
            traceback.print_exc() 
    
    def __toFilterObjectList(self,listFiltersToAdd):     
        list_filterObjects =[]
        try:
            AgentLogger.log(AgentLogger.UDP, '===========================Creating filter Object List============================= ' + repr(listFiltersToAdd) + ' --- ')
            for eachCustomFilter in self.__class__.__customFilters:
                filter = self.__class__.__customFilters[eachCustomFilter]
                AgentLogger.log(AgentLogger.UDP, ' Deleting Syslog Custom filter with filterName(id) as : ' + str(filter.filterName))
            self.__class__.__customFilters.clear()
            for each_filterToAdd in listFiltersToAdd:
                if 'count' in each_filterToAdd:
                    filter = CustomFilters(each_filterToAdd['FilterName'],each_filterToAdd['count'])
                else:
                    filter = CustomFilters(each_filterToAdd['FilterName'],1)
                if 'facility' in each_filterToAdd:
                    filter.facility = each_filterToAdd['facility']
                if 'severity' in each_filterToAdd:
                    filter.severity = each_filterToAdd['severity']
                if 'appname' in each_filterToAdd:
                    filter.appname = each_filterToAdd['appname']
                if 'message' in each_filterToAdd:
                    filter.message = each_filterToAdd['message']
                if 'count' in each_filterToAdd:
                    filter.count = int(each_filterToAdd['count'])
                if 'regex' in each_filterToAdd:
                    filter.regex = bool(each_filterToAdd['regex'])
                if (('timelimit' in each_filterToAdd) and (each_filterToAdd['timelimit'] is not None)):
                    filter.timelimit = int(each_filterToAdd['timelimit'])
                if 'clearence' in each_filterToAdd:
                    filter.clearence = int(each_filterToAdd['clearence'])
                if 'rCount' in each_filterToAdd:
                    filter.rCount = int(each_filterToAdd['rCount'])
                if 'lat' in each_filterToAdd:
                    filter.lastAlertedTime = int(each_filterToAdd['lat'])
                filter.impl = 'CustomFilter'
                list_filterObjects.append(filter)        
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while creating new filter object list*************************** '+ repr(e))
            traceback.print_exc()
        finally:
            return list_filterObjects
        
    def addAllFilters(self,list_filterObjects):
        for filter in list_filterObjects:
            self.__class__.__customFilters[filter.filterName] = filter
    
    def __filterObjectToDictionary(self,list_filterObjects):  
        try:
            
            dictToReturn = {}
            for filter in list_filterObjects:
                tempDict = {}
                tempDict['FilterName'] = filter.filterName
                if filter.facility:
                    tempDict['facility'] = filter.facility
                if filter.severity:
                    tempDict['severity'] = filter.severity
                if filter.appname:
                    tempDict['appname'] = filter.appname
                if filter.message:
                    tempDict['message'] = filter.message
                if filter.impl:
                    tempDict['impl'] = filter.impl
                if filter.count:
                    tempDict['count'] = filter.count
                if filter.regex:
                    tempDict['regex'] = filter.regex
                if filter.timelimit:
                    tempDict['timelimit'] = filter.timelimit
                if filter.clearence:
                    tempDict['clearence'] = filter.clearence
                dictToReturn.setdefault('NewFilters',{}).setdefault(filter.filterName, tempDict)
            AgentLogger.log(AgentLogger.UDP,'========New Filters to add :'+ str(dictToReturn))
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while creating dictionary for new filter object list *************************** '+ repr(e))
            traceback.print_exc()
        finally:
            return dictToReturn
        
    def updateSyslogFiltersFile(self,dictFilterDetails,listFilterNames):
        try:
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(AgentConstants.AGENT_SYS_LOG_FILTERS_FILE)
            fileObj.set_dataType('json')
            fileObj.set_mode('rb')
            fileObj.set_dataEncoding('UTF-8')
            fileObj.set_loggerName(AgentLogger.UDP)
            fileObj.set_logging(False)
            bool_toReturn, dict_sysLogFilters = FileUtil.readData(fileObj)
            dict_sysLogFilters['CustomFilters'] = {}
            dict_sysLogFilters['Filter Groups']['Custom'] = []
            if 'NewFilters' in dictFilterDetails :
                for filterName, filter in dictFilterDetails['NewFilters'].items():
                    dict_sysLogFilters['CustomFilters'].setdefault(filterName,filter)
                    dict_sysLogFilters['Filter Groups']['Custom'].append(filterName)
                AgentLogger.log([AgentLogger.UDP,AgentLogger.CHECKS],'======== Filters reloaded to file ===============')
            else:
                AgentLogger.log([AgentLogger.UDP,AgentLogger.CHECKS],'========No Syslog Filters to be added to file ===============')
            fileObj.set_data(dict_sysLogFilters)
            fileObj.set_mode('wb')
            bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
            self.updateFilterGroups(dict_sysLogFilters)
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP, AgentLogger.CHECKS, AgentLogger.STDERR], ' *************************** Exception while persisting Syslog checks/filter list  to conf file *************************** '+ repr(e))
            traceback.print_exc()
    
    #add all the impl details here
    def createImpl(self):
        FILTER_IMPL.setdefault('CustomFilter', handleCustomFilters)
        return FILTER_IMPL
    
    def getImpl(self):
        if FILTER_IMPL:
            return FILTER_IMPL
        else:
            return self.createImpl()
    
    def updateFilterGroups(self,dict_filterData):
        try:
            for filterGroupName, value in dict_filterData['Filter Groups'].items():
                filterGroup = SysLogFilterGroup(filterGroupName)
                if filterGroupName == 'Default':
                    filterGroup.filters = self.getFilters(value)
                if filterGroupName == 'Custom':
                    filterGroup.filters = self.getCustomFilters(value)
                self.__class__.__filterGroups[filterGroupName] = filterGroup
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while updating filter groups *************************** '+ repr(e))
            traceback.print_exc() 
            
    def addToBuffer(self, logMessage):
        if len(self.__buffer) == AgentConstants.MAX_SIZE_OF_SYS_LOG_BUFFER:
            self.persistLogMessages()
            #self.__buffer.clear()
            #self.__buffer.add(logMessage)
            self.__buffer[:] = []
            self.__buffer.append(logMessage)
        else:
            #self.__buffer.add(logMessage)
            self.__buffer.append(logMessage)
        #self.testQuery()
      
    def testQuery(self):
        query = SysLogQuery()
        query.startTime = AgentUtil.getCurrentTimeInMillis() - 3600*1000
        query.endTime = AgentUtil.getCurrentTimeInMillis()
        AgentLogger.log(AgentLogger.UDP,'Log messages : '+repr(self.getLogMessages(query)))
        
    def persistLogMessages(self):
        AgentLogger.log(AgentLogger.UDP, '================================ PERSISTING SYSLOG MESSAGES ================================')
        try:
            if len(self.__buffer) == 0:
                AgentLogger.log(AgentLogger.UDP, 'No Syslog messages found in buffer. Skipping persist operation.')
                return
            str_customName = str(self.__buffer[0][0])+'_'+str(self.__buffer[-1][0])
            str_fileName = FileUtil.getUniqueFileName(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'), str_customName, True)
            str_filePath = AgentConstants.AGENT_TEMP_SYS_LOG_DIR +'/'+str_fileName
            fileObj = AgentUtil.FileObject()
            fileObj.set_fileName(str_fileName)
            fileObj.set_filePath(str_filePath)
            fileObj.set_data(self.__buffer)
            fileObj.set_dataType('json')
            fileObj.set_mode('wb')
            fileObj.set_dataEncoding('UTF-8')
            fileObj.set_logging(False)
            fileObj.set_loggerName(AgentLogger.UDP)            
            bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while persisting syslog messages *************************** '+ repr(e))
            traceback.print_exc()
        
    def getLogMessageHeaders(self):
        return ['AgentTimeInMillis', 
                'AgentTimeInMillisWithTimeDiff', 
                'FormattedTime', 
                'Priority', 
                'Facility', 
                'Severity', 
                'Time', 
                'Host', 
                'Source', 
                'ProcessId', 
                'Message']
        
    def getLogMessages(self, query):      
        listToReturn = [self.getLogMessageHeaders()]  
        try:
            fileList = self.getLogFileList(query)
            fileObj = AgentUtil.FileObject()
            for filePath in fileList:
                if os.path.exists(filePath):
                    fileObj.set_filePath(filePath)
                    fileObj.set_dataType('json')
                    fileObj.set_mode('rb')
                    fileObj.set_dataEncoding('UTF-8')
                    fileObj.set_loggerName(AgentLogger.STDOUT)
                    fileObj.set_logging(False)
                    bool_toReturn, data = FileUtil.readData(fileObj)
                    for messageList in data:
                        if messageList[0] > query.startTime and messageList[0] < query.endTime:
                            listToReturn.append(messageList)
                else:
                    AgentLogger.log(AgentLogger.UDP,'Unable to get log messages from the file : '+repr(filePath))
            for messageList in self.__buffer:
                if messageList[0] > query.startTime and messageList[0] < query.endTime:
                    listToReturn.append(messageList)
            AgentLogger.log(AgentLogger.UDP, 'GET SYSLOG MESSAGES : Start time : '+str(query.startTime)+' --> '+repr(AgentUtil.getFormattedTime(query.startTime))+', End time : '+str(query.endTime)+' --> '+repr(AgentUtil.getFormattedTime(query.endTime))+', Syslog file list : '+repr(fileList)+', No. of log messages : '+repr(len(listToReturn)))
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while fetching log messages *************************** '+ repr(e))
            traceback.print_exc()
        return listToReturn
    
    def getLogFileList(self, query):
        fileListToReturn = []
        list_files = FileUtil.getSortedFileList(AgentConstants.AGENT_TEMP_SYS_LOG_DIR, str_loggerName=AgentLogger.UDP)
        for fileName in list_files:
            tempList = fileName.split('_')
            fileStartTime = tempList[1]
            fileEndTime = tempList[2][:-4]
            if int(fileStartTime) <= int(query.endTime) and int(query.startTime) <= int(fileEndTime):
                fileListToReturn.append(fileName)
        return fileListToReturn
 
    def getFilterGroups(self, list_filterGroupNames = None):
        dict_toReturn = {}
        if list_filterGroupNames == None :
            return self.__class__.__filterGroups
        for filterGroupName in list_filterGroupNames:
            dict_toReturn[filterGroupName] = self.__class__.__filterGroups[filterGroupName]
        return dict_toReturn
            
    def getFilters(self, list_filterNames):
        dict_toReturn = {}
        for filterName in list_filterNames:
            dict_toReturn[filterName] = self.__class__.__defaultFilters[filterName]
        return dict_toReturn
    
    def getCustomFilters(self, list_filterNames):
        dict_toReturn = {}
        for filterName in list_filterNames:
            dict_toReturn[filterName] = self.__class__.__customFilters[filterName]
        return dict_toReturn
    
    def applyFilters(self, rawMessage, list_filterGroupNames):
        logMessage = None
        filteredEvents = None
        try:
            filteredEvents = FilteredEvents()
            logMessage = SysLogMessage(rawMessage)
            dict_filterGroups = self.getFilterGroups(list_filterGroupNames)
            for filterGroupName, filterGroup in dict_filterGroups.items():
                for filterName, filter in filterGroup.filters.items():
                    filter.filter(logMessage, filteredEvents)
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while applying filters for the message : '+str(rawMessage)+' *************************** '+ repr(e))
            traceback.print_exc()
        finally:
            logMessage = None
        return filteredEvents
    
    def filterEvents(self, filterList):
        fileObj = None
        filteredEvents = FilteredEvents()
        try:
            fileObj = open(AgentConstants.AGENT_UDP_RAW_LOG_FILE, 'r')
            list_lines = fileObj.read().splitlines()
            for line in reversed(list_lines):
                parsedStr = line[line.find(' ::: ',line.find(' ::: '))+24:]
                logMessage = SysLogMessage(parsedStr)
                for filter in filterList:
                    filter.filter(logMessage, filteredEvents)
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR], ' *************************** Exception while filtering log messages for the criteria : '+str(filterList)+' *************************** '+ repr(e))
            traceback.print_exc()
        finally:
            if fileObj:
                fileObj.close()
        AgentLogger.log(AgentLogger.UDP, 'Filtered Events :  '+repr(filteredEvents.toJson()))
        return filteredEvents
    
    def editSyslogConfiguration(self):
        fileObj = None
        try:
            syslogExecutorObj = AgentUtil.Executor()
            syslogExecutorObj.setLogger(AgentLogger.STDOUT)
            syslogExecutorObj.setCommand(AgentConstants.AGENT_SYS_LOG_EXECUTABLE)
            syslogExecutorObj.executeCommand()
            AgentLogger.log(AgentLogger.UDP,"rsyslog enable command output: "+str(syslogExecutorObj.getStdOut()))
            if syslogExecutorObj.getStdErr():
                AgentLogger.log(AgentLogger.UDP,"rsyslog enable command error: "+str(syslogExecutorObj.getStdErr()))   
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR],' ************************* Problem while appending or inserting syslog entries to configuration file!!! ************************* '+ repr(e))
            traceback.print_exc()
        
    def deleteSyslogConfiguration(self):
        fileObj = None
        try:
            FileUtil.deleteFile(AgentConstants.AGENT_SYS_LOG_CONF_FILE)
            AgentLogger.log(AgentLogger.UDP,"Deleted syslog configuration file.")
            self.restartSyslogService()
        except Exception as e:
            AgentLogger.log([AgentLogger.UDP,AgentLogger.STDERR],' ************************* Problem while deleting syslog entries to configuration file!!! ************************* '+ repr(e))
            traceback.print_exc()
            
    def restartSyslogService(self):
        syslogExecutorObj = AgentUtil.Executor()
        syslogExecutorObj.setLogger(AgentLogger.STDOUT)
        syslogExecutorObj.setCommand(AgentConstants.AGENT_SYS_LOG_SERVICE_RESTART_COMMAND)
        syslogExecutorObj.executeCommand()        
        AgentLogger.log(AgentLogger.UDP,"Syslog service restart command output: "+str(syslogExecutorObj.getStdOut()))
        if syslogExecutorObj.getStdErr():
            AgentLogger.log(AgentLogger.UDP,"Syslog service restart command error: "+str(syslogExecutorObj.getStdErr()))