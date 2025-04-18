# $Id$
import socket, select, traceback
import errno
import json,re,copy
import six.moves.urllib
import six.moves.urllib.request as urlconnection
import time
import os
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser
import com
from com.manageengine.monagent.thirdPartyFile import pyinotify
from six.moves.urllib.parse import urlparse,urlencode
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentBuffer
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.communication import UdpHandler
from com.manageengine.monagent.util.AgentUtil import FileUtil, AGENT_CONFIG, FileZipAndUploadInfo
from com.manageengine.monagent.util import DesignUtils
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.actions import ScriptMonitoring
from com.manageengine.monagent.actions import NFSMonitoring
from com.manageengine.monagent.actions.NFSMonitoring import NFSHandler
from com.manageengine.monagent.framework.suite.helper import s247_commandexecutor
import threading


# Resource check codes > Port:4000, URL:1000, NFS:6000 Dir: 3000-4000, File: 2000-3000(unsure), syslog: 5000, ntp: 5002
POLLED_FILE_CHECKS = [2003,2005,3003,3006,3007]
LISTENER_FILE_CHECKS = [2001,2002,3001,3002,3004,3005]
WATCH_NAME_ID = {'access':[2001,3001], 'metadata':[2002,3002], 'modify':[2004], 'dir':[3005], 'file':[3004]}
PortUtil = None
URLUtil = None
NTPUtil = None
FileMonUtil = None
pathWdObject={}
globalDClock = threading.Lock()
customFileLock = threading.Lock()
defaultFileLock = threading.Lock()

CHECKS_CONFIG = configparser.RawConfigParser()

CHECKS_DATA = {}

def initialize():
    global FileMonUtil,CHECKS_CONFIG
    CHECKS_CONFIG.read(AgentConstants.AGENT_CHECKS_CONF_FILE)
    if AgentConstants.OS_NAME in AgentConstants.FILE_MON_SUPPORTED:
        FileMonUtil = FileHandler()
        FileMonUtil.start()
    else:
        AgentLogger.log(AgentLogger.CHECKS,'==== FILE MONITORING NOT SUPPORTED ====')
    
    if AgentConstants.OS_NAME in AgentConstants.NFS_MON_SUPPORTED:
        NFSMonitoring.NFSUtil = NFSHandler()
    else:
        AgentLogger.log(AgentLogger.CHECKS,'==== NFS NOT SUPPORTED ====')
    
def reload():
    try:
        global CHECKS_DATA
        CHECKS_DATA = {}
        AgentLogger.log(AgentLogger.CHECKS,'Port to be reloaded')
        PortUtil.reloadPorts()
        AgentLogger.log(AgentLogger.CHECKS,'NTP to be reloaded')
        NTPUtil.reloadNTP()
        AgentLogger.log(AgentLogger.CHECKS,'URL to be reloaded')
        URLUtil.reloadURLs()
        if AgentConstants.OS_NAME in AgentConstants.FILE_MON_SUPPORTED:
            AgentLogger.log(AgentLogger.CHECKS,'File to be reloaded')
            FileMonUtil.reloadDetails()
        AgentLogger.log(AgentLogger.CHECKS,'Script to be reloaded')
        ScriptMonitoring.ScriptUtil.reloadScripts()
        if AgentConstants.OS_NAME in AgentConstants.NFS_MON_SUPPORTED:
            AgentLogger.log(AgentLogger.CHECKS,'NFS to be reloaded') 
            NFSMonitoring.NFSUtil.reloadNFS()
        #AgentLogger.log(AgentLogger.CHECKS,'===================== Collecting checks data for instant notification ====================')
        checksMonitor()
    except Exception as e:
        AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while reloading configuration for checks monitoring *************************** '+ repr(e))
        traceback.print_exc()

def doNTPMonitoring(checks_dict):
    ntp_data={}
    try:
        ntp = NTP()
        ntp.setNTPDetails(checks_dict)
        statusChange, ntp_data = ntp.startNTPDataCollection()
        if 'State' in ntp_data and ntp_data['State']:
            if ntp_data['State'] == 'Up':
                ntp_data['st']=1
            else:
                ntp_data['st']=0
        AgentLogger.log(AgentLogger.CHECKS,' NTP Server : {} on which machine clock is checked /  Output : {} '.format(checks_dict['ntp'],json.dumps(ntp_data)))
    except Exception as e:
        pass
    return ntp_data 

def doPortMonitoring(checks_dict):
    port_data={}
    try:
        port = Port()
        port.setPortDetails(checks_dict)
        statusChange, port_data = port.startPortDataCollection()
        if 'State' in port_data and port_data['State']:
            if port_data['State'] == 'Up':
                port_data['st']=1
            else:
                port_data['st']=0
        AgentLogger.log(AgentLogger.CHECKS,' Port Number : {} /  Output : {} '.format(checks_dict['port'],json.dumps(port_data)))
    except Exception as e:
        pass
    return port_data 

def doURLMonitoring(checks_dict):
    url_data={}
    try:
        url = URL()
        url.setURLDetails(checks_dict)
        statusChange, url_data = url.startURLDataCollection()
        if 'STATE' in url_data and url_data['STATE']:
            if url_data['STATE'] == 'Up':
                url_data['st']=1
            else:
                url_data['st']=0
        AgentLogger.log(AgentLogger.CHECKS,' URL : {} /  Output : {} '.format(checks_dict['url'],json.dumps(url_data)))
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR], ' *************************** Exception while doing URL Monitoring *************************** '+ repr(e))
        traceback.print_exc()
    return url_data

def doFileandDirMonitoring(checks_dict):
    parent_dir=''
    file=''
    file_data = {}
    try:
        if 'pdir' in checks_dict:
            parent_dir = checks_dict['pdir']
        if 'dir' in checks_dict:
            parent_dir+= checks_dict['dir']
        if 'file' in checks_dict:
            parent_dir+= checks_dict['file']
        AgentLogger.log(AgentLogger.CHECKS,' file monitoring path =====> {0}'.format(parent_dir))
        if os.path.exists(parent_dir):
            file_data['st']=1
        else:
            file_data['st']=0
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR], ' *************************** Exception while doing URL Monitoring *************************** '+ repr(e))
        traceback.print_exc()
    return file_data

def instantNotification(checksData):
    listURLs = []
    listPorts = []
    listFiles = []
    listSyslogs = []
    listNFS = []
    listNTP = []
    dictData = {}
    try:
        if 'url' in checksData:
            for each_id in checksData['url']:
                tempDict = {}
                tempDict = dict(checksData['url'][each_id])
                tempDict['id'] = each_id
                listURLs.append(tempDict)
        dictData.setdefault('url',listURLs)
        if 'port' in checksData:
            for each_id in checksData['port']:
                tempDict = {}
                tempDict = dict(checksData['port'][each_id])
                tempDict['id'] = each_id
                listPorts.append(tempDict)
        dictData.setdefault('port',listPorts)
        if 'file' in checksData:
            for each_id in checksData['file']:
                tempDict = {}
                tempDict = dict(checksData['file'][each_id])
                tempDict['id'] = each_id
                listFiles.append(tempDict)
        dictData.setdefault('file',listFiles)
        if 'logrule' in checksData:
            for each_log in checksData['logrule']:
                tempDict = {}
                tempDict = dict(checksData['logrule'][each_log])
                listSyslogs.append(tempDict)
        dictData.setdefault('logrule',listSyslogs)
        if 'nfs' in checksData:
            for each_id in checksData['nfs']:
                tempDict = {}
                tempDict = dict(checksData['nfs'][each_id])
                tempDict['id'] = each_id
                listNFS.append(tempDict)
        dictData.setdefault('nfs',listNFS)
        if 'ntp' in checksData:
            for each_id in checksData['ntp']:
                tempDict = {}
                tempDict = dict(checksData['ntp'][each_id])
                tempDict['id'] = each_id
                listNTP.append(tempDict)
        dictData.setdefault('ntp',listNTP)
        uploadData(dictData,AgentConstants.RESOURCE_UPLOAD_PARAM)
        AgentLogger.log(AgentLogger.CHECKS,'dict Data for instant notification '+repr(dictData))
    except Exception as e:
        AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception in instant notification in checks monitoring *************************** '+ repr(e))
        traceback.print_exc()
    
def contentInstantNotify(contentData):
    global CHECKS_DATA
    try:
        with customFileLock:
            if 'file' in CHECKS_DATA:
                for id in contentData:
                    if int(id) in CHECKS_DATA['file']:
                        CHECKS_DATA['file'][int(id)] = contentData[id]
                instantNotification(CHECKS_DATA)
                AgentLogger.log(AgentLogger.CHECKS,'After uploading instant notification for : CONTENT CHECK global checks data is : ' + str(json.dumps(CHECKS_DATA)))
    except Exception as e:
        AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while content instant notification in checks monitoring *************************** '+ repr(e))
        traceback.print_exc()
            
