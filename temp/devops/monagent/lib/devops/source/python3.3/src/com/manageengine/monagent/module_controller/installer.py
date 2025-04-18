'''
Created on 27-December-2017

@author: giri
'''

from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger

import subprocess
import pkgutil
import os
import signal 
import traceback
import time

if AgentConstants.IS_VENV_ACTIVATED and not os.path.isdir(AgentConstants.AGENT_PIP_INSTALL_LOG_DIR):
    os.mkdir(AgentConstants.AGENT_PIP_INSTALL_LOG_DIR)

def mod_attendance(mod_name):
    _status = False
    try:
        if pkgutil.find_loader(mod_name):
            _status = True
    except Exception as e:
        pass
    finally:
        return _status

def cmd_executor(cmd, timeout=90):
    _is_terminated, timeout_counter, proc = False, 0, None
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        proc_id = proc.pid
        while  timeout_counter <= timeout:      
            timeout_counter += 1
            time.sleep(1)
            if not proc.poll() is None:
                _is_terminated = True
                break
        if not _is_terminated:
            os.killpg(os.getpgid(proc_id), signal.SIGKILL)
    except Exception as e:
        traceback.print_exc()
    finally:
        if type(proc) is subprocess.Popen:
            if proc:
                proc.kill()
                proc.poll()
            else:
                AgentLogger.log(AgentLogger.LT, "proc object is none".format(cmd))
                      

def install_package(package_name):
    _status, _msg, cmd = False, "", "{} -m pip install {} >> {}".format(AgentConstants.AGENT_VENV_BIN_PYTHON, package_name, os.path.join(AgentConstants.AGENT_PIP_INSTALL_LOG_DIR, "package_installer.log"))
    try:
        if AgentConstants.IS_VENV_ACTIVATED is True:
            '''Install using pip'''
            if not mod_attendance(package_name):
                cmd_executor(cmd)
                if mod_attendance(package_name):
                    AgentLogger.log(AgentLogger.LT, " {0} module present".format(package_name))
                    _status = True
                else:
                    AgentLogger.log(AgentLogger.LT, "{0} module not present".format(package_name))
                
            else:
                _status = True
                AgentLogger.log(AgentLogger.LT, "{0} already present".format(package_name))
            
    except Exception as e:
        traceback.print_exc()
    finally:
        return _status