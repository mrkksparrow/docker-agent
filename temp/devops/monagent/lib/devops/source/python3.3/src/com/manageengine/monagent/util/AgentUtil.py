# $Id$
import os
import sys
import shutil
import codecs
import time
import threading
import traceback
import json
import math
import zipfile
import copy
import hashlib
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser
import subprocess, signal
import xml.etree.ElementTree as xml
import collections
import re
from six.moves.urllib.parse import urlencode
from datetime import datetime, timedelta
import socket
import struct
import functools

import com
from com.manageengine.monagent import AgentConstants,module_object_holder
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentBuffer
from com.manageengine.monagent.util import DesignUtils
from com.manageengine.monagent.security import AgentCrypt
from com.manageengine.monagent.util.filehash import FileHash
from com.manageengine.monagent.kubernetes import KubeGlobal

if not AgentConstants.IS_VENV_ACTIVATED:
    try:
        from func_timeout import func_timeout, FunctionTimedOut
        from com.manageengine.monagent.applications.mysql import mysql
    except Exception as e:
        traceback.print_exc()

from com.manageengine.monagent.pypackages import statsd

import sys
import tempfile
from time import sleep
from itertools import islice
import platform
# Process exit codes
# http://stackoverflow.com/questions/1101957/are-there-any-standard-exit-status-codes-in-linux


AGENT_CONFIG = configparser.RawConfigParser()
UPLOAD_CONFIG = configparser.RawConfigParser()
WATCHDOGCONFIG = configparser.RawConfigParser()
WATCHDOGCONFIG.read(AgentConstants.WATCHDOG_CONF_FILE)

AGENT_CPU_THRESHOLD = float(WATCHDOGCONFIG.get('AGENT_THRESHOLD','CPU'))
AGENT_MEMORY_THRESHOLD = float(WATCHDOGCONFIG.get('AGENT_THRESHOLD','MEMORY'))
AGENT_THREAD_THRESHOLD = int(WATCHDOGCONFIG.get('AGENT_THRESHOLD','THREADS'))
AGENT_ZOMBIES_THRESHOLD = int(WATCHDOGCONFIG.get('AGENT_THRESHOLD','ZOMBIES'))
AGENT_CHECK_INTERVAL = int(WATCHDOGCONFIG.get('WATCHDOG_PARAMS','WATCHDOG_INTERVAL'))

AGENT_PARAMS = {"AGENT_FILE_ID": "0", "AGENT_ZIP_ID": "0"}

ZipUtil = None
UploadUtil = None
FileUtil = None
ZipInfoUtil = None
file_hash_util = None

TERMINATE_AGENT = False
TERMINATE_AGENT_NOTIFIER = threading.Event()

DONT_PRINT_CONSTANTS = ['proxy_password','encrypted_proxy_password','customer_id']

MUST_PRESENT_CONSTANTS = {
    'PRODUCT' : ['product_name'],
    'SERVER_INFO' : ['server_name', 'server_port', 'server_protocol'],
    'AGENT_INFO' : ['agent_key', 'agent_unique_id'],
    'TYPE' : ['docker_agent'],
}

PLUGIN_NAME_VS_PATH = {'mysql.py':'com.manageengine.monagent.applications.mysql.mysql'}

COUNTER_PARAMS_DICT={}

def initialize():
    global ZipUtil, FileUtil,file_hash_util
    ZipUtil = ZipCycleHandler()
    ZipUtil.setDaemon(True)
    ZipUtil.name = 'ZIPPER'
    FileUtil = FileHandler()
    ZipInfoUtil = FileZipAndUploadInfo()
    file_hash_util = FileHash()
    
def persistAgentParams():
    if not AGENT_PARAMS == None:        
        if not writeDataToFile(AgentConstants.AGENT_PARAMS_FILE, AGENT_PARAMS):
            AgentLogger.log(AgentLogger.STDOUT,'************************* Problem while Persisting Agent Params *************************') 
    else:
        AgentLogger.log(AgentLogger.STDOUT,'************************* Agent Params Not Populated *************************')

def backupConfFile():
    try:        
        AgentLogger.log(AgentLogger.STDOUT,'Taking backup of the configuration file : '+repr(AgentConstants.AGENT_CONF_FILE)+' to : '+repr(AgentConstants.AGENT_CONF_BACKUP_FILE))
        shutil.copy(AgentConstants.AGENT_CONF_FILE, AgentConstants.AGENT_CONF_BACKUP_FILE)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while taking backup of the configuration file : '+repr(AgentConstants.AGENT_CONF_FILE)+' ************************* ')
        traceback.print_exc()  
        
def isWarmShutdown():
    try:
        if not os.path.exists(AgentConstants.AGENT_SHUTDOWN_FLAG_FILE):
            AgentLogger.log(AgentLogger.STDOUT,'AGENT_SHUTDOWN_FLAG_FILE is not present. Setting AGENT_WARM_SHUTDOWN = False')
            AgentConstants.AGENT_WARM_SHUTDOWN = False
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AGENT_SHUTDOWN_FLAG_FILE is present. Setting AGENT_WARM_SHUTDOWN = True')
    except Exception as e:
        AgentLogger.log([AgentLogger.CRITICAL],' ************************* Exception while setting AGENT_WARM_SHUTDOWN variable ************************* ')
        traceback.print_exc()
    finally:
        FileUtil.deleteFile(AgentConstants.AGENT_SHUTDOWN_FLAG_FILE)

def handleSpecialTasks():
    try:
        if AgentConstants.MON_AGENT_UPGRADED:
            AgentLogger.log(AgentLogger.STDOUT,'================================= HANDLE SPECIAL TASKS =================================')
            com.manageengine.monagent.collector.DataCollector.ProcessUtil.updateProcessDetailsForAgentVersionsBelow11_0_0()
            com.manageengine.monagent.communication.UdpHandler.SysLogUtil.editSyslogConfiguration()
            if os.path.exists(AgentConstants.DOCKER_AGENT_FOLDER):
                shutil.rmtree(AgentConstants.DOCKER_AGENT_FOLDER,True)
            for each in AgentConstants.FILES_LIST_TO_DELETE:
                FileUtil.deleteFile(each, AgentLogger.APPS)
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT, AgentLogger.STDERR],' ************************* Exception while handling special tasks ************************* ')
        traceback.print_exc()
        
def updateShutdownTime():
    try:
        str_shutdownTime = 'Shutdown at '+repr(datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S"))
        fileObj = FileObject()
        fileObj.set_filePath(AgentConstants.AGENT_SHUTDOWN_FLAG_FILE)
        fileObj.set_data(str_shutdownTime)
        fileObj.set_loggerName(AgentLogger.MAIN)
        FileUtil.saveData(fileObj)
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT, AgentLogger.STDERR],'Exception while updating agent shut down time' + repr(e))
        traceback.print_exc()
        
def shutdownAgent(signum, frame):
    try:  
        AgentLogger.log(AgentLogger.MAIN,'Received Shutdown Notification : \n')
        shutdownTime = getCurrentTimeInMillis()
        updateShutdownTime()
        com.manageengine.monagent.util.MetricsUtil.terminate_agent()
        com.manageengine.monagent.util.eBPFUtil.stop()
        com.manageengine.monagent.communication.applog.stop()
        if not (com.manageengine.monagent.upgrade.AgentUpgrader.UPGRADE or os.path.exists(AgentConstants.AGENT_WATCHDOG_SILENT_RESTART_FLAG_FILE) or os.path.exists(AgentConstants.AGENT_RESTART_FLAG_FILE)):
            com.manageengine.monagent.communication.AgentStatusHandler.notifyShutdown(shutdownTime)
        else:
            AgentLogger.log(AgentLogger.STDOUT,'Server is not notified - upgrade ' +repr(com.manageengine.monagent.upgrade.AgentUpgrader.UPGRADE))
            AgentLogger.log(AgentLogger.STDOUT,'Watch dog restart flag file : '+repr(os.path.exists(AgentConstants.AGENT_WATCHDOG_SILENT_RESTART_FLAG_FILE)))
            AgentLogger.log(AgentLogger.STDOUT,'Agent restart flag file : '+repr(os.path.exists(AgentConstants.AGENT_RESTART_FLAG_FILE)))
        com.manageengine.monagent.util.rca.RcaHandler.backupRCAReport(AgentConstants.AGENT_TEMP_RCA_REPORT_DIR)
        TerminateAgent()
        cleanAll()
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT, AgentLogger.STDERR],'*************************** Exception while handling shutdown notification *************************** '+ repr(e))        
        traceback.print_exc()        

def shutdownListener():
    signal.signal(signal.SIGTERM, shutdownAgent)
    #atexit.register(shutdownHandler)

def updateEbpfProcessInterval():
    EBPF_CONFIG = configparser.RawConfigParser()
    EBPF_CONFIG.read(AgentConstants.EBPF_CONFIG_PATH)
    if EBPF_CONFIG.has_section("server") and str(EBPF_CONFIG.get("server", "seconds")) != str(AgentConstants.POLL_INTERVAL):
        EBPF_CONFIG.set("server", "seconds", AgentConstants.POLL_INTERVAL)
        with open(AgentConstants.EBPF_CONFIG_PATH,"w") as configfile:
            EBPF_CONFIG.write(configfile)

def persistAgentInfo(config=None):
    try:
        AgentLogger.log(AgentLogger.STDOUT,'================================= PERSISTING AGENT INFO =================================')
        if config == None:
            config = AGENT_CONFIG
        list_sections = config.sections()
        for sec in list_sections:
            for key, value in config.items(sec):
                if value == None:
                    value = '0'
                    config.set(sec, key, value)
                if key not in DONT_PRINT_CONSTANTS:
                    AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : '+key+' : '+repr(value))
        with open(AgentConstants.AGENT_CONF_FILE,"w") as configfile:
            config.write(configfile)
        with open(AgentConstants.AGENT_CONF_BACKUP_FILE,"w") as configfile:
            config.write(configfile)
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,'***** Exception while persisting monagent.cfg ***** :: error - {}'.format(e))
        traceback.print_exc()
def readAgentInfo(recursive_call=False):
    conf_file_corrupted = False
    try:
        AgentLogger.log(AgentLogger.STDOUT,'================================= READING AGENT INFO =================================')
        if os.path.exists(AgentConstants.AGENT_CONF_FILE):
            try:
                AGENT_CONFIG.read(AgentConstants.AGENT_CONF_FILE)
            except Exception as e:
                AgentLogger.log(AgentLogger.MAIN,'***** Exception while reading monagent.cfg format ***** :: error - {}'.format(e))
                traceback.print_exc()
                os.remove(AgentConstants.AGENT_CONF_FILE)
                shutil.copy(AgentConstants.AGENT_CONF_BACKUP_FILE, AgentConstants.AGENT_CONF_FILE)
                recursive_call = True # since monagent.cfg is corrupted at starting itself
                AGENT_CONFIG.read(AgentConstants.AGENT_CONF_FILE)
            for section, key_list in MUST_PRESENT_CONSTANTS.items():
                if not AGENT_CONFIG.has_section(section):
                    conf_file_corrupted = True
                    break
                else:
                    for key in key_list:
                        if not AGENT_CONFIG.has_option(section, key):
                            conf_file_corrupted = True
                            break

        if recursive_call and conf_file_corrupted:
            AgentLogger.log(AgentLogger.MAIN,'****** backup/monagent.cfg is also corrupted ******')
            return conf_file_corrupted
        elif recursive_call and not conf_file_corrupted:
            AgentLogger.log(AgentLogger.MAIN,'****** backup/monagent.cfg is copied and used as AGENT_CONFIG ******')
            return conf_file_corrupted
        elif conf_file_corrupted:
            AgentLogger.log(AgentLogger.MAIN,'****** monagent.cfg is corrupted, copying backup/monagent.cfg ******')
            os.remove(AgentConstants.AGENT_CONF_FILE)
            shutil.copy(AgentConstants.AGENT_CONF_BACKUP_FILE, AgentConstants.AGENT_CONF_FILE)
            conf_file_corrupted = readAgentInfo(True)
        else:
            return conf_file_corrupted
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,'***** Exception while reading monagent.cfg ***** :: error - {}'.format(e))
        traceback.print_exc()
        return False

def persistUploadPropertiesInfo():
    AgentLogger.log(AgentLogger.STDOUT,'================================= PERSISTING UPLOAD PROPERTIES INFO =================================')
    list_sections = UPLOAD_CONFIG.sections()
    for sec in list_sections:
        for key, value in UPLOAD_CONFIG.items(sec):
            if value == None:
                value = '0'
                UPLOAD_CONFIG.set(sec, key, value)
            AgentLogger.log(AgentLogger.STDOUT,'UPLOAD PROPERTIES CONSTANTS : '+key+' : '+repr(value))
    confFile = open(AgentConstants.AGENT_UPLOAD_PROPERTIES_FILE,"w")
    UPLOAD_CONFIG.write(confFile)

def persistProfile(str_fileName, dict_content):
    bool_toReturn = True
    str_dataToWrite = ''
    file_obj = None
    try:
        AgentLogger.log(AgentLogger.STDOUT,'Persisting the profile data : '+repr(dict_content)+' in the file : '+repr(str_fileName))
        for key in dict_content:
            str_dataToWrite += key
            str_dataToWrite += '='
            str_dataToWrite += dict_content[key]            
            str_dataToWrite += ';export '
            str_dataToWrite += key
            str_dataToWrite += '\n'
        try:
            if str_dataToWrite != '':  
                file_obj = open(str_fileName, 'w')
                file_obj.write(str_dataToWrite)
                os.chmod(str_fileName, 0o755)
        except:
            AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while saving profile data : '+repr(str_dataToWrite)+' To File '+str(str_fileName)+' ************************* ')
            traceback.print_exc()
            bool_toReturn = False
        finally:        
            if not file_obj == None:
                file_obj.close()
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while creating profile ************************* '+ repr(e))
        traceback.print_exc()
        bool_toReturn = False
    return bool_toReturn   

def getAgentVersion():
    bool_returnStatus = True
    file_obj = None
    str_agentVersion = None
    try:
        file_obj = open(AgentConstants.AGENT_VERSION_FILE,'r')
        str_agentVersion = file_obj.read()
        if "\n" in str_agentVersion:
            str_agentVersion = str_agentVersion.replace("\n","") 
    except:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while reading agent version from the file '+AgentConstants.AGENT_VERSION_FILE+' ************************* ')
        traceback.print_exc()
        bool_returnStatus = False
    finally:
        if not file_obj == None:
            file_obj.close()
    if bool_returnStatus:
        AgentLogger.log(AgentLogger.STDOUT,'Agent version : '+repr(str_agentVersion)+' from the file : '+AgentConstants.AGENT_VERSION_FILE)
    return bool_returnStatus, str_agentVersion

def getAgentBuildNumber():
    bool_returnStatus = True
    file_obj = None
    str_agentBno = None
    try:
        file_obj = open(AgentConstants.AGENT_BUILD_NUMBER_FILE,'r')
        str_agentBno = file_obj.read()
        if "\n" in str_agentBno:
            str_agentBno = str_agentBno.replace("\n","")
    except:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while reading agent version from the file '+AgentConstants.AGENT_BUILD_NUMBER_FILE+' ************************* ')
        traceback.print_exc()
        bool_returnStatus = False
    finally:
        if not file_obj == None:
            file_obj.close()
    if bool_returnStatus:
        AgentLogger.log(AgentLogger.STDOUT,'Agent build number : '+repr(str_agentBno)+' from the file : '+AgentConstants.AGENT_BUILD_NUMBER_FILE)
    return bool_returnStatus, str_agentBno


def get_agent_install_time():
    bool_returnStatus = True
    file_obj = None
    str_agent_install_time = None
    try:
        file_obj = open(AgentConstants.AGENT_INSTALL_TIME_FILE,'r')
        str_agent_install_time = file_obj.read()
        if "\n" in str_agent_install_time:
            str_agent_install_time = str_agent_install_time.replace("\n","") 
    except:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while reading agent install time from the file '+AgentConstants.AGENT_INSTALL_TIME_FILE+' ************************* ')
        traceback.print_exc()
        bool_returnStatus = False
    finally:
        if not file_obj == None:
            file_obj.close()
    if bool_returnStatus:
        AgentLogger.log(AgentLogger.STDOUT,'Agent install time : '+repr(str_agent_install_time)+' from the file : '+AgentConstants.AGENT_INSTALL_TIME_FILE)
    return bool_returnStatus, str_agent_install_time

def reinit_childs():
    from com.manageengine.monagent.util import AppUtil, DatabaseUtil
    from com.manageengine.monagent.hardware import HardwareMonitoring
    try:
        AgentLogger.log([AgentLogger.MAIN, AgentLogger.APPS], "Reinitializing child applications")
        AppUtil.rediscover_application()
        HardwareMonitoring.rediscover_hardware_monitoring()
        # MetricsUtil.statsd_util_obj.enable_statsd_monitoring()
        DatabaseUtil.clear_database_config_files()
        module_object_holder.plugins_util.re_register_plugins()
    except:
        AgentLogger.log(AgentLogger.STDOUT,'************************* Exception while re-registering applications *************************')
        traceback.print_exc()

def get_auid_from_file():
    bool_returnStatus = True
    file_obj = None
    str_agentuid = None
    try:
        file_obj = open(AgentConstants.AUID_FILE,'r')
        str_agentuid = file_obj.read()
        if "\n" in str_agentuid:
            str_agentuid = str_agentuid.replace("\n","")
    except:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while reading agent uid from the file '+AgentConstants.AUID_FILE+' ************************* ')
        traceback.print_exc()
        bool_returnStatus = False
    finally:
        if not file_obj == None:
            file_obj.close()
    if bool_returnStatus:
        AgentLogger.log(AgentLogger.STDOUT,'Agent UID  : '+repr(str_agentuid)+' from the file : '+AgentConstants.AUID_FILE)
    return bool_returnStatus, str_agentuid

