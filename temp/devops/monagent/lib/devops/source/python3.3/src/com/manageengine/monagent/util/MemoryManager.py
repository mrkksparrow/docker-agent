#$Id$
import os, traceback, json, time
from six.moves.urllib.parse import urlencode
from collections import OrderedDict

import com
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil

RcaUtil = None

RCA_DICT = None

class RcaInfo:
    def __init__(self):
        self.requestType = None
        self.requestInitiatedTime = AgentUtil.getCurrentTimeInMillis()
        self.action = None
        self.isUserInitiated = False
        self.collectionTime = None
        self.downTimeInServer = None
        self.searchTime = None
        self.sysLogQuery = None
        self.data = None
        self.fileName = None
        self.filePath = None
        self.reason = AgentConstants.AGENT_BOOT_STATUS
        
    def __str__(self):
        rcaInfo = ''
        rcaInfo += 'RequestType : ' + repr(self.requestType)
        rcaInfo += ', Action : ' + repr(self.action)
        rcaInfo += ', UserInitiated : ' + repr(self.isUserInitiated)
        if self.collectionTime:
            rcaInfo += ', CollectionTime : ' + repr(self.collectionTime)+' --> '+repr(AgentUtil.getFormattedTime(self.collectionTime))
        if self.searchTime:
            rcaInfo += ', SearchTime : ' + repr(self.searchTime)+' --> '+repr(AgentUtil.getFormattedTime(self.searchTime))
        if self.downTimeInServer:
            rcaInfo += ', Down time in server : ' + repr(self.downTimeInServer)+' --> '+repr(AgentUtil.getFormattedTime(self.downTimeInServer))
        if self.sysLogQuery:
            rcaInfo += ', SysLogQuery startTime : ' + repr(self.sysLogQuery.startTime)+' --> '+repr(AgentUtil.getFormattedTime(self.sysLogQuery.startTime))
            rcaInfo += ', SysLogQuery endTime : ' + repr(self.sysLogQuery.endTime)+' --> '+repr(AgentUtil.getFormattedTime(self.sysLogQuery.endTime))
        rcaInfo += ', FileName : ' + repr(self.fileName)
        rcaInfo += ', FilePath : ' + repr(self.filePath)
        return rcaInfo
        
    def __repr__(self):
        return self.__str__()
    
