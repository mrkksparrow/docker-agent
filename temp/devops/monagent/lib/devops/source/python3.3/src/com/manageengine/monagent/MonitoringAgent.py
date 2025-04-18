#$Id$
import traceback
import threading
import subprocess
from datetime import datetime
import signal
import time
import os
import stat
import fcntl
import sys

try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

AGENT_SRC_CHECK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[0]))))
splitted_paths = os.path.split(AGENT_SRC_CHECK)
if splitted_paths[1].lower() == "com":
    AGENT_SOURCE_DIR = os.path.dirname(AGENT_SRC_CHECK)
    sys.path.append(AGENT_SOURCE_DIR)

from com.manageengine.monagent import AgentConstants

from com.manageengine import monagent

from com.manageengine.monagent.logger import AgentLogger
AgentLogger.initialize(AgentConstants.AGENT_LOGGING_CONF_FILE, AgentConstants.AGENT_LOG_DIR)
AgentLogger.log(AgentLogger.MAIN,'====================================================== STARTING AGENT ====================================================== \n\n')
from com.manageengine.monagent import AgentInitializer
from com.manageengine.monagent import module_checker
from com.manageengine.monagent.util import AgentUtil, AgentBuffer, eBPFUtil
from com.manageengine.monagent.util.AgentUtil import write_pid_to_pidfile


MON_AGENT_WATCHDOG_DETAILS_COMMAND = AgentConstants.AGENT_SCRIPTS_DIR + '/agentwatchdogdetails.sh'

def parseProcDetails(strOutput):
    tempDict = {}
    try:
        listOutput = strOutput.split()
        tempDict.setdefault('pcpu', listOutput[2])
        tempDict.setdefault('pmem', listOutput[3])
        tempDict.setdefault('threads', listOutput[4])
        tempDict.setdefault('pArgs', str(listOutput[7]).replace('\n',''))
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,' *************************** Exception while parsing process output details *************************** '+ repr(e))
        traceback.print_exc()
    finally:
        return tempDict

def monitorService():
    try:
        isBoolSuccess, strOutput = AgentUtil.executeCommand(MON_AGENT_WATCHDOG_DETAILS_COMMAND, AgentLogger.MAIN, 5)
        if (not AgentConstants.BOOL_AGENT_UPGRADE) and AgentConstants.IS_DOCKER_AGENT == '0':
            if isBoolSuccess and strOutput:
                dictProcessDetails = parseProcDetails(strOutput)
                AgentLogger.debug(AgentLogger.CRITICAL,'agent process check :: {}'.format(dictProcessDetails))
                if ( (float(dictProcessDetails['pcpu']) > AgentUtil.AGENT_CPU_THRESHOLD) or (float(dictProcessDetails['pmem']) > AgentUtil.AGENT_MEMORY_THRESHOLD) or (float(dictProcessDetails['threads']) > AgentUtil.AGENT_THREAD_THRESHOLD)):
                    AgentLogger.log(AgentLogger.MAIN,' output of '+MON_AGENT_WATCHDOG_DETAILS_COMMAND+' --> ' + strOutput)
                    AgentLogger.log(AgentLogger.MAIN,'Watchdog consumption threshold violated !!!!')
                    AgentUtil.restartWatchdog()
            else:
                AgentLogger.log(AgentLogger.MAIN,'watchdog process is not running..')
                AgentUtil.restartWatchdog()
        if AgentUtil.is_module_enabled(AgentConstants.EBPF_SETTING):
            restart_needed = True
            ebpf_status_cmd = "/bin/ps -ef | grep Site24x7Ebpf | grep -v grep"
            isBoolSuccess, strOutput = AgentUtil.executeCommand(ebpf_status_cmd, AgentLogger.MAIN, 5)
            for each_process in str(strOutput).split("\n"):
                if each_process:
                    if "<defunct>" in str(each_process):
                        AgentLogger.log(AgentLogger.MAIN,'defunct ebpf process found, silently restarting agent => {}'.format(str(each_process)))
                        str_uninstallTime = 'Restart : '+repr(datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S"))
                        file_obj = open(AgentConstants.AGENT_WATCHDOG_SILENT_RESTART_FLAG_FILE,'w')
                        file_obj.write(str_uninstallTime)
                        AgentUtil.create_file(AgentConstants.AGENT_RESTART_FLAG_FILE)
                        restart_needed = False
                    elif AgentConstants.EBPF_PROCESS and str(AgentConstants.EBPF_PROCESS.pid) not in str(each_process):
                        AgentLogger.log(AgentLogger.MAIN,'duplicate dummy ebpf process found, killing the process => {} :: {}'.format(str(AgentConstants.EBPF_PROCESS.pid),str(each_process)))
                        dummpy_proc_pid = str(each_process).split()[1]
                        os.kill(int(dummpy_proc_pid), signal.SIGKILL)
                    elif AgentConstants.EBPF_PROCESS and str(AgentConstants.EBPF_PROCESS.pid) in str(each_process):
                        restart_needed = False
            if restart_needed:
                eBPFUtil.initialize(True)


    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,'******* Exception while checking watchdog details by agent ***********{}'.format(traceback.format_exc()))
        traceback.print_exc()

