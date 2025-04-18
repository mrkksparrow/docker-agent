# $Id$
import traceback
import sys, os, time
import collections

from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil
from com.manageengine.monagent import ifaddrs
import com

def parse(dict_inputMonitorInfo, tuple_commandResult):  
    list_outputLines = None
    list_lineTokens = None    
    str_outputDelimiter = ' '
    int_lineToParse = 0
    int_tokenToParse = 0
    list_collectedData = []
    dict_collectedData = collections.OrderedDict()
    boolean_isSuccess = False
    str_commandOutput = None
    try:
        boolean_isSuccess, str_commandOutput = tuple_commandResult
        str_monitorName = dict_inputMonitorInfo['Id']
        #AgentLogger.log(AgentLogger.MAIN,'monitor info dict : '+repr(dict_inputMonitorInfo))
        if 'filePath' in dict_inputMonitorInfo:
            boolean_isSuccess, str_commandOutput = getOutputFromFile(dict_inputMonitorInfo['filePath'])
            FileUtil.deleteFile(dict_inputMonitorInfo['filePath'])
        dict_monInfo = com.manageengine.monagent.collector.DataCollector.COLLECTOR.getMonitors()[str_monitorName]
        AgentLogger.debug(AgentLogger.COLLECTOR,'Monitor attributes from xml : '+repr(dict_inputMonitorInfo))
        #AgentLogger.log(AgentLogger.COLLECTOR,'Parse info from xml : '+ repr(dict_monInfo))
        if 'counter' in dict_inputMonitorInfo:
            if str_monitorName in com.manageengine.monagent.collector.DataCollector.PREVIOUS_COUNTER_VALUES:
                com.manageengine.monagent.collector.DataCollector.PREVIOUS_COUNTER_VALUES[str_monitorName]['CollectionTime_Previous'] = com.manageengine.monagent.collector.DataCollector.PREVIOUS_COUNTER_VALUES[str_monitorName]['CollectionTime']
                com.manageengine.monagent.collector.DataCollector.PREVIOUS_COUNTER_VALUES[str_monitorName]['CollectionTime'] = time.time()
            else:
                com.manageengine.monagent.collector.DataCollector.PREVIOUS_COUNTER_VALUES[str_monitorName] = {}
                com.manageengine.monagent.collector.DataCollector.PREVIOUS_COUNTER_VALUES[str_monitorName]['CollectionTime_Previous'] = time.time()
                com.manageengine.monagent.collector.DataCollector.PREVIOUS_COUNTER_VALUES[str_monitorName]['CollectionTime'] = time.time()
            AgentLogger.debug(AgentLogger.COLLECTOR,'PREVIOUS_COUNTER_VALUES : '+ repr(com.manageengine.monagent.collector.DataCollector.PREVIOUS_COUNTER_VALUES[str_monitorName]))
        if boolean_isSuccess:
            dict_collectedData['ERRORMSG'] = 'NO ERROR'
            if str_monitorName == AgentConstants.PROCESS_MONITORING:
                dict_collectedEntityInfo, list_psCommandOutput = com.manageengine.monagent.collector.DataCollector.ProcessUtil.getProcessMonitoringData(str_commandOutput)
            elif str_monitorName == AgentConstants.PROCESS_AND_SERVICE_DETAILS:
                #AgentLogger.log(AgentLogger.MAIN, "process output in parse {}".format(str_commandOutput))          
                dict_collectedEntityInfo, list_psCommandOutput = com.manageengine.monagent.collector.DataCollector.ProcessUtil.getProcessDetails(str_monitorName, str_commandOutput)
            elif 'parse' in dict_inputMonitorInfo and dict_inputMonitorInfo['parse'] == 'false':
                dict_collectedEntityInfo = collections.OrderedDict()
                if 'alias' in dict_inputMonitorInfo:
                    dict_collectedEntityInfo[dict_inputMonitorInfo['alias']] = str_commandOutput
                else:
                    dict_collectedEntityInfo['Output'] = str_commandOutput
                list_collectedData.append(dict_collectedEntityInfo)
            elif 'parseAll' in dict_inputMonitorInfo and dict_inputMonitorInfo['parseAll'] == 'true':
                list_outputLines = str_commandOutput.split('\n')
                if dict_inputMonitorInfo['Id'] == 'Network Data':
                    dict_hostIntfDetails = ifaddrs.getifaddrs()
                for outputLine in list_outputLines:
                    #AgentLogger.log(AgentLogger.COLLECTOR,'Parsing output line : '+ repr(outputLine))
                    if outputLine.strip() == '':
                        continue
                    dict_collectedEntityInfo = collections.OrderedDict()
                    dict_entityDetails = None
                    for key in list(dict_monInfo['Entities'].keys()):     
                        str_parsedValue = ''          
                        try:
                            dict_entityDetails = dict_monInfo['Entities'][key] 
                            if 'default' in dict_entityDetails:
                                str_parsedValue = dict_entityDetails['default']
                            #AgentLogger.log(AgentLogger.COLLECTOR,'Entity Details : '+ repr(dict_entityDetails))                   
                            int_tokenToParse = int(dict_entityDetails['token'])
                            if 'delimiter' in dict_entityDetails:
                                str_outputDelimiter = dict_entityDetails['delimiter']
                            if not str_outputDelimiter in outputLine:
                                continue        
                            list_lineTokens = removeEmptyTokens(outputLine.split(str_outputDelimiter))
                            #AgentLogger.log(AgentLogger.COLLECTOR,'Output Line Tokens : '+ repr(list_lineTokens))
                            if len(list_lineTokens) >= int_tokenToParse:                            
                                str_parsedValue  = list_lineTokens.pop(int_tokenToParse - 1)
                            if 'counter' in dict_entityDetails and dict_entityDetails['counter'] == 'true':
                                str_parsedValue = handleCounterValues(str_monitorName, dict_entityDetails, str_parsedValue.strip(), dict_collectedEntityInfo)
                            if 'sendValue' in dict_entityDetails and dict_entityDetails['sendValue'] == 'false':
                                pass
                            else:
                                dict_collectedEntityInfo[dict_entityDetails['name']] = str_parsedValue.strip()
                        except Exception as e:
                            AgentLogger.log(AgentLogger.COLLECTOR,' *************************** Exception while trying to parse value for entity : '+key+', Command output : '+repr(list_lineTokens)+', Entity details : '+repr(dict_entityDetails)+' *************************** '+ repr(e))
                            traceback.print_exc()
                            dict_collectedEntityInfo[dict_entityDetails['name']] = str_parsedValue
                        finally:                    
                            list_lineTokens = None
                            str_outputDelimiter = ' '
                    AgentLogger.debug(AgentLogger.COLLECTOR,'Parsed values : '+repr(dict_collectedEntityInfo))
                    if dict_inputMonitorInfo['Id'] == 'CPU Cores Usage':
                        individualCoreCpuUtilization(dict_collectedEntityInfo)
                    if dict_inputMonitorInfo['Id'] == 'Disk Utilization':
                        calcDiskPercentages(dict_collectedEntityInfo)
                    if dict_inputMonitorInfo['Id'] == 'Network Data':
                        setNetworkData(dict_collectedEntityInfo, dict_hostIntfDetails)
                    if dict_collectedEntityInfo:
                        list_collectedData.append(dict_collectedEntityInfo)
            else:
                dict_collectedEntityInfo = collections.OrderedDict()
                dict_entityDetails = None
                for key in list(dict_monInfo['Entities'].keys()):     
                    str_parsedValue = '' 
                    str_lineToParse = ''      
                    try:
                        dict_entityDetails = dict_monInfo['Entities'][key] 
                        #AgentLogger.log(AgentLogger.COLLECTOR,'Entity Details : '+ repr(dict_entityDetails))   
                        if 'default' in dict_entityDetails:
                            str_parsedValue = dict_entityDetails['default']          
                            dict_collectedEntityInfo[dict_entityDetails['name']] = str_parsedValue.strip()
                            continue
                        int_lineToParse = int(dict_entityDetails['parseLine'])
                        int_tokenToParse = int(dict_entityDetails['token'])
                        if 'delimiter' in dict_entityDetails:
                            str_outputDelimiter = dict_entityDetails['delimiter']
                        list_outputLines = str_commandOutput.split('\n')   
                        if len(list_outputLines) >= int_lineToParse:
                            str_lineToParse = list_outputLines.pop(int_lineToParse - 1)
                        if not str_outputDelimiter in str_lineToParse:
                            continue
                        list_lineTokens = removeEmptyTokens(str_lineToParse.split(str_outputDelimiter))
                        #AgentLogger.log(AgentLogger.COLLECTOR,'Output Line Tokens : '+ repr(list_lineTokens))
                        if not len(list_lineTokens) < int_tokenToParse:
                            str_parsedValue  = list_lineTokens.pop(int_tokenToParse - 1)
                        if 'counter' in dict_entityDetails and dict_entityDetails['counter'] == 'true':
                            str_parsedValue = handleCounterValues(str_monitorName, dict_entityDetails, str_parsedValue.strip(), dict_collectedEntityInfo)
                        if 'sendValue' in dict_entityDetails and dict_entityDetails['sendValue'] == 'false':
                            pass
                        else:
                            dict_collectedEntityInfo[dict_entityDetails['name']] = str_parsedValue.strip()
                    except Exception as e:
                        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],' *************************** Exception while trying to parse value for entity : '+key+', Command output : '+repr(list_lineTokens)+', Entity details : '+repr(dict_entityDetails)+' *************************** '+ repr(e))
                        traceback.print_exc()
                        dict_collectedEntityInfo[dict_entityDetails['name']] = str_parsedValue.strip()
                    finally:
                        list_outputLines = None
                        list_lineTokens = None
                        str_outputDelimiter = ' '
                if dict_inputMonitorInfo['Id'] == 'CPU Utilization':
                    calculateAvgCPU(dict_collectedEntityInfo)
                if dict_inputMonitorInfo['Id'] == 'Memory Utilization':
                    calcMemoryPercentages(dict_collectedEntityInfo)
                AgentLogger.debug([AgentLogger.COLLECTOR,AgentLogger.STDERR],'Parsed Values : '+repr(dict_collectedEntityInfo))
                if dict_collectedEntityInfo:
                    list_collectedData.append(dict_collectedEntityInfo)
        else:
            dict_collectedData['ERRORMSG'] = 'FAILURE'   
            dict_collectedEntityInfo = collections.OrderedDict()
            list_collectedData.append(dict_collectedEntityInfo) 
        if str_monitorName == AgentConstants.PROCESS_AND_SERVICE_DETAILS or str_monitorName == AgentConstants.PROCESS_MONITORING:
            dict_collectedData['NAME'] = dict_inputMonitorInfo['Id']
            dict_collectedData['Process Details'] = dict_collectedEntityInfo['Process Details']
        else:
            if 'alias' in dict_inputMonitorInfo:
                dict_collectedData[dict_inputMonitorInfo['alias']] = list_collectedData
            else:
                dict_collectedData[dict_inputMonitorInfo['Id']] = list_collectedData
        if 'parseImpl' in dict_inputMonitorInfo:
            dict_collectedData['parseTag'] = dict_inputMonitorInfo['parseImpl']
        #AgentLogger.log(AgentLogger.MAIN,'collected data -- {0}'.format(dict_collectedData))
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],' *************************** Exception While Parsing Command Output *************************** '+ repr(e))
        traceback.print_exc()
    finally:
        list_outputLines = None
        list_lineTokens = None  
        str_commandOutput = None
    return dict_collectedData

