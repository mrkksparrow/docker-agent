#$Id$
import traceback
import platform
import os
import zipfile
import json
import time
from six.moves.urllib.parse import urlparse
from six.moves.urllib.parse import urlencode

import com
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentBuffer
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.util import AgentUtil,DatabaseUtil
from com.manageengine.monagent.util.AgentUtil import ZipUtil, FileUtil, AGENT_CONFIG, FileZipAndUploadInfo
from com.manageengine.monagent.communication import CommunicationHandler
import shutil
        
def getLogFiles(dictFileDetails , str_loggerName=AgentLogger.STDOUT):
    '''Utility method to get log files and upload'''
    listIgnoreFiles = ['stderr','stdout']
    dict_requestParameters = {}
    try:
        zipFileName = 'Agent_'+str(AGENT_CONFIG.get('AGENT_INFO', 'agent_key'))+'_ViewLinuxLogs_'+str(AgentUtil.getCurrentTimeInMillis()) +'.zip'
        logs_upload_dir_path = AgentConstants.AGENT_UPLOAD_DIR+'/017'
        if not os.path.exists(logs_upload_dir_path):
            os.mkdir(logs_upload_dir_path)
        zipFilePath = logs_upload_dir_path + zipFileName
        zip_fileObj = zipfile.ZipFile(zipFilePath, 'w')        
        
        if 'path' in dictFileDetails:
            filePath = dictFileDetails['path']
            if ".." in filePath:
                AgentLogger.log(str_loggerName,'Relative Path of the file mentioned :: {}'.format(filePath))
                return
            fileName = AgentConstants.AGENT_WORKING_DIR + '/' + filePath
            head,tail=os.path.split(fileName)
            listfiles= os.listdir(head)
            count=0
            for each_file in listfiles:
                AgentLogger.log(str_loggerName,'File :'+ each_file)
                AgentLogger.log(str_loggerName,'Tail :'+tail)
                if each_file == tail:
                    zip_fileObj.write(head+'/'+each_file,'data/'+each_file)
                    AgentLogger.log(str_loggerName,'File :'+ each_file + ' added to the zip file :'+zipFilePath)
                    count = count+1
            if count==0:
                AgentLogger.log(str_loggerName,'File :' + each_file + ' does not exists')
        else:
            listFilesToZip = os.listdir(AgentConstants.AGENT_LOG_DETAIL_DIR)
            for each_file in listFilesToZip:
                filePath = AgentConstants.AGENT_LOG_DETAIL_DIR + '/' + each_file
                fileName = each_file
                zip_fileObj.write(filePath,'data/'+fileName)
                AgentLogger.log(str_loggerName,'File :' + filePath + ' added to zip file :'+zipFilePath)
            
            if platform.system() == 'Darwin':
                mainLogPath ='/var/log/Site24x7_Agent/main.txt'
                criticalLogPath ='/var/log/Site24x7_Agent/critical.txt' 
            else:
                mainLogPath = os.path.join(AgentConstants.AGENT_LOG_DIR, "main.txt")
                criticalLogPath = os.path.join(AgentConstants.AGENT_LOG_DIR, "critical.txt")
            mainLogName = 'main.txt'
            criticalLogName= 'critical.txt'
            mainLogPath = os.path.join(AgentConstants.AGENT_LOG_DIR, mainLogName)
            criticalLogPath = os.path.join(AgentConstants.AGENT_LOG_DIR, criticalLogName)
            if os.path.exists(mainLogPath):
                zip_fileObj.write(mainLogPath,'data/'+mainLogName)
                AgentLogger.log(str_loggerName,'File :' + mainLogPath + ' added to zip file :'+zipFilePath)
            else:
                AgentLogger.log(str_loggerName,'File :' + mainLogPath + ' does not exists in agent directory')
            if os.path.exists(criticalLogPath):
                zip_fileObj.write(criticalLogPath,'data/'+criticalLogName)
                AgentLogger.log(str_loggerName,'File :' + criticalLogPath + ' added to zip file :'+zipFilePath)
            else:
                AgentLogger.log(str_loggerName,'File :' + criticalLogPath + ' does not exists in agent directory')
        
        zip_fileObj.close()
        '''UPLOAD ZIP FILE'''
        str_url = None
        file_obj = open(zipFilePath,'rb')
        str_dataToSend = file_obj.read()
        str_contentType = 'application/zip'
        dict_requestParameters['agentUniqueID'] = AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        dict_requestParameters['custID'] = AgentConstants.CUSTOMER_ID
        dict_requestParameters['DFS_KEY'] = dictFileDetails['DFS_KEY']
        dict_requestParameters['action'] = AgentConstants.SHARE_LOGS_REQUEST
        dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
        str_servlet = AgentConstants.DATA_AGENT_HANDLER_SERVLET
        if not dict_requestParameters == None:
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(str_loggerName)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.set_data(str_dataToSend)
        requestInfo.set_dataType(str_contentType)
        requestInfo.add_header("Content-Type", str_contentType)
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
        if bool_isSuccess:
            AgentLogger.log(str_loggerName,'File :' + zipFileName + ' uploaded successfully. Now deleting the zip file from agent directory.')
            os.remove(zipFilePath)
            os.removedirs(logs_upload_dir_path)
        else:
            AgentLogger.log(str_loggerName,'Failed to upload the file: ' + zipFilePath)
            if os.path.exists(zipFilePath):
                os.remove(zipFilePath)
            if os.path.exists(logs_upload_dir_path):
                os.removedirs(logs_upload_dir_path)
    except Exception as e:
        AgentLogger.log(str_loggerName,'***************************** Exception while getting log files *****************************')
        traceback.print_exc()