def sendSysLogInstantNotif(dictSysLogData):
    try:
        global CHECKS_DATA
        CHECKS_DATA['logrule'] = dictSysLogData['logrule']
        AgentLogger.log(AgentLogger.CHECKS,'Syslog instant data updated in checks ' + str(CHECKS_DATA['logrule']))
        instantNotification(CHECKS_DATA)
    except Exception as e:
        AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while uploading data for syslog instant notification *************************** '+ repr(e))
        traceback.print_exc()

def fileInstantNotify(instantData):
    try:
        global CHECKS_DATA
        checksDataCopy = {}
        with customFileLock:
            checksDataCopy = copy.deepcopy(CHECKS_DATA)
            if 'file' in checksDataCopy and int(instantData['id']) in checksDataCopy['file']:
                checksDataCopy['file'][int(instantData['id'])]['status'] = 0
                if 'file' in instantData:
                    checksDataCopy['file'][int(instantData['id'])]['files'] = [instantData['file']]
                    checksDataCopy['file'][int(instantData['id'])]['count'] = 1
                AgentLogger.debug(AgentLogger.CHECKS,'Before uploading instant notification for : ' + str(json.dumps(checksDataCopy)) + ' global checks data is : ' + str(json.dumps(CHECKS_DATA)))
                instantNotification(checksDataCopy)
    except Exception as e:
        AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while file instant notification in checks monitoring *************************** '+ repr(e))
        traceback.print_exc()   

def checksMonitor():
    if AgentUtil.is_module_enabled(AgentConstants.RESOURCE_CHECK_SETTING):
        toUpdate = False
        try:
            fileData1 = None
            fileData2 = None
            NFSData = None
            AgentLogger.log(AgentLogger.CHECKS,'================================= COLLECTING DATA FOR THE GROUP : ChecksMonitoring =================================')
            global CHECKS_DATA
            fileData = {}
            dirData = {}
            portData = PortUtil.checkPortStatus()
            urlData = URLUtil.checkURLStatus()
            NTPData = NTPUtil.checkNTPStatus()
            if AgentConstants.OS_NAME in AgentConstants.FILE_MON_SUPPORTED:
                FileMonUtil.reloadDetails()
                fileData1, fileData2 = FileMonUtil.checkFileStatus()
                fileData1.update(fileData2)
            sysLogData = UdpHandler.SysLogUtil.checkSyslogData()
            scriptData = ScriptMonitoring.ScriptUtil.checkScriptDC()
            if scriptData:
                AgentLogger.log(AgentLogger.CHECKS,'Script Data ===> '+repr(json.dumps(scriptData)))
            if AgentConstants.OS_NAME in AgentConstants.NFS_MON_SUPPORTED:
                NFSData = NFSMonitoring.NFSUtil.checkNFSDC()
                if NFSData:
                    AgentLogger.log(AgentLogger.CHECKS,'NFS Data ====> '+repr(json.dumps(NFSData)))
            with globalDClock:
                if urlData:
                    toUpdate = True
                    if 'url' in CHECKS_DATA:
                        CHECKS_DATA['url'] = urlData
                    else:
                        CHECKS_DATA.setdefault('url',urlData)
                if portData:
                    toUpdate = True
                    if 'port' in CHECKS_DATA:
                        CHECKS_DATA['port'] = portData
                    else:
                        CHECKS_DATA.setdefault('port',portData)
                if NTPData:
                    toUpdate = True
                    if 'ntp' in CHECKS_DATA:
                        CHECKS_DATA['ntp'] = NTPData
                    else:
                        CHECKS_DATA.setdefault('ntp',NTPData)
                if sysLogData:
                    if 'logrule' in CHECKS_DATA:
                        CHECKS_DATA['logrule'] = sysLogData['logrule']
                    else:
                        CHECKS_DATA.setdefault('logrule',sysLogData['logrule'])
                if fileData1:
                    if 'file' in CHECKS_DATA:
                        CHECKS_DATA['file'] = fileData1
                    else:
                        CHECKS_DATA.setdefault('file',fileData1)
                if scriptData:
                    if 'script' in CHECKS_DATA:
                        CHECKS_DATA['script'] = scriptData
                    else:
                        CHECKS_DATA.setdefault('script',scriptData)
                if NFSData:
                    toUpdate=True
                    if 'nfs' in CHECKS_DATA:
                        CHECKS_DATA['nfs'] = NFSData
                    else:
                        CHECKS_DATA.setdefault('nfs',NFSData)
                if CHECKS_DATA:
                    AgentLogger.log(AgentLogger.CHECKS,'CHECKS DATA is '+repr(CHECKS_DATA))
            if toUpdate:
                instantNotification(CHECKS_DATA)
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while checking returning data to data consolidator in checks monitoring *************************** '+ repr(e))
            traceback.print_exc()
        
def uploadData(dictData,str_action):
    dict_requestParameters = {}
    dir_prop = AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['011']
    try:
        AgentUtil.get_default_param(dir_prop,dict_requestParameters,str_action)
        str_servlet = AgentConstants.SERVER_INSTANT_NOTIFIER_SERVLET
        str_requestParameters = urlencode(dict_requestParameters)
        str_url = str_servlet + str_requestParameters
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.CHECKS)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.set_timeout(30)
        str_jsonData = json.dumps(dictData)#python dictionary to json string
        requestInfo.set_data(str_jsonData)
        requestInfo.add_header("Content-Type", 'application/json')
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        bool_isSuccess, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
        CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'FILE UPLOADER')
        AgentLogger.log(AgentLogger.CHECKS,'[ Upload instant data ] '+repr(str_jsonData))
        if bool_isSuccess:
            AgentLogger.log([AgentLogger.STDOUT], 'Successfully posted the instant JSON data to the server')
            dictUploadedData = json.loads(str_jsonData)
            if AgentConstants.CHECKS_VERIFY_TEXT in dictUploadedData:
                AgentLogger.debug(AgentLogger.STDOUT, 'Changing status after instant notification')
                URLUtil.updateURLStatus(dictUploadedData)
                PortUtil.updatePortStatus(dictUploadedData)
                NTPUtil.updateNTPStatus(dictUploadedData)
                if 'logrule' in dictUploadedData:
                    UdpHandler.SysLogUtil.updateSyslogData(dictUploadedData)
                '''elif AgentConstants.PORT_VERIFY_TEXT in dictUploadedData:
                        BasicClientHandler.PortUtil.updatePortStatus(dictUploadedData)'''
        else:
            AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDOUT], '************************* Unable to post the instant JSON data to the server. ************************* \n')
            CommunicationHandler.checkNetworkStatus(AgentLogger.STDOUT)

    except Exception as e:
        AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while checking setting upload details for checks monitoring *************************** '+ repr(e))
        traceback.print_exc()