def calculateAvgCPU(dictData):
    try:
        if 'LoadPercentage' in dictData:
            AgentLogger.log(AgentLogger.COLLECTOR,' Add and extract for CPU value : ' + str(dictData['LoadPercentage']) ) 
            cpu_util = AgentUtil.custom_float(dictData['LoadPercentage'])
            avg_cpu = com.manageengine.monagent.collector.DataCollector.addAndFindAverage(cpu_util)
            dictData['LoadPercentage'] = str(avg_cpu)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],' *************************** Exception while calculation average cpu utilization ***************************** '+ repr(e))
        traceback.print_exc()

def calcDiskPercentages(dictData):
    diskFreePercent = 0
    try:
        freeSpace = int(dictData['FreeSpace'])
        totalSize = int(dictData['Size'])
        diskFreePercent = round(((freeSpace/totalSize)*100),2)
        AgentLogger.log(AgentLogger.COLLECTOR,'Free disk percent for %s is %s '%(dictData['Name'],str(diskFreePercent)))
        dictData['FreeDiskPercent'] = str(diskFreePercent)
    except ZeroDivisionError as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'Free disk percent for %s is %s '%(dictData['Name'],str(diskFreePercent)))
        dictData['FreeDiskPercent'] = str(diskFreePercent)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],' *************************** Exception while calculating individual disk utilization free percentage ***************************** '+ repr(e))
        traceback.print_exc()
                 