class Executor:
    def __init__(self):
        self.__str_command = None
        self.__int_timeout = 5
        self.__str_loggerName = AgentLogger.STDOUT
        self.__bool_redirectToFile = False
        self.__str_stdout = None
        self.__str_stderr = None
        self.__str_outputEncoding = 'UTF-8'
        self.__bool_isSuccess = False
        self.__str_customNameForOutputFile = 'Temp_Raw_Data'
        self.__str_ouputFilePath = None
        self.__str_commandExecuted = None
        self.__returnCode = None
        self.__is_timed_out = False
    def setCommand(self, str_command):
        self.__str_command = str_command
    def getCommand(self):
        return self.__str_command
    def getCommandExecuted(self):
        return self.__str_commandExecuted
    def setTimeout(self, int_timeout):
        self.__int_timeout = int_timeout
    def getTimeout(self):
        return self.__int_timeout
    def setLogger(self, str_loggerName):
        self.__str_loggerName = str_loggerName
    def getLogger(self):
        return self.__str_loggerName
    def redirectToFile(self, bool_redirectToFile):
        self.__bool_redirectToFile = bool_redirectToFile
    def getRedirectToFile(self):
        return self.__bool_redirectToFile
    def getStdOut(self):
        return self.__str_stdout
    def getStdErr(self):
        return self.__str_stderr
    def getReturnCode(self):
        return self.__returnCode
    def setOutputEncoding(self, str_outputEncoding):
        self.__str_outputEncoding = str_outputEncoding
    def getOutputEncoding(self):
        return self.__str_outputEncoding
    def isSuccess(self):
        return self.__bool_isSuccess
    def setCustomNameForOutputFile(self, str_customNameForOutputFile):
        self.__str_customNameForOutputFile = str_customNameForOutputFile
    def getCustomNameForOutputFile(self):
        return self.__str_customNameForOutputFile
    def getOutputFilePath(self):
        return self.__str_ouputFilePath
    def is_timed_out(self):
        return self.__is_timed_out
    def __captureOutput(self, process):
        isSuccess = False
        out, err = process.communicate()
        self.__returnCode = process.returncode
        if ((process.returncode is not None) and (process.returncode not in AgentConstants.SCRIPT_ERROR_CODES)):
            AgentLogger.debug(self.__str_loggerName,'Return Code : '+str(process.returncode)+' Command \''+str(self.__str_commandExecuted)+'\' executed successfully')
            isSuccess = True
        else:
            AgentLogger.debug(self.__str_loggerName,'Return Code : '+str(process.returncode)+' Error while executing the command \''+str(self.__str_commandExecuted)+'\'')
            isSuccess = False  
        return isSuccess, out, err
    def executeCommand(self):    
        bool_isSuccess = False
        str_CommandOutput = None
        str_ErrorOutput = None
        int_timeoutCounter = 0
        isTerminated = False
        int_timeout = self.__int_timeout
        str_loggerName = self.__str_loggerName
        try:
            if self.__bool_redirectToFile:
                str_fileName = FileUtil.getUniqueFileName(AGENT_CONFIG.get('AGENT_INFO', 'agent_key'), self.__str_customNameForOutputFile)
                self.__str_ouputFilePath = AgentConstants.AGENT_TEMP_RAW_DATA_DIR +'/'+str_fileName
                self.__str_commandExecuted = self.__str_command + ' > '+ '"'+self.__str_ouputFilePath+'"'
            else:
                self.__str_commandExecuted = self.__str_command
            list_commandArgs = [self.__str_commandExecuted]
            import os
            if os.path.exists(AgentConstants.COLUMN_EXTEND_FILE):
                env_copy = os.environ.copy()
                env_copy['COLUMNS']=str(AgentConstants.DISCOVER_PROCESS_ARGUMENT_LENGTH)
                proc = subprocess.Popen(list_commandArgs, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,env=env_copy,preexec_fn=os.setsid)
            else:
                proc = subprocess.Popen(list_commandArgs, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,preexec_fn=os.setsid)

            processId = proc.pid
            while int_timeoutCounter <= int_timeout:      
                int_timeoutCounter +=.5                
                time.sleep(.5)
                AgentLogger.debug(str_loggerName,' Polling process, Return Code : '+str(proc.poll()))
                if proc.poll() is not None:
                    bool_isSuccess, byte_CommandOutput, byte_ErrorOutput = self.__captureOutput(proc)
                    str_CommandOutput = byte_CommandOutput.decode(self.__str_outputEncoding)
                    str_ErrorOutput = byte_ErrorOutput.decode(self.__str_outputEncoding)
                    isTerminated = True
                    break
            if not isTerminated:
                self.__is_timed_out = True
                AgentLogger.log([str_loggerName],'Command Failed To Terminate, Hence issuing \'kill\' command -- {0} \n'.format(list_commandArgs))
                os.killpg(os.getpgid(processId), signal.SIGKILL)  
        except Exception as e:
            AgentLogger.log([str_loggerName,AgentLogger.MAIN],'***************************** Exception while executing command : '+str(self.__str_commandExecuted)+' *****************************')
            traceback.print_exc()
        finally:   
            self.__bool_isSuccess = bool_isSuccess
            self.__str_stdout = str_CommandOutput
            self.__str_stderr = str_ErrorOutput
    
    def execute_cmd_with_tmp_file_buffer(self):
        bool_isSuccess = True
        output=''
        err=''
        return_code=''
        try:
            AgentLogger.log(AgentLogger.STDOUT,'command for execution -- {}'.format(self.__str_command.split()))
            with tempfile.TemporaryFile() as stdout_f, tempfile.TemporaryFile() as stderr_f:
                proc = subprocess.Popen(self.__str_command.split(), stdout=stdout_f, stderr=stderr_f,preexec_fn=os.setsid)
                pid = proc.pid
                proc.wait(self.__int_timeout)
                stderr_f.seek(0)
                err = stderr_f.read()
                stdout_f.seek(0)
                output = stdout_f.read()
                return_code = proc.returncode
        except subprocess.TimeoutExpired:
                bool_isSuccess = False
                err='timeout occurred'
                return_code = '408'
                os.killpg(os.getpgid(pid),signal.SIGKILL)
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,'***************************** Exception while executing command : '+str(self.__str_command.split())+' *****************************')
            traceback.print_exc()
        finally:
               self.__bool_isSuccess = bool_isSuccess
               self.__str_stdout = output if isinstance(output, str) else output.decode('utf-8')
               self.__str_stderr = err if isinstance(err,str) else err.decode('utf-8')
               self.__returnCode = return_code
                           
def executeCommand(str_command, str_loggerName=AgentLogger.STDOUT, int_timeout=5):    
    bool_isSuccess = False
    str_CommandOutput = None
    int_timeoutCounter = 0
    isTerminated = False
    def captureOutput(process):
        isSuccess = False
        out, err = process.communicate()
        if process.returncode is not None:
            AgentLogger.debug(str_loggerName,'Return Code : '+str(process.returncode)+' Command \''+str(str_command)+'\' executed successfully')
            isSuccess = True
            output = out
        else:
            AgentLogger.debug(str_loggerName,'Return Code : '+str(process.returncode)+' Error while executing the command \''+str(str_command)+'\'')
            isSuccess = False
            output = err    
        return isSuccess, output
    list_commandArgs = [str_command]
    if os.path.exists(AgentConstants.COLUMN_EXTEND_FILE):
        env_copy = os.environ.copy()
        env_copy['COLUMNS']=str(AgentConstants.DISCOVER_PROCESS_ARGUMENT_LENGTH)
        proc = subprocess.Popen(list_commandArgs, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,preexec_fn=os.setsid,env=env_copy)
    else:
        proc = subprocess.Popen(list_commandArgs, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,preexec_fn=os.setsid)
    processId = proc.pid    
    try:
        while int_timeoutCounter <= int_timeout:      
            int_timeoutCounter +=.5                
            time.sleep(.5)
            AgentLogger.debug(str_loggerName,' Polling process, Return Code : '+str(proc.poll()))
            if proc.poll() is not None:
                bool_isSuccess, byte_CommandOutput = captureOutput(proc)
                str_CommandOutput = byte_CommandOutput.decode('UTF-8')
                isTerminated = True
                break
        if not isTerminated:
            AgentLogger.log(str_loggerName,'Command Failed To Terminate, Hence issuing \'kill\' command -- {0} \n'.format(list_commandArgs))
            os.killpg(os.getpgid(processId), signal.SIGKILL)     
    except Exception as e:
        AgentLogger.log(str_loggerName,'***************************** Exception while executing command : '+str(str_command)+' *****************************')
        traceback.print_exc()        
    return bool_isSuccess, str_CommandOutput

def writeDataToFile(str_fileName, dic_DataToWrite):
    bool_toReturn = True
    file_obj = None
    try:
        file_obj = open(str_fileName,'w')
        json.dump(dic_DataToWrite, file_obj)        
    except:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception While Writing Data : '+repr(dic_DataToWrite)+' To File '+str_fileName+' ************************* ')
        traceback.print_exc()
        bool_toReturn = False
    finally:        
        if not file_obj == None:
            file_obj.close() 
    return bool_toReturn

def writeRawDataToFile(str_fileName, raw_DataToWrite):
    bool_toReturn = True
    file_obj = None
    try:
        file_obj = open(str_fileName,'w')
        file_obj.write(raw_DataToWrite)
    except:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception While Writing Raw Data : '+repr(raw_DataToWrite)+' To File '+str_fileName+' ************************* ')
        traceback.print_exc()
        bool_toReturn = False
    finally:
        if not file_obj == None:
            file_obj.close()
    return bool_toReturn

def writeUnicodeDataToFile(str_fileName, dic_DataToWrite):
    bool_toReturn = True
    file_obj = None
    try:       
        file_obj = codecs.open(str_fileName,'w','UTF-16')
        file_obj.write(str(dic_DataToWrite))  
    except:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception While Writing Data : '+repr(dic_DataToWrite)+' To File '+str_fileName+' ************************* ')
        traceback.print_exc()
        bool_toReturn = False
    finally:        
        if not file_obj == None:
            file_obj.close() 
    return bool_toReturn
        
def loadDataFromFile(str_fileName):
    bool_returnStatus = True
    file_obj = None
    dic_dataToReturn = None
    try:
        file_obj = open(str_fileName,'r')
        dic_dataToReturn = json.load(file_obj,object_pairs_hook=collections.OrderedDict)    
    except:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception While Loading Data From File '+str_fileName+' ************************* ')
        traceback.print_exc()
        bool_returnStatus = False
    finally:
        if not file_obj == None:
            file_obj.close() 
    return bool_returnStatus, dic_dataToReturn

def loadRawDataFromFile(str_fileName):
    bool_returnStatus = True
    file_obj = None
    raw_dataToReturn = None
    try:
        file_obj = open(str_fileName,'r')
        raw_dataToReturn = file_obj.read()    
    except:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception While Loading Data From File '+str_fileName+' ************************* ')
        traceback.print_exc()
        bool_returnStatus = False
    finally:
        if not file_obj == None:
            file_obj.close() 
    return bool_returnStatus, raw_dataToReturn

def loadUnicodeDataFromFile(str_fileName):
    bool_returnStatus = True
    file_obj = None
    dic_dataToReturn = None
    try:
        file_obj = open(str_fileName,'rb')
        byte_data = file_obj.read()
        unicodeData = byte_data.decode('UTF-16')
        dic_dataToReturn = json.loads(unicodeData)
    except:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception While Loading Unicode Data From File '+str_fileName+' ************************* ')
        traceback.print_exc()
        bool_returnStatus = False
    finally:
        if not file_obj == None:
            file_obj.close() 
    return bool_returnStatus, dic_dataToReturn

def convertXmlToMap(str_fileName):
    dict_toReturn = {}
    try:         
        tree = xml.parse(str_fileName)
        for node in tree.iter(): 
            dict_toReturn[node.tag] = node.text
    except Exception as e:
        print(' ************************* Exception While Converting XML Data To Map From The File : '+str_fileName+' ************************* '+repr(e))
        traceback.print_exc()
        dict_toReturn = None
    return dict_toReturn

def loadMonitorsXml(str_fileName):
    dict_toReturn = collections.OrderedDict()
    try:         
        tree = xml.parse(str_fileName)
        def getChildTags(node):
            list_childTags = None
            if len(list(node))>0:
                list_childTags = []
                for elem in list(node):                    
                    list_childTags.append(elem.tag)
            return list_childTags
        str_rootTag = None   
        str_parentTag = None
        str_monitorTagId = None
        list_rootChildTags = None     
        for node in tree.iter():            
            if node.tag == 'MonitorsXml':
                str_rootTag = node.tag
                dict_toReturn[str_rootTag] = collections.OrderedDict()
                dict_toReturn[str_rootTag]['Attributes'] = node.attrib
                list_rootChildTags = getChildTags(node)                
            elif node.tag in list_rootChildTags:
                dict_toReturn[str_rootTag][node.tag] = collections.OrderedDict()
                dict_toReturn[str_rootTag][node.tag]['Attributes'] = node.attrib
                str_parentTag = node.tag
            elif node.tag == 'Monitor':
                str_monitorTagId = node.attrib['Id']
                dict_toReturn[str_rootTag][str_parentTag][str_monitorTagId] = collections.OrderedDict()
                dict_toReturn[str_rootTag][str_parentTag][str_monitorTagId]['Attributes'] = node.attrib
                dict_toReturn[str_rootTag][str_parentTag][str_monitorTagId]['Entities'] = collections.OrderedDict()
            elif node.tag == 'Entity':
                str_entityId = node.attrib['Id']
                dict_toReturn[str_rootTag][str_parentTag][str_monitorTagId]['Entities'][str_entityId] = node.attrib   
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,' ************************* Exception While Loading Monitors From The XML File : '+str_fileName+' ************************* '+repr(e))
        traceback.print_exc()
        dict_toReturn = None
    return dict_toReturn

def convertDataToDictionary(str_filePath):
    bool_toReturn = True        
    fileSysEncoding = sys.getfilesystemencoding()
    file_obj = None
    dict_toReturn = None
    try:            
        if os.path.isfile(str_filePath):                
            file_obj = open(str_filePath,'rb')
            byte_data = file_obj.read()
            str_data = byte_data.decode(fileSysEncoding)
            dict_toReturn = json.loads(str_data)#String to python object (dictionary)
        else:
            bool_toReturn = False
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception While Reading The file '+repr(str_filePath)+' ************************* '+ repr(e))
        traceback.print_exc()      
        bool_toReturn = False          
    finally:
        if file_obj:
            file_obj.close()
    return bool_toReturn, dict_toReturn

def getModifiedString(strData,initial,last):
    returnStr = strData
    try:
        if strData:
            if len(strData) > int(initial) + int(last):
                returnStr = strData[:initial] + "....." + strData[len(strData) - last:]
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while creating modified string ************************* '+ repr(e))
        traceback.print_exc()
    finally:
        return returnStr

def get_nicspeed(nicname):
    try:
        default_speed = -1
        nic_stat = None
        if AgentConstants.PSUTIL_OBJECT:
            netstats = AgentConstants.PSUTIL_OBJECT.net_if_stats()
            nic_stat=netstats[nicname]
            if nic_stat.speed != 0:
                return nic_stat.speed
        if (nic_stat and nic_stat.speed == 0) or not AgentConstants.PSUTIL_OBJECT:
            cmd = "iwconfig "+nicname+" | grep Bit | awk '{print $2}'"
            executorObj = Executor()
            executorObj.setLogger(AgentLogger.COLLECTOR)
            executorObj.setTimeout(10)
            executorObj.setCommand(cmd)
            executorObj.executeCommand()
            stdOutput = executorObj.getStdOut()
            if stdOutput:
                speed = stdOutput.split('=')[1]
                return int(float(speed)) if stdOutput.find("no wireless extensions") == -1 else default_speed
            else:
                return default_speed
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'************************* Exception occurred while fetching network bandwidth *************************')
        traceback.print_exc()
        return default_speed

def process_uptime_in_secs(uptime, epoch):
    try:
        if epoch:
            #uptime will be in epoch (seconds)
            up_timestamp = datetime.fromtimestamp(uptime)
            present_timestamp = datetime.now()
            return str(int((present_timestamp - up_timestamp).total_seconds())) #To strip milliseconds, converting to seconds
        else:    
            #converting uptime of any format into DD-HH:MM:SS
            if len(uptime.split(':')) < 3:
                uptime = '00:' + uptime
            if uptime.find('-') == -1:
                uptime = '00-' + uptime
            # 1 day = 86400secs
            updays_sec = int(uptime.split('-')[0]) * 86400       
            x = time.strptime(uptime.split('-')[1],'%H:%M:%S')
            perday_sec = timedelta(hours=x.tm_hour,minutes=x.tm_min,seconds=x.tm_sec).total_seconds()
            total_sec = perday_sec + updays_sec
            return str(int(total_sec))
    except:
        AgentLogger.log(AgentLogger.STDERR,'************************* Exception occurred while calculating process uptime in seconds *************************')
        traceback.print_exc()
        return '-'

def offset_in_machine_clock(NTPserver = None, NTPserverport = 123):
    offset = 0
    NTPserverList = []
    if NTPserver:
        NTPserverList.append(NTPserver)
    else:
        NTPserverList = AgentConstants.NTP_SERVER_ADDRESSES

    for each in NTPserverList:
        try:
            Ref_time_1970 = 2208988800  # time diff between 1900 - 1970 in seconds
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(AgentConstants.DEFAULT_NTP_TIMEOUT)
            data = b'\x1b' + 47 * b'\0'
            start_time = time.time()
            try:
                client.sendto(data, (each, NTPserverport))
            except Exception as e:
                return False, offset, str(e)
            end_time = time.time()
            half_round_trip = int((end_time - start_time)/2)
            recv_data, address = client.recvfrom(1024)
            if recv_data:
                network_time = struct.unpack('!12I', recv_data)[10]
                AgentLogger.log(AgentLogger.CHECKS,"Network returned raw time from {} is {}".format(NTPserver, str(network_time)))
                network_time -= Ref_time_1970   #network_time is in seconds since 1900, hence subtracting period 1900-1970 to get epoch seconds
                network_timestamp = datetime.fromtimestamp(network_time)
                present_timestamp = datetime.now()
                AgentLogger.log(AgentLogger.CHECKS,"Present timestamp - {} | Network timestamp - {} | half_round_trip - {}".format(repr(present_timestamp), repr(network_timestamp), repr(half_round_trip)))
                offset = int((present_timestamp - network_timestamp).total_seconds()) - half_round_trip
                return True, offset, 'success'   
        except Exception as e:
            AgentLogger.log(AgentLogger.STDERR,'********* Exception occurred while calculating offset value for machine time. May be unable to reach NTP server {0} *********'.format(each))
            traceback.print_exc()
            msg = str(e)
        finally:
            if client:
                client.close()
    return False, offset, msg