class File():
    def __init__(self):
        self._check_id = None
        self._check_type = None
        self._fileName = None
        self._timeout = AgentConstants.DEFAULT_FILE_CHECK_TIMEOUT
        self._path = None
        self._string = None
        self._modify = None
        self._threshold = None
        self._interval = 300
        #self._lastDC = None
        self._mask = None
        self._watch = None
        self._event = None
        self.fileList = None
        self._previousFile = {} #Previous Data collection results of each file for the content check type
        self._wrongPath = False
        self._noFile = False
        self._search_level = '1'
        
    def getFileList(self):
        return self.fileList
    
    def setFileList(self,listFiles):
        self.fileList = listFiles
    
    def setFileDetails(self,fileDetails):
        try:
            self._check_id = int(fileDetails['id'])
            self._check_type = int(fileDetails['ctype'])
            if self._check_type in (AgentConstants.FILE_ACCESS_CHECK, AgentConstants.FILE_META_CHECK, AgentConstants.FILE_MODIFY_CHECK):
                self._mask = pyinotify.IN_ACCESS|pyinotify.IN_ATTRIB|pyinotify.IN_MODIFY
            elif self._check_type in (AgentConstants.DIRECTORY_SUBDIR_CHECK, AgentConstants.DIRECTORY_FILE_CHECK, AgentConstants.DIRECTORY_ACCESS_CHECK, AgentConstants.DIRECTORY_META_CHECK):
                self._mask = pyinotify.IN_CREATE|pyinotify.IN_DELETE|pyinotify.IN_ACCESS|pyinotify.IN_ATTRIB
                if 'event' in fileDetails:
                    self._event = fileDetails['event']        
            setPath = fileDetails['pdir'].rstrip('/')
            self._path = setPath
            if 'poll_interval' in fileDetails:
                self._interval = int(fileDetails['poll_interval'])
            if 'file' in fileDetails:
                self._fileName = fileDetails['file']
            if 'dir' in fileDetails:
                self._fileName = fileDetails['dir']
            if 'watch' in fileDetails:
                self._watch = fileDetails['watch']
            if 'search' in fileDetails:
                self._string = fileDetails['search']
            if 'timelimit' in fileDetails and fileDetails['timelimit'] != -1:
                self._timeout = int(fileDetails['timelimit'])
            if 'threshold' in fileDetails:
                self._threshold = int(fileDetails['threshold'])
            if 'searchLevel' in fileDetails:
                self._search_level = str(fileDetails['searchLevel'])
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while setting file/directory monitor details *************************** '+ repr(e))
            traceback.print_exc()
    
    def previousDataCollection(self,each_file):
        boolProceed = False
        try:
            # PMT is previous modified time, PLN is previous line number and PIN is previous inode number
            if os.path.isfile(each_file):
                if os.path.exists(AgentConstants.PREVIOUS_FILE_OBJ_FILE):
                    with open(AgentConstants.PREVIOUS_FILE_OBJ_FILE, 'r') as fobj:
                        AgentConstants.PREVIOUS_FILE_OBJ = json.load(fobj)
                if ((AgentConstants.PREVIOUS_FILE_OBJ) and (each_file in AgentConstants.PREVIOUS_FILE_OBJ)):
                    pmt = AgentConstants.PREVIOUS_FILE_OBJ[each_file]['PMT']
                    if 'PLN' in AgentConstants.PREVIOUS_FILE_OBJ[each_file]:
                        pln = AgentConstants.PREVIOUS_FILE_OBJ[each_file]['PLN']
                    else:
                        boolProceed = False
                        return boolProceed
                    pin = AgentConstants.PREVIOUS_FILE_OBJ[each_file]['PIN']
                    st = os.stat(each_file)
                    cin = st.st_ino
                    cmt = st.st_mtime
                    if (cmt > pmt and cin == pin):
                        AgentConstants.PREVIOUS_FILE_OBJ[each_file]['PMT'] = cmt
                        try:
                            line_no = AgentUtil.get_line_count_of_a_file(each_file)
                            if line_no < AgentConstants.PREVIOUS_FILE_OBJ[each_file]['PLN']:
                                AgentConstants.PREVIOUS_FILE_OBJ[each_file]['PLN'] = 0
                                AgentLogger.log(AgentLogger.CHECKS,'line no reduces')
                        except:
                            AgentLogger.log(AgentLogger.CHECKS,'something wrong with file')
                        AgentLogger.log(AgentLogger.CHECKS,'file modified but same file '+repr(AgentConstants.PREVIOUS_FILE_OBJ[each_file])+ ' file name '+repr(each_file))
                        boolProceed = True
                    elif (cmt > pmt and cin != pin):
                        AgentConstants.PREVIOUS_FILE_OBJ[each_file]['PMT'] = cmt
                        AgentConstants.PREVIOUS_FILE_OBJ[each_file]['PIN'] = cin
                        AgentLogger.log(AgentLogger.CHECKS,'file modified and inode changes, different file '+repr(AgentConstants.PREVIOUS_FILE_OBJ[each_file])+ ' file name '+repr(each_file))
                        boolProceed = True
                else:
                    st = os.stat(each_file)
                    AgentConstants.PREVIOUS_FILE_OBJ.setdefault(each_file,{})
                    AgentConstants.PREVIOUS_FILE_OBJ[each_file]['PMT'] = st.st_mtime
                    AgentConstants.PREVIOUS_FILE_OBJ[each_file]['PIN'] = st.st_ino
                    AgentConstants.PREVIOUS_FILE_OBJ[each_file]['PLN'] = 1
                    AgentLogger.log(AgentLogger.CHECKS,'initializing previous file details'+repr(AgentConstants.PREVIOUS_FILE_OBJ[each_file])+ ' file name '+repr(each_file))
                    boolProceed = True
            else:
                AgentLogger.log(AgentLogger.CHECKS,'File does not exists '+repr(each_file))
                boolProceed = False
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while setting file/directory monitor details *************************** '+ repr(e))
            traceback.print_exc()
        finally:
            return boolProceed
    
    def contentCheck(self,fileList,listData):
        try:
            for each_file in fileList:
                proceed = self.previousDataCollection(each_file)
                action = AgentConstants.CONTENT_CHECK
                out_line = None
                if proceed:
                    tempDict = {}
                    tempDict[os.path.basename(each_file)] = []
                    for value in self._string:
                        command_file = '"'+each_file+'"'
                        command = AgentConstants.AGENT_FILE_MONITORING_SCRIPT + ' ' + action + ' ' + command_file +' '+'"'+value['searchstr']+'"'+' '+str(value['casesensitive']) + ' ' + str(AgentConstants.PREVIOUS_FILE_OBJ[each_file]['PLN']) + ' ' + str(value['max'])
                        returnValue, error = self.scriptExe(command)
                        tempDetails = {}
                        lineDetails = []
                        match_no = 0
                        AgentLogger.debug(AgentLogger.CHECKS, "Content check command [{}] | Return [{}] ".format(command, repr(returnValue)))
                        if returnValue != None:
                            if returnValue == '-1\n':
                                AgentLogger.log(AgentLogger.CHECKS,'error in content check command execution for '+repr(self._check_id))
                            else:
                                out_line = returnValue.split('\n')
                                if out_line[0] != 'None':
                                    lineDetails = out_line[0].split(':',1)
                                    tempDetails['searchstr'] = value['searchstr']
                                    tempDetails['linecount'] = int(lineDetails[0]) + AgentConstants.PREVIOUS_FILE_OBJ[each_file]['PLN']
                                    tempDetails['content'] = lineDetails[1][0:50]
                                    tempDict[os.path.basename(each_file)].append(tempDetails)
                        else:
                            AgentLogger.log(AgentLogger.CHECKS,'Command execution time exceeds the limit in content check')
                    if out_line:
                        AgentConstants.PREVIOUS_FILE_OBJ[each_file]['PLN'] = int(out_line[1])
                        with open(AgentConstants.PREVIOUS_FILE_OBJ_FILE, 'w') as f:
                            f.write(json.dumps(AgentConstants.PREVIOUS_FILE_OBJ))
                    if tempDict[os.path.basename(each_file)]:
                        listData.append(tempDict)
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while performing content check *************************** '+ repr(e))
            traceback.print_exc()

    def sizeCheckFile(self,fileList,listData):
        try:
            if fileList:
                for each_file in fileList:
                    temp = self.sizeCheck(each_file,self._threshold)
                    if temp:
                        listData.append(temp)
            else:
                temp = self.sizeCheck(self._path,self._threshold)
                if temp:
                    listData.append(temp)
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while performing size check *************************** '+ repr(e))
            traceback.print_exc()

    def modifyCheck(self,fileList,listData):
        try:
            for each_file in fileList:
                tempdict = {}
                action = AgentConstants.LAST_MODIFICATION_CHECK
                command_file = '"'+each_file+'"'
                command = AgentConstants.AGENT_FILE_MONITORING_SCRIPT + ' ' + action + ' ' + command_file + ' ' + str(self._threshold)
                returnValue,error = self.scriptExe(command)
                if returnValue != None:
                    returnValue = returnValue.rstrip('\n')
                    if returnValue == each_file:
                        listData.append(os.path.basename(each_file))
                else:
                    AgentLogger.log(AgentLogger.CHECKS,'Command execution time exceeds the limit in last modification check')
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while performing size check *************************** '+ repr(e))
            traceback.print_exc()

    def fileDataCollection(self):
        listData = []
        try:
            fileList = self.fileList
            if self._check_type == AgentConstants.FILE_CONTENT_CHECK and fileList:
                self.contentCheck(fileList, listData)
            elif self._check_type in (AgentConstants.FILE_SIZE_CHECK, AgentConstants.DIRECTORY_SIZE_CHECK):
                self.sizeCheckFile(fileList,listData)
            elif self._check_type == AgentConstants.FILE_MODIFY_CHECK and fileList:
               self.modifyCheck(fileList,listData)
            elif self._check_type in [AgentConstants.FILE_COUNT_CHECK,AgentConstants.DIR_COUNT_CHECK]:
                self.file_dir_count_check(self._check_type,self._path,self._threshold,listData,self._search_level)
            return listData
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while collecting polled file/directory monitor details *************************** '+ repr(e))
            traceback.print_exc()
    
    def file_dir_count_check(self,check_type,file_or_dir,threshold,listData,search_level):
        tempdict = []
        count = 0
        action = AgentConstants.FILECOUNT_CHECK if check_type==3006 else AgentConstants.DIRCOUNT_CHECK
        command_file = '"'+file_or_dir+'"'
        command = AgentConstants.AGENT_FILE_MONITORING_SCRIPT + ' ' + action + ' ' + command_file + ' ' + search_level
        returnValue,error = self.scriptExe(command)
        AgentLogger.debug(AgentLogger.CHECKS,'command for file / dir count check -- {} return value --  {}'.format(command,returnValue))
        if returnValue != None:
            if returnValue == '-1\n':
                AgentLogger.log(AgentLogger.CHECKS,'error in command execution in size Check '+repr(self._check_id))
                return None
            else:
                try:
                    count = int(returnValue)
                except ValueError:
                    count = float(returnValue)
                if (count) > threshold:
                    listData.append(file_or_dir)
                else:
                    return None
        else:
           AgentLogger.log(AgentLogger.CHECKS,'Command execution time exceeds the limit in size check')
           return None
    
    
    def sizeCheck(self,each_file,threshold):
        tempdict = []
        size = 0
        action = AgentConstants.FILESIZE_CHECK
        command_file = '"'+each_file+'"'
        command = AgentConstants.AGENT_FILE_MONITORING_SCRIPT + ' ' + action + ' ' + command_file
        AgentLogger.debug(AgentLogger.CHECKS,'command for file size check -- {}'.format(command))
        returnValue,error = self.scriptExe(command)
        if returnValue != None:
            if returnValue == '-1\n':
                AgentLogger.log(AgentLogger.CHECKS,'error in command execution in size Check '+repr(self._check_id))
                return None
            else:
                try:
                    size = int(returnValue)
                except ValueError:
                    size = float(returnValue)
                if (size*1024) > threshold:
                    #AgentLogger.log(AgentLogger.CHECKS,'threshold crossed')
                    return os.path.basename(each_file.rstrip('/'))
                else:
                    return None
        else:
           AgentLogger.log(AgentLogger.CHECKS,'Command execution time exceeds the limit in size check')
           return None 
    
    def scriptExe(self,command):
        executorObj = AgentUtil.Executor()
        executorObj.setLogger(AgentLogger.CHECKS)
        executorObj.setTimeout(self._timeout)
        executorObj.setCommand(command)
        executorObj.executeCommand()
        output = executorObj.getStdOut()
        error = executorObj.getStdErr()
        return output,error

