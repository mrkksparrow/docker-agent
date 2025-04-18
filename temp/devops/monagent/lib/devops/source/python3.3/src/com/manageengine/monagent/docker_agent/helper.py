'''
Created on 25-Jan-2018

@author: giri
'''
#python packages
from contextlib import contextmanager
import json
from six.moves.urllib.parse import urlencode
import traceback
import os
import threading
import copy
#s24x7 packages
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil
from com.manageengine.monagent.util.AgentUtil import ZipUtil
from com.manageengine.monagent.util.AgentUtil import FileZipAndUploadInfo
from com.manageengine.monagent.docker_agent import constants as da_constants
from com.manageengine.monagent.communication import BasicClientHandler, UdpHandler

LOCK = threading.Lock()

def get_default_req_params():
    req_params = {}
    req_params["agentKey"] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
    req_params["bno"] = AgentConstants.AGENT_VERSION
    return req_params

@contextmanager
def post_process_data(result_dict, dict_task):
    _status, _error_code, _response_headers, _response_data = True, None, None, None
    try:
        str_result = json.dumps(result_dict)
        str_url = None
        str_servlet = AgentConstants.DATA_AGENT_HANDLER_SERVLET
        req_params = get_default_req_params()
        req_params["action"] = dict_task['REQUEST_TYPE']
        req_params["requestId"] = str(dict_task['AGENT_REQUEST_ID'])
        req_params["custID"] = AgentConstants.CUSTOMER_ID
        if not req_params == None:
            str_req_params = urlencode(req_params)
            str_url = str_servlet + str_req_params
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.MAIN)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.set_data(str_result)
        requestInfo.add_header("Content-Type", 'application/json')
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        _status, _error_code, _response_headers, _response_data = CommunicationHandler.sendRequest(requestInfo)
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN, ' *************************** Exception while discovering processes | docker_agent helper *************************** '+ repr(e))
        traceback.print_exc()
        _status = False
    finally:
        yield _status

#it is called only for server metrics through docker agent [collector.py -> construct()]
def upload_collected_metrics(dict_data, dir_prop, server_monitoring_data=False):
    _status, _file_name = False, None
    try:
        dict_data['MSPCUSTOMERID'] = AgentConstants.CUSTOMER_ID
        dict_data['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        if server_monitoring_data:
            custom = "{}_SMData_millis_{}".format(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'), AgentUtil.getTimeInMillis())
            file_name = FileUtil.getUniqueFileName(dict_data['AGENTKEY'], custom, True)
        else:
            dict_data['DATACOLLECTTIME'] = str(AgentUtil.getTimeInMillis())
            file_name = FileUtil.getUniqueFileName(dict_data['AGENTKEY'])
        file_path = os.path.join(dir_prop['data_path'], file_name)
        fileObj = AgentUtil.FileObject()
        fileObj.set_fileName(file_name)
        fileObj.set_filePath(file_path)
        fileObj.set_data(dict_data)
        fileObj.set_dataType('json')
        fileObj.set_mode('wb')
        fileObj.set_dataEncoding('UTF-16LE')
        fileObj.set_loggerName(AgentLogger.COLLECTOR)
        _status, file_path = FileUtil.saveData(fileObj)
    except Exception as e:
        _status = False
        AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], '*************************** Exception while saving collected data : '+repr(dict_data)+'*************************** '+ repr(e) + '\n')
        traceback.print_exc()
    return _status, _file_name