def entropy_avail():
    try:
        executorObj = Executor()
        executorObj.setTimeout(30)
        executorObj.setCommand(AgentConstants.ENTROPY_AVAIL_COMMAND)
        executorObj.executeCommand()
        stdout = executorObj.getStdOut()
        entropy_availed = stdout.strip() if stdout else '-1'
        return entropy_availed
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,'************************* Exception occured while calculating entropy availed in the server *************************')
        traceback.print_exc()

def metrics_from_iostat():
    dbusy = didle = readops = writeops = 0
    try:
        str_command = AgentConstants.IOSTAT_COMMAND
        executorObj = Executor()
        executorObj.setLogger(AgentLogger.CHECKS)
        executorObj.setTimeout(10)
        executorObj.setCommand(str_command)
        executorObj.executeCommand()
        command_output = executorObj.getStdOut()
        return_code = executorObj.getReturnCode()
        AgentLogger.debug(AgentLogger.COLLECTOR, 'Command Output ======>' + repr(command_output))
        AgentLogger.debug(AgentLogger.COLLECTOR, 'Return Code ======>' + repr(executorObj.getReturnCode()))
        command_error  = getModifiedString(executorObj.getStdErr(), 100, 100)
        if return_code!=0 and command_error:
            AgentLogger.log(AgentLogger.COLLECTOR, 'Command Error Output 1 ======>' + repr(command_error))
        if command_output:
            output_list = command_output.split('\n')
            disk_io_utilised,disk_in_use,readops,writeops,avg_queue_len = 0,0,0,0,0
            util_index, readops_index, writeops_index, aql_index = -1, 1, 7, -2
            for each in output_list:
                if each:
                    each_line_list = each.split()
                    if each.startswith(('Linux', 'Device', 'loop', 'device', 'extended')):
                        if 'Device' in each or 'device' in each:
                            try: util_index = each_line_list.index("%util")
                            except: pass
                            try: readops_index = each_line_list.index("r/s")
                            except: pass
                            try: writeops_index = each_line_list.index("w/s")
                            except: pass
                            try: aql_index = each_line_list.index("aqu-sz")
                            except: pass
                        continue
                    util_value = each_line_list[util_index]
                    readops += custom_float(each_line_list[readops_index])  #refer: https://www.howtouselinux.com/post/check-disk-iops-in-linux
                    writeops += custom_float(each_line_list[writeops_index])
                    avg_queue_len += custom_float(each_line_list[aql_index])
                    if not util_value == '0.00' and not util_value == '0':
                        disk_in_use += 1 
                    disk_io_utilised += custom_float(util_value)
            if disk_in_use != 0:
                disk_io_utilised = disk_io_utilised / disk_in_use
            dbusy = disk_io_utilised
            didle = 100-disk_io_utilised
            readops = str(round(readops, 2))    #per sec
            writeops = str(round(writeops, 2))
    except:
        AgentLogger.log(AgentLogger.STDERR,'************************* Exception occured while getting dbusy, didle, readops, writeops *************************')
        traceback.print_exc()
    finally:
        return dbusy, didle, readops, writeops, avg_queue_len

#float converter for French locale
def custom_float(string):
    if isinstance(string, str):
        string = string.replace(',','.')
    return float(string)

#returns True if port is busy
def port_open_check(port):
    bool_status = False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        status = sock.connect_ex((AgentConstants.PORT_MONITOR_SERVER_IP, port))
        if status == 0:
           bool_status = True
    except:
        AgentLogger.log(AgentLogger.STDERR, "************************* Unable to check port listening status *************************")
        traceback.print_exc()
    finally:
        return bool_status

def count_dir_file(path, option, pattern = ''):
    count = 0
    try:
        for dirpath, dirname, filename in os.walk(path):
            if option == 'file':
                if pattern in filename:
                    count = count + len(filename)
            if option == 'dir':
                if pattern in dirname:
                    count = count + len(dirname)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR, "************************* Unable to count file/dir *************************")
        traceback.print_exc()
    finally:
        return str(count)

def unschedule_task(task, scheduler='AgentScheduler'):
    try:
        from com.manageengine.monagent.scheduler import AgentScheduler
        scheduleInfo = AgentScheduler.ScheduleInfo()
        scheduleInfo.setSchedulerName(scheduler)
        scheduleInfo.setTaskName(task)
        AgentScheduler.deleteSchedule(scheduleInfo)
        AgentLogger.log(AgentLogger.MAIN, "Unscheduling the task {} from running schedule".format(task))
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR, "************************* Unable to unschedule [{0}]:[{1}] *************************".format(scheduler, task))
        traceback.print_exc()

def edit_monitorsgroup(monitor, action):
    """
    Edit the monitorsgroup.json file to enable or disable a monitor.
    
    Args:
        monitor (str): The name of the monitor to enable or disable.
        action (str): The action to perform, either 'enable' or 'disable'.
    """
    try:
        if action == 'enable':
            value = 'true'
        elif action == 'disable': 
            value = 'false'
        else:
            raise ValueError("Invalid action")
        
        from com.manageengine.monagent.collector.DataCollector import COLLECTOR, COLLECTOR_IMPL
        #seperate read and write else new and old contents gets mixed
        with open(AgentConstants.AGENT_MONITORS_GROUP_FILE, 'r') as f:
            monitorsgroup_dict = json.loads(f.read())
        
        if monitor in monitorsgroup_dict['MonitorGroup'] and monitorsgroup_dict['MonitorGroup'][monitor]['Schedule'] != value:
            if value == 'false':
                unschedule_task(monitor)
                
            with open(AgentConstants.AGENT_MONITORS_GROUP_FILE, 'w') as f:
                monitorsgroup_dict['MonitorGroup'][monitor]['Schedule'] = value
                f.write(json.dumps(monitorsgroup_dict))

            #FIXME: Instead of rescheduling all monitors, only modified monitors needs to re-scheduled.
            COLLECTOR.loadMonitors()
            if COLLECTOR_IMPL != None:
                COLLECTOR.scheduleDataCollection(True)
            AgentLogger.log(AgentLogger.MAIN, "{} monitor {}d in monitorsgroup.json".format(monitor, action))
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR, "************************* Unable to {0} monitor [{1}] *************************".format(monitor))
        traceback.print_exc()

#change task of monitorsgroup interval 
def ChangeTaskInterval(taskName, pollInterval):
    from com.manageengine.monagent.collector import DataCollector
    try:
        if taskName in DataCollector.SCHEDULED_THREAD_DICT:
            prevInterval = str(DataCollector.SCHEDULED_THREAD_DICT[taskName].getInterval())
            DataCollector.SCHEDULED_THREAD_DICT[taskName].setInterval(int(pollInterval))
        fileObj = FileObject()
        fileObj.set_filePath(AgentConstants.AGENT_MONITORS_GROUP_FILE)
        fileObj.set_dataType('json')
        fileObj.set_mode('rb')
        fileObj.set_dataEncoding('UTF-8')
        fileObj.set_loggerName(AgentLogger.COLLECTOR)
        fileObj.set_logging(False)
        bool_toReturn, dictMonitors = FileUtil.readData(fileObj)
        dictMonitors['MonitorGroup'][taskName]['Interval'] = pollInterval
        AgentLogger.log(AgentLogger.MAIN,' updated monitoring configuraton -- '+repr(dictMonitors)+'\n')
        fileObj.set_data(dictMonitors)
        fileObj.set_mode('wb')
        bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
        AgentLogger.log(AgentLogger.MAIN,'Updating interval of {0} from {1} to {2}\n'.format(taskName, prevInterval, pollInterval))
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,' ************************** Exception while updating {} interval **************************** '.format(taskName))
        traceback.print_exc()

def change_agentlog_level(loglevel = '3'):
    try:
        if loglevel == '1':
            params = "-debug_on"
        elif loglevel == '3':
            params = "-debug_off"
        command = " ".join([AgentConstants.AGENTMANAGER_FILE, params])
        isSuccess, str_output = executeCommand(command)
    except:
        AgentLogger.log(AgentLogger.STDERR,' ************************** Exception while changing agent loglevel to {} **************************** '.format(loglevel))
        traceback.print_exc()

def check_dc_bottlenecks():
    try:
        #partition read only check
        isSuccess, str_output = executeCommand(AgentConstants.PROC_MOUNT_COMMAND)
        if str_output:
            lines = str_output.split('\n')[:-1]
            for each in lines:
                mount_info = each.split()
                if mount_info and mount_info[1]=='/':
                    if mount_info[3].startswith('ro'):
                        AgentLogger.log(AgentLogger.MAIN,'File system "/" is in read only mode - {}\n'.format(mount_info))
                        AgentConstants.error_in_server['100']="file system '/' changed to read only mode"
                    else:
                        AgentConstants.error_in_server.pop("100", None)
                    break
        
        # agent partition full check
        isSuccess, str_output = executeCommand(AgentConstants.AGENT_PARTITION_UTIL_CMD)
        if str_output:
            str_output = str_output.strip()
            if float(str_output) < 300:
                partition_exceeded_error = "Agent partition have less than 300MB of disk space | size available: {}".format(str_output)
                AgentConstants.error_in_server['101'] = partition_exceeded_error
                AgentLogger.log(AgentLogger.MAIN,partition_exceeded_error)
                AgentLogger.log(AgentLogger.MAIN,'Agent logger stopped')
                AgentConstants.STOP_LOGGING = True
            else:
                AgentConstants.STOP_LOGGING = False
                AgentConstants.error_in_server.pop("101", None)

    except Exception as e:
        traceback.print_exc()

def getTimeInMillis(float_timeInMillis = None, timeDiff = None):
    ''' With time_diff by default '''
    
    toReturn = None
    try:
        if float_timeInMillis and timeDiff:
            toReturn = round(float(float_timeInMillis)+float(timeDiff))
        elif float_timeInMillis:
            toReturn = round(float(float_timeInMillis)+float(AGENT_CONFIG.get('AGENT_INFO', 'time_diff')))
        else:
            toReturn = round((time.time()*1000)+float(AGENT_CONFIG.get('AGENT_INFO', 'time_diff')))
        AgentLogger.debug(AgentLogger.STDOUT,'Time in millis returned : '+repr(toReturn)+' ----> '+repr(getFormattedTime(toReturn)))
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while calculating time based on time diff ************************* '+ repr(e))
        traceback.print_exc()      
        toReturn = round(time.time()*1000)
    finally:
        if not toReturn is None:
            toReturn = int(toReturn)
    return toReturn

def getCurrentTimeInMillis(float_timeInMillis = None, timeDiff = None):
    ''' Without time_diff by default '''
    toReturn = None
    try:
        if float_timeInMillis and timeDiff:
            toReturn = round(float(float_timeInMillis)-float(timeDiff))
        elif float_timeInMillis:
            toReturn = round(float(float_timeInMillis)-float(AGENT_CONFIG.get('AGENT_INFO', 'time_diff')))
        else:
            toReturn = round(time.time()*1000)
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while calculating current time based on time diff ************************* '+ repr(e))
        traceback.print_exc()      
        toReturn = round(time.time()*1000)
    finally:
        if not toReturn is None:
            toReturn = int(toReturn)
    return toReturn

def getFormattedTime(timeInMillis):
    try:
        return time.asctime(time.localtime(float(timeInMillis)/1000))
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT, "exponential exception {}".format(e))
        timeInMillis = float(timeInMillis)/1000
        return time.asctime(time.localtime(float(timeInMillis)/1000))

def getUniqueId():
    import random
    int_uniqueId = 0
    try:    
        int_uniqueId = int(str(random.randint(1,9))+str(getCurrentTimeInMillis())+str(random.randint(10,99)))
        AgentLogger.log(AgentLogger.STDOUT,'UNIQUE ID GENERATED : '+repr(int_uniqueId))
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while generating unique Id ************************* '+ repr(e))
        traceback.print_exc()      
        int_uniqueId = 0
    return int_uniqueId

def construct_auid():
    import random
    str_uniqueId = "-1"
    try:    
        str_uniqueId = str(getCurrentTimeInMillis())+str(random.randint(10,99))
        AgentLogger.log(AgentLogger.STDOUT,'AUID GENERATED : '+repr(str_uniqueId))
        fileObj = FileObject()
        fileObj.set_filePath(AgentConstants.AUID_FILE)
        fileObj.set_data(str_uniqueId)
        fileObj.set_loggerName(AgentLogger.STDOUT)
        FileUtil.saveData(fileObj)
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while generating unique Id ************************* '+ repr(e))
        traceback.print_exc()      
        str_uniqueId = "-1"
    return str_uniqueId

def get_default_param(upload_point_props,request_params,zipname_or_action):
    try:
        for each_param in upload_point_props['param']:
            if each_param[0] == 'APPNAME':
                request_params['APPNAME'] = each_param[1]
            if each_param[0] == 'AGENT':
                request_params['AGENT'] = each_param[1]
            if each_param[0] == 'AGENTUNIQUEID':
                request_params['AGENTUNIQUEID'] = AGENT_CONFIG.get('AGENT_INFO', 'agent_unique_id')
            if each_param[0] in ['AGENTKEY', 'agentKey', 'agentkey']:
                request_params[each_param[0]] = AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
            if each_param[0] == 'bno':
                request_params['bno'] = AgentConstants.AGENT_VERSION
            if each_param[0] in ['action', 'type', 'FILENAME']:
                request_params[each_param[0]] = zipname_or_action
            if each_param[0] == 'zipname':
                request_params['zipname'] = zipname_or_action.split('/').pop()
            if each_param[0] in ['CUSTOMERID', 'apikey', 'custID']:
                request_params[each_param[0]] = AgentConstants.CUSTOMER_ID
            if each_param[0] in ['timeStamp', 'LASTUPDATETIME', 'dc']:
                request_params[each_param[0]] = getCurrentTimeInMillis()
            if each_param[0] == 'auid':
                request_params['auid'] = AgentConstants.AUID
            if each_param[0] == 'auid_old':
                request_params['auid_old'] = AgentConstants.AUID_OLD
            if each_param[0] == 'sct':
                request_params['sct'] = getTimeInMillis()
            if each_param[0] == 'ZIPS_IN_BUFFER':
                request_params['ZIPS_IN_BUFFER'] = upload_point_props['zips_in_buffer']
            if each_param[0] == 'installer':
                if AGENT_CONFIG.has_option('AGENT_INFO','installer') and not AGENT_CONFIG.get('AGENT_INFO','installer')=='0':
                    request_params['installer'] = AGENT_CONFIG.get('AGENT_INFO','installer')
        return request_params
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while generating default request param ************************* '+ repr(e))
        traceback.print_exc()

def getAgentUpgradeStatusMsg():
    upgrade_msg=None
    try:
        if os.path.exists(AgentConstants.AGENT_UPGRADE_STATUS_MSG_FILE):
            with open(AgentConstants.AGENT_UPGRADE_STATUS_MSG_FILE,'r') as fp:
                upgrade_msg = fp.read()
            AgentLogger.log(AgentLogger.MAIN,'Agent Upgrade Status Message :: {}'.format(upgrade_msg))
        else:
            upgrade_msg = "upgrade status msg file not found"
    except Exception as e:
        AgentLogger.log([AgentLogger.MAIN,AgentLogger.STDERR],' ************************* Exception while reading agent upgrade status msg file ************************* '+ repr(e))
        traceback.print_exc()
    finally:
        return str(upgrade_msg)

def writeMonagentUpgMsg(str_fileName,message=None):
    try:
        if message:
            with open(str_fileName,'w') as fp:
                fp.write(message)
    except Exception as e:
        AgentLogger.log([AgentLogger.STDERR],' ************************* Exception while writing monagent agent upgrade status msg ************************* '+ repr(e))
        traceback.print_exc()

def get_gcd(numeric_list):
    gcd = None
    try:
        g = lambda a,b:a if b==0 else g(b,a%b)
        gcd = functools.reduce(lambda x,y:g(x,y),numeric_list)
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.CRITICAL],' ************************* Exception while calculating GDC ************************* :: {}'.format(e))
        traceback.print_exc()
    finally:
        return gcd

class ZipUploaderObject(object):
    group_dir_path = None
    zips_in_group = None
    zip_files_path_list = None
    def __init__(self):
        self.zip_path = None
        self.zips_in_group = None
        self.zip_files_path_list = None

    def setZipsInGroupedDir(self,zip_in_group_count):
        self.zips_in_group = int(zip_in_group_count)

    def getZipsInGroupedDir(self):
        return self.zips_in_group

    def setGroupedZipDirPath(self,group_dir_path):
        self.group_dir_path = str(group_dir_path)

    def getGroupedZipDirPath(self):
        return self.group_dir_path

    def setZipFilesPathInGroup(self,zip_files_path_list):
        self.zip_files_path_list = zip_files_path_list

    def getZipFilesPathInGroup(self):
        return self.zip_files_path_list

