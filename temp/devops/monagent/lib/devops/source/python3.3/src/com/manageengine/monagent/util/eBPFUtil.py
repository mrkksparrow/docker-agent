# $Id$
import os
import platform
import sys
import subprocess
import shutil
import signal
import time
import threading
import traceback
import json
from six.moves.urllib.parse import urlencode
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser
from datetime import datetime

import com
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from . import ZipManager, AgentUtil, AgentArchiver
from com.manageengine.monagent.util.AgentUtil import FileUtil

def initialize(restart=False):
    try:
        if AgentUtil.is_module_enabled(AgentConstants.EBPF_SETTING):
            if AgentConstants.EBPF_PROCESS is None or restart:
                if os.path.exists(AgentConstants.EBPF_EXEC_PATH):
                    if os.path.exists(os.path.join(AgentConstants.EBPF_EXEC_HOME,'temp','eBPF.lock')):
                        stop()
                    AgentUtil.updateEbpfProcessInterval()
                    AgentConstants.EBPF_PROCESS = subprocess.Popen(AgentConstants.EBPF_EXEC_PATH, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    AgentLogger.log(AgentLogger.MAIN,'eBPF process - Success - {} '.format(str(AgentConstants.EBPF_PROCESS.pid)))
                else:
                    AgentLogger.log(AgentLogger.MAIN,'eBPF Binary File not found :: {} '.format(AgentConstants.EBPF_EXEC_PATH))
        else:
            AgentLogger.log(AgentLogger.MAIN,' eBPF Status :: {} '.format(AgentConstants.EBPF_ENABLED))
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'***** Exception while initializing eBPF process :: Error - {} *****'.format(e))
        traceback.print_exc()


def remove_ebpf_agent():
    try:
        AgentLogger.log(AgentLogger.MAIN,'===== Removing eBPF binary from agent =====')
        stop()
        if os.path.exists(AgentConstants.EBPF_EXEC_PATH):
            try:
                shutil.rmtree(AgentConstants.EBPF_EXEC_HOME)
            except Exception as e:
                AgentLogger.log(AgentLogger.MAIN,'***** Exception while removing eBPF module :: Error - {} *****'.format(e))
                traceback.print_exc()
        else:
            AgentLogger.log(AgentLogger.MAIN,'===== eBPF module already removed =====')
        AgentConstants.AGENT_SETTINGS["ebpf"] = "0"

    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'***** Exception while removing eBPF binary :: Error - {} *****'.format(e))
        traceback.print_exc()

def checkEbpfRequirement():
    bool_success = False
    message = None
    try:
        kernal_model = platform.release()
        if "oem" not in kernal_model:
            kernal_version = kernal_model.split("-")[0]
            if kernal_version >= "4.16.0":
                bool_success =True
            else:
                message = "kernal version not compatible - {}".format(kernal_model)
        else:
            message = "kernal version not compatible - {}".format(kernal_model)

    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,'***** Exception while Checking eBPF Requirement :: Error - {} *****'.format(e))
        traceback.print_exc()
        message = "exception while checking ebpf - {}".format(str(e))
    finally:
        return bool_success, message

def ack_ebpf_install_status(message):
    try:
        str_servlet = AgentConstants.DATA_AGENT_HANDLER_SERVLET
        dict_requestParameters = {
            'action'   :   "EBPF_INSTALL",
            'agentKey'  :   AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key'),
            'bno' : AgentConstants.AGENT_VERSION,
            'custID'  :   AgentConstants.CUSTOMER_ID,
            'message' :  message
        }

        str_requestParameters = urlencode(dict_requestParameters)
        str_url = str_servlet + str_requestParameters

        requestInfo = com.manageengine.monagent.communication.CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.MAIN)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        bool_toReturn, int_errorCode, dict_responseHeaders, dict_responseData = com.manageengine.monagent.communication.CommunicationHandler.sendRequest(requestInfo)
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,'***** Exception while Acknowlwdging eBPF installation :: Error - {} *****'.format(e))
        traceback.print_exc()