def handle_new_configurations(dict_config_data, restart):
    try:
        with LOCK:
            da_constants.NEW_CONFIG_DICT = {}
            da_constants.NEW_CONFIG_DICT.update(dict_config_data)
            if (('reloadNotRequired' not in dict_config_data) or (dict_config_data['reloadNotRequired'] != True) or (restart)):
                if 'url' in dict_config_data:
                    da_constants.CONFIG_DICT['URL'] = {}
                    listURLs = dict_config_data['url']
                    for each_URL in listURLs:
                        da_constants.CONFIG_DICT['URL'][each_URL['id']] = each_URL['id']
                if 'port' in dict_config_data:
                    da_constants.CONFIG_DICT['PORT'] = {}
                    listPorts = dict_config_data['port']
                    for each_port in listPorts:
                        da_constants.CONFIG_DICT['PORT'][each_port['id']] = each_port['id']
                if 'ntp' in dict_config_data:
                    da_constants.CONFIG_DICT['NTP'] = {}
                    listNTP = dict_config_data['ntp']
                    for each_port in listNTP:
                        da_constants.CONFIG_DICT['NTP'][each_port['id']] = each_port['id']
                if 'script' in dict_config_data:
                    da_constants.CONFIG_DICT['SCRIPT'] = {}
                    listScripts = dict_config_data['script']
                    for each_script in listScripts:
                        da_constants.CONFIG_DICT['SCRIPT'][each_script['PATH']] = each_script['id']
                if (('nfs' in dict_config_data) and  (AgentConstants.OS_NAME in AgentConstants.NFS_MON_SUPPORTED)):
                    da_constants.CONFIG_DICT['NFS'] = {}
                    listNFS = dict_config_data['nfs']
                    for each_nfs in listNFS:
                        da_constants.CONFIG_DICT['NFS'][each_nfs['id']] = each_nfs['id']
                if ((('file' in dict_config_data) or ('dir' in dict_config_data)) and  (AgentConstants.OS_NAME in AgentConstants.NFS_MON_SUPPORTED)):
                    da_constants.CONFIG_DICT['FILE'] = {}
                    if 'file' in dict_config_data:
                        listFiles = dict_config_data['file']
                        for each_file in listFiles:
                            da_constants.CONFIG_DICT['FILE'][each_file['id']] = each_file['id']
                    if 'dir' in dict_config_data:
                        listDirs = dict_config_data['dir']
                        for each_dir in listDirs:
                            da_constants.CONFIG_DICT['FILE'][each_dir['id']] = each_dir['id']
                if 'logrule' in dict_config_data:
                    da_constants.CONFIG_DICT['logrule'] = {}
                    listFilters = dict_config_data['logrule']
                    if listFilters:
                        UdpHandler.SysLogUtil.reloadCustomFilters(listFilters)
                    for each_filter in listFilters:
                        da_constants.CONFIG_DICT['logrule'][each_filter['filter_name']] = each_filter['id']
                fileObj = AgentUtil.FileObject()
                fileObj.set_filePath(AgentConstants.AGENT_CUSTOM_MONITORS_GROUP_FILE)
                fileObj.set_dataType('json')
                fileObj.set_mode('rb')
                fileObj.set_dataEncoding('UTF-8')
                fileObj.set_loggerName(AgentLogger.CHECKS)
                fileObj.set_logging(False)
                bool_toReturn, dict_monitorsInfo = FileUtil.readData(fileObj)
                dict_monitorsInfo['MonitorGroup']['ChecksMonitoring']['Port'] = da_constants.NEW_CONFIG_DICT['port']
                dict_monitorsInfo['MonitorGroup']['ChecksMonitoring']['URL'] = da_constants.NEW_CONFIG_DICT['url']
                dict_monitorsInfo['MonitorGroup']['ChecksMonitoring']['NTP'] = da_constants.NEW_CONFIG_DICT['ntp']
                if 'nfs' in da_constants.NEW_CONFIG_DICT:
                    dict_monitorsInfo['MonitorGroup']['ChecksMonitoring']['NFSMonitoring'] = da_constants.NEW_CONFIG_DICT['nfs']
                dict_monitorsInfo['MonitorGroup']['ChecksMonitoring']['FileDirectory'] = da_constants.NEW_CONFIG_DICT['file'] + da_constants.NEW_CONFIG_DICT['dir']
                fileObj.set_data(dict_monitorsInfo)
                fileObj.set_mode('wb')
                bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
                BasicClientHandler.reload()
            else:
                AgentLogger.log(AgentLogger.STDOUT,'=============== Skipped Updating resource configuration values =======')
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception in handle_new_configurations *********************************')
        traceback.print_exc()

def handle_configuration_assignment():
    with LOCK:
        da_constants.CONFIG_DICT = copy.deepcopy(da_constants.NEW_CONFIG_DICT)
        # da_constants.NEW_CONFIG_DICT = {}

