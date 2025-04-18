#$Id$
import json
import os
import time
import traceback
import threading
from six.moves.urllib.parse import urlencode
from com.manageengine.monagent import AgentConstants
#from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentBuffer
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util import DesignUtils
from com.manageengine.monagent.util.AgentUtil import FileUtil, FileZipAndUploadInfo, Executor

ScriptUtil = None

'''def checkScriptMonitor():
    scriptData = {}
    try:
        scriptData = ScriptUtil.checkScriptDC()
        AgentLogger.log(AgentLogger.CHECKS,'script Data is '+repr(scriptData))
    except Exception as e:
        AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR],'******** Exception while DC of script Monitoring*****'+repr(e))
        traceback.print_exc()'''

class Script():
    def __init__(self):
        self.sID = None
        self.path = None
        self.args = None
        self.timeout = AgentConstants.DEFAULT_SCRIPT_TIMEOUT
        self.type = None
        self.cmd = None
        self.er = None
        #self.outputForm = None #key%%value
    
    def setScriptDetails(self,dictDetails):
        try:
            self.sID = dictDetails['id']
            self.type = dictDetails['type']
            if '$$' in dictDetails['path']:
                file = dictDetails['path'].split('$$')[2]
                dictDetails['path'] = AgentConstants.AGENT_WORKING_DIR + file
            if os.path.exists(dictDetails['path']):
                self.path = dictDetails['path']
                os.chmod(self.path, 0o755)
                self.cmd = dictDetails['command'] + " " + self.path
            else:
                self.er = AgentConstants.WRONG_PATH
            if 'args' in dictDetails:
                self.args = dictDetails['args']
                self.cmd = self.cmd + " " + self.args
            if 'timeout' in dictDetails:
                self.timeout = dictDetails['timeout']
            #self.outputForm = dictDetails['outputForm']
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR],' *************************** Exception while setting script monitor details *************************** '+ repr(e))
            traceback.print_exc()
    
    def executeScript(self):
        dictToReturn = {}
        try:
            executorObj = AgentUtil.Executor()
            executorObj.setLogger(AgentLogger.CHECKS)
            executorObj.setTimeout(self.timeout)
            executorObj.setCommand(self.cmd)
            startTime = AgentUtil.getTimeInMillis()
            executorObj.executeCommand()
            endTime = AgentUtil.getTimeInMillis()
            timeDiff = endTime - startTime
            tuple_commandStatus = executorObj.isSuccess()
            dictToReturn['status'] = tuple_commandStatus
            dictToReturn['output'] = executorObj.getStdOut()
            #dictToReturn['response'] = AgentUtil.getModifiedString(executorObj.getStdOut(),100,100)
            dictToReturn['start_time'] = startTime
            dictToReturn['end_time'] = endTime
            dictToReturn['duration'] = timeDiff
            retVal = executorObj.getReturnCode()
            if ((retVal == 0) or (retVal is not None)):
                dictToReturn['return_code'] = retVal
                error = executorObj.getStdErr()
                if error:
                    dictToReturn['error'] = AgentUtil.getModifiedString(error,100,100)
                #dictToReturn['Error'] =  AgentUtil.getModifiedString(executorObj.getStdErr(),100,100)
            else:
                dictToReturn['return_code'] = 408
                dictToReturn['error'] = 'Timeout error occured'
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR],'*************************** Exception while script monitor execution *************************** '+ repr(e))
            traceback.print_exc()
        finally:
            #AgentLogger.log(AgentLogger.CHECKS,'data collection after script execution '+repr(dictToReturn))
            return dictToReturn
    
    def scriptDC(self):#to be called from script handler
        dcData = {}
        try:
            if not self.er:
                dcData = self.executeScript()
                if dcData and dcData['output']:
                    parsedData = self.parseData(dcData['output'])
                    dcData['output'] = parsedData
                #parse the receivedData
            else:
                dcData['status'] = False
                dcData['return_code'] = self.er
                dcData['error'] = 'File not Found'
                dcData['output'] = None
                dcData['start_time'] = dcData['end_time'] = AgentUtil.getTimeInMillis()
                dcData['duration'] = 0
                #AgentLogger.log(AgentLogger.CHECKS,'error in configuration in script monitoring')
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR],'**********Exception while DC of Script Monitoring********** '+repr(e))
            traceback.print_exc()
        finally:
            #AgentLogger.log(AgentLogger.CHECKS,'dc Data after parsing '+repr(dcData))
            return dcData
    
    def parseData(self,dataToParse):
        listLineData = []
        parsedData = {}
        try:
            listLineData = dataToParse.split('\n')
            for eachLine in listLineData:
                temp = eachLine.split('%%')
                if len(temp) > 0 and temp[0]:
                    if len(temp) == 2:
                        parsedData[temp[0]] = temp[1]
                    else:
                        parsedData[temp[0]] = "None"
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR],'********Exception while parsing script DC*****'+repr(e))
            traceback.print_exc()
        finally:
            #AgentLogger.log(AgentLogger.CHECKS,'only parsed data '+repr(parsedData))
            return parsedData

class ScriptHandler(DesignUtils.Singleton):
    _scripts = {}
    _lock = threading.Lock()
    
    def __init__(self):
        self._loadCustomScripts()
    
    def _loadCustomScripts(self):
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
                for each_script in dict_monitorsInfo['MonitorGroup']['ScriptMonitoring']:
                    script = Script()
                    script.setScriptDetails(each_script)
                    self.__class__._scripts[each_script['id']] = script
                    #AgentLogger.log(AgentLogger.CHECKS,'each script dict details '+repr(each_script))
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while loading custom scripts for script monitoring  *************************** '+ repr(e))
            traceback.print_exc()
            
    def deleteAllScripts(self):
        try:
            for each_script in self.__class__._scripts:
                script = self.__class__._scripts[each_script]
                AgentLogger.log(AgentLogger.CHECKS,'Deleting Script check with Script id : '+repr(script.sID))
            self.__class__._scripts.clear()
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' CheckError | *************************** Exception while deleting Script checks *************************** '+ repr(e))
            traceback.print_exc()
    
    def reloadScripts(self):
        with self._lock:
            self.deleteAllScripts()
        self._loadCustomScripts()
    
    def checkScriptDC(self):
        dictDataToSend = {}
        try:
            with self._lock:
                for scriptId, script in self.__class__._scripts.items():
                    tempDict = {}
                    #AgentLogger.log(AgentLogger.CHECKS,'start DC for script id:'+repr(scriptId))
                    tempDict = script.scriptDC()
                    dictDataToSend.setdefault(scriptId,tempDict)
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR],'************* Exception while DC of script****'+repr(e))
            traceback.print_exc()
        finally:
            return dictDataToSend
        
            