def calcMemoryPercentages(dictData):
    freePhyMemPercentage = 0
    freeVirtualMemPercentage = 0
    try:
        freePhyMem = int(dictData['FreePhysicalMemory'])
        totPhyMem = int(dictData['TotalVisibleMemorySize'])
        freePhyMemPercentage = round(((freePhyMem/totPhyMem)*100),2)
        freeVirtMem = int(dictData['FreeVirtualMemory'])
        totVirtMem = int(dictData['TotalVirtualMemorySize'])
        freeVirtualMemPercentage = round(((freeVirtMem/totVirtMem)*100),2)
        #AgentLogger.log(AgentLogger.COLLECTOR,' Memory percentages calculated are %s and %s '%(str(freePhyMemPercentage),str(freeVirtualMemPercentage)))
        dictData['FreePhyPercent'] = str(freePhyMemPercentage)
        dictData['FreeVirtPercent'] = str(freeVirtualMemPercentage)
    except ZeroDivisionError as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'Free Physical and virtual memory percentages are %s and %s '%(str(freePhyMemPercentage),str(freeVirtualMemPercentage)))
        dictData['FreePhyPercent'] = str(freePhyMemPercentage)
        dictData['FreeVirtPercent'] = str(freeVirtualMemPercentage)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],' *************************** Exception while calculating individual disk utilization free percentage ***************************** '+ repr(e))
        traceback.print_exc()