class AgentService(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.name = 'AgentServiceThread'

    def run(self):
        try:
            time.sleep(20)
            while not AgentUtil.TERMINATE_AGENT:
                try:
                    time.sleep(AgentUtil.AGENT_CHECK_INTERVAL) # This wait is before monitorService() to avoid the race condition in starting agent service via /etc/init.d
                    monitorService()
                except Exception as e:
                    AgentLogger.log(AgentLogger.STDERR,' *************************** Exception while running watchdog service thread *************************** '+ repr(e))
                    traceback.print_exc()
        except Exception as e:
            AgentLogger.log(AgentLogger.STDERR,' *************************** Exception while executing watchdog service thread *************************** '+ repr(e))
            traceback.print_exc()

def init_watchdog_watcher():
    try:
        agentServiceThread = AgentService()
        agentServiceThread.start()
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,'\n ************************* Problem While Initializing Watchdog Watcher ************************* ')
        traceback.print_exc()

# Daemon Threads:
#    Memory Manager
#    Status Thread

# Non-Daemon Threads:(Must complete the specified task and then terminate)
#    Scheduler and its Worker Threads
#    File Uploader
#    Request Server Thread

def init_agent():
    try:
        AgentConstants.APPLICATION_LOCK = open(AgentConstants.AGENT_LOCK_FILE, 'w')
        try:
            os.chmod(AgentConstants.AGENT_LOCK_FILE, 0o755)
            fcntl.lockf(AgentConstants.APPLICATION_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
            AgentConstants.APPLICATION_LOCK.write(AgentConstants.AGENT_USER_NAME)
            AgentConstants.APPLICATION_LOCK.flush()
        except IOError:
            print('Site24x7 monitoring agent is already running')
            sys.exit(1)
    except Exception as e:
        print('Please login as root or use sudo to run Site24x7 monitoring agent')
        traceback.print_exc()
        sys.exit(1)


def agent_main():
    try:
        #check if uninstall flag file is present
        if os.path.exists(AgentConstants.AGENT_UNINSTALL_FLAG_FILE):
            AgentLogger.log(AgentLogger.MAIN,'\n ======================================= UNINSTALL MONITORING AGENT ======================================= ')
            return False
        #pid file handler
        if os.path.exists(AgentConstants.AGENT_LOG_DETAIL_DIR+'/monagent_pid'):
            AgentLogger.log(AgentLogger.MAIN,' monagent_pid file exists deleting the same \n')
            os.remove(AgentConstants.AGENT_LOG_DETAIL_DIR+'/monagent_pid')
        write_pid_to_pidfile(AgentConstants.AGENT_LOG_DETAIL_DIR+'/monagent_pid')
        #shutdown listener
        AgentUtil.shutdownListener()
        if not AgentInitializer.initialize():
            AgentLogger.log([AgentLogger.MAIN, AgentLogger.CRITICAL],'\n ************************* Problem While Initializing Agent. Hence Quiting!!! ************************* ')
            return False        
    except Exception as e:
        AgentLogger.log([AgentLogger.MAIN, AgentLogger.CRITICAL],'\n *************************** Exception While Initializing Agent *************************** '+ repr(e))
        traceback.print_exc()
        return False         
    return True


def start_agent():
    init_agent()
    #FIXME: This is a temporary fix to not run watchdog watcher for source agent
    if not AgentConstants.IS_VENV_ACTIVATED:
        init_watchdog_watcher()
    
    try:
        if not agent_main():
            AgentLogger.log([AgentLogger.MAIN,AgentLogger.CRITICAL],'************************* PROBLEM WHILE STARTING AGENT. HENCE QUITING!!! ************************* ')
        else:
            AgentLogger.log(AgentLogger.MAIN,'=============================== AGENT STARTED SUCCESSFULLY =============================== \n')
            while not AgentUtil.TERMINATE_AGENT:                        
                AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(AgentConstants.AGENT_SLEEP_INTERVAL)
                # Prevent conf backup when shutdown is initiated.
                if not AgentUtil.TERMINATE_AGENT:
                    AgentUtil.backupConfFile()
    except Exception as e:        
        AgentLogger.log(AgentLogger.CRITICAL,'************************* PROBLEM WHILE STARTING AGENT. HENCE QUITING!!! ************************* '+ repr(e))
        traceback.print_exc()
    finally:
        AgentUtil.TerminateAgent()
        AgentUtil.cleanAll()


start_agent()
    