# removed uploadPlugin() [BUG BOUNTY]
        
def getApplicationStatistics(listApps):
    dictAppStatus = {}
    try:
        for strName in listApps:
            cmd = "ps aux | grep -i "+strName+" | grep -v grep | awk '{print $2}'"
            boolIsSuccess, cmdOutput = AgentUtil.executeCommand(cmd, AgentLogger.STDOUT)
            if cmdOutput:
                AgentLogger.log(AgentLogger.STDOUT,'Output for '+ strName + ' is ' +str(cmdOutput))
                strStatus = 'Installed and Running'
                dictAppStatus[strName] = strStatus
            else:
                boolReturned, cmdOutput = AgentUtil.executeCommand(AgentConstants.APP_STATS_SCRIPT_FILE + ' ' + strName, AgentLogger.STDOUT)
                scriptOutput = cmdOutput.rstrip('\n')
                AgentLogger.log(AgentLogger.STDOUT,'Script Output for '+ strName + ' is ' + scriptOutput)
                if scriptOutput:
                    if scriptOutput == '0' or scriptOutput == '3':
                        strStatus = 'Installed'
                    else:
                        strStatus = 'Not installed'
                else:
                    strStatus = 'Not Found error'
                dictAppStatus[strName] = strStatus
        
        AgentLogger.log(AgentLogger.STDOUT,'Final status is '+ str(dictAppStatus))
    except Exception as e:        
        AgentLogger.log([AgentLogger.STDOUT, AgentLogger.STDERR],' ************************* Exception while getting app statistics************************* '+ repr(e))
        traceback.print_exc()
        
def extractCompressedFiles(destination,fileName):
    compress_status=True
    error_msg=None
    try:
        bool_toDelete=False
        Name, file_extension = os.path.splitext(fileName)
        if file_extension=='.gz':
            if Name.split('.')[-1]=='tar':
                tarHandle = AgentArchiver.getArchiver(AgentArchiver.ZIP)
                tarHandle.setMode('r:gz')
                tarHandle.setFile(destination)
                tarHandle.setPath(untarDir)
                tarHandle.decompress()
                tarHandle.close()
                bool_toDelete=True
        elif file_extension=='.zip':
            zipHandler = zipfile.ZipFile(os.path.join(destination,fileName), 'r')
            zipHandler.extractall(destination)
            zipHandler.close()
            bool_toDelete=True
        if bool_toDelete:
            os.remove(os.path.join(destination,fileName))
    except Exception as e:
        compress_status = False
        error_msg = 'Problem while extracting the file'
        traceback.print_exc()
        AgentLogger.log(AgentLogger.STDOUT,'Exception while uncompressing compressed files.')
    return compress_status,error_msg
        