class ZipCycleHandler(threading.Thread):
    cycle_min_timer = 0
    hold_instant_zipper_lock = None
    hold_cycle_zipper_lock = None
    def __init__(self):
        threading.Thread.__init__(self)
        self.task_name = 'File Zip Cycle'
        self.cycle_min_timer = 0
        self.hold_instant_zipper_lock = False
        self.hold_cycle_zipper_lock = True

    def updateFailedZipsInBuffer(self):
        try:
            for zips in os.listdir(AgentConstants.AGENT_UPLOAD_DIR):
                upload_file_path = os.path.join(AgentConstants.AGENT_UPLOAD_DIR, zips)
                try:
                    if os.path.isfile(upload_file_path):
                        AgentLogger.log(AgentLogger.STDOUT,'Deleting the zip file outside specific folder -- {}'.format(upload_file_path))
                        os.remove(upload_file_path)
                except Exception as e:
                    traceback.print_exc()
            for files in os.listdir(AgentConstants.AGENT_DATA_DIR):
                data_file_path = os.path.join(AgentConstants.AGENT_UPLOAD_DIR, files)
                try:
                    if os.path.isfile(data_file_path):
                        AgentLogger.log(AgentLogger.STDOUT,'Deleting the data file outside specific folder -- {}'.format(data_file_path))
                        os.remove(data_file_path)
                except Exception as e:
                    traceback.print_exc()
            AgentLogger.log(AgentLogger.STDOUT,'===================================== ADDING FAILED ZIPS TO BUFFER =====================================')
            for dir, dir_props in AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER.items():
                if dir_props['content_type'] != 'application/json':
                    current_node_buffer = dir_props['buffer']
                    current_node_zip_path = dir_props['zip_path']
                    current_node_zips_count = 0
                    if (os.path.exists(current_node_zip_path)):
                        grouped_dir_list = sorted(os.listdir(current_node_zip_path),reverse=False)
                        while len(grouped_dir_list) > 0:
                            zip_file_path_list = []
                            grouped_dir = grouped_dir_list.pop(0)
                            grouped_dir_path = current_node_zip_path + '/' + grouped_dir
                            if "no_backlog" in dir_props and dir_props["no_backlog"] == True:
                                for zip_file in os.listdir(grouped_dir_path):
                                    AgentLogger.log(AgentLogger.STDOUT, 'Deleting the zip file ['+grouped_dir_path+'/'+ zip_file +'] due to no_backlog \n')
                                    os.remove(os.path.join(grouped_dir_path,zip_file))
                                os.rmdir(grouped_dir_path)
                            else:
                                for zip_file in os.listdir(grouped_dir_path):
                                    if zip_file.endswith('.zip'):
                                        zip_file_path_list.append(grouped_dir_path + '/' + zip_file)
                                        current_node_zips_count += 1
                                group_dir_object = ZipUploaderObject()
                                group_dir_object.setZipsInGroupedDir(len(zip_file_path_list))
                                group_dir_object.setGroupedZipDirPath(grouped_dir_path)
                                group_dir_object.setZipFilesPathInGroup(zip_file_path_list)
                                current_node_buffer[1].append(group_dir_object)
                        dir_props['zips_in_buffer'] = current_node_zips_count
                        dir_props['buffer'] = current_node_buffer
                        AgentLogger.log([AgentLogger.STDOUT],'======= [{}] Zips added to [{}] failed buffer list :: Grouped Object Count [{}] ======='.format(current_node_zips_count, dir, len(AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[dir]['buffer'][1])))

        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while adding failed zips in buffer ************************* :: {}'.format(e))
            traceback.print_exc()

    def getZipCycleInterval(self):
        interval = None
        try:
            upload_zip_interval_list = []
            for dir, dir_props in AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER.items():
                if not dir_props['instant_zip']:
                    upload_zip_interval_list.append(int(dir_props['zip_interval']))
            interval = get_gcd(upload_zip_interval_list)
            interval = 1 if not interval else interval
            if interval != self.cycle_min_timer:
                for dir, dir_props in AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER.items():
                    if not dir_props['instant_zip']:
                        dir_props['zip_modulo'] = interval
            return interval
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while getting Zip Cycle Interval ************************* :: {}'.format(e))
            traceback.print_exc()

    def updateZipCycleInterval(self,dir_prop, new_interval):
        try:
            dir_prop['zip_interval'] = new_interval
            self.cycle_min_timer = self.getZipCycleInterval()
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while updating Upload Cycle Interval for [{}] - New Value [{}] ************************* :: {} '.format(dir_prop['code'],new_interval,e))
            traceback.print_exc()

    def zipCycleIntervalCheck(self,dir_prop):
        do_zip = False
        try:
            if dir_prop['instant_zip']:
                do_zip = False
            else:
                zip_interval = dir_prop['zip_interval']
                zip_modulo = dir_prop['zip_modulo']
                if int(zip_modulo) == int(zip_interval):
                    do_zip = True
                    dir_prop['zip_modulo'] = int(self.cycle_min_timer)
                else:
                    dir_prop['zip_modulo'] = int(zip_modulo) + int(self.cycle_min_timer)
            return do_zip
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while checking zip cycle time *************************:: {}'.format(e))
            traceback.print_exc()


    def getZipFileName(self,dir_props,file_number=None):
        zipName = None
        try:
            if AgentConstants.ZIP_POSTED >= 10000:
                AgentConstants.ZIP_POSTED = 0
            AgentConstants.ZIP_POSTED = AgentConstants.ZIP_POSTED + 1
            if dir_props['code'] == '001':
                return 'Agent_'+str(AGENT_CONFIG.get('AGENT_INFO', 'agent_key'))+'_'+'Upload_' +str(getTimeInMillis())+'.zip'
            elif dir_props['code'] == '002':
                return 'Plugins_'+str(AGENT_CONFIG.get('AGENT_INFO', 'agent_key'))+'_'+str(getTimeInMillis())+'.zip'
            elif dir_props['code'] == '003':
                return 'Agent_'+str(AGENT_CONFIG.get('AGENT_INFO', 'agent_key'))+'_'+'Application_'+str(file_number)+'_'+str(getTimeInMillis())+'.zip'
            elif dir_props['code'] == '004':
                return 'Agent_'+str(AGENT_CONFIG.get('AGENT_INFO', 'agent_key'))+'_'+'Statistics_'+str(getTimeInMillis())+'.zip'
            elif dir_props['code'] == '012':
                return 'Database_'+str(AGENT_CONFIG.get('AGENT_INFO', 'agent_key'))+'_'+str(getTimeInMillis())+'_'+str(AgentConstants.ZIP_POSTED)+'.zip'
            elif dir_props['code'] in ['005', '006', '007', '008', '009', '010','017', '020']:
                return 'Agent_'+str(AGENT_CONFIG.get('AGENT_INFO', 'agent_key'))+'_'+'Application_'+str(getTimeInMillis())+'.zip'
            elif dir_props['code'] in ['015','016']:
                return 'Agent_'+str(AGENT_CONFIG.get('AGENT_INFO', 'agent_key'))+'_addm_'+str(getTimeInMillis())+'.zip'
            else:
                return 'Agent_'+str(AGENT_CONFIG.get('AGENT_INFO', 'agent_key'))+'_'+'Application_'+str(getTimeInMillis())+'.zip'

        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while getting zip file name [{}] ************************* '+ repr(dir_props['name']))
            traceback.print_exc()

    def zipFilesAtInstance(self,listOfFileListToZip, dir_props, file_number=None):
        try:
            self.hold_instant_zipper_lock = True
            if self.hold_cycle_zipper_lock:
                while (self.hold_cycle_zipper_lock):
                    time.sleep(1)

            zip_file_list = []
            file_number = 0
            current_node_buffer = dir_props['buffer']
            groupDataDirName = str(getTimeInMillis())
            zip_dir_path = dir_props['zip_path']
            if not os.path.exists(zip_dir_path):
                os.makedirs(zip_dir_path)
            data_dir_path = dir_props['data_path']
            group_dir_path = zip_dir_path + '/' + groupDataDirName
            os.makedirs(group_dir_path)

            AgentLogger.log(AgentLogger.STDOUT,'===================================== ZIPPING FILES INSTANTLY IN DATA DIRECTORY [{}::{}] ====================================='.format(dir_props['code'],group_dir_path))
            for file_list_to_zip in listOfFileListToZip:
                for file_name in file_list_to_zip:
                    file_number = file_number + 1
                    zipFileName = self.getZipFileName(dir_props,file_number)
                    zipFilePath = group_dir_path + '/' + zipFileName
                    zip_fileObj = zipfile.ZipFile(zipFilePath, 'w')
                    dataFilePath = os.path.join(data_dir_path + '/' + file_name)
                    try:
                        if os.path.isfile(dataFilePath):
                            zip_fileObj.write(dataFilePath,'data/'+dataFilePath, zipfile.ZIP_DEFLATED)
                            AgentLogger.log(AgentLogger.STDOUT,'File added to zip : ' + str(dataFilePath))
                            os.remove(dataFilePath)
                        else:
                            AgentLogger.log(AgentLogger.STDOUT,'File not added to zip : ' + str(dataFilePath))
                    except Exception as e:
                        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while writing the file : '+repr(dataFilePath)+' to the zip file '+repr(zipFileName)+' ************************* '+repr(e))
                        traceback.print_exc()
                    AgentLogger.log(AgentLogger.STDOUT,'============== [{}] added to zip :: [{}] =============='.format(file_name,zipFilePath))
                    zip_file_list.append(zipFilePath)
            group_dir_object = ZipUploaderObject()
            group_dir_object.setZipsInGroupedDir(len(zip_file_list))
            group_dir_object.setGroupedZipDirPath(group_dir_path)
            group_dir_object.setZipFilesPathInGroup(zip_file_list)
            current_node_buffer[0].append(group_dir_object)
            dir_props['zips_in_buffer'] += len(zip_file_list)
            dir_props['buffer'] = current_node_buffer
            AgentLogger.log(AgentLogger.STDOUT,'==================== [{}-{}] - [Zips in Group : {}] [Zips in Buffer : {}] ===================='.format(dir_props['code'],dir_props['name'],len(zip_file_list),dir_props['zips_in_buffer']))

        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while adding zip insitantly to Upload Dir [{}] ************************* '+ repr(dir_props['code']))
            traceback.print_exc()
        finally:
            self.hold_instant_zipper_lock = False

    def zipFilesToUpload(self,listOfFileListToZip, dir_props):
        try:
            zip_file_list = []
            current_node_buffer = dir_props['buffer']
            groupDataDirName = str(getTimeInMillis())
            zip_dir_path = dir_props['zip_path']
            if not os.path.exists(zip_dir_path):
                os.makedirs(zip_dir_path)
            data_dir_path = dir_props['data_path']
            group_dir_path = zip_dir_path + '/' + groupDataDirName
            os.makedirs(group_dir_path)

            AgentLogger.log(AgentLogger.STDOUT,'===================================== ZIPPING FILES IN DATA DIRECTORY [{}::{}] ====================================='.format(dir_props['code'],group_dir_path))
            for file_list_to_zip in listOfFileListToZip:
                int_noOfFilesAddedToZip = 0
                zipFileName = self.getZipFileName(dir_props)
                zipFilePath = group_dir_path + '/' + zipFileName
                zip_fileObj = zipfile.ZipFile(zipFilePath, 'w')
                for dataFile in file_list_to_zip:
                    dataFilePath = os.path.join(data_dir_path + '/' + dataFile)
                    if "file_size" in dir_props and os.path.isfile(dataFilePath):
                        if os.path.getsize(dataFilePath) > int(dir_props["file_size"]):
                            os.remove(dataFilePath)
                            AgentLogger.log(AgentLogger.STDOUT,'***** File Size Limit exceeded [{}] - [{}], Skiping and Deleting file *****'.format(dir_props["code"],str(dataFilePath)))
                            continue
                    try:
                        if os.path.isfile(dataFilePath):
                            zip_fileObj.write(dataFilePath,'data/'+dataFile, zipfile.ZIP_DEFLATED)
                            AgentLogger.log(AgentLogger.STDOUT,'File added to zip : ' + str(dataFilePath))
                            int_noOfFilesAddedToZip+=1
                            os.remove(dataFilePath)
                    except Exception as e:
                        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while writing the file : '+repr(dataFilePath)+' to the zip file '+repr(zipFileName)+' ************************* '+repr(e))
                        traceback.print_exc()
                AgentLogger.log(AgentLogger.STDOUT,'============== [{}] Number of Files added to zip :: [{}] =============='.format(len(file_list_to_zip),zipFilePath))
                zip_file_list.append(zipFilePath)
            group_dir_object = ZipUploaderObject()
            group_dir_object.setZipsInGroupedDir(len(zip_file_list))
            group_dir_object.setGroupedZipDirPath(group_dir_path)
            group_dir_object.setZipFilesPathInGroup(zip_file_list)
            current_node_buffer[0].append(group_dir_object)
            dir_props['zips_in_buffer'] += len(zip_file_list)
            dir_props['buffer'] = current_node_buffer
            AgentLogger.log(AgentLogger.STDOUT,'==================== [{}-{}] - [Zips in Group : {}] [Zips in Buffer : {}] ===================='.format(dir_props['code'],dir_props['name'],len(zip_file_list),dir_props['zips_in_buffer']))

        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while adding zip to Upload Dir [{}] ************************* '+ format(dir_props['code']))
            traceback.print_exc()

    def zipFilesInDataDirCycle(self):
        dataDirFileList = []
        listOfFileListToZip = []
        try:
            for dir,dir_prop in AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER.items():
                if self.hold_instant_zipper_lock:
                    self.hold_cycle_zipper_lock = False
                    while(self.hold_instant_zipper_lock):
                        time.sleep(1)
                data_dir_path = dir_prop['data_path']
                files_per_zip_count = dir_prop['files_in_zip']
                if self.zipCycleIntervalCheck(dir_prop):
                    dataDirFileList = os.listdir(data_dir_path)
                    if len(dataDirFileList) > 0:
                        listOfFileListToZip = list_chunks(dataDirFileList,files_per_zip_count)
                        self.zipFilesToUpload(listOfFileListToZip,dir_prop)

        except Exception as e:
            AgentLogger.log([AgentLogger.MAIN,AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while getting Zip Cycle Interval ************************* '+ repr(e))
            traceback.print_exc()

    def run(self):
        current_cycle_interval = None
        try:
            self.cycle_min_timer = self.getZipCycleInterval()
            current_cycle_interval = self.cycle_min_timer
            self.updateFailedZipsInBuffer()
            while not TERMINATE_AGENT:
                self.cycle_min_timer = self.getZipCycleInterval()
                if current_cycle_interval != self.cycle_min_timer:
                    current_cycle_interval = self.cycle_min_timer
                    AgentLogger.log(AgentLogger.STDOUT, "========= New Zip Cycle Interval - {} ===========".format(self.cycle_min_timer))
                self.hold_cycle_zipper_lock = True
                self.zipFilesInDataDirCycle()
                self.hold_cycle_zipper_lock = False
                time.sleep(self.cycle_min_timer)
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],' ************************* Exception while starting ZipCycleHandler ************************* '+ repr(e))
            traceback.print_exc()

