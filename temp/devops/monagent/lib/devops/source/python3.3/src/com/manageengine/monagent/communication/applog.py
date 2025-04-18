'''
Created on 08-Feb-2017

@author: giri
'''
import platform

from com.manageengine.monagent import AgentConstants
import subprocess, traceback, os, time, json, tarfile, signal
from functools import wraps
from contextlib import contextmanager
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import ZipManager, AgentUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil
from six.moves.urllib.parse import urlencode
import shutil
current_milli_time = lambda: int(round(time.time() * 1000))

@contextmanager
def s247_applog_communicator(filename):
    try:
        '''check if directory is present or not'''
        if not os.path.isdir(AgentConstants.APPLOG_S247_DMS_DIR_PATH):
            os.mkdir(AgentConstants.APPLOG_S247_DMS_DIR_PATH)
        filepath = os.path.join(AgentConstants.APPLOG_S247_DMS_DIR_PATH, filename+str(current_milli_time()))
        f = open(filepath, 'w')
        yield f
    except Exception as e:
        traceback.print_exc()
    finally:
        f.close()

def exceptionhandler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if type(AgentConstants.APPLOG_PROCESS) is subprocess.Popen:
                AgentConstants.APPLOG_PROCESS.kill()   #kill subprocess
                AgentConstants.APPLOG_PROCESS.poll()   #poll and inform the os about pid
            AgentLogger.log(AgentLogger.STDERR,'exceptionhandler : ')
            traceback.print_exc()
            return False
    return wrapper

@exceptionhandler
def enable():
    if AgentConstants.APPLOG_AGENT_ENABLED == 0:
        AgentConstants.APPLOG_AGENT_ENABLED = 1
        AgentUtil.AGENT_CONFIG.set('APPLOG_AGENT_INFO', 'applog_enabled',AgentConstants.APPLOG_AGENT_ENABLED)
        AgentUtil.persistAgentInfo()
        AgentLogger.log(AgentLogger.MAIN, "Applog Agent successfully enabled in this server")

@exceptionhandler
def disable():
    if AgentConstants.APPLOG_AGENT_ENABLED == 1:
        AgentConstants.APPLOG_AGENT_ENABLED = 0
        AgentUtil.AGENT_CONFIG.set('APPLOG_AGENT_INFO', 'applog_enabled',AgentConstants.APPLOG_AGENT_ENABLED)
        AgentUtil.persistAgentInfo()
        AgentLogger.log(AgentLogger.MAIN, "Applog Agent successfully disabled in this server")