class FileHandler(threading.Thread):
    _files={}
    _polledFiles = {}
    _lock = threading.Lock()
    ACTIVE_WATCHES = {}
    WRONG_WATCHES = []
    wm = None
    wd = None
    _mask = pyinotify.ALL_EVENTS
    def __init__(self):
        threading.Thread.__init__(self)
        self._mask=pyinotify.ALL_EVENTS
        self.wm=pyinotify.WatchManager()
        self.wd=0
        
    def run(self):
        try:
            handler=EventHandler()
            notifier=pyinotify.Notifier(self.wm,handler)
            AgentLogger.log(AgentLogger.CHECKS,'Pyinotify started')
            self._loadCustomFileDetails()
            notifier.loop()
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while starting pyinotify in checks monitoring *************************** '+ repr(e))
            traceback.print_exc()
    
    def addWatch(self,path,mask=None):
        if mask:
            wd=self.wm.add_watch(path,mask,rec=False)
        else:
            wd=self.wm.add_watch(path,self._mask,rec=False)
        
        AgentLogger.log(AgentLogger.CHECKS,'add watch is started for mask '+repr(mask)+' with wds '+repr(wd))
        return wd
    
    def removeWatch(self,wd):
        AgentLogger.log(AgentLogger.CHECKS,'Request to remove the watch for '+repr(wd))
        checkStatus=self.wm.rm_watch(wd)
        AgentLogger.log(AgentLogger.CHECKS,'Watch removed status '+repr(checkStatus))
        
    def getWatch(self,wd):
        watch=self.wm.get_watch(wd)
        return watch
    
    def deleteAll(self):
        try:
            for each_id in self.ACTIVE_WATCHES:
                for each_wd in self.ACTIVE_WATCHES[each_id]:
                    wd = each_wd['wd']
                    if self.getWatch(wd):
                        self.removeWatch(wd)
                    AgentLogger.log(AgentLogger.CHECKS,'Deleting File/Directory check with wd:'+repr(wd))
                    del wd
            self.ACTIVE_WATCHES.clear()
            self.__class__._files.clear()
            pathWdObject.clear()
            for each_file in self.__class__._polledFiles:
                file = self.__class__._polledFiles[each_file]
                AgentLogger.log(AgentLogger.CHECKS,'Deleting File/Directory check with check_type:'+repr(file._check_type))
            self.__class__._polledFiles.clear()
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' FileError | *************************** Exception while deleting File/Directory checks *************************** '+ repr(e))
            traceback.print_exc()
            
    def reloadDetails(self):
        with self._lock:
            self.deleteAll()
        self._loadCustomFileDetails()
    
    def fileListDetails(self,each_file):
        listFiles = []
        listFilesToAdd = None
        is_valid = None
        status = None
        try:
            filesFound = False
            listFilesToAdd = []
            try:
                re.compile(each_file['file'])
                is_valid = True
            except re.error:
                is_valid = False
            if is_valid:
                if os.path.exists(each_file['pdir'].rstrip('/')):
                    listFiles = os.listdir(each_file['pdir'])
                    for f in listFiles:
                        mo = re.search(each_file['file'],f)
                        if mo:
                            if os.path.exists(each_file['pdir'].rstrip('/') + '/' + f) and os.path.isfile(each_file['pdir'].rstrip('/') + '/' + f):
                                if not (f[-1] == '~'  and f[:-1] in listFiles):
                                    filesFound = True
                                    listFilesToAdd.append(each_file['pdir'].rstrip('/') + '/' + f)
                    if filesFound:
                        status = True
                    else:
                        status = 'no_file'
            else:
                status = 're_error'
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' FileError | *************************** Exception while making list of files *************************** '+ repr(e))
            traceback.print_exc()
        return status, listFilesToAdd
    
    def _loadCustomFileDetails(self):
        tempDict = None
        try:
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(AgentConstants.AGENT_CUSTOM_MONITORS_GROUP_FILE)
            fileObj.set_dataType('json')
            fileObj.set_mode('rb')
            fileObj.set_dataEncoding('UTF-8')
            fileObj.set_loggerName(AgentLogger.CHECKS)
            fileObj.set_logging(False)
            bool_toReturn, dict_monitorsInfo = FileUtil.readData(fileObj)
            with self._lock:
                for each_file in dict_monitorsInfo['MonitorGroup']['ChecksMonitoring']['FileDirectory']:
                    file = File()
                    file.setFileDetails(each_file)
                    listFiles = []
                    pathToWatch = []
                    status = None
                    if not os.path.exists(each_file['pdir'].rstrip('/')):
                        AgentLogger.log(AgentLogger.CHECKS,'Path is wrong for this check id '+repr(each_file['id']))
                        file._wrongPath = True
                    if ('file' in each_file) and (int(each_file['ctype']) not in (3004,3005)):
                        status, listFiles = self.fileListDetails(each_file)
                        if status in ('re_error', 'no_file'):
                            AgentLogger.log(AgentLogger.CHECKS,'No file found for this check id '+repr(each_file['id']))
                            file._noFile = True
                    if (int(each_file['ctype']) in LISTENER_FILE_CHECKS) or (int(each_file['ctype']) == 2004 and each_file['modify']=='m'):
                        if file._wrongPath or file._noFile:
                            self.WRONG_WATCHES.append(int(each_file['id']))
                            self.__class__._files[each_file['id']] = file
                            continue
                        if listFiles:
                            file.setFileList(listFiles)
                            pathToWatch = listFiles
                        else:
                            pathToWatch = each_file['pdir'].rstrip('/')
                        if pathToWatch:
                            if file._mask:
                                wds = self.addWatch(pathToWatch,file._mask)
                            else:
                                wds = self.addWatch(pathToWatch)
                            for path, wd in wds.items():
                                eventObject = EventHistory(path,each_file['id'],each_file['ctype'])
                                if wd > 0:
                                    if wd not in pathWdObject:
                                        pathWdObject[wd]={}
                                    if each_file['id'] not in pathWdObject[wd]:
                                        pathWdObject[wd][each_file['id']] = eventObject
                                        if each_file['id'] not in self.ACTIVE_WATCHES:
                                            self.ACTIVE_WATCHES.setdefault(int(each_file['id']),[])
                                        tempDict = {}
                                        tempDict['wd'] = wd
                                        tempDict['file_path'] = path
                                        st = os.stat(path)
                                        cin = st.st_ino
                                        tempDict['inode'] = cin
                                        self.ACTIVE_WATCHES[int(each_file['id'])].append(tempDict)
                                        self.__class__._files[each_file['id']] = file
                                    else:
                                        AgentLogger.log(AgentLogger.CHECKS,'same path on same id')
                                else:
                                    AgentLogger.log(AgentLogger.CHECKS,' FileError | Negative wd for path : ' + str(path))
                        else:
                            AgentLogger.log(AgentLogger.CHECKS,'No path to watch for check id '+repr(each_file['id']))
                    elif (int(each_file['ctype']) in POLLED_FILE_CHECKS) or (int(each_file['ctype']) == 2004 and each_file['modify']=='n'):
                        if listFiles:
                            file.setFileList(listFiles)
                        self.__class__._polledFiles[each_file['id']] = file
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' FileError | *************************** Exception while loading custom File/Directory checks *************************** '+ repr(e))
            traceback.print_exc()
    
    def checkFileStatus(self):
        dictDataToSend = {}
        dictDataToSendPolled = {}
        tempDict = None
        tempDetails = None
        contentData = {}
        try:
            with self._lock:
                for fileName, file in self.__class__._polledFiles.items():
                    tempDict = []
                    tempDetails = {}
                    if file._wrongPath:
                        tempDetails['status'] = 0
                        tempDetails['er'] = 1000
                    elif file._noFile:
                        tempDetails['status'] = 0
                        tempDetails['er'] = 2000
                    else:
                        tempDict = file.fileDataCollection()
                        if file._check_type == 2005:
                            if tempDict:
                                tempDetails['status'] = 0
                                tempDetails['files'] = []
                                tempDetails['count'] = len(tempDict)
                                tempDict = tempDict[0:3]
                                for details in tempDict:
                                    for key,value in details.items():
                                        tempDetails['files'].append(key)
                                        tempDetails[key] = value
                                contentData[file._check_id] = tempDetails
                            else:
                                tempDetails['status'] = 1
                        else:
                            if tempDict:        
                                tempDetails['status'] = 0
                                if file._check_type not in (3003,3006,3007):
                                    tempDetails['count'] = len(tempDict)
                                    tempDetails['files'] = tempDict[0:3]
                            else:        
                                tempDetails['status'] = 1
                    dictDataToSendPolled[file._check_id] = tempDetails
                for fileName, file in self.__class__._files.items():
                    tempList = []
                    tempDetails = {}
                    if file._check_id in self.ACTIVE_WATCHES:
                        temp_activeWatch = list(self.ACTIVE_WATCHES[file._check_id])
                        for each_dict in temp_activeWatch:
                            wdc = each_dict['wd']
                            inode = None
                            if os.path.exists(each_dict['file_path']) and file._check_type in (2001,2002,2004):
                                st = os.stat(each_dict['file_path'])
                                inode = st.st_ino
                            if inode and inode != each_dict['inode'] and file._check_type in (2001,2002,2004):
                                watchDetails = self.getWatch(wdc)
                                if watchDetails:
                                    self.removeWatch(wdc)
                        #if watchDetails is None and os.path.exists(each_dict['file_path']) and file._check_type in (2001,2002,2004):
                                if file._check_type == 2004:
                                    path = each_dict['file_path']
                                    tempModify = {}
                                    command = AgentConstants.AGENT_FILE_MONITORING_SCRIPT + ' ' + 'modification' + ' ' + path
                                    returnValue,error = file.scriptExe(command)
                                    if returnValue == '':
                                        tempModify['LAST_UPDATED'] = None
                                    else:
                                        try:
                                            tempModify['LAST_UPDATED'] = int(returnValue)
                                        except ValueError:
                                            tempModify['LAST_UPDATED'] = float(returnValue)
                                    tempModify['EVENT_TYPE'] = 'modify'
                                    tempModify['FILE_NAME'] = path
                                    if tempModify['LAST_UPDATED']:
                                        tempList.append(path)
                                ind = self.ACTIVE_WATCHES[file._check_id].index(each_dict)
                                del self.ACTIVE_WATCHES[file._check_id][ind]
                                if wdc in pathWdObject:
                                    del pathWdObject[wdc]
                                if os.path.exists(each_dict['file_path']):
                                    AgentLogger.log(AgentLogger.CHECKS,'change in inode,starting watch')
                                    if file._check_type in (2001,2002,2004):
                                        wd = self.addWatch(each_dict['file_path'], pyinotify.IN_ACCESS|pyinotify.IN_ATTRIB|pyinotify.IN_MODIFY)
                                    for path_new, wd_new in wd.items():
                                        eventObject = EventHistory(path_new,str(file._check_id),file._check_type)
                                        if wd_new not in pathWdObject:
                                            pathWdObject[wd_new]={}
                                        if file._check_id not in pathWdObject[wd_new]:
                                            pathWdObject[wd_new][str(file._check_id)] = eventObject
                                            if file._check_id not in self.ACTIVE_WATCHES:
                                                self.ACTIVE_WATCHES.setdefault(int(file._check_id),[])
                                            temp_new = {}
                                            temp_new['wd'] = wd_new
                                            temp_new['file_path'] = path_new
                                            temp_new['inode'] = inode
                                            self.ACTIVE_WATCHES[int(file._check_id)].append(temp_new)
                                        else:
                                            AgentLogger.log(AgentLogger.CHECKS,'same path on same id')
                            else:
                                temp = pathWdObject[wdc][str(file._check_id)].getHistory()
                                if temp:
                                    tempList.append(temp)
                        if tempList:        
                            tempDetails['status'] = 0
                            if file._check_type not in (3001,3002):
                                tempDetails['count'] = len(tempList)
                                tempDetails['files'] = tempList[0:3]        
                        else:        
                            tempDetails['status'] = 1
                        dictDataToSend[file._check_id] = tempDetails
                    elif file._check_id in self.WRONG_WATCHES:
                        tempDetails = {}
                        if file._wrongPath:
                            tempDetails['status'] = 0
                            tempDetails['er'] = 1000
                        elif file._noFile:
                            tempDetails['status'] = 0
                            tempDetails['er'] = 2000
                        dictDataToSend[file._check_id] = tempDetails
            if contentData:
                contentInstantNotify(contentData)
            return dictDataToSendPolled, dictDataToSend
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' FileError | *************************** Exception while checking file status *************************** '+ repr(e))
            traceback.print_exc()
        
