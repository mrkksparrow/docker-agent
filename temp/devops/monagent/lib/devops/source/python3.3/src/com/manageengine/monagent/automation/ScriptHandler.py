#$Id$
import json
import os
import time
import traceback
import threading
import shutil
from six.moves.urllib.parse import urlencode
import com
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentBuffer
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util import DesignUtils
from com.manageengine.monagent.util.AgentUtil import FileUtil, FileZipAndUploadInfo, Executor
from com.manageengine.monagent.actions import checksum_validator

ScriptUtil = None

class Script():
    def __init__(self):
        self.iTime = None
        self.sID = None
        self.pth = None
        self.args = None
        self.type = None
        self.cmd = None
        self.timeout = 10
        self.neededFlag = None 
        self.origin = None
        self.delete_file = False

    def setScriptDetails(self,dictDetails):
        boolStatus = True
        self.type = dictDetails['TYPE']
        if "COMMAND" in dictDetails and ".." in dictDetails['COMMAND']:
            AgentLogger.log(AgentLogger.STDOUT,'skipping it automation action as the command contains .. character :: {}'.format(dictDetails['COMMAND']))
            boolStatus = False
            return boolStatus
        if "PATH" in dictDetails and ".." in dictDetails['PATH']:
            AgentLogger.log(AgentLogger.STDOUT,'skipping it automation action as the file path contains .. character :: {}'.format(dictDetails['PATH']))
            boolStatus = False
            return boolStatus
        if self.type == 204:
            self.cmd = dictDetails['COMMAND']
        else:
            if '$$' in dictDetails['PATH']:
                file = dictDetails['PATH'].split('$$')[2]
                dictDetails['PATH'] = AgentConstants.AGENT_WORKING_DIR + file
                self.delete_file = True
            if not os.path.exists(dictDetails['PATH']):
                  if 'DFS_BLOCK_ID' in dictDetails and (dictDetails['DFS_BLOCK_ID'] is not None or dictDetails['DFS_BLOCK_ID']!='') and 'DFS_FILE_PATH' in dictDetails and (dictDetails['DFS_FILE_PATH'] is not None or dictDetails['DFS_FILE_PATH']!=''):
                      dictDetails['DESTINATION'] = os.path.split(dictDetails['PATH'])[0]   
                      dictDetails['FILE_NAME'] = 'temp.zip'      
                      if not os.path.exists(dictDetails['DESTINATION']):        
                          os.makedirs(dictDetails['DESTINATION'])                  
                      com.manageengine.monagent.actions.AgentAction.constructUrlAndDeploy(dictDetails)
            if os.path.exists(dictDetails['PATH']):
                self.pth = dictDetails['PATH']
                os.chmod(self.pth, 0o755)
                self.cmd = dictDetails['COMMAND'] + " " + self.pth
            else:
                boolStatus = False
        self.iTime = dictDetails['INIT_TIME']
        self.sID = dictDetails['SCRIPT_ID']
        if 'ARGS' in dictDetails:
            self.args = dictDetails['ARGS']
            if boolStatus:
                self.cmd = self.cmd + " " + self.args
        if 'TIMEOUT' in dictDetails:
            self.timeout = dictDetails['TIMEOUT']
        if 'SCRIPT_OUTPUT_NEEDED' in dictDetails:
            self.neededFlag = dictDetails['SCRIPT_OUTPUT_NEEDED']
        if 'ORIGIN' in dictDetails:
            self.origin = dictDetails['ORIGIN']
        return boolStatus

    def getErrorResp(self):
        dictToReturn = {}
        try:
            dictToReturn['status'] = False
            dictToReturn['response'] = None
            dictToReturn['start_time'] = AgentUtil.getTimeInMillis()
            dictToReturn['duration'] = 0
            dictToReturn['Return Code'] = 404
            dictToReturn['Error'] = "File not found"
            if self.origin is not None:
                dictToReturn['origin'] = self.origin
            dictToReturn['script_id'] = self.sID
            dictToReturn['init_time'] = self.iTime
            AgentLogger.debug(AgentLogger.STDOUT,'IT Automation Error Response result :: {}'.format(dictToReturn))
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,' Exception in getting error response')
            traceback.print_exc()
        finally:
            return dictToReturn

    def executeScript(self):
        dictToReturn = {}
        try:
            executorObj = AgentUtil.Executor()
            executorObj.setLogger(AgentLogger.STDOUT)
            executorObj.setTimeout(self.timeout)
            executorObj.setCommand(self.cmd)
            startTime = AgentUtil.getTimeInMillis()
            executorObj.executeCommand()
            endTime = AgentUtil.getTimeInMillis()
            timeDiff = endTime - startTime
            tuple_commandStatus = executorObj.isSuccess()
            dictToReturn['status'] = tuple_commandStatus
            response = executorObj.getStdOut()
            if response:
                response = response[0:10000]
            dictToReturn['response'] = response 
            dictToReturn['start_time'] = startTime
            dictToReturn['duration'] = timeDiff
            retVal = executorObj.getReturnCode()
            if ((retVal == 0) or (retVal is not None)):
                dictToReturn['Return Code'] = retVal
                errorString = executorObj.getStdErr()
                if errorString:
                    if len(errorString) > 200:
                        pass
                dictToReturn['Error'] =  AgentUtil.getModifiedString(executorObj.getStdErr(),100,100)
            else:
                dictToReturn['Return Code'] = 408
                dictToReturn['Error'] = 'Timeout error occured'
            if self.origin is not None:
                dictToReturn['origin'] = self.origin
            dictToReturn['script_id'] = self.sID
            dictToReturn['init_time'] = self.iTime
            AgentLogger.debug(AgentLogger.STDOUT,'IT Automation Execution result :: {}'.format(dictToReturn))
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,' Exception in executing script')
            traceback.print_exc()
        finally:
            return dictToReturn