def get_resource_checks():
    listURLs = []
    listPorts = []
    listFiles = []
    listScripts = []
    listNFS = []
    listNTP = []
    listSysLogs = []
    dictURLData = None
    dictPortData = None
    dictFileData = None
    dictScriptData = None
    dictNFSData = None
    dictNTPData = None
    dictSysLogData = None
    checks_dict = {}
    dictConfig = da_constants.CONFIG_DICT
    AgentLogger.debug(AgentLogger.CHECKS, " checks data "+repr(json.dumps(BasicClientHandler.CHECKS_DATA)))
    try:
        with BasicClientHandler.globalDClock:
            if 'url' in BasicClientHandler.CHECKS_DATA:
                dictURLData = BasicClientHandler.CHECKS_DATA['url']
            if 'port' in BasicClientHandler.CHECKS_DATA:
                dictPortData = BasicClientHandler.CHECKS_DATA['port']
            if 'file' in BasicClientHandler.CHECKS_DATA:
                dictFileData = BasicClientHandler.CHECKS_DATA['file']
            if 'logrule' in BasicClientHandler.CHECKS_DATA:
                dictSysLogData = BasicClientHandler.CHECKS_DATA['logrule']
            if 'script' in BasicClientHandler.CHECKS_DATA:
                dictScriptData = BasicClientHandler.CHECKS_DATA['script']
            if 'nfs' in BasicClientHandler.CHECKS_DATA:
                dictNFSData = BasicClientHandler.CHECKS_DATA['nfs']
            if 'ntp' in BasicClientHandler.CHECKS_DATA:
                dictNTPData = BasicClientHandler.CHECKS_DATA['ntp']
        if dictURLData:
            for each_check_id in dictURLData:
                temp_dict = {}
                temp_dict = dict(dictURLData[each_check_id])
                if ((dictConfig) and ('URL' in dictConfig) and (str(each_check_id) in dictConfig['URL'])):
                    temp_dict['id'] = dictConfig['URL'][str(each_check_id)]
                else:
                    temp_dict['id'] = "None"
                listURLs.append(temp_dict)
        checks_dict.setdefault('url',listURLs)
        if dictPortData:
            for each_check_id in dictPortData:
                temp_dict = {}
                temp_dict = dict(dictPortData[each_check_id])
                if ((dictConfig) and ('PORT' in dictConfig) and (str(each_check_id) in dictConfig['PORT'])):
                    temp_dict['id'] = dictConfig['PORT'][str(each_check_id)]
                else:
                    temp_dict['id'] = "None"
                listPorts.append(temp_dict)
        checks_dict.setdefault('port',listPorts)
        if dictFileData:
            for each_check_id in dictFileData:
                temp_dict_file = {}
                temp_dict_file = dict(dictFileData[each_check_id])
                if (dictConfig and ('FILE' in dictConfig) and (str(each_check_id) in dictConfig['FILE'])):
                    temp_dict_file['id'] = dictConfig['FILE'][str(each_check_id)]
                else:
                    temp_dict_file['id'] = "None"
                listFiles.append(temp_dict_file)
        checks_dict.setdefault('file',listFiles)
        if dictScriptData:
            for each_check_id in dictScriptData:
                temp_dict = {}
                temp_dict = dict(dictScriptData[each_check_id])
                if ((dictConfig) and ('SCRIPT' in dictConfig) and (str(each_check_id) in dictConfig['SCRIPT'])):
                    temp_dict['id'] = dictConfig['SCRIPT'][str(each_check_id)]
                else:
                    temp_dict['id'] = "None"
                listScripts.append(temp_dict)
        checks_dict.setdefault('script',listScripts)
        if dictNFSData:
            for each_check_id in dictNFSData:
                temp_dict = {}
                temp_dict = dict(dictNFSData[each_check_id])
                if ((dictConfig) and ('NFS' in dictConfig) and (str(each_check_id) in dictConfig['NFS'])):
                    temp_dict['id'] = dictConfig['NFS'][str(each_check_id)]
                else:
                    temp_dict['id'] = "None"
                listNFS.append(temp_dict)
        checks_dict.setdefault('nfs',listNFS)
        if dictNTPData:
            for each_check_id in dictNTPData:
                temp_dict = {}
                temp_dict = dict(dictNTPData[each_check_id])
                if ((dictConfig) and ('NTP' in dictConfig) and (str(each_check_id) in dictConfig['NTP'])):
                    temp_dict['id'] = dictConfig['NTP'][str(each_check_id)]
                else:
                    temp_dict['id'] = "None"
                listNTP.append(temp_dict)
        checks_dict.setdefault('ntp',listNTP)
        if dictSysLogData:
            for each_log in dictSysLogData:
                temp_dict_syslog = {}
                temp_dict_syslog = dictSysLogData[each_log]
                listSysLogs.append(temp_dict_syslog)
        checks_dict.setdefault('logrule',listSysLogs)
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while getting resource checks *********************************')
        traceback.print_exc()
    finally:
        return checks_dict