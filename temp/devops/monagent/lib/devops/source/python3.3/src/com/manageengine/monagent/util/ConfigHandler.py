# $Id$
import traceback
import os
import zipfile
import json
from six.moves.urllib.parse import urlencode

from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil, AGENT_CONFIG, FileZipAndUploadInfo
from com.manageengine.monagent.communication import CommunicationHandler, BasicClientHandler

def configProcessData(dictData):
    '''Update Process data in agent from recieved config data'''
    
    list_p = []
    try:
        if dictData and 'process' in dictData:
            for each_p in dictData['process']:
                dict_p = {}
                AgentLogger.log(AgentLogger.STDOUT,' Recieved Process details in config for: '+repr(each_p))
                dict_p['Name']=each_p['pn']
                list_p.append(dict_p)
                
            if not AgentUtil.writeDataToFile(AgentConstants.AGENT_PROCESS_LIST_FILE, list_p):
                AgentLogger.log(AgentLogger.STDOUT,'Unable to load config process list to agent')
            else:
                AgentLogger.log(AgentLogger.STDOUT,' Loaded config process list to agent file')
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR], '*************************** Exception while updating process details in agent *************************** '+ repr(e))
        traceback.print_exc()

def configResourceData(dictData):
    '''Find the Ports and URL in config data different than the agent Ports and URLs'''
    
    try:
        set_ConfigPorts = set({})
        set_ConfigURLs = set({})
        if 'port' in dictData:
            set_ConfigPorts = set(dictData['port'])
        if 'url' in dictData:
            set_ConfigURLs = set(dictData['url'])
        set_AgentPorts = set({})
        set_AgentURLs = set({})
        fileObj = AgentUtil.FileObject()
        fileObj.set_filePath(AgentConstants.AGENT_CUSTOM_MONITORS_GROUP_FILE)
        fileObj.set_dataType('json')
        fileObj.set_mode('rb')
        fileObj.set_dataEncoding('UTF-8')
        fileObj.set_loggerName(AgentLogger.COLLECTOR)
        fileObj.set_logging(False)
        bool_toReturn, dict_monitorsInfo = FileUtil.readData(fileObj)
        if dict_monitorsInfo['MonitorGroup']['PortMonitoring']['CustomPorts']:
            set_AgentPorts = set(dict_monitorsInfo['MonitorGroup']['PortMonitoring']['CustomPorts'])
        if dict_monitorsInfo['MonitorGroup']['URLMonitoring']['CustomURLs']:
            set_AgentURLs = set(dict_monitorsInfo['MonitorGroup']['URLMonitoring']['CustomURLs'])
        setPortsToAdd = set_ConfigPorts.difference(set_AgentPorts)
        setPortsToDelete = set_AgentPorts.difference(set_ConfigPorts)
        if setPortsToAdd:
            AgentLogger.log([AgentLogger.STDOUT],' Adding Ports in Config Data not found in agent : ' + repr(setPortsToAdd))
            #BasicClientHandler.PortUtil.addPorts(list(setPortsToAdd),True)
        else:
            AgentLogger.log([AgentLogger.STDOUT],' No new ports found to  be added from config data') 
        if setPortsToDelete:
            AgentLogger.log([AgentLogger.STDOUT],' Deleting Ports in Config Data found present in agent : ' + repr(setPortsToDelete))
            #BasicClientHandler.PortUtil.deletePorts(list(setPortsToDelete))
        else:
            AgentLogger.log([AgentLogger.STDOUT],' No new ports found to  be deleted from config data')
        setURLsToAdd = set_ConfigURLs.difference(set_AgentURLs)
        setURLsToDelete = set_AgentURLs.difference(set_ConfigURLs)
        if setURLsToAdd:
            AgentLogger.log([AgentLogger.STDOUT],' Adding URLs in Config Data not found in agent : ' + repr(setURLsToAdd))
            #BasicClientHandler.URLUtil.addURLs(list(setURLsToAdd),True)
        else:
            AgentLogger.log([AgentLogger.STDOUT],' No new URLs found to  be added from config data')
        if setURLsToDelete:
            AgentLogger.log([AgentLogger.STDOUT],' Deleting URLs in Config Data found  present in agent : ' + repr(setURLsToDelete))
            #BasicClientHandler.URLUtil.deleteURLs(list(setURLsToDelete))
        else:
            AgentLogger.log([AgentLogger.STDOUT],' No new URLs found to  be deleted from config data')
    except Exception as e:
            AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], ' *************************** Exception while loading default ports for port monitoring  *************************** '+ repr(e))
            traceback.print_exc()

def reloadConfigData():
    ''' To sync the Process,URL and Port Data with server'''
    
    str_servlet = AgentConstants.AGENT_CONFIG_SERVLET
    dictRequestParameters = {}
    try:
        dictRequestParameters['CUSTOMERID'] = AgentConstants.CUSTOMER_ID
        dictRequestParameters['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        dictRequestParameters['bno'] = AgentConstants.AGENT_VERSION
        if not dictRequestParameters == None:
            str_requestParameters = urlencode(dictRequestParameters)
            str_url = str_servlet + str_requestParameters
        AgentLogger.log([AgentLogger.STDOUT],'================================= RELOADING CONFIG DATA =================================')
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.STDOUT)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.add_header("Content-Type", 'application/json')
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        (isSuccess, int_errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
        if isSuccess and dict_responseData:
            #decodedData = dict_responseData.decode('UTF-16LE')
            dictParsedData = json.loads(dict_responseData)
            AgentLogger.log([AgentLogger.STDOUT],'Server returned config data :' + repr(dictParsedData))
            #configResourceData(dictParsedData)
            configProcessData(dictParsedData)
        else:
            AgentLogger.log([AgentLogger.STDOUT],'Server returned no config data or connection failure')
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],'*************************** Exception While loading agent config data from server *************************** '+ repr(e))
        traceback.print_exc()