'''
class ZipHandler(DesignUtils.Singleton):
    __zipId = 0
    __zipIdCounterLock = threading.Lock()
    __zipProcessLock = threading.Lock()
    def __init__(self):
        pass
    def getUniqueZipId(self):
        with ZipHandler.__zipIdCounterLock:
            ZipHandler.__zipId+=1
            if ZipHandler.__zipId - int(AGENT_PARAMS['AGENT_ZIP_ID']) >= 100:
                AGENT_PARAMS['AGENT_ZIP_ID'] = str(ZipHandler.__zipId)
                persistAgentParams()
            return ZipHandler.__zipId
    def setZipId(self, int_id):
        ZipHandler.__zipId = int_id
    def getUniqueZipFileName(self,var_agentKey,str_customName=None):
        if str_customName:
            return 'Agent_'+str(var_agentKey)+'_'+str(str_customName)+'.zip'
        else:
            return 'Agent_'+str(var_agentKey)+'_'+str(self.getUniqueZipId())+'.zip'
    def getUniquePluginZipFileName(self,var_agentKey,str_customName=None):
        if str_customName:
            return 'Plugins_'+str(var_agentKey)+'_'+str(str_customName)+'_'+str(self.getUniqueZipId())+'.zip'
        else:
            return 'Plugins_'+str(var_agentKey)+'_'+str(self.getUniqueZipId())+'.zip'
    # A Method to zip files in buffer
    # Each zip file has a max of 1000 files - This param is configurable
    # A call to this method will create a max of 30 zip files
    def zipFilesInBuffer(self):
        Max_Zip_Files_To_Be_Created = 30
        bool_toReturn = True        
        bool_isBufferEmpty = False
        #buffer_filesToZip = None
        buffer_ZipInfoObjects = None
        int_sizeOfInfoBuffer = 0
        int_noOfZipFiles = 0        
        MAX_FILES_IN_ZIP = 0
        try:
            #buffer_filesToZip = AgentBuffer.getBuffer('FILES_TO_ZIP_BUFFER')
            buffer_ZipInfoObjects = AgentBuffer.getBuffer('FILES_TO_ZIP_BUFFER')
            buffer_filesToUpload = AgentBuffer.getBuffer('FILES_TO_UPLOAD_BUFFER')
            #int_sizeOfBuffer = buffer_filesToZip.size()
            int_sizeOfInfoBuffer = buffer_ZipInfoObjects.size()
            if int_sizeOfInfoBuffer > 0:
                with ZipHandler.__zipProcessLock:
                    AgentLogger.log(AgentLogger.STDOUT,'================================= ZIPPING FILES IN BUFFER =================================')
                    AgentLogger.debug(AgentLogger.STDOUT,'Obtained zip lock')
                    #MAX_FILES_IN_ZIP = len(com.manageengine.monagent.collector.DataCollector.COLLECTOR.getMonitors())-1 if not com.manageengine.monagent.collector.DataCollector.COLLECTOR.getMonitors() is None else 1
                    while not bool_isBufferEmpty and int_sizeOfInfoBuffer > 0 and int_noOfZipFiles < Max_Zip_Files_To_Be_Created and not TERMINATE_AGENT: # Temporary hack to ensure that this loop is not infinite in zipping                
                        int_noOfFilesAddedToZip = 0
                        zipFileName = None
                        zip_fileObj = None
                        bool_isZippingSuccess = True                
                        try:
                            #while int_noOfFilesAddedToZip < MAX_FILES_IN_ZIP and not TERMINATE_AGENT: # This loop will break when buffer is empty or maximum file count in a zip is reached                
                            fileName = None
                            str_fileToZipPath = None 
                            if buffer_ZipInfoObjects.size() > 0:
                                zipAndUploadInfo = FileZipAndUploadInfo()
                                zipAndUploadInfo = buffer_ZipInfoObjects.pop() 
                                list_fileNames = zipAndUploadInfo.filesToZip 
                                #list_fileNames = buffer_filesToZip.pop()  
                                int_sizeOfInfoBuffer-=1
                                if ((list_fileNames) and (len(list_fileNames) > 0)):
                                    #zipFileName = AgentConstants.AGENT_UPLOAD_DIR+'/'+self.getUniqueZipFileName(AGENT_CONFIG.get('AGENT_INFO', 'agent_key'), getTimeInMillis())
                                    zipFileName = zipAndUploadInfo.zipFilePath
                                    zip_fileObj = zipfile.ZipFile(zipFileName, 'w')   
                                    for fileName in list_fileNames: 
                                        try:                            
                                            str_fileToZipPath = os.path.join(zipAndUploadInfo.str_fileToZipPath,fileName)
                                            if os.path.isfile(str_fileToZipPath):                                
                                                zip_fileObj.write(str_fileToZipPath,'data/'+fileName, zipfile.ZIP_DEFLATED)
                                                AgentLogger.log(AgentLogger.STDOUT,'File added to zip : ' + str(str_fileToZipPath))
                                                int_noOfFilesAddedToZip+=1
                                                os.remove(str_fileToZipPath)
                                        except Exception as e:
                                            AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while writing the file : '+repr(str_fileToZipPath)+' to the zip file '+repr(zipFileName)+' ************************* '+repr(e))
                                            traceback.print_exc()
                                else:
                                    AgentLogger.log(AgentLogger.STDOUT,'No files to zip in the list fetched from buffer : ' + repr(list_fileNames)) 
                            else:
                                AgentLogger.log(AgentLogger.STDOUT,'Buffer is empty, hence no files to zip')
                                bool_isBufferEmpty = True
                                break
                            AgentLogger.debug(AgentLogger.STDOUT,str(int_noOfFilesAddedToZip)+' File(s) added to the zip file : '+ str(zipFileName))
                            # Increment zip file count when zipping is success
                            int_noOfZipFiles+=1
                        except Exception as e:
                            AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while zipping the file : '+str(zipFileName)+' ************************* '+repr(e))
                            traceback.print_exc()
                            bool_isZippingSuccess = False
                        finally:        
                            if not zip_fileObj == None:
                                zip_fileObj.close()
                            if zipFileName is not None and os.path.exists(zipFileName) and not bool_isZippingSuccess:
                                AgentLogger.log(AgentLogger.STDOUT,'Deleting the corrupted zip file :'+str(zipFileName))
                                try:
                                    os.remove(zipFileName)
                                except Exception as e:
                                    AgentLogger.log(AgentLogger.STDOUT,'************************* Exception while deleting the corrupted zip file :'+str(zipFileName)+' *************************')
                                    traceback.print_exc()
                            else:
                                AgentLogger.log([AgentLogger.STDOUT],'Adding the zipanduploadinfo object to upload buffer :'+str(zipAndUploadInfo.zipFileName))
                                buffer_filesToUpload.add(zipAndUploadInfo)
                                AgentLogger.log(AgentLogger.STDOUT,'New object added in the upload buffer with a total of : ' + str(len(buffer_filesToUpload)) + 'zips')
                    AgentLogger.debug(AgentLogger.STDOUT,str(int_noOfZipFiles)+' Zip file(s) created in this zipping process')
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while zipping the files in the buffer : '+repr(buffer_ZipInfoObjects)+' ************************* '+repr(e))
            traceback.print_exc()
            bool_toReturn = False
        finally:
            AgentLogger.debug(AgentLogger.STDOUT,'Released zip lock')
        return bool_toReturn
    # A Method to zip files in data directory
    # Each zip file has a max of 1000 files - This param is configurable
    # A call to this method will create a max of 30 zip files
    def zipFilesInDataDirectory(self):
        Max_Zip_Files_To_Be_Created = 30
        bool_toReturn = True        
        bool_isDirEmpty = False        
        int_noOfZipFiles = 0       
        buffer_filesToZip = None
        MAX_FILES_IN_ZIP = 0         
        try:
            with ZipHandler.__zipProcessLock:
                AgentLogger.log(AgentLogger.STDOUT,'===================================== ZIPPING FILES IN DATA DIRECTORY =====================================')
                AgentLogger.debug(AgentLogger.STDOUT,'Obtained zip lock')
                MAX_FILES_IN_ZIP = len(com.manageengine.monagent.collector.DataCollector.COLLECTOR.getMonitors())-1
                directoryToZip = AgentConstants.AGENT_DATA_DIR
                buffer_filesToZip = AgentBuffer.getBuffer('FILES_TO_ZIP_BUFFER')
                buffer_filesToUpload = AgentBuffer.getBuffer('FILES_TO_UPLOAD_BUFFER')
                list_fileNames = sorted(os.listdir(directoryToZip))
                if len(list_fileNames) == 0:
                    AgentLogger.log(AgentLogger.STDOUT,'Data directory is empty. No files to zip')
                else:
                    while not bool_isDirEmpty and int_noOfZipFiles < Max_Zip_Files_To_Be_Created and not TERMINATE_AGENT: # Temporary hack to ensure that this loop is not infinite in zipping                
                        int_noOfFilesAddedToZip = 0
                        zipFileName = None
                        zip_fileObj = None
                        bool_isZippingSuccess = True                
                        try:                    
                            zipFileName = AgentConstants.AGENT_UPLOAD_DIR+'/'+self.getUniqueZipFileName(AGENT_CONFIG.get('AGENT_INFO', 'agent_key'), getTimeInMillis())
                            str_fileToZipPath = None
                            if len(list_fileNames) >= MAX_FILES_IN_ZIP:
                                zip_fileObj = zipfile.ZipFile(zipFileName, 'w')
                                for fileName in list_fileNames: # This loop will break when directory is empty or maximum file count in a zip is reached
                                    if int_noOfFilesAddedToZip >= MAX_FILES_IN_ZIP:
                                        break
                                    else:                                              
                                        try:                            
                                            str_fileToZipPath = os.path.join(AgentConstants.AGENT_DATA_DIR, fileName)
                                            if os.path.isfile(str_fileToZipPath):                                
                                                zip_fileObj.write(str_fileToZipPath,'data/'+fileName, zipfile.ZIP_DEFLATED)
                                                AgentLogger.log(AgentLogger.STDOUT,'File Added To Zip : ' + str(fileName))
                                                int_noOfFilesAddedToZip+=1
                                                os.remove(str_fileToZipPath)   
                                                if fileName in buffer_filesToZip:                 
                                                    buffer_filesToZip.pop()
                                        except Exception as e:
                                            AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while writing the file : '+str_fileToZipPath+' to the zip file '+zipFileName+' ************************* '+repr(e))
                                            traceback.print_exc()
                            else: # remove previous incomplete data collection set files.
                                try:
                                    for fileName in list_fileNames:
                                        str_fileToZipPath = os.path.join(AgentConstants.AGENT_DATA_DIR, fileName)
                                        if os.path.isfile(str_fileToZipPath):
                                            AgentLogger.log(AgentLogger.STDOUT,'Removing incomplete data collection set file : ' + str(str_fileToZipPath))
                                            os.remove(str_fileToZipPath)
                                            if fileName in buffer_filesToZip:                 
                                                buffer_filesToZip.pop()
                                except Exception as e:
                                    AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while deleting incomplete data collection set files ************************* '+repr(e))
                                    traceback.print_exc()
                            bool_isDirEmpty = True
                            AgentLogger.log(AgentLogger.STDOUT,str(int_noOfFilesAddedToZip)+' File(s) added to the zip file : '+zipFileName)
                            # Increment zip file count when zipping is success
                            int_noOfZipFiles+=1
                        except Exception as e:
                            AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while zipping the file : '+str(zipFileName)+' ************************* '+repr(e))
                            traceback.print_exc()
                            bool_isZippingSuccess = False
                        finally:                    
                            if not zip_fileObj == None:
                                zip_fileObj.close()
                            if zipFileName is not None and os.path.exists(zipFileName) and not bool_isZippingSuccess:
                                AgentLogger.log(AgentLogger.STDOUT,'Deleting The Corrupted Zip File :'+str(zipFileName))
                                try:
                                    os.remove(zipFileName)
                                except Exception as e:
                                    AgentLogger.log(AgentLogger.STDOUT,'************************* Exception while deleting the corrupted Zip File :'+zipFileName+' *************************')
                                    traceback.print_exc()
                            else:
                                AgentLogger.log([AgentLogger.STDOUT],'Adding the following zip file to upload buffer :'+str(zipFileName))
                                buffer_filesToUpload.add(zipFileName)
                    AgentLogger.log(AgentLogger.STDOUT,str(int_noOfZipFiles)+' Zip file(s) created in this zipping process')
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while zipping the files in the data directory ************************* '+repr(e))
            traceback.print_exc()
            bool_toReturn = False
        finally:
            AgentLogger.debug(AgentLogger.STDOUT,'Released zip lock')
        return bool_toReturn
'''

class FileObject:
    def __init__(self):
        self.str_fileName = None
        self.str_filePath = None
        self.data = None
        self.str_dataType = None
        self.str_dataEncoding = None
        self.str_mode = 'w'
        self.str_loggerName = None
        self.bool_changePermission = False
        self.bool_logging = True
        self.bool_forceSave = False
    def set_fileName(self, str_fileName):
        self.str_fileName = str_fileName
    def get_fileName(self):
        return self.str_fileName
    def set_filePath(self, str_filePath):
        self.str_filePath = str_filePath
    def get_filePath(self):
        return self.str_filePath
    def set_data(self, data):
        self.data = data
    def get_data(self):
        return self.data
    def set_dataType(self, str_dataType):
        self.str_dataType = str_dataType
    def get_dataType(self):
        return self.str_dataType
    def set_dataEncoding(self, str_dataEncoding):
        self.str_dataEncoding = str_dataEncoding
    def get_dataEncoding(self):
        return self.str_dataEncoding
    def set_mode(self, str_mode):
        self.str_mode = str_mode
    def get_mode(self):
        return self.str_mode
    def set_logging(self, bool_logging):
        self.bool_logging = bool_logging
    def get_logging(self):
        return self.bool_logging
    def set_loggerName(self, str_loggerName):
        self.str_loggerName = str_loggerName
    def get_loggerName(self):
        return self.str_loggerName
    def set_changePermission(self, bool_changePermission):
        self.bool_changePermission = bool_changePermission
    def get_changePermission(self):
        return self.bool_changePermission
    def set_forceSave(self, bool_value):
        self.bool_forceSave = bool_value
    def get_forceSave(self):
        return self.bool_forceSave

#Create objects of this class and put in zipBuffer and uploadBuffer
class FileZipAndUploadInfo:
    def __init__(self):
        self.filesToZip = None
        self.zipFileName = 'DEFAULT'
        self.uploadServlet = None
        self.uploadRequestParameters = None
        self.zipFilePath = 'DEFAULT'
        self.uploadData = None
        self.isZipFile = None
        self.str_fileToZipPath = AgentConstants.AGENT_DATA_DIR
        self.method = AgentConstants.HTTP_POST
    
    def setZipFileName(self,str_zipFileName):
        self.zipFileName = str_zipFileName
    
    def setUploadMethod(self,strMethod):
        self.method = strMethod 
    
    def getUploadMethod(self):
        return self.method
    
    def setFilesToZip(self,listFilesToZip):
        self.filesToZip = listFilesToZip
    
    def setFileToZipPath(self,str_path):
        self.str_fileToZipPath = str_path
    
    def setUploadServlet(self,str_uploadServlet):
        self.uploadServlet = str_uploadServlet
        
    def setUploadRequestParameters(self,listUploadRequestParameters):
        self.uploadRequestParameters = listUploadRequestParameters
    
    def setZipFilePath(self,str_zipFilePath):
        self.zipFilePath = str_zipFilePath
    
    def setUploadData(self, dataToSend):
        self.uploadData = dataToSend
        
    def getZipFileName(self):
        return self.zipFileName
    
    def getFilesToZip(self):
        return self.filesToZip
    
    def getFilesToZipPath(self):
        return self.str_fileToZipPath
    
    def getUploadServlet(self):
        return self.uploadServlet
    
    def getUploadRequestParameters(self):
        return self.uploadRequestParameters
    
    def getZipFilePath(self):
        return self.zipFilePath