class NTP:
    def __init__(self):
        self._check_id = None
        self._socket = None
        self._serverName = None
        self._serverPort = None
        self._status = None
        self._threshold = None
        self._timeout = AgentConstants.DEFAULT_NTP_TIMEOUT
        self.skip_timeout = "true"

    def getNTPstatus(self):
        return self._status
    
    def updateStatus(self,str_state):
        try:
            if int(str_state) == 1:
                self._status = True
            elif int(str_state) == 0:
                self._status = False
            AgentLogger.log(AgentLogger.CHECKS, 'NTP Status updated after upload of instant notification ' + str(self._serverName))
        except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], ' *************************** Exception while updating NTP status after upload************************ '+ repr(e))
            traceback.print_exc()

    def setNTPDetails(self,NTPDict):
        self._serverName = NTPDict['ntpserver']
        self._threshold = float(NTPDict['threshold'])
        self._serverPort = NTPDict.get('port',123)
        self.skip_timeout = NTPDict.get('skipTimeout', "false")
        if 'id' in NTPDict:
            self._check_id = int(NTPDict['id'])
        else:
            AgentLogger.log(AgentLogger.CHECKS, 'NTP ID Not Available for NTP Config ===== {0}'.format(NTPDict['NTP']))

    def startNTPDataCollection(self):
        dictDataToReturn = {}
        statusChange = False
        try:
            bool_toreturn, offset, msg = AgentUtil.offset_in_machine_clock(self._serverName, self._serverPort)
            if bool_toreturn:
                dictDataToReturn['diff'] = str(offset) 
                if abs(offset) <= self._threshold:
                    dictDataToReturn['State'] = AgentConstants.RSC_CHECK_UP
                else: 
                    dictDataToReturn['State'] = AgentConstants.RSC_CHECK_DOWN
            else:
                dictDataToReturn['msg'] = msg
                if self.skip_timeout == 'true':
                    AgentLogger.log(AgentLogger.CHECKS, "NTP communication failure {} alert skipped | skip timedout - {}".format(msg,self.skip_timeout))
                    dictDataToReturn['State'] = AgentConstants.RSC_CHECK_UP
                else:
                    dictDataToReturn['State'] = AgentConstants.RSC_CHECK_DOWN

            if dictDataToReturn['State'] == AgentConstants.RSC_CHECK_UP:
                if self._status == False or self._status == None:
                    statusChange = True
            else:
                if self._status == True or self._status == None:
                    statusChange = True
            return statusChange, dictDataToReturn
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while NTP monitor-data collection for '+str(self._serverName)+' *************************** '+ repr(e))
            traceback.print_exc()

