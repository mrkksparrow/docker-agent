#$Id$
import json
import os
import time
import traceback
import threading
import shutil
from six.moves.urllib.parse import urlencode
import com
from com.manageengine.monagent import AgentConstants,module_object_holder
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.util import AgentBuffer
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util import DesignUtils
from com.manageengine.monagent.util.AgentUtil import FileUtil, FileZipAndUploadInfo, Executor

ScriptUtil = None
import zipfile

class Script():
    def __init__(self):
        self.iTime = None
        self.sID = None
        self.pth = None
        self.args = None
        self.type = None
        self.cmd = None
        self.timeout = 30
        self.neededFlag = None 
        self.origin = None
        self.execute_script= False
        self.delete_script_post_execute = False
        self.destination_folder = None

    def set_script_metadata(self,dictDetails):
        boolStatus = True
        self.iTime = dictDetails['INIT_TIME']
        self.sID = dictDetails['SCRIPT_ID']
        if 'DESTINATION_FOLDER' in dictDetails:
            self.destination_folder = dictDetails['DESTINATION_FOLDER']
            if '$$' in self.destination_folder:
                file = self.destination_folder.split('$$')[2]
                self.destination_folder = AgentConstants.AGENT_WORKING_DIR + file
            if not os.path.exists(self.destination_folder):        
                os.makedirs(self.destination_folder)
        if 'PATH' in dictDetails:
            if '$$' in dictDetails['PATH']:
                file = dictDetails['PATH'].split('$$')[2]
                self.pth = AgentConstants.AGENT_WORKING_DIR + file
            else:
                self.pth = dictDetails['PATH']
        if 'COMMAND' in dictDetails:
            self.cmd = dictDetails['COMMAND']
        if 'PATH' in dictDetails:
            self.cmd = dictDetails['COMMAND'] + " " + self.pth
        if 'ARGS' in dictDetails:
            self.args = dictDetails['ARGS']
            self.cmd = self.cmd + " " + self.args
        if 'TIMEOUT' in dictDetails:
            self.timeout = dictDetails['TIMEOUT']
        if 'SCRIPT_OUTPUT_NEEDED' in dictDetails:
            self.neededFlag = dictDetails['SCRIPT_OUTPUT_NEEDED']
        if 'ORIGIN' in dictDetails:
            self.origin = dictDetails['ORIGIN']
        if 'EXECUTE' in dictDetails and dictDetails['EXECUTE']=='true':
            self.execute_script=True
        if 'DELETE_SCRIPT' in dictDetails and dictDetails['DELETE_SCRIPT']=='true':
            self.delete_script_post_execute=True
        return boolStatus

    def script_execute(self):
        dictToReturn = {}
        try:
            dictToReturn['Error']='-'
            executorObj = AgentUtil.Executor()
            executorObj.setLogger(AgentLogger.MAIN)
            executorObj.setTimeout(self.timeout)
            executorObj.setCommand(self.cmd)
            startTime = AgentUtil.getTimeInMillis()
            if AgentConstants.PYTHON_VERSION < 3 or os.path.exists(AgentConstants.USE_DC_CMD_EXECUTOR):
                AgentLogger.debug(AgentLogger.DEPLOYMENT,' using dc command executor')
                executorObj.executeCommand()
            else:
                executorObj.execute_cmd_with_tmp_file_buffer()
            endTime = AgentUtil.getTimeInMillis()
            timeDiff = endTime - startTime
            tuple_commandStatus = executorObj.isSuccess()
            dictToReturn['status'] = tuple_commandStatus
            stdout = executorObj.getStdOut()
            stderr = executorObj.getStdErr()
            retVal = executorObj.getReturnCode()
            dictToReturn['exit_code'] = retVal
            dictToReturn['response'] = stdout
            if not stdout and stderr:
                dictToReturn['response'] = stderr
            else:
                dictToReturn['Error'] = stderr
            if retVal and retVal!=0:
                dictToReturn['status'] = False 
            dictToReturn['start_time'] = startTime
            dictToReturn['end_time'] = endTime
            dictToReturn['duration'] = timeDiff
            if self.origin is not None:
                dictToReturn['origin'] = self.origin
            dictToReturn['script_id'] = self.sID
            dictToReturn['init_time'] = self.iTime
            AgentLogger.debug(AgentLogger.DEPLOYMENT,'out stream -- {}'.format(stdout)+'\n')
            AgentLogger.debug(AgentLogger.DEPLOYMENT,'err stream -- {}'.format(stderr)+'\n')
            AgentLogger.debug(AgentLogger.DEPLOYMENT,'exit code -- {}'.format(retVal)+'\n')
        except Exception as e:
            AgentLogger.log(AgentLogger.DEPLOYMENT,' Exception in executing script')
            traceback.print_exc()
        finally:
            AgentLogger.log(AgentLogger.DEPLOYMENT,' Final Output -- {}'.format(json.dumps(dictToReturn))+'\n')
            return dictToReturn