def setNetworkData(dict_collectedEntityInfo,dict_hostIntfDetails):
    try:
        if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS]:
            dict_collectedEntityInfo['Ipv4Addrs'] = AgentConstants.DEFAULT_IPV4_ADDRESS
            dict_collectedEntityInfo['Ipv6Addrs'] = AgentConstants.DEFAULT_IPV6_ADDRESS
        if (('AdapterDesc' in dict_collectedEntityInfo) and (dict_collectedEntityInfo['AdapterDesc'] in dict_hostIntfDetails) and (dict_hostIntfDetails[dict_collectedEntityInfo['AdapterDesc']])):
            if 2 in dict_hostIntfDetails[dict_collectedEntityInfo['AdapterDesc']] and 'addr' in dict_hostIntfDetails[dict_collectedEntityInfo['AdapterDesc']][int('2')]:
                dict_collectedEntityInfo['Ipv4Addrs'] = dict_hostIntfDetails[dict_collectedEntityInfo['AdapterDesc']][int('2')]['addr']
            if 10 in dict_hostIntfDetails[dict_collectedEntityInfo['AdapterDesc']] and 'addr' in dict_hostIntfDetails[dict_collectedEntityInfo['AdapterDesc']][int('10')]:
                dict_collectedEntityInfo['Ipv6Addrs'] = dict_hostIntfDetails[dict_collectedEntityInfo['AdapterDesc']][int('10')]['addr']
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],' *************************** Exception While Parsing Network Data only *************************** '+ repr(e))
        traceback.print_exc()

def individualCoreCpuUtilization(dict_collectedEntityInfo):
    coreUtilizationPercent = 0
    try:
        dict_collectedEntityInfo['Name'] = dict_collectedEntityInfo['Name'].strip('cpu')  #Stripping cpu from Name key
        coreCpuTotalTime = int(float(dict_collectedEntityInfo['UserModeTime']))+int(float(dict_collectedEntityInfo['NiceTime']))+int(float(dict_collectedEntityInfo['SystemModeTime']))+int(float(dict_collectedEntityInfo['IdleTime']))+int(float(dict_collectedEntityInfo['IOWaitTime']))+int(float(dict_collectedEntityInfo['InterruptServicingTime']))+int(float(dict_collectedEntityInfo['SoftirqsServicingTime']))+int(float(dict_collectedEntityInfo['OtherOsVirtualEnvTime']))+int(float(dict_collectedEntityInfo['GuestOsVirtualCpuRunTime']))+int(float(dict_collectedEntityInfo['NicedGuestRunTime']))
        coreCpuUsage = int(float(dict_collectedEntityInfo['UserModeTime']))+int(float(dict_collectedEntityInfo['SystemModeTime']))
        #AgentLogger.log(AgentLogger.COLLECTOR,'Core cpu total : '+str(coreCpuTotalTime))
        #coreIdleTime = int(dict_collectedEntityInfo['IdleTime'])  
        #coreIdleTime = int(dict_collectedEntityInfo['IdleTime'])+int(dict_collectedEntityInfo['IOWaitTime'])
        coreUtilizationPercent = round((((coreCpuUsage)/coreCpuTotalTime)*100),2) 
        #coreUtilizationPercent = round((((coreCpuTotalTime - coreIdleTime)/coreCpuTotalTime)*100),2)
        AgentLogger.debug(AgentLogger.COLLECTOR,'Core utilization percent for %s is %s ' %(dict_collectedEntityInfo['Name'],str(coreUtilizationPercent)))
        dict_collectedEntityInfo['PercentProcessorTime'] = str(coreUtilizationPercent)
    except ZeroDivisionError as e:
        AgentLogger.debug(AgentLogger.COLLECTOR,'Core utilization percent for %s is %s ' %(dict_collectedEntityInfo['Name'],str(coreUtilizationPercent)))
        dict_collectedEntityInfo['PercentProcessorTime'] = str(coreUtilizationPercent)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],' *************************** Exception while calculation individual core cpu utilization ***************************** '+ repr(e))
        traceback.print_exc()
    