class NTPHandler:
    _ntp = {}
    _lock = threading.Lock()
    def __init__(self):
        self._loadCustomNTP()
            
    def _loadCustomNTP(self):
        try:
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(AgentConstants.AGENT_CUSTOM_MONITORS_GROUP_FILE)
            fileObj.set_dataType('json')
            fileObj.set_mode('rb')
            fileObj.set_dataEncoding('UTF-8')
            fileObj.set_loggerName(AgentLogger.CHECKS)
            fileObj.set_logging(False)
            bool_toReturn, dict_monitorsInfo = FileUtil.readData(fileObj)
            with self._lock:
                for each_NTP in dict_monitorsInfo['MonitorGroup']['ChecksMonitoring']['NTP']:
                    ntp = NTP()
                    ntp.setNTPDetails(each_NTP)
                    self.__class__._ntp[each_NTP['id']] = ntp
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while loading custom ntp for ntp monitoring  *************************** '+ repr(e))
            traceback.print_exc()

    def deleteAllNTP(self):
        try:
            for each_ntp in self.__class__._ntp:
                ntp = self.__class__._ntp[each_ntp]
                AgentLogger.log(AgentLogger.CHECKS,'Deleting NTP check with ntp no: '+repr(ntp._serverName))
            self.__class__._ntp.clear()
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' CheckError | *************************** Exception while deleting ntp checks *************************** '+ repr(e))
            traceback.print_exc()

    def reloadNTP(self):
        with self._lock:
            self.deleteAllNTP()
        self._loadCustomNTP()

    def updateNTPStatus(self,dictData):
        try:
            if 'ntp' in dictData:
                listNTPData = dictData['ntp']
                AgentLogger.log(AgentLogger.CHECKS, ' NTP data notified: '+ str(listNTPData)) 
                for NTPData in listNTPData:
                    with self._lock:
                        if str(NTPData['id']) in self.__class__._ntp:
                            ntp = self.__class__._ntp[str(NTPData['id'])]
                            ntp.updateStatus(NTPData['status'])
                        else:
                            AgentLogger.log(AgentLogger.CHECKS, ' NTP already deleted with id : ' + str(NTPData['id']))
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while updating NTP status after upload*************************** '+ repr(e))
            traceback.print_exc()

    def checkNTPStatus(self):
        dictDataToSend = {}
        toUpdate = False
        try:
            with self._lock:
                for ntp_id, ntp in self.__class__._ntp.items():
                    statusChange, dictDataRecieved = ntp.startNTPDataCollection()
                    if dictDataRecieved['State'] == AgentConstants.RSC_CHECK_UP:
                        AgentLogger.debug(AgentLogger.CHECKS, 'Time difference between NTP server: '+str(ntp._serverName) + ' and  machine is within threshold')
                        dictDataRecieved['status'] = 1
                    else:
                        AgentLogger.debug(AgentLogger.CHECKS, 'Time difference between NTP server: '+str(ntp._serverName) + ' and machine is greater than threshold or communication failure')
                        dictDataRecieved['status'] = 0
                    dictDataRecieved.pop('State', None)
                    dictDataToSend.setdefault(ntp._check_id,dictDataRecieved)
                    if statusChange:
                        toUpdate = True
            if toUpdate:
                return dictDataToSend
            else:
                return None
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while checking NTP status *************************** '+ repr(e))
            traceback.print_exc()
           
class Port():
    def __init__(self):
        self._check_id = None
        self._serverName = None
        self._socket = None
        self._address_family = None
        self._socketType = None
        self._serverAddress = None
        self._serverPort = None
        self._status = None
        self._responseTime = None
        self._timeout = AgentConstants.DEFAULT_PORT_TIMEOUT
        self._interval = 120
        #self._type = None
    
    def getPortStatus(self):
        return self._status
    
    def updateStatus(self,str_state):
        try:
            if int(str_state) == 1:
                self._status = True
            elif int(str_state) == 0:
                self._status = False
            AgentLogger.log(AgentLogger.CHECKS, 'Port Status updated after upload of instant notification ' + str(self._serverPort))
        except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], ' *************************** Exception while updating Port status after upload************************ '+ repr(e))
            traceback.print_exc()
    
    def setPortDetails(self,portDict):
        self._address_family = socket.AF_INET
        self._socketType = socket.SOCK_STREAM
        self._serverName = AgentConstants.PORT_MONITOR_SERVER_NAME
        self._serverAddress = AgentConstants.PORT_MONITOR_SERVER_IP
        self._serverPort = int(portDict['port'])
        if 'timelimit' in portDict and  portDict['timelimit'] != -1:
            self._timeout = portDict['timelimit']
        if 'id' in portDict:
            self._check_id = int(portDict['id'])
        else:
            AgentLogger.log(AgentLogger.CHECKS, 'Port Id Not Available for Port Config ===== {0}'.format(portDict['port']))
        if 'poll_interval' in portDict:
            self._interval = int(portDict['poll_interval'])
        
    def startPortDataCollection(self):
        dictDataToReturn = {}
        try:
            statusChange = False
            #self.setPortDetails(dictDetails)
            # validate address family
            startTime = AgentUtil.getCurrentTimeInMillis()
            self._socket = socket.socket(self._address_family, self._socketType)
            # get resolved IP for port
            if not self._serverAddress:
                self._serverAddress = socket.gethostbyname(self._serverName)
            # set timeout and validate
            if self._timeout < AgentConstants.MIN_PORT_TIMEOUT or self._timeout > AgentConstants.MAX_PORT_TIMEOUT:
                self._timeout = AgentConstants.DEFAULT_PORT_TIMEOUT
            self._socket.settimeout(self._timeout)
            # connect socket with timeout
            try:
                result = self._socket.connect_ex((self._serverAddress,self._serverPort))
                if result != 0:
                    self._socket.close()
                    self._socket = socket.socket(self._address_family, self._socketType)
                    retry_ip_address=AgentConstants.IP_ADDRESS
                    if retry_ip_address == '127.0.0.1':
                        isSuccess, retry_ip_address = CommunicationHandler.pingServer(AgentLogger.CHECKS)
                    result = self._socket.connect_ex((retry_ip_address,self._serverPort))
                    AgentLogger.log(AgentLogger.CHECKS,'PORT Check retry ip ::  {0} :: port {1} | result :: {2}'.format(retry_ip_address,self._serverPort,result))
                    if result !=0 :
                        with s247_commandexecutor("/bin/netstat -lntp") as op:
                            _output, _returncode, _errormsg, _outputtype = op
                        if _output:
                            string_to_check = ":"+str(self._serverPort)+" "
                            if string_to_check in _output:
                                result = 0
                if result == 0:
                    dictDataToReturn['State'] = AgentConstants.RSC_CHECK_UP
                else:
                    dictDataToReturn['State'] = AgentConstants.RSC_CHECK_DOWN
                if result == 0 and (self._status == False or self._status == None):
                    #self._status = True
                    statusChange = True
                elif result != 0 and (self._status == True or self._status == None):
                    #self._status = False
                    statusChange = True
            except OverflowError as e:
                AgentLogger.log(AgentLogger.CHECKS, ' *************************** Overflow error occured ***********' + repr(e))
            
            endTime = AgentUtil.getCurrentTimeInMillis()
            self._responseTime = endTime - startTime
            dictDataToReturn['ResponseTime'] = self._responseTime
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while port monitor-data collection for '+str(self._serverName)+' *************************** '+ repr(e))
            traceback.print_exc()
        finally:
            if self._socket:
                self._socket.close()
        return statusChange,dictDataToReturn
    
                