class FileHandler(DesignUtils.Singleton):
    __fileId = 0
    __fileIdCounterLock = threading.Lock()
    def __init__(self):
        pass
    
    def setFileId(self, int_id):
        FileHandler.__fileId = int_id
        
    def getUniqueFileId(self):
        with FileHandler.__fileIdCounterLock:
            FileHandler.__fileId+=1
            if FileHandler.__fileId - int(AGENT_PARAMS['AGENT_FILE_ID']) >= 100:
                AGENT_PARAMS['AGENT_FILE_ID'] = str(FileHandler.__fileId)
                persistAgentParams()
            return FileHandler.__fileId
          
    def getUniqueFileName(self,var_agentKey,str_customName = None, ignoreDefaultName = False):
        if ignoreDefaultName:
            return 'Agent_'+str(str_customName)+'.txt'
        if str_customName:
            return 'Agent_'+str(var_agentKey)+'_'+str(str_customName)+'_'+str(self.getUniqueFileId())+'.txt'
        else:
            return 'Agent_'+str(var_agentKey)+'_'+str(self.getUniqueFileId())+'.txt'
    
    def getUniquePluginFileName(self,var_pluginKey,str_customName = None):
        return 'Plugin_'+str(var_pluginKey)+'_'+str(self.getUniqueFileId())+'.txt'
    
    def getUniquePluginFileName(self,var_pluginKey,str_customName = None):
        if str_customName:
            return 'Plugin_'+str(var_pluginKey)+'_'+str(str_customName)+'_'+str(self.getUniqueFileId())+'.txt'
        else:
            return 'Plugin_'+str(var_pluginKey)+'_'+str(self.getUniqueFileId())+'.txt'

    def getUniqueDatabaseFileName(self,var_agentKey,str_customName = None):
        return str(str_customName)+'_'+str(var_agentKey)+'_'+str(getCurrentTimeInMillis())+'.txt'
    
    def getFileCount(self,directory,filename):
        count = 0
        fileList = os.listdir(directory)
        for file in fileList:
            if filename in file:
                count+=1
        return count
        
            
    # Returns a tuple (bool_isSuccess, str_fileName)
    def saveData(self, fileObj):
        bool_toReturn = True
        file_obj = None
        str_fileName = None
        str_filePath = None
        str_dataType = None
        str_dataEncoding = None
        dataToWrite = None
        dic_DataToWrite = None
        str_loggerName = None
        bool_changePermission = None
        str_mode = None
        bool_logging = True
        bool_forceSave = False
        duplicate_dataToWrite = None
        try:
            if not fileObj.get_forceSave() and  TERMINATE_AGENT:
                return False, None
            str_filePath = fileObj.get_filePath()
            dataToWrite = fileObj.get_data()
            str_dataType = fileObj.get_dataType()
            str_dataEncoding = fileObj.get_dataEncoding()
            str_mode = fileObj.get_mode()
            str_loggerName = fileObj.get_loggerName()
            bool_changePermission = fileObj.get_changePermission()
            bool_logging = fileObj.get_logging()
            duplicate_dataToWrite = copy.deepcopy(dataToWrite)
            if str_dataType == 'json':
                if 'AGENTKEY' in duplicate_dataToWrite:
                    del duplicate_dataToWrite['AGENTKEY']
                if 'dc' in duplicate_dataToWrite:
                    del duplicate_dataToWrite['dc']
                if 'MSPCUSTOMERID' in duplicate_dataToWrite:
                    del duplicate_dataToWrite['MSPCUSTOMERID']
                if 'reason' in duplicate_dataToWrite:
                    del duplicate_dataToWrite['reason']
                if 'avail' in duplicate_dataToWrite:
                    del duplicate_dataToWrite['avail']
                file_obj = codecs.open(str_filePath,str_mode,str_dataEncoding)
                duplicate_dataToWrite = json.dumps(duplicate_dataToWrite)#python dictionary to json string
            elif str_dataType == 'xml':
                file_obj = codecs.open(str_filePath,str_mode,str_dataEncoding)
            else:
                file_obj = open(str_filePath,str_mode)    
            file_obj.write(duplicate_dataToWrite)
        except:
            AgentLogger.log(str_loggerName,'************************* Exception while saving data : '+repr(duplicate_dataToWrite)+' to the file '+str(str_filePath)+' ************************* ')
            traceback.print_exc()
            bool_toReturn = False
        finally:
            if not file_obj == None:
                file_obj.close()
        if bool_toReturn and bool_logging:        
            AgentLogger.log(str_loggerName,'SAVED DATA : ')
            AgentLogger.debug(str_loggerName,'SAVED DATA BEFORE TRIMMING :: {0}'.format(json.dumps(duplicate_dataToWrite)))
            #AgentLogger.log(AgentLogger.MAIN,'\n\nData sent to plus with process :: {0}'.format(json.dumps(json.loads(duplicate_dataToWrite))))
            dataDict = json.loads(duplicate_dataToWrite)
            if 'TOPMEMORYPROCESS' in dataToWrite:
                if 'TOPMEMORYPROCESS' in dataDict:
                    del dataDict['TOPMEMORYPROCESS']
                if 'TOPCPUPROCESS' in dataDict:
                    del dataDict['TOPCPUPROCESS']
                if 'process' in dataDict:
                    del dataDict['process']
            duplicate_dataToWrite=json.dumps(dataDict)
            AgentLogger.log(str_loggerName,' File : '+str(str_filePath))
            AgentLogger.log(str_loggerName,duplicate_dataToWrite)
        return bool_toReturn, str_filePath
    
    def readData(self, fileObj):
        bool_toReturn = True
        file_obj = None
        str_fileName = None
        str_filePath = None
        str_dataType = None
        str_dataEncoding = None
        var_dataToReturn = None
        str_loggerName = None
        bool_changePermission = None
        str_mode = None
        bool_logging = True
        try:
            if TERMINATE_AGENT:
                return False, None
            str_filePath = fileObj.get_filePath()
            str_dataType = fileObj.get_dataType()
            str_dataEncoding = fileObj.get_dataEncoding()
            str_mode = fileObj.get_mode()
            str_loggerName = fileObj.get_loggerName()
            bool_logging = fileObj.get_logging()
            if str_dataType == 'json':
                file_obj = open(str_filePath,str_mode)
                byte_data = file_obj.read()
                unicodeData = byte_data.decode(str_dataEncoding)
                var_dataToReturn = json.loads(unicodeData, object_pairs_hook=collections.OrderedDict)
            else:
                file_obj = open(str_filePath,str_mode)
                var_dataToReturn = file_obj.read()
        except:
            AgentLogger.log(str_loggerName,'************************* Exception while reading data from the file '+str(str_filePath)+' ************************* ')
            traceback.print_exc()
            bool_toReturn = False
        finally:
            if not file_obj == None:
                file_obj.close()
        if bool_toReturn and bool_logging:        
            AgentLogger.log(str_loggerName,'Data read from file : ')
            AgentLogger.log(str_loggerName,repr(var_dataToReturn)+' File : '+str(str_filePath))
        return bool_toReturn, var_dataToReturn
    
    # Sort by time - Returns file list sorted in ascending order
    def getSortedFileList(self, str_dirName, str_loggerName=AgentLogger.STDOUT, sortBy='time'):
        list_fileNames = None
        try:
            list_fileNames = os.listdir(str_dirName)
            list_fileNames = [os.path.join(str_dirName, f) for f in list_fileNames] # add path to each file
            if sortBy == 'time':
                list_fileNames.sort(key=lambda x: os.path.getmtime(x))
            AgentLogger.debug(str_loggerName,'Directory : '+repr(str_dirName)+', Sorted files : ' + repr(list_fileNames))
        except Exception as e:
            AgentLogger.log([str_loggerName,AgentLogger.STDERR], ' *************************** Exception while fetching sorted file list for the directory : '+repr(str_dirName)+', Sort by : '+repr(sortBy)+' *************************** '+ repr(e))
            traceback.print_exc()
        return list_fileNames


    # [
    #  (AGENT_TEMP_RAW_DATA_DIR,['Temp_Raw_Data']),
    #  (AGENT_TEMP_RCA_RAW_DATA_DIR,['Rca_Raw']),
    #  (AGENT_TEMP_RCA_REPORT_DIR,['Rca_Report']),
    #  (AGENT_TEMP_RCA_REPORT_BACKUP_DIR,['Rca_Report']),
    #  (AGENT_TEMP_RCA_REPORT_NETWORK_DIR,['_Rca_Report_Network']),
    #  (AGENT_TEMP_RCA_REPORT_UPLOADED_DIR,['_Rca_Report_Network', 'Rca_Report']),
    #  (AGENT_TEMP_SYS_LOG_DIR,['Agent_'])
    # ]
    def cleanUpFiles(self):
        try:   
            AgentLogger.debug(AgentLogger.STDOUT,'================================= CLEANING TEMP FILES =================================')
            for tuple_folderVsFileList in AgentConstants.FOLDER_VS_CLEAN_UP_FILE_LIST:
                str_cleanUpDirectory = tuple_folderVsFileList[0]
                list_cleanUpFileNames = tuple_folderVsFileList[1]
                bytes_FileSizeThreshold = tuple_folderVsFileList[2]
                for str_cleanUpFileName in list_cleanUpFileNames:
                    list_tempFileNames = []
                    list_fileNames = self.getSortedFileList(str_cleanUpDirectory, str_loggerName=AgentLogger.STDOUT)
                    for filePath in list_fileNames:
                        if str_cleanUpFileName in filePath:
                            list_tempFileNames.append(filePath)
                            #AgentLogger.log(AgentLogger.COLLECTOR,'List of temp files : ' + repr(list_tempFileNames))
                            file_size = os.path.getsize(filePath)
                            if int(file_size) > bytes_FileSizeThreshold:
                                AgentLogger.log(AgentLogger.STDOUT,'File size above threshold limit, deleting the file :: Size(by) {} : Path {} '.format(str(file_size),filePath))
                                list_tempFileNames.pop()
                                self.deleteFile(filePath, AgentLogger.STDOUT)
                            if len(list_tempFileNames) > 10:
                                str_fileToDeletePath = list_tempFileNames.pop(0)
                                self.deleteFile(str_fileToDeletePath, AgentLogger.STDOUT)
        except Exception as e:
            AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR], ' *************************** Exception while deleting temp data collection files *************************** '+ repr(e))
            traceback.print_exc()
            
    def deleteFile(self, str_filePath, str_loggerName=AgentLogger.STDOUT):
        bool_isSuccess = True
        try:
            AgentLogger.log(str_loggerName,'Deleting the file :'+str(str_filePath))
            if str_filePath is not None and os.path.exists(str_filePath):
                os.remove(str_filePath)
            else:
                AgentLogger.log([str_loggerName,AgentLogger.CRITICAL],'Failed to delete the file :'+str(str_filePath))
                bool_isSuccess = False
        except Exception as e:
            AgentLogger.log([str_loggerName,AgentLogger.STDERR],'************************* Exception while deleting the file :'+str(str_filePath)+' *************************')
            traceback.print_exc()
            bool_isSuccess = False
        return bool_isSuccess
    
    def copyFile(self, src, dst):
        bool_isSuccess = True
        try:
            shutil.copy2(src, dst)
        except Exception as e:
            AgentLogger.log(AgentLogger.STDERR,'************************* Exception while copying the file : '+str(src)+' to : '+repr(dst)+' *************************')
            traceback.print_exc()
            bool_isSuccess = False
        return bool_isSuccess

    def copyAndOverwriteFolder(self, src_folder, dest_folder):
        bool_isSuccess = True
        try:
            # Ensure the destination folder exists, create it if it doesn't
            if not os.path.exists(dest_folder):
                os.makedirs(dest_folder)

            # Copy and overwrite the files from the source folder to the destination folder
            for item in os.listdir(src_folder):
                src_item = os.path.join(src_folder, item)
                dest_item = os.path.join(dest_folder, item)

                if os.path.isdir(src_item):
                    # Recursively copy subfolders
                    bool_isSuccess = self.copyAndOverwriteFolder(src_item, dest_item)
                    if bool_isSuccess == False:
                        return bool_isSuccess
                else:
                    # Copy and overwrite files
                    shutil.copy2(src_item, dest_item)
                    AgentLogger.log(AgentLogger.STDOUT, "File '{0}' copied to '{1}' and overwritten.".format(src_item, dest_item))
            AgentLogger.log(AgentLogger.STDOUT, "Folder '{0}' copied to '{1}' and files overwritten successfully.".format(src_folder, dest_folder))
        except Exception as e:
            AgentLogger.log(AgentLogger.STDERR,"************************* Exception while copying the files from : {0} to : {1}' *************************".format(src_folder, dest_folder))
            traceback.print_exc()
            bool_isSuccess = False
        return bool_isSuccess

    def createFile(self, str_filePath, str_loggerName=AgentLogger.STDOUT):
        bool_isSuccess = True
        try:
            AgentLogger.log(str_loggerName,'File Name :'+str(str_filePath))
            if str_filePath is not None and not os.path.exists(str_filePath):
                file_obj=open(str_filePath,'w')
            else:
                AgentLogger.log(str_loggerName,'File Already Exists ----> :'+str(str_filePath))
                bool_isSuccess=False
        except Exception as e:
            AgentLogger.log([str_loggerName,AgentLogger.STDERR],'************************* Exception while creating the file :'+str(str_filePath)+' *************************')
            traceback.print_exc()
            bool_isSuccess = False
        finally:
            if not file_obj == None:
                file_obj.close()
        return bool_isSuccess
    
def startWatchdog():
    try:
        isSuccess, str_output = executeCommand(AgentConstants.AGENT_WATCHDOG_START_COMMAND)
        AgentLogger.log(AgentLogger.MAIN,'Watchdog status after invoking start command : '+repr(str_output))
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,' ************************* Exception while starting watchdog ************************* '+ repr(e))
        traceback.print_exc()

def restartWatchdog():
    try:
        AgentLogger.log(AgentLogger.MAIN,'======================================= RESTARTING WATCHDOG AGENT =======================================')
        isSuccess, str_output = executeCommand(AgentConstants.AGENT_WATCHDOG_RESTART_COMMAND)
        AgentLogger.log(AgentLogger.MAIN,'Watchdog status after invoking restart command : '+repr(str_output))
        if os.path.exists(AgentConstants.AGENT_SILENT_RESTART_FLAG_FILE):
            os.remove(AgentConstants.AGENT_SILENT_RESTART_FLAG_FILE)
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,' ************************* Exception while restarting watchdog ************************* '+ repr(e))
        traceback.print_exc()

def ReleaseApplicationLock():
    try:
        import fcntl
        fcntl.flock(AgentConstants.APPLICATION_LOCK, fcntl.LOCK_UN)
    except Exception as e:
        traceback.print_exc()
        
def UninstallAgent():
    try:
        AgentLogger.log([AgentLogger.STDOUT],'======================================= UNINSTALL AGENT : CREATING UNINSTALL FLAG =======================================')
        str_uninstallTime = 'Uninstall : '+repr(datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S"))
        fileObj = FileObject()
        fileObj.set_filePath(AgentConstants.AGENT_UNINSTALL_FLAG_FILE)
        fileObj.set_data(str_uninstallTime)
        fileObj.set_mode('wb')
        fileObj.set_loggerName([AgentLogger.STDOUT])
        FileUtil.saveData(fileObj)
        if AgentConstants.IS_DOCKER_AGENT == "0":
            com.manageengine.monagent.collector.DataCollector.COLLECTOR.stopDataCollection()
        else:
            AgentConstants.DOCKER_COLLECTOR_OBJECT.stop()
        TerminateAgent()
        cleanAll()
        if AGENT_CONFIG.has_section('AGENT_INFO') and ((AGENT_CONFIG.get('AGENT_INFO','agent_instance_type')==AgentConstants.AZURE_INSTANCE) or (AGENT_CONFIG.get('AGENT_INFO','agent_instance_type')==AgentConstants.AZURE_INSTANCE_CLASSIC)):
            do_status_report('Agent Uninstall','success',0,'Agent uninstalled successfully')
    except Exception as e:        
        AgentLogger.log([ AgentLogger.STDERR],' ************************* Exception while creating uninstall flag file!!! ************************* '+ repr(e))
        traceback.print_exc()
                
def RestartAgent():
    try:
        AgentLogger.log([AgentLogger.STDOUT],'======================================= RESTART AGENT : CREATING RESTART FLAG =======================================')
        str_uninstallTime = 'Restart : '+repr(datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S"))
        fileObj = FileObject()
        fileObj.set_filePath(AgentConstants.AGENT_RESTART_FLAG_FILE)
        fileObj.set_data(str_uninstallTime)
        fileObj.set_loggerName([AgentLogger.STDOUT])
        FileUtil.saveData(fileObj)
    except Exception as e:        
        AgentLogger.log([ AgentLogger.STDERR],' ************************* Exception while creating restart flag file!!! ************************* '+ repr(e))
        traceback.print_exc()

def TerminateAgent():
    global TERMINATE_AGENT
    if not TERMINATE_AGENT:
        AgentLogger.log(AgentLogger.MAIN,'======================================= SHUTTING DOWN AGENT ======================================= ')
        TERMINATE_AGENT = True
        TERMINATE_AGENT_NOTIFIER.set()
    #azure stop status update
    try:
        if AGENT_CONFIG.has_section('AGENT_INFO') and AGENT_CONFIG.get('AGENT_INFO','agent_instance_type')==AgentConstants.AZURE_INSTANCE or AGENT_CONFIG.get('AGENT_INFO','agent_instance_type')==AgentConstants.AZURE_INSTANCE_CLASSIC:
            do_status_report('Agent Termination','success',0,'Agent stopped successfully')
    except Exception as e:
        AgentLogger.log(AgentLogger.CRITICAL,' Exception While updating agent stop status ')
        traceback.print_exc()
        
        
def cleanAll():
    try:
        # Cleanup code
        AgentLogger.log(AgentLogger.MAIN,' ======================================= CLEANING UP AGENT RESOURCES ======================================= ')
        from com.manageengine.monagent.scheduler import AgentScheduler
        AgentScheduler.stopSchedulers()
        com.manageengine.monagent.communication.UdpHandler.SysLogUtil.persistLogMessages()
        persistAgentParams()
        AgentBuffer.cleanUp()
        AgentLogger.shutdown()
        ReleaseApplicationLock()
    except Exception as e:        
        AgentLogger.log(AgentLogger.CRITICAL,' ************************* PROBLEM WHILE CLEANING UP AGENT RESOURCES!!! ************************* '+ repr(e))
        traceback.print_exc()
    finally:
        ReleaseApplicationLock()
        
def timeConversion(timeinms):
    str_time=''
    days = math.floor(timeinms / 86400000)
    timeinms = timeinms-days*86400000

    hrs = math.floor(timeinms / 3600000)
    timeinms = timeinms-hrs*3600000

    mins = math.floor(timeinms / 60000)
    timeinms=timeinms-mins*60000
    
    secs=math.floor(timeinms/1000)
    ms=timeinms-secs*1000
    if days>0:
        str_time = str(int(days))+' '+'day(s)'
    if hrs>0:
        str_time+= ' '+str(int(hrs))+' '+'hr(s)'
    if mins>0:
        str_time+= ' '+str(int(mins))+' '+'min(s)'
    if secs>0:
        str_time+= ' '+str(int(secs))+' '+'sec(s)'
    #if ms>0:
     #   str_time+= ' '+str(ms)+' '+'ms'
    return str_time

def getUptimeInChar():
    isSuccess, str_output = executeCommand(AgentConstants.UPTIME_CLIENT) if AgentConstants.OS_NAME == AgentConstants.LINUX_OS else executeCommand(AgentConstants.UPTIME_COMMAND)
    if isSuccess:
        uptime = re.sub('\s+','',str_output).strip()
        return int(float(uptime))
    else:
        return '0'
    
def do_status_report(operation, status, status_code, message):
        try:
            azure_status_file=getStatusFileName()
            if azure_status_file:
                DateTimeFormat = "%Y-%m-%dT%H:%M:%SZ"
                tstamp=time.strftime(DateTimeFormat, time.gmtime())
                stat = [{
                    "version" : "1.0.0",
                    "timestampUTC" : tstamp,
                    "status" : {
                        "operation" : operation,
                        "status" : status,
                        "code" : status_code,
                        "formattedMessage" : {
                            "lang" : "en-US",
                            "message" : message
                        }
                    }
                }]
                stat_rept = json.dumps(stat)
                with open(azure_status_file,'w') as f:
                    f.write(stat_rept)
            else:
                AgentLogger.log(AgentLogger.STDOUT,' Not Able to fetch status file '+repr(azure_status_file))
        except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,' Exception While Updating the Agent Status '+ repr(e))
            traceback.print_exc()

def getStatusFileName():
    try:
        latest_status_file=None
        if os.path.exists(AgentConstants.AZURE_HANDLER_FILE):
            file_obj = open(AgentConstants.AZURE_HANDLER_FILE,'r')
            handler_conf_dict = json.load(file_obj,object_pairs_hook=collections.OrderedDict)
            for each in handler_conf_dict:
                for k in each:
                    if k=='handlerEnvironment':
                        conf_file_directory = each[k]['configFolder']
                        status_file_directory = each[k]['statusFolder']
            if not file_obj == None:
                        file_obj.close()
            if conf_file_directory:
                for dirname, dirnames, filenames in os.walk(conf_file_directory):
                    for file in filenames:
                        if '.settings' in file:
                            max_mtime = 0
                            full_path = os.path.join(dirname, file)
                            mtime = os.stat(full_path).st_mtime
                            if mtime > max_mtime:
                                max_mtime = mtime
                                max_dir = dirname
                                max_file = file
                latest_modified_config_file = max_file
                if latest_modified_config_file:
                    file_no=latest_modified_config_file.split('.')[0]
                    latest_status_file=status_file_directory+'/'+file_no+'.status'
        else:
            AgentLogger.log(AgentLogger.STDOUT,' Azure Handler Environment File not exists ')
    except Exception as e:
        traceback.print_exc()
    return latest_status_file


def generateTraceRoute():
    try:
        trace_dict={}
        str_fileName = 'trace_route_'+str(getTimeInMillis())+'.txt'
        executorObj = Executor()
        executorObj.setLogger(AgentLogger.STDOUT)
        executorObj.setTimeout(240)
        command = AgentConstants.TRACEROUTE_COMMAND.format(AGENT_CONFIG.get('SERVER_INFO', 'server_name'))
        AgentLogger.log(AgentLogger.CHECKS,'trace route command is '+repr(command))
        executorObj.setCommand(command)
        executorObj.executeCommand()
        trace_dict['status'] = executorObj.isSuccess()
        retVal = executorObj.getReturnCode()
        if not ((retVal == 0) or (retVal is not None)):
            trace_dict['timeout'] = True
        trace_dict['output'] = executorObj.getStdOut()
        trace_dict['error'] = getModifiedString(executorObj.getStdErr(),100,100)
        if trace_dict['error']!='' and 'unknown host' in trace_dict['error']:
            trace_dict['output']=trace_dict['error']
            AgentLogger.log(AgentLogger.CHECKS,'trace route error assigned to output ---> '+json.dumps(trace_dict))
        if not trace_dict['output'] == None and trace_dict['output']!='':
            str_filePath = AgentConstants.AGENT_TEMP_RCA_DIR+'/'+str_fileName
            trace_dict['output'] = trace_dict['output'].replace('\n','#')
            fileObj = FileObject()
            fileObj.set_fileName(str_fileName)
            fileObj.set_filePath(str_filePath)
            fileObj.set_data(trace_dict['output'])
            fileObj.set_dataType('json')
            fileObj.set_mode('wb')
            fileObj.set_dataEncoding('UTF-16LE')
            fileObj.set_loggerName(AgentLogger.STDOUT)
            bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
        AgentLogger.log(AgentLogger.CHECKS,'trace route output ---> '+json.dumps(trace_dict))
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.STDOUT,'Exception occurred while generating trace route')
    return trace_dict