class scriptDeployer(threading.Thread):
    dict_wms_params = None
    def __init__(self,dictParams=None):
        threading.Thread.__init__(self)
        if dictParams:
            self.dict_wms_params = {}
            self.dict_wms_params = dictParams
            self.zip_name_list = []
    
    def run(self):
        deploy_dict = self.execute_deployment()
        if deploy_dict:
            self.send_deployment_result(self.dict_wms_params,deploy_dict)
    
    def execute_deployment(self):
        AgentLogger.log(AgentLogger.DEPLOYMENT,'Deploy script action request :: {} '.format(self.dict_wms_params) +'\n')
        error_msg = None
        files_extract_status = False
        deploy_result = {}
        plugin_deployment_name = None
        upload_data = str(self.dict_wms_params['SCRIPT_ID'])+"_"+str(self.dict_wms_params['INIT_TIME'])+'_'+str(self.dict_wms_params['ORIGIN']['action_type'])
        self.send_acknowledgement('ACK_SD',upload_data)
        try:
            script_object = Script()
            script_object.set_script_metadata(self.dict_wms_params)
            self.dict_wms_params['destination_folder'] = script_object.destination_folder
            deploy_start_time=AgentUtil.getTimeInMillis()
            deploy_result = {'status':True,'msg':AgentConstants.DS,'start_time':deploy_start_time}
            if 'URL' in self.dict_wms_params and self.dict_wms_params['URL']:
                download_status , error_msg = self.download_from_url(self.dict_wms_params,AgentLogger.DEPLOYMENT)
            else:
                download_status , error_msg = self.download_from_dfs(self.dict_wms_params)
            AgentLogger.log(AgentLogger.DEPLOYMENT,'downloads status :  {} |  error msg : {}'.format(download_status,error_msg)+'\n')
            if not download_status:
                deploy_result = {'status':download_status,'msg':str(error_msg),'start_time':deploy_start_time}
                return deploy_result
            files_extract_status , error_msg = self.extract_zip_files(script_object.destination_folder,'temp.zip')
            AgentLogger.log(AgentLogger.DEPLOYMENT,'extract status :  {} |  error msg : {}'.format(files_extract_status,error_msg)+'\n')
            if not files_extract_status:
                deploy_result = {'status':files_extract_status,'msg':error_msg,'start_time':deploy_start_time}
                return deploy_result
            if str(self.dict_wms_params['ORIGIN']['action_type']) == "102":
                if not AgentConstants.PLUGIN_DEPLOY_CONFIG:
                    AgentConstants.PLUGIN_DEPLOY_CONFIG={}
                for dirname, dirnames, filenames in os.walk(script_object.destination_folder+self.zip_name_list[0]):
                    for file in filenames:
                        if dirname.split('/')[-2].lower() == os.path.splitext(file)[0].lower():
                            if os.path.splitext(file)[1] in ['.py','.sh']:
                                deploy_result['plugin_name'] = file
                                AgentConstants.PLUGIN_DEPLOY_CONFIG[deploy_result['plugin_name']] = self.dict_wms_params
                if 'plugin_name' not in deploy_result:
                    deploy_result = {'status':False,'msg':'Executable plugin file not found','start_time':deploy_start_time}
            if script_object.execute_script:
                dict_response = script_object.script_execute()
                if dict_response:
                    self.uploadResponse(dict_response)
                if str(self.dict_wms_params['ORIGIN']['action_type']) == "104":
                    time.sleep(25)
                    ack_param = {}
                    if os.path.exists(AgentConstants.ZOHO_ASSIST_RESOURCEID):
                        bool_returnStatus,resource_id_dict = AgentUtil.loadDataFromFile(AgentConstants.ZOHO_ASSIST_RESOURCEID)
                        ack_param["success"]="true"
                        ack_param["script_id"] = str(self.dict_wms_params['SCRIPT_ID'])
                        ack_param["init_time"] = str(self.dict_wms_params['INIT_TIME'])
                        ack_param["action_type"] = str(self.dict_wms_params['ORIGIN']['action_type'])
                        ack_param["res_id"] = str(resource_id_dict['ResourceID'])
                    else:
                        ack_param = {"failed":"resource id not found"}
                    self.send_acknowledgement("assist_integ", ack_param)
                if script_object.delete_script_post_execute:
                    AgentLogger.log(AgentLogger.DEPLOYMENT,'deployment files for delete post execution -- {}'.format(self.zip_name_list))
                    for each in self.zip_name_list:
                        os.remove(script_object.destination_folder+'/'+each)
            else:
                return deploy_result
        except Exception as e:
            traceback.print_exc()
        finally:
            module_object_holder.script_obj.removeSchedule(self.dict_wms_params['SCRIPT_ID'])
    
    def send_acknowledgement(self,action,ack_data):
        try:
            dict_requestParameters = {}
            requestInfo = com.manageengine.monagent.communication.CommunicationHandler.RequestInfo()
            dict_requestParameters['agentKey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
            dict_requestParameters['dc'] = AgentUtil.getCurrentTimeInMillis()
            dict_requestParameters['action'] = action
            dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
            dict_requestParameters[action] = ack_data
            AgentLogger.log(AgentLogger.DEPLOYMENT, 'SD Acknowledgment Data =======> {0}'.format(json.dumps(dict_requestParameters))+'\n')
            dict_requestParameters['custID'] = AgentConstants.CUSTOMER_ID
            str_servlet = AgentConstants.SCRIPT_RESULT_SERVLET
            if not dict_requestParameters == None:
                str_requestParameters = urlencode(dict_requestParameters)
                str_url = str_servlet + str_requestParameters
            requestInfo.set_loggerName(AgentLogger.DEPLOYMENT)
            requestInfo.set_method(AgentConstants.HTTP_GET)
            requestInfo.set_url(str_url)
            requestInfo.add_header("Accept", "text/plain")
            requestInfo.add_header("Connection", 'close')
            bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData = com.manageengine.monagent.communication.CommunicationHandler.sendRequest(requestInfo)
        except Exception as e:
            traceback.print_exc()
    
    def send_deployment_result(self,dict_wms_params,deploy_dict):
        status = deploy_dict['status']
        error_msg = deploy_dict['msg']
        deploy_start_time = deploy_dict['start_time']
        if status:
            dict_response=scriptDeployer.get_default_response(dict_wms_params,deploy_start_time)
        else:
            dict_response=scriptDeployer.get_default_response(dict_wms_params,deploy_start_time,True,error_msg)
        if 'plugin_name' in deploy_dict:
            dict_response['plugin_name'] = deploy_dict['plugin_name']
        AgentLogger.debug(AgentLogger.DEPLOYMENT,' final response for upload -- {}'.format(dict_response))
        scriptDeployer.uploadResponse(dict_response)
    
    def download_from_url(self,dict_request_info):
        download_status = True
        error_msg = None
        try:
            url = dict_request_info['URL']
            if '$$STATIC_DOWNLOADS$$' in url:
                url = url.split('$$STATIC_DOWNLOADS$$')[1]
            AgentLogger.log(AgentLogger.DEPLOYMENT,' url is -- {} -- {}'.format(url,dict_request_info['destination_folder']))
            download_status , error_msg= CommunicationHandler.download_from_url(url,os.path.join(dict_request_info['destination_folder'],'temp.zip'), AgentLogger.DEPLOYMENT)
        except Exception as e:
            traceback.print_exc()
        return  download_status,error_msg

    def download_from_dfs(self,dict_request_info):
        download_status=True
        error_msg = None
        str_requestParameters=None
        str_url=None
        dict_requestParameters = {}
        hash_value = None
        ack_dict = {'action':'Deployment'}
        try:
            if 'checksum' in dict_request_info:
                hash_value = dict_request_info['checksum']
            dict_requestParameters['filePath']=dict_request_info['DFS_FILE_PATH']
            dict_requestParameters['blockID'] = dict_request_info['DFS_BLOCK_ID']
            dict_requestParameters['CUSTOMERID']=AgentConstants.CUSTOMER_ID
            dict_requestParameters['agentkey']=AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
            str_servlet=AgentConstants.DOWNLOAD_FILE_SERVLET
            if not dict_requestParameters == None:
                str_requestParameters = urlencode(dict_requestParameters)
                str_url = str_servlet + str_requestParameters
            file_path = os.path.join(dict_request_info['destination_folder'],'temp.zip')
            download_status, error_msg , resp_headers, resp_data = CommunicationHandler.downloadFile(str_url,file_path,logger=AgentLogger.STDOUT,checksum=hash_value,ack=ack_dict,return_all_params=True) 
            if not download_status:
                error_msg = "Download Failed from server"
        except Exception as e:
            traceback.print_exc()
            download_status=False
            error_msg='Exception while downloading the file :: trace :: {}'.format(e)
        return download_status,error_msg
    
    def extract_zip_files(self,destination,fileName):
        compress_status=True
        error_msg=None
        try:
            Name, file_extension = os.path.splitext(fileName)
            zipHandler = zipfile.ZipFile(os.path.join(destination,fileName), 'r')
            self.zip_name_list = zipHandler.namelist()
            zipHandler.extractall(destination)
            zipHandler.close()
            os.remove(os.path.join(destination,fileName))
        except Exception as e:
            compress_status = False
            error_msg = 'Problem while extracting the file :: trace :: {}'.format(e)
            traceback.print_exc()
            AgentLogger.log(AgentLogger.STDOUT,'Exception while uncompressing compressed files.')
        return compress_status,error_msg
    
    @staticmethod
    def uploadResponse(dictData):
        dict_requestParameters = {}
        dir_prop = AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['011']
        AgentLogger.debug(AgentLogger.STDOUT,'Deployment Response -- {}'.format(json.dumps(dictData)))
        try:
            AgentUtil.get_default_param(dir_prop,dict_requestParameters,AgentConstants.SD_RESULT)
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
            AgentLogger.log(AgentLogger.DEPLOYMENT,'[ Upload deployment response data ] '+repr(str_jsonData))
            if bool_isSuccess:
                AgentLogger.log([AgentLogger.DEPLOYMENT,AgentLogger.STDOUT], 'Successfully posted the script deployment response data to the server')
            else:
                AgentLogger.log([AgentLogger.DEPLOYMENT,AgentLogger.STDOUT], '************************* Unable to post the script deployment response data to the server. ************************* \n')
                CommunicationHandler.checkNetworkStatus(AgentLogger.STDOUT)

        except Exception as e:
            AgentLogger.log([AgentLogger.DEPLOYMENT,AgentLogger.STDERR], ' *************************** Exception while uploading deployment response *************************** '+ repr(e))
            traceback.print_exc()
    
    @staticmethod
    def get_default_response(dict_wms_params,deploy_start_time,error=False,error_msg=None):
        dictToReturn = {}
        dictToReturn['Error'] = "-"
        dictToReturn['status'] = True
        dictToReturn['response'] = AgentConstants.DS
        dictToReturn['start_time'] = deploy_start_time
        dictToReturn['end_time'] = AgentUtil.getTimeInMillis()
        dictToReturn['duration'] = dictToReturn['end_time'] - dictToReturn['start_time']
        if error:
            dictToReturn['Error'] = error_msg if error_msg else AgentConstants.DF
            dictToReturn['response'] = ""
            dictToReturn['status'] = False
        if dict_wms_params['ORIGIN'] is not None:
            dictToReturn['origin'] = dict_wms_params['ORIGIN']
        dictToReturn['script_id'] = dict_wms_params['SCRIPT_ID']
        dictToReturn['init_time'] = dict_wms_params['INIT_TIME']
        return dictToReturn