class PortHandler(DesignUtils.Singleton):
    _ports = {}
    _lock = threading.Lock()
    def __init__(self):
        self._loadCustomPorts()
            
    def _loadCustomPorts(self):
        try:
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(AgentConstants.AGENT_CUSTOM_MONITORS_GROUP_FILE)
            fileObj.set_dataType('json')
            fileObj.set_mode('rb')
            fileObj.set_dataEncoding('UTF-8')
            fileObj.set_loggerName(AgentLogger.CHECKS)
            fileObj.set_logging(False)
            bool_toReturn, dict_monitorsInfo = FileUtil.readData(fileObj)
            with self._lock:
                for each_port in dict_monitorsInfo['MonitorGroup']['ChecksMonitoring']['Port']:
                    port = Port()
                    port.setPortDetails(each_port)
                    self.__class__._ports[each_port['id']] = port
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while loading custom ports for port monitoring  *************************** '+ repr(e))
            traceback.print_exc()

    def deleteAllPorts(self):
        try:
            for each_port in self.__class__._ports:
                port = self.__class__._ports[each_port]
                AgentLogger.log(AgentLogger.CHECKS,'Deleting Port check with port no: '+repr(port._serverPort))
            self.__class__._ports.clear()
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' CheckError | *************************** Exception while deleting Port checks *************************** '+ repr(e))
            traceback.print_exc()
    
    def reloadPorts(self):
        with self._lock:
            self.deleteAllPorts()
        self._loadCustomPorts()
    
    
    def updatePortStatus(self,dictData):
        try:
            if 'port' in dictData:
                listPortData = dictData['port']
                AgentLogger.log(AgentLogger.CHECKS, ' Port data notified: '+ str(listPortData)) 
                for portData in listPortData:
                    with self._lock:
                        if str(portData['id']) in self.__class__._ports:
                            port = self.__class__._ports[str(portData['id'])]
                            port.updateStatus(portData['status'])
                        else:
                            AgentLogger.log(AgentLogger.CHECKS, ' Port already deleted with id : ' + str(portData['id']))
                        #AgentLogger.log(AgentLogger.CHECKS, 'Port of cid :' + str(portData['id']) + 'status updated successfully after upload')
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while updating Port status after upload*************************** '+ repr(e))
            traceback.print_exc()

    def checkPortStatus(self):
        dictDataToSend = {}
        toUpdate = False
        try:
            with self._lock:
                for portName, port in self.__class__._ports.items():
                    tempDict = {}
                    statusChange, dictDataRecieved = port.startPortDataCollection()
                    
                    if dictDataRecieved['State'] == AgentConstants.RSC_CHECK_UP:
                        AgentLogger.debug(AgentLogger.CHECKS, 'Port :' + str(port._serverPort)+' is now open in server :'+str(port._serverAddress))
                        str_status = 1
                    else:
                        AgentLogger.debug(AgentLogger.CHECKS, 'Port :'+str(port._serverPort)+' is now closed in server :'+str(port._serverAddress))
                        str_status = 0
                    #tempDict['port'] = port._serverPort
                    tempDict['status'] = str_status
                    #tempDict['RESPONSETIME'] = dictDataRecieved['ResponseTime']
                    dictDataToSend.setdefault(port._check_id,tempDict)
                    
                    if statusChange:
                        toUpdate = True
                        
            if toUpdate:
                return dictDataToSend
            else:
                return None
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while checking port status *************************** '+ repr(e))
            traceback.print_exc()
    
    
class URL():
    _statusLock = threading.Lock()
    def __init__(self):
        self._serverName = None
        self._serverAddress = None
        self._serverPort = None
        self._status = None
        self._proxyName = None
        self._proxyAddress = None
        self._proxyUserName = None
        self._proxyPassword = None
        self._userName = None
        self._userPass = None
        self._protocol = None
        self._method = None
        self._url = None
        self._responseTime = None
        self._timeout = AgentConstants.DEFAULT_URL_TIMEOUT
        self._check_id = None
        self._interval = 120
        self._rsrc = None
    
    def checkLocalURL(self,strURL):
        pass
    
    def updateStatus(self,str_state):
        try:
            if int(str_state) == 1:
                self._status = True
            elif int(str_state) == 0:
                self._status = False
            AgentLogger.log(AgentLogger.CHECKS, 'URL Status updated after upload of instatnt notification ' + str(self._rsrc))
        except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], ' *************************** Exception while updating Port status after upload************************ '+ repr(e))
            traceback.print_exc()
    
    def setURLDetails(self,url):
        try:
            self.checkLocalURL(url)
            self._rsrc = url['url']
            parsedURL = urlparse(url['url'])
            if parsedURL.scheme != '':
                self._protocol = parsedURL.scheme
            else:
                self._protocol = AgentConstants.HTTP_PROTOCOL
                
            if parsedURL.hostname:
                self._serverName = parsedURL.hostname
            else:
                self._serverName = parsedURL.path
        
            if parsedURL.port:
                self._serverPort = parsedURL.port
            else:
                if self._protocol == AgentConstants.HTTPS_PROTOCOL:
                    self._serverPort = AgentConstants.URL_HTTPS_PORT
                else:
                    self._serverPort = AgentConstants.URL_HTTP_PORT
            
            if parsedURL.path:
                self._url = parsedURL.path
            
            if parsedURL.username:
                self._userName = parsedURL.username
            if parsedURL.password:
                self._userPass = parsedURL.password
            if 'id' in url:
                self._check_id = int(url['id'])
            else:
                AgentLogger.log(AgentLogger.CHECKS, 'Url Id Not Available for Url Config ===== {0}'.format(url['url']))
            if 'timelimit' in url and url['timelimit'] != -1:
                self._timeout = url['timelimit']
            if 'poll_interval' in url:
                self._interval = int(url['poll_interval'])
                
            if parsedURL.query:
                query_params = parsedURL.query
                if '&' not in query_params:
                    self._url=self._url+"?"+query_params
                else:
                    params_list = query_params.split('&')
                    dict_request_params = {}
                    str_request_parameters = None
                    for each_param in params_list:
                        param_kv = each_param.split('=')
                        dict_request_params[param_kv[0]] = param_kv[1]
                        if not dict_request_params == None:
                            str_request_parameters = urlencode(dict_request_params)
                    self._url=self._url+"?"+str_request_parameters
        except ValueError as e:
             AgentLogger.log(AgentLogger.CHECKS, '==Value error occured' + repr(e))
        
        finally:
            self._method = AgentConstants.HTTP_GET
            
    def startURLDataCollection(self):
        statusChange = False
        dictDataToReturn = {}
        try:
            if self._userName and self._userPass:
                password_mgr = urlconnection.HTTPPasswordMgr()
                password_mgr.add_password(None, self._url, self._userName, self._userPass)
                auth_handler = urlconnection.HTTPBasicAuthHandler(password_mgr)
                opener = urlconnection.build_opener(auth_handler)
                urlconnection.install_opener(opener)
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.CHECKS)
            requestInfo.set_parseResponse(False)
            requestInfo.set_responseAction(CommunicationHandler.dummy)
            requestInfo.set_method(self._method)
            requestInfo.set_host(self._serverName)
            if self._serverPort:
                requestInfo.set_port(self._serverPort)
            requestInfo.set_protocol(self._protocol)
            if self._url:
                requestInfo.set_url(self._url)
            requestInfo.set_timeout(self._timeout)
            requestInfo.bypass_proxy()
            requestInfo.set_ssl_verification(False)
            startTime = AgentUtil.getCurrentTimeInMillis()
            if self._url:
                AgentLogger.log(AgentLogger.CHECKS, 'URL Check :: {}'.format(self._protocol+'://'+self._serverName+':'+str(self._serverPort)+self._url))
            else:
                AgentLogger.log(AgentLogger.CHECKS, 'URL Check :: {}'.format(self._protocol+'://'+self._serverName+':'+str(self._serverPort)))
            isSuccess, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
            endTime = AgentUtil.getCurrentTimeInMillis()
            rspTime = endTime - startTime
            if isSuccess:
                AgentLogger.log(AgentLogger.CHECKS, 'URL Check Success | ResponseTime is: '+str(rspTime))
                dictDataToReturn['STATE'] = AgentConstants.RSC_CHECK_UP
            else:
                AgentLogger.log(AgentLogger.CHECKS, 'URL Check Failure')
                dictDataToReturn['STATE'] = AgentConstants.RSC_CHECK_DOWN
            
            dictDataToReturn['Response Time'] = rspTime
            with self._statusLock:
                if isSuccess and (self._status == False or self._status == None):
                    statusChange = True
                if not isSuccess and (self._status == True or self._status == None):
                    statusChange = True
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while url monitor-data collection for '+str(self._url)+' *************************** '+ repr(e))
            traceback.print_exc()
        return statusChange , dictDataToReturn
    
    