@exceptionhandler
def start():
    if AgentConstants.APPLOG_AGENT_ENABLED == 1:
        if os.path.isfile(AgentConstants.APPLOG_EXEC_PATH):
            if AgentConstants.APPLOG_UPGRADE_INPROGRESS == False:
                AgentLogger.log(AgentLogger.MAIN, "Going to start Applog Agent... \n")
                applog_exec_cmd = AgentConstants.APPLOG_EXEC_PATH
                if AgentConstants.IS_VENV_ACTIVATED:
                    applog_exec_cmd = [AgentConstants.AGENT_VENV_BIN_PYTHON , applog_exec_cmd]
                AgentConstants.APPLOG_PROCESS = subprocess.Popen(applog_exec_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                time.sleep(5)
                if AgentConstants.APPLOG_PROCESS.poll() is None:
                    AgentLogger.log(AgentLogger.MAIN,'Applog Agent Started Successfully \n')
                else:
                    AgentLogger.log(AgentLogger.MAIN,'Applog Agent Already running \n')
            else:
                AgentLogger.log(AgentLogger.MAIN, 'Applog Agent upgrade inprogress \n')
        else:
            AgentLogger.log(AgentLogger.MAIN,'Applog Agent file not present \n')
            notify_applog_not_found()
    else:
        AgentLogger.log(AgentLogger.MAIN, "Applog Agent disabled in this server \n")

@exceptionhandler
def notify_applog_not_found():
    dict_requestParameters = {}
    dict_requestParameters['monitorKey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
    dict_requestParameters['deviceKey'] = AgentConstants.CUSTOMER_ID
    dict_requestParameters['type'] = AgentConstants.APPLOG_NOT_FOUND
    dict_requestParameters['status'] = AgentConstants.FAIL
    str_servlet = AgentConstants.APPLOG_NOTIFICATION_SERVLET
    if not dict_requestParameters == None:
        str_requestParameters = urlencode(dict_requestParameters)
        str_url = str_servlet + str_requestParameters
    data={"action":AgentConstants.APPLOG_NOT_FOUND}
    str_dataToSend=json.dumps(data)
    requestInfo = CommunicationHandler.RequestInfo()
    requestInfo.set_loggerName(AgentLogger.STDOUT)
    requestInfo.set_method(AgentConstants.HTTP_POST)
    requestInfo.set_data(str_dataToSend)
    requestInfo.set_url(str_url)
    requestInfo.add_header("Content-Type", 'application/json')
    requestInfo.add_header("Accept", "text/plain")
    requestInfo.add_header("Connection", 'close')
    (isSuccess, int_errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
    AgentLogger.log(AgentLogger.STDOUT,'applog notification call :: response data :: {} error code :: {}'.format(dict_responseData,int_errorCode))

'''
def stop():
    if type(AgentConstants.APPLOG_PROCESS) is subprocess.Popen:
        try:
            AgentConstants.APPLOG_PROCESS.kill()   #kill subprocess
            time.sleep(5)
            AgentConstants.APPLOG_PROCESS.poll()  #poll and inform the os about pid
            force_stop()
            AgentLogger.log(AgentLogger.MAIN,'Applog Agent Stopped')
        except ProcessLookupError:
            AgentLogger.log(AgentLogger.STDOUT,'stop : Applog ProcessLookupError')
            force_stop()
    else:
        AgentLogger.log(AgentLogger.STDOUT,'Applog Agent is not running')
'''

@exceptionhandler
def stop():
    try:
        cmd = "ps -eo pid,comm,args | grep "+("Site24x7Applog" if not AgentConstants.IS_VENV_ACTIVATED else "applog_starter")+" | grep -v grep | awk '{print $1}'"
        boolIsSuccess, processId = AgentUtil.executeCommand(cmd, AgentLogger.STDOUT)
        if boolIsSuccess and processId:
            for pid in processId.split("\n"):
                if pid:
                    AgentLogger.log(AgentLogger.STDOUT,'stop : SIGKILL send to processId :'+str(pid))
                    os.kill(int(pid), signal.SIGKILL)
                    AgentLogger.log(AgentLogger.MAIN,'Applog Agent Stopped')
        else:
            AgentLogger.log(AgentLogger.MAIN,'Applog Agent is not running')
    except Exception:
        traceback.print_exc()

@exceptionhandler
def restart():
    stop()
    start()
    AgentLogger.log(AgentLogger.STDOUT, 'restart : Applog Agent Restarted')

@exceptionhandler
def configure(data):
    with s247_applog_communicator("conf.json.") as fp:
        fp.write(json.dumps(data))
    AgentLogger.log(AgentLogger.STDOUT, 'configure : configuration communicated by s24x7agent')

@exceptionhandler
def install(data):
    deployment_success = True
    check_sum = None
    ack_dict={'action':'Applog Agent Install','msg':'checksum mismatch'}
    if 'checksum' in data:
        check_sum = data['checksum']
    if not os.path.isfile(AgentConstants.APPLOG_EXEC_PATH):
        if 'overRide' in data:
            staticUrl = data['STATIC_URL']
        else:
            staticUrl = get_staticUrl(data['STATIC_URL'])
        file_path=AgentConstants.AGENT_TEMP_DIR+'/applog_agent.zip'
        AgentLogger.log(AgentLogger.STDOUT,'install : Downloading Applog Agent From Static Server {0}'.format(staticUrl))
        bool_DownloadStatus = CommunicationHandler.downloadFile(staticUrl, file_path,logger=AgentLogger.STDOUT,host=AgentConstants.STATIC_SERVER_HOST,checksum=check_sum,ack=ack_dict)
        if not bool_DownloadStatus:
            if 'overRide' in data:
                sagentUrl = data['SAGENT_URL']
            else:
                sagentUrl = get_staticUrl(data['SAGENT_URL'])
            AgentLogger.log(AgentLogger.STDOUT,'install : Downloading Applog Agent From sagent {0}'.format(sagentUrl))
            bool_DownloadStatus = CommunicationHandler.downloadFile(sagentUrl,file_path,logger=AgentLogger.STDOUT,checksum=check_sum,ack=ack_dict)
            if not bool_DownloadStatus:
                AgentLogger.log(AgentLogger.STDOUT,'install : Applog Agent Download Failed')
                deployment_success=False
            else:
                AgentLogger.log(AgentLogger.STDOUT,'install : Applog Agent Download Successfully via sagent')
        else:
            AgentLogger.log(AgentLogger.STDOUT,'install : Applog Agent Download Successfully')

        if deployment_success:
            bool_Unzip=True
            try:
                AgentLogger.log(AgentLogger.STDOUT,'install : Going to extract Applog Agent Zip')
                with ZipManager.ZipManager(file_path) as zfp:
                    zfp.extractall(AgentConstants.AGENT_WORKING_DIR)
            except Exception as e:
                bool_Unzip=False
                AgentLogger.log(AgentLogger.STDOUT,'install : exception while extracting Applog Agent Zip')
                traceback.print_exc()
        if bool_Unzip:
            os.remove(file_path)
            AgentLogger.log(AgentLogger.STDOUT,'install : Applog Agent Zip File Removed Successfully')
            os.chmod(AgentConstants.APPLOG_EXEC_PATH, 0o755)
            start()
    else:
        AgentLogger.log(AgentLogger.STDOUT, 'install : Applog Agent already exist')

@exceptionhandler
def upgrade(data):
    AgentLogger.log(AgentLogger.STDOUT, 'AL_UPGRADE : Upgrade request received')
    check_sum = None
    ack_dict={'action':'Applog Agent Upgrade','msg':'checksum mismatch'}
    if 'checksum' in data:
        check_sum = data['checksum']
    deployment_success = True
    if os.path.isfile(AgentConstants.APPLOG_EXEC_PATH):
        if 'overRide' in data:
            staticUrl = data['STATIC_URL']
        else:
            staticUrl = get_staticUrl(data['STATIC_URL'],upgrade=True)
        file_path=AgentConstants.AGENT_TEMP_DIR+'/applog_agent.zip'
        AgentLogger.log(AgentLogger.STDOUT,'AL_UPGRADE :Downloading Applog Agent From Static Server {0}'.format(staticUrl))
        bool_DownloadStatus = CommunicationHandler.downloadFile(staticUrl,file_path,logger=AgentLogger.STDOUT,host=AgentConstants.STATIC_SERVER_HOST,checksum=check_sum,ack=ack_dict)
        if not bool_DownloadStatus:
            if 'overRide' in data:
                sagentUrl = data['SAGENT_URL']
            else:
                sagentUrl = get_staticUrl(data['SAGENT_URL'], upgrade=True)
            AgentLogger.log(AgentLogger.STDOUT,'AL_UPGRADE :Downloading Applog Agent From sagent {0}'.format(sagentUrl))
            bool_DownloadStatus = CommunicationHandler.downloadFile(sagentUrl,file_path,logger=AgentLogger.STDOUT,checksum=check_sum,ack=ack_dict)
            if not bool_DownloadStatus:
                AgentLogger.log(AgentLogger.STDOUT,'AL_UPGRADE :Applog Agent Download Failed')
                deployment_success=False
            else:
                AgentLogger.log(AgentLogger.STDOUT,'AL_UPGRADE :Applog Agent Download Successfully via sagent')
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AL_UPGRADE :Applog Agent Download Successfully')

        if deployment_success:
            stop()
            AgentLogger.log(AgentLogger.STDOUT,'AL_UPGRADE :Applog Agent Stopped Successfully')
            AgentConstants.APPLOG_UPGRADE_INPROGRESS=True
            try:
                if not os.path.isdir(AgentConstants.AGENT_APPLOG_UPGRADE_DIR):
                    os.mkdir(AgentConstants.AGENT_APPLOG_UPGRADE_DIR)

                AgentLogger.log(AgentLogger.STDOUT,'AL_UPGRADE :Going to extract Applog Agent Zip')
                with ZipManager.ZipManager(file_path) as zfp:
                    zfp.extractall(AgentConstants.AGENT_APPLOG_UPGRADE_DIR)
                AgentLogger.log(AgentLogger.STDOUT,'AL_UPGRADE :Applog Agent Zip extracton completed to {0}'.format(AgentConstants.AGENT_APPLOG_UPGRADE_DIR))
                AgentLogger.log(AgentLogger.STDOUT, 'AL_UPGRADE : Going to copy Applog Agent files from {0} to {1}'.format(AgentConstants.AGENT_APPLOG_UPGRADE_DIR, AgentConstants.AGENT_WORKING_DIR))
                if FileUtil.copyAndOverwriteFolder(AgentConstants.AGENT_APPLOG_UPGRADE_DIR, AgentConstants.AGENT_WORKING_DIR):
                    AgentLogger.log(AgentLogger.STDOUT,'AL_UPGRADE :Applog Agent file copied from {0} to {1}'.format(AgentConstants.AGENT_APPLOG_UPGRADE_DIR, AgentConstants.AGENT_WORKING_DIR))
                    shutil.rmtree(AgentConstants.AGENT_APPLOG_UPGRADE_DIR)
                    AgentLogger.log(AgentLogger.STDOUT,'AL_UPGRADE :Applog Agent upgrade directory({0}) removed'.format(AgentConstants.AGENT_APPLOG_UPGRADE_DIR))
                    os.remove(file_path)
                    AgentLogger.log(AgentLogger.STDOUT,'AL_UPGRADE :Applog Agent Zip File({0}) Removed Successfully'.format(file_path))
                    postUpgrade()
                    AgentLogger.log(AgentLogger.STDOUT, 'AL_UPGRADE : Upgrade completed')
                else:
                    AgentLogger.log(AgentLogger.STDOUT, 'AL_UPGRADE :Problem in coping Applog Agent file to workdir')
            except Exception as e:
                AgentLogger.log(AgentLogger.STDOUT,'AL_UPGRADE :exception while extracting Applog Agent Zip')
                traceback.print_exc()
            AgentConstants.APPLOG_UPGRADE_INPROGRESS=False
            os.chmod(AgentConstants.APPLOG_EXEC_PATH, 0o755)
            start()
            AgentLogger.log(AgentLogger.STDOUT, 'AL_UPGRADE : Agent started after upgrade')
    else:
        AgentLogger.log(AgentLogger.STDOUT, 'AL_UPGRADE :Applog Agent not exist')


def postUpgrade():
    try:
        if os.path.isfile(AgentConstants.APPLOG_EXEC_HOME+ '/array.cpython-33m.so') or os.path.isfile(AgentConstants.APPLOG_EXEC_HOME+ '/lib/libcrypto.so.3'):
            ''' Removing .so files inside the lib folder due to cx_freeze module update for TLS1.2 support'''
            cmd = "rm -rf "+ AgentConstants.APPLOG_EXEC_HOME + "/*.so*"
            AgentUtil.executeCommand(cmd, AgentLogger.STDOUT)
            AgentLogger.log(AgentLogger.STDOUT,'postUpgrade : Old .so files removed successfully')
    except Exception as e:
        pass

def get_staticUrl(staticUrl,upgrade=False):
    if AgentConstants.IS_VENV_ACTIVATED:
        return staticUrl[:staticUrl.rindex('/')] + '/applog_source_agent.zip'
    elif platform.architecture()[0] == '32bit':
        if upgrade:
            return staticUrl[:staticUrl.rindex('/')] + '/applog_linux32_upgrade.zip'
        return staticUrl[:staticUrl.rindex('/')] + '/applog_linux32.zip'
    elif str(platform.machine()) in ["arm64", "aarch64", "ARM", "Arm", "aarch"]:
        if upgrade:
            return staticUrl[:staticUrl.rindex('/')] + '/applog_linux64_arm_upgrade.zip'
        return staticUrl[:staticUrl.rindex('/')] + '/applog_linux64_arm.zip'
    else:
        if upgrade:
            return staticUrl[:staticUrl.rindex('/')] + '/applog_linux64_upgrade.zip'
        return staticUrl[:staticUrl.rindex('/')] + '/applog_linux64.zip'