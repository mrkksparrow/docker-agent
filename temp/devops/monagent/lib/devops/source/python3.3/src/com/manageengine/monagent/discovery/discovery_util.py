# $Id$

from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.logger import AgentLogger
from six.moves.urllib.parse import urlencode

import traceback,sys,os,json

def post_discovery_result(final_dict,dir_prop,action=AgentConstants.CD):
    try:
        from com.manageengine.monagent.communication import CommunicationHandler
        AgentLogger.log(AgentLogger.APPS,' final dict {} :: {}'.format(dir_prop['code'],json.dumps(final_dict)))
        request_params = {}
        AgentUtil.get_default_param(dir_prop,request_params,action)
        str_servlet = dir_prop['uri']
        if not request_params == None:
            str_requestParameters = urlencode(request_params)
            str_url = str_servlet + str_requestParameters
        str_dataToSend = json.dumps(final_dict)
        str_contentType = dir_prop['content_type']
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.APPS)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.set_data(str_dataToSend)
        requestInfo.set_dataType(str_contentType)
        requestInfo.add_header("Content-Type", str_contentType)
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
        AgentLogger.log(AgentLogger.APPS,'post [{}] discovery response :: {} status :: {} error code :: {}'.format(dir_prop['code'],dict_responseData,bool_isSuccess,errorCode))
        CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData,'APPS_DISCOVERY')
    except Exception as e:
        traceback.print_exc()