def constructUrlAndDeploy(dict_task):
    try:
        str_requestParameters=None
        str_url=None
        checksum_value = None
        ack_dict = {'action':'Automation','script_id':dict_task['SCRIPT_ID']}
        dict_requestParameters = {}
        dict_requestParameters['filePath']=dict_task['DFS_FILE_PATH']
        dict_requestParameters['blockID']=dict_task['DFS_BLOCK_ID']
        dict_requestParameters['CUSTOMERID']=AgentConstants.CUSTOMER_ID
        dict_requestParameters['agentkey']=AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        str_servlet=AgentConstants.DOWNLOAD_FILE_SERVLET
        if not dict_requestParameters == None:
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
        if 'checksum' in dict_task:
            checksum_value = dict_task['checksum']
        file_path = os.path.join(dict_task['DESTINATION'],dict_task['FILE_NAME'])
        bool_isSuccess = CommunicationHandler.downloadFile(str_url, file_path,logger=AgentLogger.STDOUT,checksum=checksum_value,ack=ack_dict)
        if bool_isSuccess:
            extractCompressedFiles(dict_task['DESTINATION'],dict_task['FILE_NAME'])
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.STDOUT,'Exception while deploying the file for action script')

def startWatchdog(dict_task):
    try:
        isSuccess, str_output = AgentUtil.executeCommand(AgentConstants.AGENT_WATCHDOG_STATUS_COMMAND, AgentLogger.MAIN, 5)
        AgentLogger.log(AgentLogger.MAIN,'WATCHDOG STATUS : '+str(isSuccess) +' : ' +str(str_output))
        if AgentConstants.AGENT_WATCHDOG_SERVICE_DOWN_MESSAGE in str_output:
            isBoolSuccess, str_out = AgentUtil.executeCommand(AgentConstants.AGENT_WATCHDOG_START_COMMAND, AgentLogger.MAIN, 5)
            AgentLogger.log(AgentLogger.MAIN,'STARTING WATCHDOG : '+str(isBoolSuccess) +' : ' +str(str_out))
            if AgentConstants.AGENT_WATCHDOG_SERVICE_STARTED_MESSAGE in str_out:
                AgentLogger.log(AgentLogger.MAIN,'Watchdog started successfully.')
            else:
                AgentLogger.log(AgentLogger.MAIN,'Watchdog start failed.')
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Exception while starting the watchdog service')
        traceback.print_exc()