class URLHandler(DesignUtils.Singleton):
    _urls = {}
    _lock = threading.Lock()
    _list_URls = []
    def __init__(self):
        self._loadCustomURLs()
            
    def _loadCustomURLs(self):
        try:
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(AgentConstants.AGENT_CUSTOM_MONITORS_GROUP_FILE)
            fileObj.set_dataType('json')
            fileObj.set_mode('rb')
            fileObj.set_dataEncoding('UTF-8')
            fileObj.set_loggerName(AgentLogger.CHECKS)
            fileObj.set_logging(False)
            bool_toReturn, dict_monitorsInfo = FileUtil.readData(fileObj)
            with self._lock:
                for each_url in dict_monitorsInfo['MonitorGroup']['ChecksMonitoring']['URL']:
                    url = URL()
                    url.setURLDetails(each_url)
                    self.__class__._urls[each_url['id']] = url
            #self.checkSingleURLStatus()
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while loading custom URLs *************************** '+ repr(e))
            traceback.print_exc()
            
    def deleteAllURLs(self):
        try:
            for each_url in self.__class__._urls:
                url = self.__class__._urls[each_url]
                AgentLogger.log(AgentLogger.CHECKS,'Deleting URL check with chek_id: '+repr(url._check_id))
            self.__class__._urls.clear()
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' CheckError | *************************** Exception while deleting URL checks *************************** '+ repr(e))
            traceback.print_exc()
    
    def reloadURLs(self):
        with self._lock:
            self.deleteAllURLs()
        self._loadCustomURLs()
    

    def updateURLStatus(self,dictData):
        try:
            if 'url' in dictData:
                listURLData = dictData['url']
                AgentLogger.log(AgentLogger.CHECKS, ' URL data notified: '+ str(listURLData)) 
                for urlData in listURLData:
                    with self._lock:
                        if str(urlData['id']) in self.__class__._urls:
                            url = self.__class__._urls[str(urlData['id'])]
                            url.updateStatus(urlData['status'])
                        else:
                            AgentLogger.log(AgentLogger.CHECKS, ' URL already deleted with id : ' + str(urlData['id']))
                        #AgentLogger.log(AgentLogger.CHECKS, 'URL of cid :' + str(urlData['id']) + 'status updated successfully after upload')
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while updating URL status after upload*************************** '+ repr(e))
            traceback.print_exc()
    
    def checkURLStatus(self):
        toUpdate = False
        dictDataToSend = {}
        try:
            with self._lock:
                for urlName, url in self.__class__._urls.items():
                    tempDict = {}
                    statusChange, dictDataToReturn = url.startURLDataCollection()
                    if statusChange:
                        toUpdate = True
                    
                    if dictDataToReturn['STATE'] == AgentConstants.RSC_CHECK_UP:
                        tempDict['status'] = 1
                    elif dictDataToReturn['STATE'] == AgentConstants.RSC_CHECK_DOWN:
                        tempDict['status'] = 0
                    #tempDict['url'] = url._rsrc
                    #tempDict['RESPONSETIME'] = dictDataToReturn['Response Time']
                    dictDataToSend.setdefault(url._check_id,tempDict)
            if toUpdate:
                return dictDataToSend
            else:
                return None
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while checking URL status in data collection *************************** '+ repr(e))
            traceback.print_exc()
    

class EventHandler(pyinotify.ProcessEvent):
    def process_IN_CREATE(self,event):
        
        #filePath = pathWdObject[event.wd].fileName
        mo = None
        is_valid = None
        AgentLogger.debug(AgentLogger.CHECKS,'Pyinotify: in create for: ' + repr(event))
        for check_id in pathWdObject[event.wd]:
            filePath = pathWdObject[event.wd][check_id].fileName
            for fileName, file in FileMonUtil._files.items():
                #AgentLogger.log(AgentLogger.CHECKS,'file and check '+repr(file._check_id)+' '+repr(check_id))
                if str(file._check_id) == check_id and file._check_type in (3004, 3005) and file._event == 'A' and file._path == filePath:
                    if file._watch == 'p':
                        try:
                            re.compile(file._fileName)
                            is_valid = True
                        except re.error:
                            is_valid = False
                        if is_valid:
                            mo = re.search(file._fileName,event.pathname)
                    if mo or file._watch == 'a':
                        if (file._check_type == 3004 and os.path.isfile(event.pathname)):
                            pathWdObject[event.wd][check_id].setHistory('file',check_id,event.pathname)
                        elif (file._check_type == 3005 and os.path.isdir(event.pathname)):
                            pathWdObject[event.wd][check_id].setHistory('dir',check_id,event.pathname)
                            #AgentLogger.log(AgentLogger.CHECKS,'Pyinotify: in create '+repr(event.pathname))
    
    def process_IN_DELETE(self,event):
        #for check_id in pathWdObject[event.wd]:
        #filePath = pathWdObject[event.wd].fileName
        mo = None
        is_valid = None
        AgentLogger.debug(AgentLogger.CHECKS,'Pyinotify: in delete for: ' + repr(event))
        for check_id in pathWdObject[event.wd]:
            filePath = pathWdObject[event.wd][check_id].fileName
            for fileName, file in FileMonUtil._files.items():
                if str(file._check_id) == check_id and file._check_type in (3004, 3005) and file._event == 'D' and file._path == filePath: 
                    if file._watch == 'p':
                        try:
                            re.compile(file._fileName)
                            is_valid = True
                        except re.error:
                            is_valid = False
                        if is_valid:
                            mo = re.search(file._fileName,event.pathname)
                    if mo or file._watch == 'a':
                        if (file._check_type == 3004 and os.path.splitext(event.pathname)[1]):
                            pathWdObject[event.wd][check_id].setHistory('file',check_id,event.pathname)
                        elif (file._check_type == 3005 and not os.path.splitext(event.pathname)[1]):
                            pathWdObject[event.wd][check_id].setHistory('dir',check_id,event.pathname)
                        #AgentLogger.log(AgentLogger.CHECKS,'Pyinotify: delete '+repr(event.pathname))
    
    def process_IN_ACCESS(self,event):
        AgentLogger.debug(AgentLogger.CHECKS,'Pyinotify: in access for: ' + repr(event))
        for check_id in pathWdObject[event.wd]:
            pathWdObject[event.wd][check_id].setHistory('access',check_id)
    
    def process_IN_MODIFY(self,event):
        AgentLogger.debug(AgentLogger.CHECKS,'Pyinotify: in modify for: '+ repr(event))
        for check_id in pathWdObject[event.wd]:
            pathWdObject[event.wd][check_id].setHistory('modify',check_id)
    
    def process_IN_ATTRIB(self,event):
        AgentLogger.debug(AgentLogger.CHECKS,'Pyinotify: in metadata for: ' + repr(event))
        for check_id in pathWdObject[event.wd]:
            pathWdObject[event.wd][check_id].setHistory('metadata',check_id)


class EventHistory():
    def __init__(self, fn, id, ctype):
        self.lastUpdatedTime = None
        self.lastEventType = None
        self.fileName = fn
        self.fileCreateDeleteName = None
        self.check_id = id
        self.lastNotified = None
        self.lastPermissionStat = None
        if ctype in (2002,3002):
            stats = os.stat(fn)
            self.lastPermissionStat = stats.st_mode 
        self.check_type = ctype
    
    def getHistory(self):
        dictToReturn = {}
        try:
            if self.lastUpdatedTime:
                self.lastUpdatedTime = None
                if self.check_type in (3004,3005):
                    return self.fileCreateDeleteName
                return os.path.basename(self.fileName.rstrip('/'))
            else:
                return None
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while getting event history *************************** '+ repr(e))
            traceback.print_exc()
        
    def setHistory(self, type, cid, file_name = None):
        instantNotify_dict = {}
        proceed = True
        try:
            if self.check_type in WATCH_NAME_ID[type] and self.check_id == cid:
                if self.check_type in (2002,3002):
                    if os.path.exists(self.fileName):
                        cStat = os.stat(self.fileName)
                        if cStat.st_mode != self.lastPermissionStat:
                            self.lastPermissionStat = cStat.st_mode
                        else:
                            proceed = False
                    else:
                        proceed = False
                if proceed:
                    instantNotify_dict['id'] = self.check_id
                    self.lastUpdatedTime = str(time.time())
                    self.lastEventType = type
                    if file_name:
                        self.fileCreateDeleteName = os.path.basename(file_name.rstrip('/'))
                    if self.check_type not in (3001,3002):
                        instantNotify_dict['file'] = os.path.basename(self.fileName)
                    currentTime = AgentUtil.getCurrentTimeInMillis()
                    if (self.lastNotified == None) or ((currentTime - self.lastNotified) >= AgentConstants.MIN_CHECK_ALERT_INTERVAL):
                        AgentLogger.log(AgentLogger.CHECKS,'Uploading file/dir instant notification with details: '+repr(instantNotify_dict))
                        if self.check_type in (3004,3005):
                           instantNotify_dict['file'] = self.fileCreateDeleteName 
                        fileInstantNotify(instantNotify_dict)
                        self.lastNotified = currentTime
                    else:
                        AgentLogger.log(AgentLogger.CHECKS,'Skipping upload instant notification because recently updated at: '+repr(self.lastNotified))
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while setting event history *************************** '+ repr(e))
            traceback.print_exc()