def getTraceRouteData(float_timeInMillis):
    AgentLogger.log(AgentLogger.STDOUT,' Search Time ---> '+repr(float_timeInMillis))
    try:
        fileList = FileUtil.getSortedFileList(AgentConstants.AGENT_TEMP_RCA_DIR)
        tracedict=None
        for file in fileList:
            if 'trace_route' in file:
                fileName = os.path.basename(file)
                AgentLogger.log(AgentLogger.STDOUT,' File Name ---> '+repr(fileName))
                name,fileExt = os.path.splitext(fileName)
                list = name.split('_')
                time = list[2]
                if int(time) < float_timeInMillis:
                    boolStatus,tracedict = loadUnicodeDataFromFile(file)
                    break
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.STDOUT,'Exception occurred while getting trace route')
    return tracedict

def deleteTraceRoute():
    try:
        list = FileUtil.getSortedFileList(AgentConstants.AGENT_TEMP_RCA_DIR, str_loggerName=AgentLogger.STDOUT)
        if not list == None:
            for file in list:
                if 'trace_route' in file:
                    AgentLogger.log(AgentLogger.CHECKS,'Trace Route File to be removed ---> '+repr(file))
                    os.remove(file)
        else:
            AgentLogger.log(AgentLogger.STDOUT,'Trace Route File List Empty')
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Exception occurred while deleting trace route files')
        traceback.print_exc()

def invokeUptimeMonitoringFC():
    try:
        AgentLogger.log(AgentLogger.STDOUT,'########## UPTIME MONITORING FILE COLLECTOR ##########')
        str_url = None
        str_servlet = AgentConstants.AGENT_FILE_COLLECTOR_SERVLET
        dict_requestParameters = {
            'AGENTKEY' : AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),
            'CUSTOMERID' :  AgentConstants.CUSTOMER_ID,
            'AGENTUNIQUEID' : AGENT_CONFIG.get('AGENT_INFO', 'agent_unique_id'),
            'bno' : AgentConstants.AGENT_VERSION,
            'UPTIME_MONITORING': 'true'
        }
        if not dict_requestParameters == None:
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
        requestInfo = com.manageengine.monagent.communication.CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.STDOUT)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.set_timeout(30)
        bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData = com.manageengine.monagent.communication.CommunicationHandler.sendRequest(requestInfo)
        AgentLogger.log(AgentLogger.STDOUT,'Repsonse --- {0}'.format(bool_toReturn))
        AgentLogger.log(AgentLogger.STDOUT,'Error Code --- {0}'.format(int_errorCode))
        AgentLogger.log(AgentLogger.STDOUT,'Response Data --- {0}'.format(dict_responseData))
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Exception while updating file collector - uptime monitoring')
        traceback.print_exc()

def updateKeys(keysDict):
    agent_key=None
    customer_id=None
    try:
        AgentLogger.log(AgentLogger.STDOUT,'########## update keys action called  ########## {}'.format(json.dumps(keysDict)))
        if 'AGENTKEY' in keysDict:
            agent_key=keysDict['AGENTKEY']
        if 'DEVICEKEY' in keysDict:
            customer_id=keysDict['DEVICEKEY']
            agent_key = '0'
        if agent_key or customer_id:
            persist_agent_info_in_file_only(agent_key,customer_id)
            reinit_childs()
            create_file(AgentConstants.AGENT_RESTART_FLAG_FILE)
        else:
            AgentLogger.log(AgentLogger.STDOUT,'########## no agent / device key found ##########')
    except Exception as e:
        traceback.print_exc()

def calculateNoOfCpuCores():
    try:
        if AgentConstants.IS_DOCKER_AGENT == "0":
            if AgentConstants.OS_NAME == AgentConstants.FREEBSD_OS:
                command = AgentConstants.NO_OF_CPU_CORES_COMMAND_BSD
            elif AgentConstants.OS_NAME == AgentConstants.OS_X:
                command = AgentConstants.NO_OF_CPU_CORES_COMMAND_OSX
            elif AgentConstants.OS_NAME == AgentConstants.SUN_OS:
                command = AgentConstants.NO_OF_CPU_CORES_COMMAND_SUNOS
            else:
                command = AgentConstants.NO_OF_CPU_CORES_COMMAND
            output = None
            executorObj = Executor()
            executorObj.setLogger(AgentLogger.STDOUT)
            AgentLogger.log(AgentLogger.STDOUT,'no of cores command :: '+repr(command))
            executorObj.setCommand(command)
            executorObj.executeCommand()
            output = executorObj.getStdOut()
            if not output == None:
                AgentConstants.NO_OF_CPU_CORES=float(output.strip('\n'))
                AgentLogger.log(AgentLogger.STDOUT,'no of cores :: '+repr(AgentConstants.NO_OF_CPU_CORES))
        
    except Exception as e:
        traceback.print_exc()

def getProcessorName():
    try:
        if AgentConstants.IS_DOCKER_AGENT == "0":
            output=None
            executorObj = Executor()
            executorObj.setLogger(AgentLogger.STDOUT)
            command = AgentConstants.PROCESSOR_NAME_COMMAND
            AgentLogger.log(AgentLogger.STDOUT,'processor name command :: '+repr(command))
            executorObj.setCommand(command)
            executorObj.executeCommand()
            executorObj.setTimeout(10)
            output = executorObj.getStdOut()
            if not output == None:
                AgentConstants.PROCESSOR_NAME=output.strip()
                AgentLogger.log(AgentLogger.STDOUT,'processor name :: '+repr(AgentConstants.PROCESSOR_NAME))
        else:
            AgentConstants.PROCESSOR_NAME = AgentConstants.DOCKER_SYSTEM_OBJECT.get_processorname()
    except Exception as e:
        traceback.print_exc()

def getSystemUUID():
    try:
        output = None
        if KubeGlobal.gkeAutoPilot or KubeGlobal.fargate or KubeGlobal.nonMountedAgent:
            AgentConstants.SYSTEM_UUID = get_k8s_node_uuid()
        else:
            executorObj = Executor()
            executorObj.setLogger(AgentLogger.STDOUT)
            command = AgentConstants.SYSTEM_UUID_COMMAND
            AgentLogger.log(AgentLogger.STDOUT,'server uuid command :: '+repr(command))
            executorObj.setCommand(command)
            executorObj.executeCommand()
            output = executorObj.getStdOut()
            if not output == None:
                AgentConstants.SYSTEM_UUID=(output.strip('\n'))
                AgentLogger.log(AgentLogger.STDOUT,'system uuid :: '+repr(AgentConstants.SYSTEM_UUID))
    except Exception as e:
        traceback.print_exc()

def updateTaskInfo(dict_task):
    try:
        AgentLogger.log(AgentLogger.STDOUT,'update task info  :: '+repr(dict_task))
        if dict_task:
            updateKey = dict_task['key']
            updateValue = dict_task['value']
            if AGENT_CONFIG.has_option('AGENT_INFO', updateKey):
                AGENT_CONFIG.set('AGENT_INFO', updateKey, updateValue)
                persistAgentInfo()
                if updateKey=="pl_zip_task_interval":
                    AgentConstants.PLUGINS_ZIP_INTERVAL = updateValue
                    AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['002']['zip_interval'] = int(updateValue)
                elif updateKey=="pl_dc_task_interval":
                    AgentConstants.PLUGINS_DC_INTERVAL = updateValue
                    module_object_holder.plugins_obj.initiatePluginDC()
                elif updateKey=="pl_dc_zip_count":
                    AgentConstants.PLUGINS_ZIP_FILE_SIZE = updateValue
                elif updateKey=="top_arg_length":
                    AgentConstants.TOP_PROCESS_ARGUMENT_LENGTH = updateValue
                elif updateKey=="disc_prc_arg_length":
                    AgentConstants.DISCOVER_PROCESS_ARGUMENT_LENGTH = updateValue
                elif updateKey=="dc_upload_interval":
                    AgentConstants.UPLOAD_CHECK_INTERVAL = updateValue
                    AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['001']['zip_interval'] = int(updateValue)
                    AgentConstants.CURRENT_DC_TIME = None
    except Exception as e:
        traceback.print_exc()


def getUpTime():
    try:
        executorObj = Executor()
        executorObj.setLogger(AgentLogger.STDOUT)
        executorObj.setTimeout(10)
        executorObj.setCommand(AgentConstants.UPTIME_COMMAND)
        executorObj.executeCommand()
        uptime = int(executorObj.getStdOut())
        return uptime
    except:
        AgentLogger.log(AgentLogger.STDOUT,'Exception while calculating the uptime')
        traceback.print_exc()
        return None
            
def getBootTime():
    uptime=None
    serverRestart=None
    bootTime=None
    try:
        uptime = getUpTime()
        if os.path.exists(AgentConstants.AGENT_UPTIME_FLAG_FILE):
                executorObj=Executor()
                executorObj.setCommand(AgentConstants.UPTIME_READ_COMMAND)
                executorObj.executeCommand()
                prev_uptime = int(executorObj.getStdOut())
                if uptime < prev_uptime:
                    serverRestart =  True
                    executorObj.setCommand(AgentConstants.BOOT_TIME_COMMAND)
                    executorObj.executeCommand()
                    cmd_out=executorObj.getStdOut().split('\n')
                    try:
                        boot_time_parsed=[]
                        boottime=''
                        boot_time_raw=datetime.strptime(cmd_out[0],'%b %d %H:%M:%S %Y')-datetime.strptime(cmd_out[1],'%b %d %H:%M:%S %Y')
                        boot_time_parsed.append(boot_time_raw.days)
                        if boot_time_parsed[0] != 0:
                            boottime=str(boot_time_parsed[0])+' days '
                        boot_time_parsed.append(int(boot_time_raw.seconds/3600))
                        if boot_time_parsed[1] != 0:
                            boottime=boottime+str(boot_time_parsed[1])+' hours '
                        boot_time_parsed.append(int((boot_time_raw.seconds-boot_time_parsed[1]*3600)/60))
                        if boot_time_parsed[2] != 0:
                            boottime=boottime+str(boot_time_parsed[2])+' minutes '
                        boot_time_parsed.append(boot_time_raw.seconds%60)
                        if boot_time_parsed[3] != 0:
                            boottime=boottime+str(boot_time_parsed[3])+' seconds '
                            bootTime = boottime
                    except Exception as e1:
                        AgentLogger.log(AgentLogger.STDOUT,'Exception while calculating the boot_time')
                        traceback.print_exc()
    except Exception as e:
            AgentLogger.log(AgentLogger.STDOUT,'Exception while calculating the uptime')
            traceback.print_exc()
    return uptime,serverRestart,bootTime

def getCpuFormula():
    bool_returnStatus = True
    file_obj = None
    str_cpu_formula = None
    try:
        file_obj = open(AgentConstants.CPU_FORMULA_FILE,'r')
        str_cpu_formula = file_obj.read()
        if "\n" in str_cpu_formula:
            str_cpu_formula = str_cpu_formula.replace("\n","") 
    except:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while reading cpu formula from the file '+AgentConstants.CPU_FORMULA_FILE+' ************************* ')
        traceback.print_exc()
        bool_returnStatus = False
    finally:
        if not file_obj == None:
            file_obj.close()
    if bool_returnStatus:
        AgentLogger.log(AgentLogger.STDOUT,'CPU Formula : '+repr(str_cpu_formula)+' from the file : '+AgentConstants.CPU_FORMULA_FILE)
    return bool_returnStatus, str_cpu_formula

def setCpuFormula(instanceDict=None):
    try:
        if instanceDict:
            if 'cloudPlatform' in instanceDict and instanceDict['cloudPlatform']=='AWS':
                AgentConstants.CPU_FORMULA = AgentConstants.CPU_FORMULA_WITHOUT_STEAL
                AgentLogger.log(AgentLogger.STDOUT,'CPU Formula : '+repr(AgentConstants.CPU_FORMULA))
        if os.path.exists(AgentConstants.CPU_FORMULA_FILE):
            return_status,cpu_formula = getCpuFormula()
            AgentConstants.CPU_FORMULA = cpu_formula
    except Exception as e:
        traceback.print_exc()

def handleCpuDataCollection():
    try:
        command="op=$(top -n 1 -d 0.1 -b -o %MEM 2> /dev/null); echo $?"
        output = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE).stdout.read().decode("utf-8").strip()
        if str(output) == "0":
            AgentConstants.TOP_COMMAND_CHECK = True
        else:
            AgentLogger.log(AgentLogger.MAIN,'***** Top Command not compatible for Top Process DC :: {0} *****'.format(output))
            AgentConstants.TOP_COMMAND_CHECK = False
    except Exception as e:
        AgentConstants.TOP_COMMAND_CHECK = False
        AgentLogger.log(AgentLogger.STDERR,'***** Exception while deciding CPU/Top process dc :: {0} *****'.format(e))
        traceback.print_exc()
        
def checkSystemUtilities():
    try:
        from shutil import which
        iostat=which('iostat')
        dpkg = which('dpkg')
        rpm = which('rpm')
        AgentLogger.log(AgentLogger.STDOUT,'iostat module status :: {0}'.format(iostat))
        AgentLogger.log(AgentLogger.STDOUT,'dpkg module status :: {0}'.format(dpkg))
        AgentLogger.log(AgentLogger.STDOUT,'rpm module status :: {0}'.format(rpm))  
        if iostat:
            AgentConstants.IOSTAT_UTILITY_PRESENT=True
        if dpkg:
             AgentConstants.DPKG_UTILITY_PRESENT=True
        if rpm:
            AgentConstants.RPM_UTILITY_PRESENT=True
    except Exception as e:
        traceback.print_exc()

def create_file(file_path):
    f=None
    try:
        if not os.path.exists(file_path):
            f = open(file_path,'w')
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'problem while creating file -- {0}'.format(file_path))
    finally:
        if not f == None:
            f.close()

def update_agent_install_time(install_time):
    myfile=None
    try:
        create_file(AgentConstants.AGENT_INSTALL_TIME_FILE)
        if os.path.exists(AgentConstants.AGENT_INSTALL_TIME_FILE):
            with open(AgentConstants.AGENT_INSTALL_TIME_FILE, "a") as myfile:
                myfile.write(install_time)
    except Exception as e:
        traceback.print_exc()
    finally:
        if not myfile == None:
            myfile.close()

def handle_license():
    try:
        import shutil
        if AgentConstants.IS_VENV_ACTIVATED:
            if os.path.exists(AgentConstants.LICENSE_CONTENT):
                shutil.copyfile(AgentConstants.LICENSE_CONTENT,AgentConstants.LICENSE_FILE)
    except Exception as e:
        traceback.print_exc()

def get_server_time_zone():
    time_zone = None
    try:
        time_zone = time.tzname[0]
    except Exception as e:
        traceback.print_exc()
    return time_zone

def update_proxy_settings(secret_key):
    try:
        AgentLogger.debug(AgentLogger.MAIN,'secret server key received -- {0}'.format(secret_key)+'\n')
        AgentConstants.SSKEY=secret_key
    except Exception as e:
        traceback.print_exc()

def get_top_process_data():
    try:
        if AgentConstants.DOCKER_PROCESS_OBJECT:
            AgentConstants.DOCKER_PROCESS_OBJECT.construct()
        AgentLogger.debug(AgentLogger.MAIN, 'top process - {0}'.format(AgentConstants.PS_UTIL_PROCESS_DICT))
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while setting consolidated values for Top Process *********************************')
        traceback.print_exc()

def get_line_count_of_a_file(file_name):
    line_count=0
    file_obj = None
    try:
        with open (file_name,'rb') as file_obj:
            for line in file_obj:
                line_count+=1
    except Exception as e:
        traceback.print_exc()
    finally:
        if not file_obj==None:
            file_obj.close()
    return line_count
    
def get_server_ram_size():
    try:
        import os
        mem_bytes = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
        mem_gib = mem_bytes/(1024.**2)
        AgentConstants.RAM_SIZE=round(mem_gib,1)
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN, 'exception while fetching server ram size')
        traceback.print_exc()
        
def get_hash_id(strArgs):
    try:
        return hashlib.md5(strArgs.encode()).hexdigest()
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,'*************************** Exception While getting hash ID for args :'  +  str(strArgs) +'*************************** '+ repr(e))
        traceback.print_exc()

def persist_agent_info_in_file_only(agent_key,customer_id):
    try:
        monagent_config = configparser.RawConfigParser()
        monagent_config.read(AgentConstants.AGENT_CONF_FILE)
        if agent_key:
            monagent_config.set('AGENT_INFO','agent_key',agent_key)
        if customer_id:
            monagent_config.set('AGENT_INFO','customer_id',customer_id)
        persistAgentInfo(monagent_config)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Exception while updating monitoring agent configuration file')
        traceback.print_exc()

