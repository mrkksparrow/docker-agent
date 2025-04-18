'''
Created on 02-July-2017

@author: giri
'''

import traceback
import os

#s24x7 packages
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants,AppConstants
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil
from com.manageengine.monagent.util.AgentUtil import ZipUtil
from com.manageengine.monagent.util.AgentUtil import FileZipAndUploadInfo

def save(dir_prop, result_data ,logger_name=AgentLogger.COLLECTOR, file_name = None):
    status = True
    try:
        if type(result_data) is dict:
            result_data['MSPCUSTOMERID'] = AgentConstants.CUSTOMER_ID
            result_data['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        if not file_name:
            file_name = FileUtil.getUniqueFileName(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'))
        if file_name:
            file_path = os.path.join(dir_prop['data_path'], file_name)
            file_obj = AgentUtil.FileObject()
            file_obj.set_fileName(file_name)
            file_obj.set_filePath(file_path)
            file_obj.set_data(result_data)
            file_obj.set_dataType('json' if type(result_data) is dict else "xml")
            file_obj.set_mode('wb')
            file_obj.set_dataEncoding('UTF-16LE')
            file_obj.set_loggerName(logger_name)
            status, file_path = FileUtil.saveData(file_obj)
    except Exception as e:
        AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR], '*************************** Exception while saving collected data : '+'*************************** '+ repr(e) + '\n')
        traceback.print_exc()
        status = False
    return status, file_name