class scriptHandler(threading.Thread):
    dict_wmsParams = None
    def __init__(self,dictParams=None):
        threading.Thread.__init__(self)
        if dictParams:
            self.dict_wmsParams = {}
            self.dict_wmsParams = dictParams
    
    def run(self):
        self.handleWMSRequest()
    
    def addScript(self,dict_wmsParams):
        script_validator = True
        script = None
        try:
            validation_result = self.validate_automation(dict_wmsParams)
            if validation_result['status']=="true":
                script = Script()
                script_validator = script.setScriptDetails(dict_wmsParams)
            else:
                AgentLogger.log(AgentLogger.STDOUT,'IT Automation Validation Failed :: {}'.format(dict_wmsParams))
                script_validator = False
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDOUT,AgentLogger.STDERR], ' *************************** Exception while setting action script details *************************** '+ repr(e))
            traceback.print_exc()
        finally:
            return script,script_validator
    
    def validate_automation(self,dms_data):
        try:
            result = checksum_validator.upload_data_for_validation(dms_data,AgentConstants.AUTOMATION_SETTING)
            AgentLogger.log(AgentLogger.STDOUT,'IT Automation Validation result :: {}'.format(result))
            return result
        except Exception as e:
            traceback.print_exc()
    
    def handleWMSRequest(self):
        AgentLogger.debug(AgentLogger.STDOUT,'Received WMS request to execute action script for :: {} '.format(self.dict_wmsParams))
        sc,toExec = self.addScript(self.dict_wmsParams)
        if toExec:
            dictResponse = sc.executeScript()
        else:
            dictResponse = sc.getErrorResp()
        AgentLogger.log(AgentLogger.STDOUT,'delete file :: {}'.format(sc.delete_file))
        AgentLogger.debug(AgentLogger.STDOUT,'Uploading action script execution response :: {}'.format(json.dumps(dictResponse)))
        self.uploadResponse(dictResponse)
        if sc.delete_file:
            com.manageengine.monagent.actions.AgentAction.CleanUpActionScript(self.dict_wmsParams)
        
    def uploadResponse(self,dictData):
        dict_requestParameters = {}
        dir_prop = AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['011']
        try:
            AgentUtil.get_default_param(dir_prop,dict_requestParameters,'ACTION_SCRIPT_RESULT')
            str_servlet = AgentConstants.SCRIPT_RESULT_SERVLET
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.DEPLOYMENT)
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
            AgentLogger.log(AgentLogger.DEPLOYMENT,'[ Upload action script result data ] '+repr(str_jsonData))
            if bool_isSuccess:
                AgentLogger.log([AgentLogger.DEPLOYMENT,AgentLogger.STDOUT], 'Successfully posted the action script result data to the server')
            else:
                AgentLogger.log([AgentLogger.DEPLOYMENT,AgentLogger.STDOUT], '************************* Unable to post the i action script result data to the server. ************************* \n')
                CommunicationHandler.checkNetworkStatus(AgentLogger.STDOUT)
        except Exception as e:
            AgentLogger.log([AgentLogger.CHECKS,AgentLogger.STDERR], ' *************************** Exception while checking setting upload details for automation *************************** '+ repr(e))
            traceback.print_exc()
