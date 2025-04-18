#$Id$
import traceback
import os
import json
from six.moves.urllib.parse import urlencode
import platform

import com
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.util import AgentUtil

def initialize(temp_list):
    try:
        list_of_files = []
        AgentLogger.log(AgentLogger.STDOUT,'files for checksum calculation :: {}'.format(temp_list))
        for each in temp_list:
            list_of_files.append(os.path.join(AgentConstants.AGENT_WORKING_DIR,each))
        if list_of_files:
            data = {'validate_checksum':{}}
            file_hash_result = AgentUtil.file_hash_util.hash_files(list_of_files)
            for each in file_hash_result:
                data['validate_checksum'][each.filename.replace(AgentConstants.AGENT_WORKING_DIR,'')]= each.hash
            upload_data_for_validation(data, "validate_checksum")
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT, AgentLogger.STDERR], ' *************************** Exception while initializing checksum validation data  *************************** ' + repr(e))
        traceback.print_exc()
    
def upload_data_for_validation(data,action):
    dict_requestParameters = {}
    requestInfo = com.manageengine.monagent.communication.CommunicationHandler.RequestInfo()
    result = {}
    try:
        dict_requestParameters['agentKey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        dict_requestParameters['CUSTOMERID'] = AgentConstants.CUSTOMER_ID
        dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
        dict_requestParameters['action'] = action
        dict_requestParameters['osArch'] = platform.architecture()[0]
        AgentLogger.debug(AgentLogger.STDOUT,'uploading data for checksum validation :: {}'.format(json.dumps(data)))
        str_servlet = AgentConstants.VALIDATION_SERVLET
        if not dict_requestParameters == None:
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
        str_dataToSend = json.dumps(data)
        str_contentType = 'application/json'
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.set_data(str_dataToSend)
        requestInfo.set_dataType(str_contentType)
        requestInfo.add_header("Content-Type", str_contentType)
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = com.manageengine.monagent.communication.CommunicationHandler.sendRequest(requestInfo)
        com.manageengine.monagent.communication.CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'CONFIG_VALIDATOR')
        AgentLogger.debug(AgentLogger.MAIN,' response of validation servlet -- {} -- {}'.format(dict_responseData,type(dict_responseData)))
        if dict_responseData:
            dict_responseData = json.loads(dict_responseData)
            if 'validation_result' in dict_responseData:
                result = dict_responseData['validation_result']
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT, AgentLogger.STDERR], ' *************************** Exception while uploading config validation data  *************************** ' + repr(e))
        traceback.print_exc()
    return result