def upgrade_ebpf_agent(dict_data):
    try:
        AgentLogger.log(AgentLogger.MAIN, 'EBPF_UPGRADE : Upgrade request received')
        bool_success = False
        message = None
        bool_success, message = checkEbpfRequirement()
        if bool_success:
            # download ebpf binary zip from server
            check_sum = None
            deployment_success=True
            ack_dict={'action':'eBPF Agent Install','msg':'checksum mismatch'}
            if 'checksum' in dict_data:
                check_sum = dict_data['checksum']
            staticUrl = dict_data['STATIC_URL']
            file_path=AgentConstants.AGENT_TEMP_DIR+'/Site24x7_Ebpf_Agent.zip'
            AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE : Downloading eBPF Agent From Static Server {0}'.format(staticUrl))
            bool_DownloadStatus = com.manageengine.monagent.communication.CommunicationHandler.downloadFile(staticUrl, file_path,logger=AgentLogger.MAIN,host=AgentConstants.STATIC_SERVER_HOST,checksum=check_sum,ack=ack_dict)
            if bool_DownloadStatus:
                deployment_success=False
                backup_stored = True
                # check whether ebpf not installed, new installation
                if not os.path.exists(AgentConstants.EBPF_EXEC_HOME) or not os.path.exists(AgentConstants.EBPF_EXEC_PATH):
                    AgentLogger.log(AgentLogger.MAIN, 'EBPF_UPGRADE : eBPF agent not present, clearing ebpf dir')
                    if os.path.exists(AgentConstants.EBPF_EXEC_HOME):
                        shutil.rmtree(AgentConstants.EBPF_EXEC_HOME)
                    os.mkdir(AgentConstants.EBPF_EXEC_HOME)
                    backup_stored = False
                else:
                    # take ebpf dir backup
                    AgentLogger.log(AgentLogger.MAIN, 'EBPF_UPGRADE : eBPF agent binary present, taking backup')
                    if os.path.exists(AgentConstants.EBPF_AGENT_UPGRADE_BACKUP_DIR):
                        shutil.rmtree(AgentConstants.EBPF_AGENT_UPGRADE_BACKUP_DIR)
                    shutil.copytree(AgentConstants.EBPF_EXEC_HOME, AgentConstants.EBPF_AGENT_UPGRADE_BACKUP_DIR)

                stop()
                AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :eBPF Agent Stopped Successfully')

                if os.path.exists(AgentConstants.EBPF_AGENT_UPGRADE_DIR):
                    shutil.rmtree(AgentConstants.EBPF_AGENT_UPGRADE_DIR)
                os.mkdir(AgentConstants.EBPF_AGENT_UPGRADE_DIR)
                try:
                    from zipfile import ZipFile
                    zip = ZipFile(file_path)
                    zip.extractall(AgentConstants.EBPF_AGENT_UPGRADE_DIR)
                    AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :unzipped eBPF Agent Zip successfully')

                    if FileUtil.copyAndOverwriteFolder(AgentConstants.EBPF_AGENT_UPGRADE_DIR, AgentConstants.EBPF_EXEC_HOME):
                        AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :eBPF Agent file copied from {0} to {1}'.format(AgentConstants.EBPF_AGENT_UPGRADE_DIR, AgentConstants.EBPF_EXEC_HOME))
                        try:
                            os.chmod(AgentConstants.EBPF_EXEC_PATH, 0o755)
                            AgentLogger.log(AgentLogger.MAIN, 'EBPF_UPGRADE : eBPF Agent setted with executable permission')
                        except Exception as e:
                            AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :***** exception while setting permission for eBPF Agent Binary ***** :: {}'.format(e))
                            traceback.print_exc()
                    else:
                        bool_success = False
                        message = "failed to setup ebpf binary"
                        AgentLogger.log(AgentLogger.MAIN, 'EBPF_UPGRADE :Problem in coping eBPF Agent file to workdir :: {} -> {}'.format(AgentConstants.EBPF_AGENT_UPGRADE_DIR, AgentConstants.EBPF_EXEC_HOME))
                except Exception as e:
                    bool_success=False
                    message = "exception in extracting ebpf zip - {}".format(str(e))
                    AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :***** exception while unzipping :: {} *****'.format(file_path))
                    traceback.print_exc()

                if not bool_success and backup_stored:
                    shutil.rmtree(AgentConstants.EBPF_EXEC_HOME)
                    os.mkdir(AgentConstants.EBPF_EXEC_HOME)
                    AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :clearing failed upgrade binary')
                    FileUtil.copyAndOverwriteFolder(AgentConstants.EBPF_AGENT_UPGRADE_BACKUP_DIR, AgentConstants.EBPF_EXEC_HOME)
                    AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :upgrade failed, restored backup')
                    try:
                        os.chmod(AgentConstants.EBPF_EXEC_PATH, 0o755)
                        AgentLogger.log(AgentLogger.MAIN, 'EBPF_UPGRADE : eBPF Agent setted with executable permission')
                    except Exception as e:
                        AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :***** exception while setting permission for eBPF Agent Binary ***** :: {}'.format(e))
                        traceback.print_exc()
                elif not bool_success and not backup_stored:
                    AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :ebpf agent was not installed, and new upgrade failed')
                else:
                    AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :ebpf agent upgraded successfully')
                    AgentConstants.AGENT_SETTINGS["ebpf"] = "1"

                if os.path.exists(AgentConstants.EBPF_AGENT_UPGRADE_DIR):
                    shutil.rmtree(AgentConstants.EBPF_AGENT_UPGRADE_DIR)
                    AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :eBPF Agent upgrade directory({0}) removed'.format(AgentConstants.EBPF_AGENT_UPGRADE_DIR))
                if os.path.exists(file_path):
                    os.remove(file_path)
                    AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :eBPF Agent Zip File({0}) Removed Successfully'.format(file_path))
                if os.path.exists(AgentConstants.EBPF_AGENT_UPGRADE_BACKUP_DIR):
                    shutil.rmtree(AgentConstants.EBPF_AGENT_UPGRADE_BACKUP_DIR)
                    AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :eBPF Agent backup folder ({0}) Removed Successfully'.format(AgentConstants.EBPF_AGENT_UPGRADE_BACKUP_DIR))
                initialize()
            else:
                AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :***** ebpf zip download failed :: {} *****'.format(bool_DownloadStatus))
                message = "ebpf file download failed"
                bool_success = False
        if (not bool_success) or (message is not None):
            AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :***** {} *****'.format(message))
            ack_ebpf_install_status(message)
            AgentLogger.log(AgentLogger.MAIN,'EBPF_UPGRADE :***** Enabling ADDM Netstat DC *****')
            AgentUtil.edit_monitorsgroup('ADDM', 'enable')
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,'***** Exception while installing eBPF binary :: Error - {} *****'.format(e))
        traceback.print_exc()


def stop():
    try:
        cmd = "ps -eo pid,comm,args | grep Site24x7EbpfAgent | grep -v grep | awk '{print $1}'"
        boolIsSuccess, processId = AgentUtil.executeCommand(cmd, AgentLogger.STDOUT)
        if boolIsSuccess and processId:
            for pid in processId.split("\n"):
                if pid:
                    AgentLogger.log(AgentLogger.MAIN,'stop : SIGKILL send to processId :'+str(pid))
                    os.kill(int(pid), signal.SIGKILL)
                    if os.path.exists(os.path.join(AgentConstants.EBPF_EXEC_HOME,'temp','eBPF.lock')):
                        os.remove(os.path.join(AgentConstants.EBPF_EXEC_HOME,'temp','eBPF.lock'))
                    AgentLogger.log(AgentLogger.MAIN,'eBPF Agent Stopped')
        else:
            AgentLogger.log(AgentLogger.MAIN,'eBPF Agent is not running')
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,'***** Exception while stopping eBPF process :: Error - {} *****'.format(e))
        traceback.print_exc()
    finally:
        AgentConstants.EBPF_PROCESS = None