class RcaReportHandler:
    def __init__(self):
        global RcaUtil
        RcaUtil = self
    
    def calculateTopProcessMetricsAvgForRca(self, list_rcaFilesForCalculatingAverage):
        dict_toReturn = None
        list_processMetrics = None
        try:
            if list_rcaFilesForCalculatingAverage:
                for str_filePath in list_rcaFilesForCalculatingAverage:
                    fileObj = AgentUtil.FileObject()
                    fileObj.set_filePath(str_filePath)
                    fileObj.set_dataType('json')
                    fileObj.set_mode('rb')
                    fileObj.set_dataEncoding('UTF-16')
                    fileObj.set_loggerName(AgentLogger.STDOUT)
                    fileObj.set_logging(False)
                    bool_toReturn, dict_processData = FileUtil.readData(fileObj)
                    dict_processIdVsProcessDetails = dict_processData['Process Details']
                    if bool_toReturn:
                        if list_processMetrics:
                            for index, list_processDetail in enumerate(list_processMetrics):
                                str_processId = list_processDetail[0]
                                if str_processId in dict_processIdVsProcessDetails:
                                    list_process = dict_processIdVsProcessDetails[str_processId]
                                    list_processDetail[2] = float(float(list_processDetail[2]) + float(list_process[2])) #float_psCpu
                                    list_processDetail[3] = float(float(list_processDetail[3]) + float(list_process[3])) #float_psMem
                                    list_processDetail[8] = float(float(list_processDetail[8]) + float(list_process[8])) #float_topCpu
                                    list_processDetail[9] = float(float(list_processDetail[9]) + float(list_process[9])) #float_topMem
                                    list_processDetail[4] = float(float(list_processDetail[4]) + float(list_process[4])) #float_psThreadCount
                                    list_processDetail[5] = float(float(list_processDetail[5]) + float(list_process[5])) #float_psHandleCount
                                else:
                                    #AgentLogger.debug(AgentLogger.STDOUT,'Details for process Id : '+repr(str_processId)+' are missing in the file : '+repr(str_filePath))
                                    list_processDetail[2] = float(list_processDetail[2]) #float_psCpu
                                    list_processDetail[3] = float(list_processDetail[3]) #float_psMem
                                    list_processDetail[8] = float(list_processDetail[8]) #float_topCpu
                                    list_processDetail[9] = float(list_processDetail[9]) #float_topMem
                                    list_processDetail[4] = float(list_processDetail[4]) #float_psThreadCount
                                    list_processDetail[5] = float(list_processDetail[5]) #float_psHandleCount
                        else:
                            list_processMetrics = []
                            for list_processDetails in dict_processIdVsProcessDetails.values():
                                list_processMetrics.append(list_processDetails)
                    else:
                        AgentLogger.log(AgentLogger.STDOUT,'*************************** Unable to fetch rca temp data from the file : '+repr(str_filePath)+'***************************')
                int_noOfRCAFilesTakenForAverage = len(list_rcaFilesForCalculatingAverage)    
                for list_processDet in list_processMetrics:
                    AgentLogger.debug(AgentLogger.STDOUT,'List of process metrics for rca : '+repr(list_processDet))
                    list_processDet[2] = "%.1f" % float(float(list_processDet[2])/int_noOfRCAFilesTakenForAverage) #float_psCpuAvg
                    list_processDet[3] = "%.1f" % float(float(list_processDet[3])/int_noOfRCAFilesTakenForAverage) #float_psMemAvg
                    list_processDet[8] = "%.1f" % float(float(list_processDet[8])/int_noOfRCAFilesTakenForAverage) #float_topCpuAvg
                    list_processDet[9] = "%.1f" % float(float(list_processDet[9])/int_noOfRCAFilesTakenForAverage) #float_topMemAvg
                    list_processDet[4] = "%.1f" % float(float(list_processDet[4])/int_noOfRCAFilesTakenForAverage) #float_psThreadCountAvg
                    list_processDet[5] = "%.1f" % float(float(list_processDet[5])/int_noOfRCAFilesTakenForAverage) #float_psHandleCountAvg
                if list_processMetrics:
                    dict_toReturn = {}
                    dict_toReturn['TopProcessByCPU'] = com.manageengine.monagent.collector.DataCollector.ProcessUtil.sortProcessListAndConvertToDict(list_processMetrics, sortKey='cpu')
                    dict_toReturn['TopProcessByMemory'] = com.manageengine.monagent.collector.DataCollector.ProcessUtil.sortProcessListAndConvertToDict(list_processMetrics, sortKey='mem')
                else:
                    AgentLogger.log(AgentLogger.STDOUT,'*************************** Unable to sort the process metrics since list is empty ***************************')
            else:
                AgentLogger.log(AgentLogger.STDOUT,'*************************** Unable to calculate process metrics avg for rca since list of temp files fetched is empty *************************** ')
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' *************************** Exception while calculating top process metrics for rca *************************** '+ repr(e))
            traceback.print_exc()
        return dict_toReturn
    
    def calculateBSDTopProcessMetricsAvgForRca(self, list_rcaFilesForCalculatingAverage):
        dict_toReturn = None
        list_processMetrics = None
        try:
            if list_rcaFilesForCalculatingAverage:
                for str_filePath in list_rcaFilesForCalculatingAverage:
                    fileObj = AgentUtil.FileObject()
                    fileObj.set_filePath(str_filePath)
                    fileObj.set_dataType('json')
                    fileObj.set_mode('rb')
                    fileObj.set_dataEncoding('UTF-16')
                    fileObj.set_loggerName(AgentLogger.STDOUT)
                    fileObj.set_logging(False)
                    bool_toReturn, dict_processData = FileUtil.readData(fileObj)
                    dict_processIdVsProcessDetails = dict_processData['Process Details']
                    if bool_toReturn:
                        if list_processMetrics:
                            for index, list_processDetail in enumerate(list_processMetrics):
                                str_processId = list_processDetail[0]
                                if str_processId in dict_processIdVsProcessDetails:
                                    list_process = dict_processIdVsProcessDetails[str_processId]
                                    list_processDetail[2] = float(float(list_processDetail[2]) + float(list_process[2])) #float_psCpu
                                    list_processDetail[3] = float(float(list_processDetail[3]) + float(list_process[3])) #float_psMem
                                    list_processDetail[8] = float(float(str(list_processDetail[8]).strip('%')) + float(str(list_process[8]).strip('%'))) #float_topCpu
                                    list_processDetail[9] = float(float(list_processDetail[9]) + float(list_process[9])) #float_topMem
                                    list_processDetail[4] = float(float(list_processDetail[4]) + float(list_process[4])) #float_psThreadCount
                                    list_processDetail[5] = float(float(list_processDetail[5]) + float(list_process[5])) #float_psHandleCount
                                else:
                                    AgentLogger.debug(AgentLogger.STDOUT,'Details for process Id : '+repr(str_processId)+' are missing in the file : '+repr(str_filePath) + ' for the list : ' + repr(list_processDetail))
                                    list_processDetail[2] = float(list_processDetail[2]) #float_psCpu
                                    list_processDetail[3] = float(list_processDetail[3]) #float_psMem
                                    list_processDetail[8] = float(str(list_processDetail[8]).strip('%')) #float_topCpu
                                    list_processDetail[9] = float(list_processDetail[9]) #float_topMem
                                    list_processDetail[4] = float(list_processDetail[4]) #float_psThreadCount
                                    list_processDetail[5] = float(list_processDetail[5]) #float_psHandleCount
                        else:
                            list_processMetrics = []
                            for list_processDetails in dict_processIdVsProcessDetails.values():
                                list_processMetrics.append(list_processDetails)
                    else:
                        AgentLogger.log(AgentLogger.STDOUT,'*************************** Unable to fetch rca temp data from the file : '+repr(str_filePath)+'***************************')
                int_noOfRCAFilesTakenForAverage = len(list_rcaFilesForCalculatingAverage)    
                for list_processDet in list_processMetrics:
                    AgentLogger.debug(AgentLogger.STDOUT,'List of process metrics for rca : '+repr(list_processDet))
                    list_processDet[2] = "%.1f" % float(float(list_processDet[2])/int_noOfRCAFilesTakenForAverage) #float_psCpuAvg
                    list_processDet[3] = "%.1f" % float(float(list_processDet[3])/int_noOfRCAFilesTakenForAverage) #float_psMemAvg
                    list_processDet[8] = "%.1f" % float(float(list_processDet[8])/int_noOfRCAFilesTakenForAverage) #float_topCpuAvg
                    list_processDet[9] = "%.1f" % float(float(list_processDet[9])/int_noOfRCAFilesTakenForAverage) #float_topMemAvg
                    list_processDet[4] = "%.1f" % float(float(list_processDet[4])/int_noOfRCAFilesTakenForAverage) #float_psThreadCountAvg
                    list_processDet[5] = "%.1f" % float(float(list_processDet[5])/int_noOfRCAFilesTakenForAverage) #float_psHandleCountAvg
                if list_processMetrics:
                    dict_toReturn = {}
                    dict_toReturn['TopProcessByCPU'] = com.manageengine.monagent.collector.DataCollector.ProcessUtil.sortProcessListAndConvertToDict(list_processMetrics, sortKey='cpu')
                    dict_toReturn['TopProcessByMemory'] = com.manageengine.monagent.collector.DataCollector.ProcessUtil.sortProcessListAndConvertToDict(list_processMetrics, sortKey='mem')
                else:
                    AgentLogger.log(AgentLogger.STDOUT,'*************************** Unable to sort the process metrics since list is empty ***************************')
            else:
                AgentLogger.log(AgentLogger.STDOUT,'*************************** Unable to calculate process metrics avg for rca since list of temp files fetched is empty *************************** ')
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' *************************** Exception while calculating top process metrics for rca *************************** '+ repr(e))
            traceback.print_exc()
        return dict_toReturn
    
    def getRcaFileListForCalculatingProcessMetricsAvg(self):
        list_tempFileNames = []
        str_tempRCADirectory = AgentConstants.AGENT_TEMP_RCA_RAW_DATA_DIR
        str_tempRCAFileName = 'Rca_Raw'
        list_rcaFilesForCalculatingAverage = None
        try:
            list_fileNames = os.listdir(str_tempRCADirectory)
            list_fileNames = [os.path.join(str_tempRCADirectory, f) for f in list_fileNames] # add path to each file
            list_fileNames.sort(key=lambda x: os.path.getmtime(x))
            AgentLogger.debug(AgentLogger.STDOUT,'RCA sorted temp files : ' + repr(list_fileNames))
            for filePath in list_fileNames:
                if str_tempRCAFileName in filePath:
                    list_tempFileNames.append(filePath)
            list_rcaFilesForCalculatingAverage = list_tempFileNames[-5:]
            AgentLogger.debug(AgentLogger.STDOUT,'List of rca files for calculating process metrics average : ' + repr(list_rcaFilesForCalculatingAverage))
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' *************************** Exception while fetching rca file list for calculating average for process metrics *************************** '+ repr(e))
            traceback.print_exc()
        return list_rcaFilesForCalculatingAverage
    
    def fetchAvgProcessMetricsForRca(self):
        try:
            list_rcaFilesForCalculatingAverage = self.getRcaFileListForCalculatingProcessMetricsAvg()
            if AgentConstants.OS_NAME == AgentConstants.FREEBSD_OS:
                dict_topProcessMetricsAvgForRCA = self.calculateBSDTopProcessMetricsAvgForRca(list_rcaFilesForCalculatingAverage)
            else:
                dict_topProcessMetricsAvgForRCA = self.calculateTopProcessMetricsAvgForRca(list_rcaFilesForCalculatingAverage)
            return dict_topProcessMetricsAvgForRCA
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' *************************** Exception while fetching average process metrics for rca : '+repr(list_psCommandOutput)+' *************************** '+ repr(e))
            traceback.print_exc()

    def setSysLogQuery(self, rcaInfo):
        if rcaInfo.requestType == AgentConstants.GENERATE_NETWORK_RCA:
            rcaInfo.sysLogQuery = com.manageengine.monagent.communication.UdpHandler.SysLogQuery()
            rcaInfo.sysLogQuery.startTime = (rcaInfo.collectionTime - (300*1000))
            rcaInfo.sysLogQuery.endTime = (rcaInfo.collectionTime + (600*1000))
        elif rcaInfo.requestType == AgentConstants.RCA_REPORT:
            rcaInfo.sysLogQuery = com.manageengine.monagent.communication.UdpHandler.SysLogQuery()
            rcaInfo.sysLogQuery.startTime = (rcaInfo.collectionTime - (120*1000))
            rcaInfo.sysLogQuery.endTime = (rcaInfo.collectionTime + (120*1000))
        else:
            rcaInfo.sysLogQuery = com.manageengine.monagent.communication.UdpHandler.SysLogQuery()
            rcaInfo.sysLogQuery.startTime = (rcaInfo.collectionTime - (60*1000))
            rcaInfo.sysLogQuery.endTime = (rcaInfo.collectionTime + (60*1000))
        #AgentLogger.log(AgentLogger.STDOUT,'======================================= SYSLOGQUERY_GENERATED : '+repr(rcaInfo)+' =======================================')
    
    def setCollectorSysLogQuery(self, rcaInfo):
        rcaInfo.collectionTime  = AgentUtil.getCurrentTimeInMillis()
        self.setSysLogQuery(rcaInfo)
        AgentLogger.log(AgentLogger.STDOUT,'=======================================COLLECTOR SYSLOGQUERY_GENERATED : '+repr(rcaInfo)+' =======================================')

    def getSysLogQuery(self, rcaInfo):
        return rcaInfo.sysLogQuery
                       
    def generateRca(self, rcaInfo):
        from com.manageengine.monagent.collector.DataCollector import COLLECTOR, ProcessUtil
        AgentLogger.debug(AgentLogger.STDOUT,'======================================= GENERATE RCA : '+repr(rcaInfo.requestType)+' =======================================')
        sysLogMessagesList = None
        try:
            rcaInfo.collectionTime = AgentUtil.getCurrentTimeInMillis()
            self.setSysLogQuery(rcaInfo)
            dict_rcaMetrics = OrderedDict()
            dict_rcaMetrics['Top Process Report'] = OrderedDict()
            dict_processMetricsForRCA = self.fetchAvgProcessMetricsForRca()
            dict_processData, list_psCommandOutput = ProcessUtil.getProcessDetails(AgentConstants.DISCOVER_PROCESSES_AND_SERVICES)
            dict_rcaMetrics['Top Process Report']['top.process.cpu'] = ProcessUtil.sortProcessListAndConvertToDict(list_psCommandOutput, sortKey='cpu')
            dict_rcaMetrics['Top Process Report']['top.process.mem'] = ProcessUtil.sortProcessListAndConvertToDict(list_psCommandOutput, sortKey='mem')
            dict_rcaMetrics['Top Process Report']['top.process.avg.cpu'] = dict_processMetricsForRCA['TopProcessByCPU']
            dict_rcaMetrics['Top Process Report']['top.process.avg.mem'] = dict_processMetricsForRCA['TopProcessByMemory']
            dict_collectedData = COLLECTOR.collectData(COLLECTOR.getMonitorsGroup()['MonitorGroup']['RootCauseAnalysis'])
            AgentLogger.debug(AgentLogger.STDOUT,'Process metrics for rca : '+repr(dict_processMetricsForRCA))
            AgentLogger.debug(AgentLogger.STDOUT,'Other metrics for rca : '+repr(json.dumps(dict_collectedData)))#python dictionary to json string
            
            
            global RCA_DICT
            RCA_DICT = OrderedDict()
            RCA_DICT['TOPPROCESSCPU'] = dict_rcaMetrics['Top Process Report']['top.process.cpu']
            RCA_DICT['TOPPROCESSMEM'] = dict_rcaMetrics['Top Process Report']['top.process.mem']
            
            AgentLogger.debug(AgentLogger.STDOUT,'Top Rca Dict ===> '+repr(json.dumps(RCA_DICT)))#python dictionary to json string
            
            dict_rcaMetrics['CPU details'] = dict_collectedData.get('CollectedData', {}).get('RCA CPU Utilization', {})
            dict_rcaMetrics['CPU details']['Uptime Details'] = dict_collectedData.get('CollectedData', {}).get('Uptime Details', {})
            dict_rcaMetrics['Disk details'] = OrderedDict()
            dict_rcaMetrics['Disk details']['Disk utilization'] = dict_collectedData.get('CollectedData', {}).get('RCA Disk Utilization', {}).get('Disk details', {})
            dict_rcaMetrics['Disk details']['Disk I/O'] = dict_collectedData.get('CollectedData', {}).get('RCA Disk Statistics', {}).get('Disk I/O', {})
            dict_rcaMetrics['Memory details'] = OrderedDict()
            dict_rcaMetrics['Memory details']['Memory utilization'] = dict_collectedData.get('CollectedData', {}).get('RCA Memory Utilization', {}).get('Memory details', {})
            dict_rcaMetrics['Memory details']['Memory statistics'] = dict_collectedData.get('CollectedData', {}).get('RCA Memory Statistics', {}).get('Memory Statistics', {})
            dict_rcaMetrics['Network details'] = OrderedDict()
            dict_rcaMetrics['Network details']['NIC status'] = dict_collectedData.get('CollectedData', {}).get('RCA Adapter Details', {}).get('NIC Status', {})
            dict_rcaMetrics['Network details']['NIC traffic'] = dict_collectedData.get('CollectedData', {}).get('RCA Network Statistics', {}).get('Network Statistics', {})
            dict_rcaMetrics['User Sessions'] = dict_collectedData.get('CollectedData', {}).get('User Sessions', {})
            dict_rcaMetrics['Disk Errors'] = dict_collectedData.get('CollectedData', {}).get('Disk Errors', {})
            dict_rcaMetrics['Driver messages'] = dict_collectedData.get('CollectedData', {}).get('Dmesg Errors', {})
            sysLogMessagesList = com.manageengine.monagent.communication.UdpHandler.SysLogUtil.getLogMessages(rcaInfo.sysLogQuery)
            dict_rcaData = {
                                'ServerRCA' : dict_rcaMetrics,
                                'AgentKey' : AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),
                                'ApiKey' : AgentConstants.CUSTOMER_ID,
                                'CollectionTime' : str(AgentUtil.getTimeInMillis(rcaInfo.collectionTime)),
                                'ErrorCode' : '0',
                                'AGENTCOLLECTIONTIME' : str(rcaInfo.collectionTime),
                                'FMTAGENTCOLLECTIONTIME' : str(AgentUtil.getFormattedTime(rcaInfo.collectionTime)),
                                
                            }
            if rcaInfo.requestType == AgentConstants.GENERATE_NETWORK_RCA:
                dict_rcaData['AGENTNWSHUTDOWNTIME'] = str(rcaInfo.collectionTime)
                dict_rcaData['FMTAGENTNWSHUTDOWNTIME'] = str(AgentUtil.getFormattedTime(rcaInfo.collectionTime))
                dict_rcaData['FMTAGENTNWCOLLECTIONTIME'] = str(AgentUtil.getFormattedTime(rcaInfo.collectionTime))
                dict_rcaData['Reason'] = 'Network connectivity error'
                if len(sysLogMessagesList) != 1:
                    dict_rcaData['NetworkRCA'] = {'Event Log' : {'EventLog' : sysLogMessagesList}}
            else:
                if rcaInfo.requestType == AgentConstants.RCA_REPORT:
                    dict_rcaData['Reason'] = '-' # user initiated request cannot have reason
                if len(sysLogMessagesList) != 1:
                    dict_rcaMetrics['Event Log'] = {'EventLog' : sysLogMessagesList}
                    AgentLogger.debug(AgentLogger.STDOUT, 'Number of sysLog messages for rca : '+repr(len(sysLogMessagesList)))
                    AgentLogger.debug(AgentLogger.STDOUT, 'SysLog messages for rca : '+repr(sysLogMessagesList))
            rcaInfo.data = dict_rcaData
            self.saveRca(rcaInfo)
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while generating rca ************************* '+repr(e))
            traceback.print_exc()
    
    def backupRcaFile(self, reason):
        AgentLogger.log([AgentLogger.STDOUT], 'Backup rca report : '+repr(reason))
        list_files = FileUtil.getSortedFileList(AgentConstants.AGENT_TEMP_RCA_REPORT_DIR, str_loggerName=AgentLogger.STDOUT)
        time.sleep(1)# Just to avoid partially generated rca reports
        for file in list_files[-2:]:
            AgentLogger.log(str_loggerName,'Copying rca report file : '+repr(src)+' to '+repr(dst))
            FileUtil.copyFile(file, AgentConstants.AGENT_TEMP_RCA_REPORT_BACKUP_DIR)
    
    def getRcaFileList(self, rcaInfo):
        list_rcaReportFiles = []
        list_files = None
        if (rcaInfo.requestType == AgentConstants.GENERATE_RCA or rcaInfo.requestType == AgentConstants.RCA_REPORT) and (rcaInfo.action == AgentConstants.UPLOAD_RCA or rcaInfo.action == AgentConstants.SAVE_AND_UPLOAD_RCA_REPORT):
            list_files = FileUtil.getSortedFileList(AgentConstants.AGENT_TEMP_RCA_REPORT_DIR, str_loggerName=AgentLogger.STDOUT)
            AgentLogger.log(AgentLogger.STDOUT, 'Rca report files fetched from : '+repr(AgentConstants.AGENT_TEMP_RCA_REPORT_DIR)+' : '+repr(self.getFormattedFileList(list_files)))
        elif rcaInfo.requestType == AgentConstants.GENERATE_NETWORK_RCA and rcaInfo.action == AgentConstants.UPLOAD_RCA:
            list_files = FileUtil.getSortedFileList(AgentConstants.AGENT_TEMP_RCA_REPORT_NETWORK_DIR, str_loggerName=AgentLogger.STDOUT)
            AgentLogger.log(AgentLogger.STDOUT, 'Rca report files fetched from : '+repr(AgentConstants.AGENT_TEMP_RCA_REPORT_NETWORK_DIR)+' : '+repr(self.getFormattedFileList(list_files)))
            if not list_files:
                list_files = FileUtil.getSortedFileList(AgentConstants.AGENT_TEMP_RCA_REPORT_DIR, str_loggerName=AgentLogger.STDOUT)
                AgentLogger.log(AgentLogger.STDOUT, 'Network rca report directory is empty. Rca report files fetched from : '+repr(AgentConstants.AGENT_TEMP_RCA_REPORT_DIR)+' : '+repr(self.getFormattedFileList(list_files)))
        if rcaInfo.searchTime: 
            for fileName in list_files:
                if '_Rca_Report' not in fileName:
                    continue
                tempList = fileName.split('_')
                rcaStartTime = tempList[1]
                rcaEndTime = tempList[2]
                if (int(rcaStartTime) <= (int(rcaInfo.searchTime))) and (int(rcaEndTime) >= (int(rcaInfo.searchTime))):
                    list_rcaReportFiles.append(fileName)
            if not list_rcaReportFiles:
                AgentLogger.log(AgentLogger.STDOUT, 'Unable to find rca report files for the search time : '+repr(rcaInfo.searchTime)+' -- > '+repr(AgentUtil.getFormattedTime(rcaInfo.searchTime)))
        else:
            list_rcaReportFiles.append(list_files[-1])
            AgentLogger.log(AgentLogger.STDOUT, 'No search period for rca. Hence sending the latest rca report file')
        AgentLogger.log(AgentLogger.STDOUT, 'List of rca report files : '+repr(self.getFormattedFileList(list_rcaReportFiles)))
        return list_rcaReportFiles
    
    def getFormattedFileList(self, list_files):
        dict_toReturn = None
        if list_files:
            dict_toReturn = OrderedDict()
            for fileName in list_files:
                tempList = fileName.split('_')
                rcaStartTime = tempList[1]
                rcaEndTime = tempList[2]
                dict_toReturn[fileName] = str(AgentUtil.getFormattedTime(rcaStartTime))+' to '+str(AgentUtil.getFormattedTime(rcaEndTime))
        return dict_toReturn
    
    def setRcaFileName(self, rcaInfo):
        str_fileName = None
        str_filePath = None
        str_customName = None
        if rcaInfo.action != AgentConstants.SAVE_RCA_RAW:
            str_customName = str(rcaInfo.sysLogQuery.startTime)+'_'+str(rcaInfo.sysLogQuery.endTime)
        if rcaInfo.requestType == AgentConstants.GENERATE_NETWORK_RCA and rcaInfo.action == AgentConstants.SAVE_RCA_REPORT:
            str_customName+='_Rca_Report_Network'
            str_fileName = FileUtil.getUniqueFileName(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'), str_customName, True)
            str_filePath = AgentConstants.AGENT_TEMP_RCA_REPORT_NETWORK_DIR +'/'+str_fileName
        elif rcaInfo.requestType == AgentConstants.GENERATE_RCA or rcaInfo.requestType == AgentConstants.RCA_REPORT:
            str_customName+='_Rca_Report'
            str_fileName = FileUtil.getUniqueFileName(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'), str_customName, True)
            str_filePath = AgentConstants.AGENT_TEMP_RCA_REPORT_DIR +'/'+str_fileName
        elif rcaInfo.action == AgentConstants.SAVE_RCA_RAW:
            str_customName = 'Rca_Raw'
            str_fileName = FileUtil.getUniqueFileName(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'), str_customName)
            str_filePath = AgentConstants.AGENT_TEMP_RCA_RAW_DATA_DIR +'/'+str_fileName
        rcaInfo.fileName = str_fileName
        rcaInfo.filePath = str_filePath

    def saveRca(self, rcaInfo):
        try:
            self.setRcaFileName(rcaInfo)
            if rcaInfo.action != AgentConstants.SAVE_RCA_RAW:
                AgentLogger.debug(AgentLogger.STDOUT,'Saving rca for the rcaInfo : '+repr(rcaInfo))
            fileObj = AgentUtil.FileObject()
            fileObj.set_fileName(rcaInfo.fileName)
            fileObj.set_filePath(rcaInfo.filePath)
            fileObj.set_data(rcaInfo.data)
            fileObj.set_dataType('json')
            fileObj.set_mode('wb')
            fileObj.set_dataEncoding('UTF-16LE')
            fileObj.set_logging(False)
            fileObj.set_loggerName(AgentLogger.STDOUT)            
            bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' *************************** Exception while saving process data for rca : '+repr(rcaInfo.data)+' *************************** '+ repr(e))
            traceback.print_exc()
        
    def uploadRca(self, rcaInfo):
        from com.manageengine.monagent.communication import CommunicationHandler
        bool_isSuccess = True
        str_rcaReportFilePath = None
        AgentLogger.log(AgentLogger.STDOUT,'======================================= UPLOAD '+repr(rcaInfo.requestType)+' =======================================')
        try:  
            AgentLogger.log(AgentLogger.STDOUT,'Uploading rca for the rcaInfo : '+repr(rcaInfo))
            if rcaInfo.requestType != AgentConstants.RCA_REPORT:
                list_rcaReportFiles = self.getRcaFileList(rcaInfo)
                if len(list_rcaReportFiles) != 0:
                    str_rcaReportFilePath = list_rcaReportFiles[0]
                else:
                    AgentLogger.log(AgentLogger.STDOUT,'Rca report file list is empty. Failed to upload rca!!!!')
                    return False
            else:
                str_rcaReportFilePath = rcaInfo.filePath
            fileObj = AgentUtil.FileObject()
            fileObj.set_filePath(str_rcaReportFilePath)
            fileObj.set_dataType('json')
            fileObj.set_mode('rb')
            fileObj.set_dataEncoding('UTF-16')
            fileObj.set_loggerName(AgentLogger.STDOUT)
            fileObj.set_logging(False)
            bool_toReturn, dict_rcaData = FileUtil.readData(fileObj)
            AgentLogger.log(AgentLogger.STDOUT,"RCA report to be uploaded was created at : "+repr(AgentUtil.getFormattedTime(float(dict_rcaData['AGENTCOLLECTIONTIME']))))
            if rcaInfo.requestType == AgentConstants.GENERATE_RCA:
                dict_rcaData['Reason'] = str(AgentConstants.AGENT_BOOT_STATUS)
            isDST = time.localtime().tm_isdst
            if isDST == 1:
                dict_rcaData['TIMEZONE'] = str(AgentConstants.AGENT_TIME_ZONE[1])
            elif isDST == 0:
                dict_rcaData['TIMEZONE'] = str(AgentConstants.AGENT_TIME_ZONE[0])
            dict_rcaData['AGENTSTARTUPTIME'] = str(AgentConstants.AGENT_MACHINE_START_TIME)
            dict_rcaData['AGENTSHUTDOWNTIME'] = str(AgentConstants.AGENT_MACHINE_SHUTDOWN_TIME)
            dict_rcaData['FMTAGENTSHUTDOWNTIME'] = str(AgentUtil.getFormattedTime(AgentConstants.AGENT_MACHINE_SHUTDOWN_TIME))
            if rcaInfo.requestType == AgentConstants.GENERATE_NETWORK_RCA:
                dict_rcaData['SHUTDOWNTIME'] = str(rcaInfo.downTimeInServer)
            else:
                dict_rcaData['SHUTDOWNTIME'] = str(AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_SHUTDOWN_TIME)
            if AgentConstants.AGENT_BOOT_STATUS == AgentConstants.AGENT_SERVICE_RESTART_MESSAGE:
                if rcaInfo.requestType == AgentConstants.GENERATE_NETWORK_RCA:
                    dict_rcaData['STARTUPTIME'] = str(rcaInfo.collectionTime)
                else:
                    if (AgentConstants.AGENT_REGISTRATION_TIME == -1):
                        AgentConstants.AGENT_REGISTRATION_TIME = AgentUtil.getCurrentTimeInMillis()
                        AgentConstants.AGENT_TIME_DIFF_BASED_REGISTRATION_TIME = AgentUtil.getTimeInMillis(AgentConstants.AGENT_REGISTRATION_TIME)
                    dict_rcaData['STARTUPTIME'] = str(AgentConstants.AGENT_TIME_DIFF_BASED_REGISTRATION_TIME)
            else:
                dict_rcaData['STARTUPTIME'] = str(AgentConstants.AGENT_MACHINE_TIME_DIFF_BASED_START_TIME)
            if not bool_toReturn:
                AgentLogger.log(AgentLogger.STDOUT, 'Unable to read data from the rca report file : '+repr(str_rcaReportFilePath))
                return False      
            if rcaInfo.isUserInitiated:
                dict_rcaData['USER_INITIATED'] = 'true'
            if rcaInfo.downTimeInServer:
                dict_rcaData['DOWNTIME'] = int(rcaInfo.downTimeInServer)
            str_jsonData = json.dumps(dict_rcaData)#python dictionary to json string
            #AgentLogger.log(AgentLogger.STDOUT,'RCA json data : '+repr(str_jsonData))
            str_url = None
            str_servlet = AgentConstants.DATA_AGENT_HANDLER_SERVLET
            dict_requestParameters      =   {
            'action'   :   AgentConstants.RCA_REPORT,
            'bno' : AgentConstants.AGENT_VERSION,
            'agentKey'  :   AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')         
            }
            if not dict_requestParameters == None:
                str_requestParameters = urlencode(dict_requestParameters)
                str_url = str_servlet + str_requestParameters
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.STDOUT)
            requestInfo.set_method(AgentConstants.HTTP_POST)
            requestInfo.set_url(str_url)
            requestInfo.set_data(str_jsonData)
            requestInfo.add_header("Content-Type", 'application/json')
            requestInfo.add_header("Accept", "text/plain")
            requestInfo.add_header("Connection", 'close')
            bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
            if bool_toReturn:
                if FileUtil.copyFile(str_rcaReportFilePath, AgentConstants.AGENT_TEMP_RCA_REPORT_UPLOADED_DIR):
                    FileUtil.deleteFile(str_rcaReportFilePath)
            if 'SHUTDOWNTIME' in dict_rcaData:
                AgentLogger.log(AgentLogger.STDOUT,'RCA SHUTDOWNTIME : '+repr(AgentUtil.getFormattedTime(dict_rcaData['SHUTDOWNTIME']))+' --> '+repr(dict_rcaData['SHUTDOWNTIME']))
            if 'DOWNTIME' in dict_rcaData:
                AgentLogger.log(AgentLogger.STDOUT,'RCA DOWNTIME : '+repr(AgentUtil.getFormattedTime(dict_rcaData['DOWNTIME']))+' --> '+repr(dict_rcaData['DOWNTIME']))
            if 'STARTUPTIME' in dict_rcaData and dict_rcaData['STARTUPTIME'] != 'None':
                AgentLogger.log(AgentLogger.STDOUT,'RCA STARTUPTIME : '+repr(AgentUtil.getFormattedTime(int(dict_rcaData['STARTUPTIME'])))+' --> '+repr(dict_rcaData['STARTUPTIME'])) 
            if 'AGENTNWSHUTDOWNTIME' in dict_rcaData:
                AgentLogger.log(AgentLogger.STDOUT,'RCA AGENTNWSHUTDOWNTIME : '+repr(AgentUtil.getFormattedTime(dict_rcaData['AGENTNWSHUTDOWNTIME']))+' --> '+repr(dict_rcaData['AGENTNWSHUTDOWNTIME']))
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR], ' *************************** Exception while uploading rca *************************** '+ repr(e))
            traceback.print_exc()
            bool_isSuccess = False
        return bool_isSuccess
    
    def generateAndUploadRca(self, rcaInfo):
        try:
            self.generateRca(rcaInfo)
            self.uploadRca(rcaInfo)
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR], ' *************************** Exception while generating and uploading rca *************************** '+ repr(e))
            traceback.print_exc()
            bool_isSuccess = False
    
    def handleWmsRequest(self, dict_wmsParams):
        str_requestType = None
        try:
            AgentLogger.log(AgentLogger.STDOUT,'======================================= RCA WMS REQUEST =======================================')
            AgentLogger.log(AgentLogger.STDOUT,'Rca parameters from WMS : '+repr(dict_wmsParams))
            str_requestType = dict_wmsParams['REQUEST_TYPE']
            if str_requestType == AgentConstants.GENERATE_NETWORK_RCA:   
                rcaInfo = RcaInfo()
                rcaInfo.requestType = AgentConstants.GENERATE_NETWORK_RCA
                rcaInfo.action = AgentConstants.UPLOAD_RCA
                if 'downtime' in dict_wmsParams:
                    rcaInfo.downTimeInServer = int(dict_wmsParams['downtime'])
                    rcaInfo.searchTime = AgentUtil.getCurrentTimeInMillis(int(dict_wmsParams['downtime']))
                if 'USER_INITIATED' in dict_wmsParams:
                    rcaInfo.isUserInitiated = dict_wmsParams['USER_INITIATED']
                self.uploadRca(rcaInfo)
            elif str_requestType == AgentConstants.GENERATE_RCA:
                rcaInfo = RcaInfo()
                rcaInfo.requestType = AgentConstants.GENERATE_RCA
                rcaInfo.action = AgentConstants.UPLOAD_RCA
                if 'downtime' in dict_wmsParams:
                    rcaInfo.downTimeInServer = int(dict_wmsParams['downtime'])
                    rcaInfo.searchTime = AgentUtil.getCurrentTimeInMillis(int(dict_wmsParams['downtime']))
                if 'USER_INITIATED' in dict_wmsParams:
                    rcaInfo.isUserInitiated = dict_wmsParams['USER_INITIATED']
                self.uploadRca(rcaInfo)
            elif str_requestType == AgentConstants.RCA_REPORT:   
                rcaInfo = RcaInfo()
                rcaInfo.requestType = AgentConstants.RCA_REPORT
                rcaInfo.action = AgentConstants.UPLOAD_RCA
                if 'USER_INITIATED' in dict_wmsParams:
                    rcaInfo.isUserInitiated = dict_wmsParams['USER_INITIATED']
                self.generateAndUploadRca(rcaInfo)
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR], ' *************************** Exception while handling rca related WMS request *************************** '+ repr(e))
            traceback.print_exc()
            bool_isSuccess = False
    