def update_monagent_config(dict_data):
    try:
        if str(dict_data['section']) in AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER:
            AgentLogger.log(AgentLogger.STDOUT,'Upload Properties Change Request Recieved :: {}:{}:{} '.format(dict_data['section'], dict_data['key'],dict_data['value']))
            UPLOAD_CONFIG.set(dict_data['section'], dict_data['key'],dict_data['value'])
            if str(dict_data['section']) in AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER:
                AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[dict_data['section']][dict_data['key']] = int(dict_data['value'])
            persistUploadPropertiesInfo()
        else:
            AGENT_CONFIG.set(dict_data['section'], dict_data['key'],dict_data['value'])
            persistAgentInfo()
            create_file(AgentConstants.AGENT_RESTART_FLAG_FILE)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Exception while updating monagent.cfg file')
        traceback.print_exc()
        
def remove_dc_zips(dict_task=None):
    dir_prop_code = None
    try:
        if dict_task and 'dir_code' in dict_task:
            dir_prop_code = dict_task['dir_code']
        for dir,dir_props in AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER.items():
            if (not (dir_prop_code == None)) or (dir_prop_code and dir_prop_code == dir):
                if os.path.exists(dir_props['zip_path']):
                    for grp_dir in os.listdir(dir_props['zip_path']):
                        grp_dir_path = os.path.join(dir_props['zip_path'], grp_dir)
                        try:
                            for the_file in os.listdir(grp_dir_path):
                                file_path = os.path.join(grp_dir_path, the_file)
                                try:
                                    if os.path.isfile(file_path):
                                        AgentLogger.log(AgentLogger.STDOUT,'Deleting the dc file -- {}'.format(file_path))
                                        os.remove(file_path)
                                except Exception as e:
                                    traceback.print_exc()
                            os.rmdir(grp_dir_path)
                        except Exception as e:
                            traceback.print_exc()
        create_file(AgentConstants.AGENT_RESTART_FLAG_FILE)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Exception while deleting dc zips')
        traceback.print_exc()
        
def process_through_mount(mountPath):
    try:
        process_list = []
        if os.path.ismount(mountPath):
            AgentConstants.PSUTIL_OBJECT.PROCFS_PATH = mountPath
            for proc in AgentConstants.PSUTIL_OBJECT.process_iter():
                try:
                    pinfo = proc.as_dict(attrs=["name", "exe", "cmdline", "pid"])
                    if type(pinfo["cmdline"]) is list:
                        cmd_str = " ".join(pinfo["cmdline"]).strip()
                    else:
                        cmd_str = pinfo["cmdline"] 
                    process_list.append(cmd_str)
                except Exception as e:
                    continue
            AgentLogger.debug(AgentLogger.CHECKS,'Mounted process psutil discovery list '+ repr(process_list))
        else:
            AgentLogger.log(AgentLogger.KUBERNETES," {} not mounted ".format(mountPath))
    except Exception as e:
        AgentLogger.log([AgentLogger.STDERR, AgentLogger.KUBERNETES],'Exception while check_if_process_running_mounted_path')
        traceback.print_exc()
    finally:
        return process_list

def MergeDataDictionaries(dict1,dict2):
    try:
        if dict1 and not dict2:
            return dict1
        
        if dict2 and not dict1:
            return dict2

        dictNew = dict(mergedicts(dict1,dict2))
        return dictNew
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,'Exception while MergeDictionaries')
        AgentLogger.log(AgentLogger.MAIN,e)
    return None

def mergedicts(dict1,dict2):
    try:
        for k in set(dict1.keys()).union(dict2.keys()):
                if k in dict1 and k in dict2:
                    if isinstance(dict1[k], dict) and isinstance(dict2[k], dict):
                        yield (k, dict(mergedicts(dict1[k], dict2[k])))
                    else:
                        # If one of the values is not a dict, you can't continue merging it.
                        # Value from second dict overrides one in first and we move on.
                        yield (k, dict2[k])
                        # Alternatively, replace this with exception raiser to alert you of value conflicts
                elif k in dict1:
                    yield (k, dict1[k])
                else:
                    yield (k, dict2[k])
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,'Exception while mergedicts')
        AgentLogger.log(AgentLogger.MAIN,e)


def get_regex_expression(regex_args):
    regex_obj = None
    try:
        regex_obj = re.compile(regex_args,re.IGNORECASE)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'Exception while getting regex object -- {}'.format(regex_args))
        traceback.print_exc()
    return regex_obj
    

def exec_util(file_name,params,temp):
    try:
        script_path = PLUGIN_NAME_VS_PATH[file_name] if file_name in PLUGIN_NAME_VS_PATH else file_name
        script_path = sys.modules[script_path]
        script_name = 'main'
        dict_val =getattr(script_path,script_name)(params)
        return dict_val
    except Exception as e:
        traceback.print_exc()

def exec_function_timeout(file_name,timeout,params):
    dict_to_return={}
    dict_to_return['result'] = True
    try:
        return_value_from_exec = func_timeout(timeout, exec_util, args=(file_name,params,1))
        dict_to_return['output'] = return_value_from_exec
        AgentLogger.debug(AgentLogger.PLUGINS,' return value -- {}'.format(dict_to_return))
    except FunctionTimedOut:
        dict_to_return['timedout']=True
        AgentLogger.log(AgentLogger.PLUGINS,' timeout occurred ')
    except Exception as e:
        AgentLogger.log(AgentLogger.PLUGINS,' exception occurred ')
        dict_to_return['result'] = False
        traceback.print_exc()
    return dict_to_return,dict_to_return['result']    

''' dict of large size will be split based on SIZE'''
def dict_chunks(kv_pairs, SIZE=10):
    it = iter(kv_pairs)
    for i in range(0, len(kv_pairs), SIZE):
        yield {k:kv_pairs[k] for k in islice(it, SIZE)}

''' list of large size will be split based on SIZE'''
def list_chunks(my_list,SIZE=4):
    final_list = [my_list[i * SIZE:(i + 1) * SIZE] for i in range((len(my_list) + SIZE - 1) // SIZE )]
    return final_list

''' large json data split into list of json based on max bytes size of each json'''
def json_list_chunk_on_size(json_list, BYTES=204800): # 204800 Bytes = 200 KB
    result_list = []
    shrinked_json = json.dumps(json_list, separators=(',', ':'))
    if len(str(shrinked_json))+1 <= BYTES:
        result_list = shrinked_json
    else:
        byte_count = 3  # 1 byte is for file creation # 2 byte for overall list brackets
        temp_single_file_json_list = []
        for each_json in shrinked_json:
            if byte_count > BYTES:
                last_json_node = temp_single_file_json_list.pop()
                result_list.append(copy.deepcopy(temp_single_file_json_list))
                temp_single_file_json_list = []
                temp_single_file_json_list.append(copy.deepcopy(last_json_node))
                byte_count = len(str(last_json_node))
            elif byte_count == BYTES:
                result_list.append(copy.deepcopy(temp_single_file_json_list))
                temp_single_file_json_list = []
                byte_count = 0
            temp_single_file_json_list.append(each_json)
            byte_count = byte_count + len(str(each_json))
    return result_list


def dict_chunk_with_file_size(json_dict, BYTES=204800):
    result_dict_list = []
    temp_dict_data = {}
    byte_count = 2
    for db_name, db_data in json_dict.items():
        temp_dict = {}
        temp_dict[db_name] = db_data
        byte_count = byte_count + len(str(temp_dict))
        temp_dict_data[db_name] = db_data
        if byte_count >= BYTES:
            result_dict_list.append(copy.deepcopy(temp_dict_data))
            temp_dict_data = {}
            byte_count = 2
    if temp_dict_data:
        result_dict_list.append(copy.deepcopy(temp_dict_data))
    return result_dict_list



def get_default_reg_params():
    request_params = {}
    request_params["agentKey"] = AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
    request_params['CUSTOMERID'] = AgentConstants.CUSTOMER_ID
    request_params['bno'] = AgentConstants.AGENT_VERSION
    request_params['REDISCOVER'] = "TRUE"
    return request_params

def text_to_bytes(data):
     if not isinstance(data, bytes):
        data = data.encode('utf-8')
     return data

def bytes_to_text(data):
    if isinstance(data, bytes):
       data = data.decode('utf-8')
    return data

def write_pid_to_pidfile(pidfile_path):
    try:
        open_flags = (os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        open_mode = 0o644
        pidfile_fd = os.open(pidfile_path, open_flags, open_mode)
        pidfile = os.fdopen(pidfile_fd, 'w')
        pid = os.getpid()
        pidfile.write("%s\n" % pid)
        pidfile.close()
        AgentLogger.log(AgentLogger.STDOUT,'========== New PID File created {} file. PID :: {}'.format(pidfile_path,pid))
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,'********** Problem while writing {} file. Error :: {}'.format(pidfile_path,e))
        traceback.print_exc()

def cleanUpOldConfig():
    try:
        for each_files in AgentConstants.CONFIG_FILES_CLEAN_UP:
            FileUtil.deleteFile(each_files)
    except Exception as e:
        traceback.print_exc()

def convert_int_to_string(int_dict):
    try:
            str_dict = {key: str(value) for key, value in int_dict.items()}
    except:
        AgentLogger.log(AgentLogger.STDERR,'********** Exception while converting {} items from int to str **********'.format(int_dict))
        traceback.print_exc()
        return int_dict
    return str_dict

def get_file_size(file_path, depth = 0):
    return_size = -1
    try:
        #output can be a value / dict of value in bytes
        output = None
        executorObj = Executor()
        executorObj.setLogger(AgentLogger.STDOUT)
        command = "du -b --max-depth={0} {1}".format(depth, file_path)
        executorObj.setCommand(command)
        executorObj.executeCommand()
        output = executorObj.getStdOut()
        if output:
            output = output.strip()
            if depth:
                return_size = {}
                for each in output.splitlines():
                    each = each.split('\t')
                    return_size[each[1].split('/')[-1]] = int(each[0]) 
            else:
                return_size = int(output.split('\t')[0])
        AgentLogger.debug(AgentLogger.STDOUT, "\nSize of the {0} ( depth {1} ) is {2}".format(file_path, str(depth), repr(return_size)))
    except Exception as e:
        traceback.print_exc()
    return return_size

def get_installedby():
    installed_by = AgentConstants.AGENT_USER_NAME
    try:
        if installed_by != 'root':
            return installed_by
        
        try:
            installed_by = os.getlogin()
            if installed_by != 'root':
                return installed_by
        except:
            pass
        
        installed_by = os.getenv('SUDO_USER')
        if installed_by != 'root':
            return installed_by
    except:   
        AgentLogger.log(AgentLogger.STDERR,"Exception on getting username of the user who installed agent")
        traceback.print_exc()
        return installed_by

def set_auid():
    try:
        if os.path.exists(AgentConstants.AUID_FILE):
            AgentConstants.AUID_OLD = get_auid_from_file()[1]
        AgentConstants.AUID = construct_auid()
    except Exception as e:
        traceback.print_exc()

def get_counter_value(param,current_value,isNotDiv=False):
    global COUNTER_PARAMS_DICT
    return_value = 0
    try:
        if param in COUNTER_PARAMS_DICT and not isNotDiv:
           return_value = ( float(current_value) - float(COUNTER_PARAMS_DICT[param]) ) / int(AgentConstants.POLL_INTERVAL)
           COUNTER_PARAMS_DICT[param] = current_value
        elif param in COUNTER_PARAMS_DICT and isNotDiv:
            return_value = float(current_value) - float(COUNTER_PARAMS_DICT[param])
            COUNTER_PARAMS_DICT[param] = current_value
        else:
            return_value = 0
            COUNTER_PARAMS_DICT[param] = current_value
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred in counter values block for param -- {0}'.format(param))
        traceback.print_exc()
    return round(return_value,2)

def get_hdd_names():
    try:
        output = None
        executorObj = Executor()
        executorObj.setLogger(AgentLogger.STDOUT)
        command = AgentConstants.HDD_NAMES_COMMAND
        AgentLogger.log(AgentLogger.STDOUT,'server hdd names command :: '+repr(command))
        executorObj.setCommand(command)
        executorObj.executeCommand()
        output = executorObj.getStdOut()
        if not output == None:
            output_lines = (output.splitlines())
            AgentLogger.log(AgentLogger.STDOUT,'hdd name command output :: '+repr(output_lines))
            for each_line in output_lines:
                if each_line:
                    AgentConstants.HDD_NAMES.append(each_line.split()[0])
        AgentLogger.log(AgentLogger.STDOUT,'hdd list :: '+repr(AgentConstants.HDD_NAMES))
    except Exception as e:
        traceback.print_exc()

def is_module_enabled(module_name):
    module_enabled = False
    try:
        if AgentConstants.AGENT_SETTINGS and module_name in AgentConstants.AGENT_SETTINGS:
            if AgentConstants.AGENT_SETTINGS[module_name]=="1":
                module_enabled = True
        elif AgentConstants.SERVER_SETTINGS and module_name in AgentConstants.SERVER_SETTINGS:
            if AgentConstants.SERVER_SETTINGS[module_name]=="1":
                module_enabled = True
        AgentLogger.debug(AgentLogger.MAIN,'module :: {} | enabled :: {}'.format(module_name,module_enabled))
    except Exception as e:
        traceback.print_exc()
    return module_enabled

def check_module_settings():
    try:
        for each,value in AgentConstants.SETTINGS_MAP.items():
            if not is_module_enabled(value["k"]):
                disable_module(value["k"],value["upgrade_check"],False)
    except Exception as e:
        traceback.print_exc()
        
def disable_module(module_name,pkg_to_disable,restart=True):
    try:
        AgentLogger.log(AgentLogger.MAIN,'module to disable :: {} :: {}'.format(module_name,pkg_to_disable))
        if os.path.exists(pkg_to_disable):
            if os.path.isdir(pkg_to_disable):
                shutil.rmtree(pkg_to_disable)
            if os.path.isfile(pkg_to_disable):
                os.remove(pkg_to_disable)
            AgentLogger.log(AgentLogger.MAIN,'module disabled successfully')
            if restart:
                invoke_agent_restart_via_watchdog()
    except Exception as e:
        traceback.print_exc()

def get_hostname_from_etc():
    bool_returnStatus = True
    file_obj = None
    host_name = None
    try:
        file_obj = open(AgentConstants.ETC_HOSTNAME_FILE_FOR_KUBE_AGENT,'r')
        host_name = file_obj.read()
        if "\n" in host_name:
            host_name = host_name.replace("\n","")
    except:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while reading host name from the file '+AgentConstants.ETC_HOSTNAME_FILE_FOR_KUBE_AGENT+' ************************* ')
        traceback.print_exc()
        bool_returnStatus = False
    finally:
        if not file_obj == None:
            file_obj.close()
    if bool_returnStatus:
        AgentLogger.log(AgentLogger.STDOUT,'Host Name  : '+repr(host_name)+' from the file : '+AgentConstants.ETC_HOSTNAME_FILE_FOR_KUBE_AGENT)
    return bool_returnStatus, host_name
         
def get_value_from_expression(expression,data_dict,round_off=False):
    locals = {}
    locals.update(data_dict)
    exec("contents="+expression,locals)
    value = round(locals['contents']) if round_off else locals['contents'] 
    return value 

def getAge(ct, cmpt=datetime.now()):
    age = None
    try:
        from dateutil import relativedelta
        if ct:
            ct=ct.split('T')
            ct=ct[0]+" "+ct[1].split('Z')[0]+".000000"
            c=datetime.strptime(ct, '%Y-%m-%d %H:%M:%S.%f')
            b=datetime.strptime(str(cmpt), '%Y-%m-%d %H:%M:%S.%f')
            d=relativedelta.relativedelta(b,c)
            day, month, year, minute, hour, sec=d.days, d.months, d.years, d.minutes, d.hours, d.seconds
            if year!=0:
                unit = ' year' if year <= 1 else ' years'
                age=str(year)+unit
            elif month!=0:
                unit = ' month' if month <= 1 else ' months'
                age=str(month)+unit
            elif day!=0:
                unit = ' day' if day <= 1 else ' days'
                age=str(day)+unit
            elif hour!=0:
                unit = ' hour' if hour <= 1 else ' hours'
                age=str(hour)+unit
            elif minute!=0:
                unit = ' min' if minute <= 1 else ' mins'
                age=str(minute)+unit
            else:
                age=str(sec)+' secs'
    except Exception as e:
        traceback.print_exc()
    return age

def get_k8s_node_uuid():
    try:
        com.manageengine.monagent.kubernetes.KubeUtil.get_bearer_token()
        status, json = com.manageengine.monagent.kubernetes.KubeUtil.curl_api_with_token('https://kubernetes.default/api/v1/nodes?fieldSelector=metadata.name={}'.format(KubeGlobal.nodeName))
        return json["items"][0]["status"]["nodeInfo"]["systemUUID"]
    except Exception as e:
        AgentLogger.log(AgentLogger.KUBERNETES, "Exception while replacing SUUID of K8s node {}".format(KubeGlobal.nodeName))
        traceback.print_exc()
    return None

def load_envs():
    try:
        conf_parser_obj = configparser.ConfigParser()
        conf_parser_obj.optionxform = lambda option: option
        file_path = os.path.join(AgentConstants.AGENT_CONF_DIR, 'agent_env_backup.conf')
        section = 'envs'

        if not os.path.exists(file_path):
            AgentLogger.log(AgentLogger.KUBERNETES, "agent_env_backup.conf file doesn't exists, hence creating")
            conf_parser_obj.read(file_path)
            conf_parser_obj.add_section(section)
            for key, value in os.environ.items():
                if key != "KEY":
                    conf_parser_obj.set(section, key, value)
            with open(file_path, 'w') as env_file:
                conf_parser_obj.write(env_file)
        else:
            conf_parser_obj.read(file_path)
            for key, value in conf_parser_obj.items(section):
                if key not in os.environ:
                    os.environ[key] = value
    except Exception as e:
        traceback.print_exc()

initialize()