def deployPlugin(dict_task):
    try:
        deployment_success=False
        ack_dict = {'action':'Plugin Installation From Client'}
        str_pluginName = dict_task['name']
        str_pluginName=str_pluginName.lower()
        plugin_config=module_object_holder.plugins_util.PLUGIN_CONF_DICT
        if str_pluginName not in plugin_config:
            static_plugin_url="//server//plugins//{0}".format(str_pluginName)+'.zip'
            file_path=AgentConstants.AGENT_PLUGINS_DIR+str_pluginName+'.zip'
            AgentLogger.log(AgentLogger.STDOUT,'Downloading {0} plugin From Static Server'.format(str_pluginName))
            bool_DownloadStatus = CommunicationHandler.downloadFile(static_plugin_url,file_path,logger=AgentLogger.STDOUT,host=AgentConstants.STATIC_SERVER_HOST,ack=ack_dict)
            if not bool_DownloadStatus:
                AgentLogger.log(AgentLogger.STDOUT,'Downloading {0} plugin From sagent'.format(str_pluginName))
                static_plugin_url="//sagent//plugins//{0}".format(str_pluginName)+'.zip'
                bool_DownloadStatus = CommunicationHandler.downloadFile(static_plugin_url,file_path,logger=AgentLogger.STDOUT,ack=ack_dict)
                if not bool_DownloadStatus:
                    AgentLogger.log(AgentLogger.STDOUT,'Plugin Deployment Failed')
                else:
                    AgentLogger.log(AgentLogger.STDOUT,'Plugin Deployed Successfully via sagent')
                    deployment_success=True
            else:
                AgentLogger.log(AgentLogger.STDOUT,'Plugin Deployed Successfully')
                deployment_success=True
            if deployment_success:
                bool_Unzip=True
                try:
                    from zipfile import ZipFile
                    zip = ZipFile(file_path)
                    zip.extractall(AgentConstants.AGENT_PLUGINS_DIR)
                except Exception as e:
                    bool_Unzip=False
                    AgentLogger.log(AgentLogger.STDOUT,'exception while unzipping plugin')
                    traceback.print_exc()
            if bool_Unzip:
                os.remove(file_path)
                AgentLogger.log(AgentLogger.STDOUT,'File Removed Successfully')
        else:
            AgentLogger.log(AgentLogger.STDOUT,'Plugin Already Deployed')
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.STDOUT,'exception while deploy plugin')


def ackAgentUpgradeStatus(message=None,action="PRIOR_UPGRADE"):
    dict_requestParameters = {}
    user_message = ""
    dev_message = ""
    try:
        upgrade_log = str(message) if message else AgentUtil.getAgentUpgradeStatusMsg()
        if action == "PRIOR_UPGRADE":
            if "##" in upgrade_log:
                user_message = upgrade_log.split("##")[0] if upgrade_log.split("##")[0] else "upg-0"
                dev_message = upgrade_log.split("##")[1] if len(upgrade_log.split("##")) > 1 else "upg-0"
            else:
                dev_message = upgrade_log
            dict_requestParameters["TEST"] = str(dev_message)
        elif action == "ACK_UPGRADE":
            user_message = upgrade_log
        if "-0" in dev_message or "-2" in dev_message or action == "ACK_UPGRADE":
            str_servlet = AgentConstants.DATA_AGENT_HANDLER_SERVLET
            dict_requestParameters["agentKey"] = AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
            dict_requestParameters["action"] = action
            dict_requestParameters["bno"] = AgentConstants.AGENT_VERSION
            dict_requestParameters["custID"] = AgentConstants.CUSTOMER_ID
            dict_requestParameters["message"] = str(user_message)
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.MAIN)
            requestInfo.set_method(AgentConstants.HTTP_POST)
            requestInfo.set_url(str_url)
            requestInfo.set_timeout(30)
            requestInfo.add_header("Content-Type", 'application/json')
            requestInfo.add_header("Accept", "text/plain")
            requestInfo.add_header("Connection", 'close')
            bool_isSuccess, int_errorCode, dict_responseHeaders, dict_responseData = CommunicationHandler.sendRequest(requestInfo)
            CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'FILE UPLOADER')
            if bool_isSuccess:
                AgentLogger.log([AgentLogger.MAIN], 'Successfully acknowledged agent upgrade status to the server')
                if os.path.exists(AgentConstants.AGENT_UPGRADE_STATUS_MSG_FILE):
                    os.remove(AgentConstants.AGENT_UPGRADE_STATUS_MSG_FILE)
            else:
                AgentLogger.log([AgentLogger.MAIN], '***** Failed to send agent upgrade status to the server ***** \n')
                CommunicationHandler.checkNetworkStatus(AgentLogger.MAIN)
        else:
            AgentLogger.log([AgentLogger.MAIN], '===== Upgrade completed successfully :: {} ====='.format(message))
            if os.path.exists(AgentConstants.AGENT_UPGRADE_STATUS_MSG_FILE):
                os.remove(AgentConstants.AGENT_UPGRADE_STATUS_MSG_FILE)
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,'***** Exception while acknowledging Agent Upgrade status ***** :: Error - {}'.format(e))
        traceback.print_exc()