def getOutputFromFile(str_filePath):
    bool_toReturn = True        
    fileSysEncoding = sys.getfilesystemencoding()
    file_obj = None
    str_data = None
    try:            
        if os.path.isfile(str_filePath):                
            file_obj = open(str_filePath,'rb')
            byte_data = file_obj.read()
            str_data = byte_data.decode(fileSysEncoding)
        else:
            bool_toReturn = False
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception While Reading The file '+repr(str_filePath)+' ************************* '+ repr(e))
        traceback.print_exc()      
        bool_toReturn = False          
    finally:
        if file_obj:
            file_obj.close()
    return bool_toReturn, str_data
    

def removeEmptyTokens(list_tokens):
    list_toReturn = []
    for token in list_tokens:
        if not token == '':
            list_toReturn.append(token)
    return list_toReturn

def handleCounterValues(str_monitorName, dict_entityDetails, str_currentValue, dict_collectedEntityInfo):
    toReturn = 0
    try:
        str_entityName = dict_entityDetails['Id']
        str_entityName_previous = str_entityName + '_Previous'
        str_expression = ''
        str_unique = ''
        str_uniqueEntityName = ''
        str_timeDiff = ''
        if 'unique' in dict_entityDetails:
            str_unique = dict_collectedEntityInfo[dict_entityDetails['unique']]
            str_uniqueEntityName = str_entityName + '_' + str_unique
        else:
            str_uniqueEntityName = str_entityName
        if str_uniqueEntityName in com.manageengine.monagent.collector.DataCollector.PREVIOUS_COUNTER_VALUES[str_monitorName]:
            str_previousValue = str(com.manageengine.monagent.collector.DataCollector.PREVIOUS_COUNTER_VALUES[str_monitorName][str_uniqueEntityName])
            if 'expression' in dict_entityDetails:
                str_expression = dict_entityDetails['expression']
                str_expression = str_expression.replace(('$'+str_entityName_previous), str_previousValue)
                str_expression = str_expression.replace(('$'+str_entityName), str_currentValue)
                if 'TimeDiff' in str_expression:
                    int_previousCollectionTime = int(com.manageengine.monagent.collector.DataCollector.PREVIOUS_COUNTER_VALUES[str_monitorName]['CollectionTime_Previous'])
                    int_collectionTime = int(com.manageengine.monagent.collector.DataCollector.PREVIOUS_COUNTER_VALUES[str_monitorName]['CollectionTime'])
                    str_timeDiff = str(int_collectionTime-int_previousCollectionTime)
                    if str_timeDiff == '0':
                        str_timeDiff = '1'
                    str_expression = str_expression.replace(('$TimeDiff'), str_timeDiff)
                try:
                    toReturn = int(eval(str_expression))
                    if toReturn < 0:
                        toReturn = 0
                        str_currentValue = '0'
                except Exception as e:
                    AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],' *************************** Exception while evaluating custom expression in agent parser *************************** '+ repr(e))
                    traceback.print_exc()
                AgentLogger.debug(AgentLogger.COLLECTOR,'Evaluating expression for '+repr(str_uniqueEntityName)+' : '+ repr(str_expression)+' --> '+repr(toReturn))
            com.manageengine.monagent.collector.DataCollector.PREVIOUS_COUNTER_VALUES[str_monitorName][str_uniqueEntityName] = str_currentValue
        else:
            com.manageengine.monagent.collector.DataCollector.PREVIOUS_COUNTER_VALUES[str_monitorName][str_uniqueEntityName] = str_currentValue
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR],' *************************** Exception while handling counter values *************************** '+ repr(e))
        traceback.print_exc()
    AgentLogger.debug(AgentLogger.COLLECTOR,'Collected info : '+ repr(dict_collectedEntityInfo))
    AgentLogger.debug(AgentLogger.COLLECTOR,'Evaluated counter value : '+ repr(toReturn))
    return str(toReturn)
            