def triggerReboot(dict_task):
    try:
        if AgentUtil.is_module_enabled(AgentConstants.AUTOMATION_SETTING):
            AgentLogger.log(AgentLogger.CHECKS,'reboot action invoked')
            sendRebootStatus(dict_task)
            createInitTimeFile(dict_task)
            cmd = 'reboot'
            AgentUtil.executeCommand(cmd, AgentLogger.STDOUT)
        else:
            AgentLogger.log(AgentLogger.CHECKS,'IT Automation : {} => Hence reboot action cancelled')
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.CHECKS,'exception while triggering reboot ')     
        
        
def createInitTimeFile(dict_task):
    try:
        if 'INIT_TIME' in dict_task:
            initTime = dict_task['INIT_TIME']
            scriptId = dict_task['SCRIPT_ID']
            str_rebootInitTime = 'reboot_'+initTime+'_'+scriptId
            file_obj = open(AgentConstants.AGENT_TEMP_DIR+'/'+str_rebootInitTime,'w')
            file_obj.write(str_rebootInitTime)
            if not file_obj == None:
                file_obj.close()
    except Exception as e:
        traceback.print_exc()
        
def sendRebootStatus(dict_task):
    dict_requestParameters = {}
    dictData={}
    requestInfo = com.manageengine.monagent.communication.CommunicationHandler.RequestInfo()
    try:
        dict_requestParameters['agentKey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        dict_requestParameters['custID'] = AgentConstants.CUSTOMER_ID
        dict_requestParameters['dc'] = AgentUtil.getCurrentTimeInMillis()
        dict_requestParameters['action'] = 'ACTION_SCRIPT_RESULT'
        dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
        dictData['script_id']=dict_task['SCRIPT_ID']
        dictData['response']='initiated'
        dictData['status']='true'
        dictData['origin']=dict_task['ORIGIN']
        dictData['init_time']=dict_task['INIT_TIME']
        dictData['start_time']=AgentUtil.getTimeInMillis()
        dictData['duration']=0
        dictData['Error']=''
        str_dataToSend = json.dumps(dictData)
        str_contentType = 'application/json'

        str_servlet = AgentConstants.SCRIPT_RESULT_SERVLET
        str_requestParameters = urlencode(dict_requestParameters)
        str_url = str_servlet + str_requestParameters
        requestInfo.set_loggerName(AgentLogger.STDOUT)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.set_data(str_dataToSend)
        requestInfo.set_dataType(str_contentType)
        requestInfo.add_header("Content-Type", str_contentType)
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        AgentLogger.log(AgentLogger.STDOUT, 'reboot action data -- {0}'.format(dictData))
        (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)

        if bool_isSuccess:
            AgentLogger.log(AgentLogger.STDOUT, 'Successfully posted the reboot action status to the server \n')
        AgentLogger.log(AgentLogger.STDOUT, '--- reboot action data posted --- ')
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR], ' *************************** Exception while sending reboot status *************************** '+ repr(e))
        traceback.print_exc()

def CleanUpActionScript(dict_task):
    try:
        if 'PATH' in dict_task:
            cleanUpFolders = dict_task['PATH']
            cleanUpFolders = os.path.dirname(cleanUpFolders)
            AgentLogger.log(AgentLogger.STDOUT,'cleaning up action script - {0}'.format(cleanUpFolders)+'\n')
            if os.path.exists(cleanUpFolders):
                shutil.rmtree(cleanUpFolders)
            else:
                AgentLogger.log(AgentLogger.STDOUT,'folder not exist - {0}'.format(cleanUpFolders))
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR], ' *************************** Exception while cleaning up action script *************************** '+ repr(e))
        traceback.print_exc()
