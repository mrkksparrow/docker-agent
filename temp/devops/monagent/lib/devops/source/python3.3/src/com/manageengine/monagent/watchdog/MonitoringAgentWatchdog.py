# $Id$
import sys

import os
import stat
import logging
import logging.handlers
import time
import threading
import platform

try:
    import configparser
except Exception as e:
    import ConfigParser as configparser
import traceback
import subprocess, signal
from six.moves.urllib.parse import urlencode
from datetime import datetime

AGENT_SRC_CHECK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[0])))))
splitted_paths = os.path.split(AGENT_SRC_CHECK)
if splitted_paths[1].lower() == "com":
    IS_VENV_ACTIVATED = True
    AGENT_SOURCE_DIR = os.path.dirname(AGENT_SRC_CHECK)
    sys.path.append(AGENT_SOURCE_DIR)
    
import com    
from com.manageengine.monagent import AgentConstants
import fcntl
try:
    AgentConstants.WATCHDOG_APPLICATION_LOCK = open(AgentConstants.AGENT_WATCHDOG_LOCK_FILE, 'w')
    try:
        os.chmod(AgentConstants.AGENT_WATCHDOG_LOCK_FILE, 0o755)
        fcntl.lockf(AgentConstants.WATCHDOG_APPLICATION_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print('Site24x7 monitoring agent watchdog is already running')
        sys.exit(1)
except Exception as e:
    print('Please login as root or use sudo to run Site24x7 monitoring agent watchdog')
    traceback.print_exc()
    sys.exit(1)

from com.manageengine.monagent import watchdog
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentArchiver
#from com.manageengine.monagent.communication import CommunicationHandler

#Watchdog Constants
MON_AGENT_WORKING_DIR = AgentConstants.AGENT_WORKING_DIR

MON_AGENT_BIN_DIR = MON_AGENT_WORKING_DIR + '/bin'
MON_AGENT_LOG_DIR = MON_AGENT_WORKING_DIR + '/logs'
MON_AGENT_DETAILS_LOG_DIR = MON_AGENT_LOG_DIR + '/details'
MON_AGENT_CONF_DIR = MON_AGENT_WORKING_DIR + '/conf'
MON_AGENT_UPGRADE_DIR = MON_AGENT_WORKING_DIR + '/upgrade'
MON_AGENT_BACKUP_DIR = MON_AGENT_WORKING_DIR + '/backup'
MON_AGENT_TEMP_DIR = MON_AGENT_WORKING_DIR + '/temp'
MON_AGENT_UPGRADE_FLAG_FILE = MON_AGENT_UPGRADE_DIR + '/upgrade.txt'
MON_AGENT_UPGRADED_FLAG_FILE = MON_AGENT_TEMP_DIR + '/monagent_upgraded.txt'

MON_AGENT_WATCHDOG_CONF_FILE = MON_AGENT_CONF_DIR+'/monagentwatchdog.cfg'

MON_AGENT_WATCHDOG_SLEEP_INTERVAL = 60

MON_AGENT_STOP_RETRY_COUNT = 5

MON_AGENT_BOOT_FILE = MON_AGENT_BIN_DIR + '/monagent'
MON_AGENT_WATCHDOG_BOOT_FILE = MON_AGENT_BIN_DIR + '/monagentwatchdog'
MON_AGENT_UPGRADE_SCRIPT = MON_AGENT_BIN_DIR + '/upgrade.sh'
HYBRID_AGENT_UPGRADE_SCRIPT = os.path.join(MON_AGENT_BIN_DIR, "hybrid_upgrade")

MON_AGENT_START = 'start'
MON_AGENT_STOP = 'stop'
MON_AGENT_STATUS = 'status'
MON_AGENT_RESTART = 'restart'

MON_AGENT_WATCHDOG_SERVICE_UP_MESSAGE='monitoring agent watchdog service is up'
MON_AGENT_WATCHDOG_SERVICE_DOWN_MESSAGE='monitoring agent watchdog service is down'
MON_AGENT_WATCHDOG_SERVICE_STARTED_MESSAGE='monitoring agent watchdog service started successfully'
MON_AGENT_WATCHDOG_SERVICE_STOPPED_MESSAGE='monitoring agent watchdog service stopped successfully'

MON_AGENT_SERVICE_UP_MESSAGE='monitoring agent service is up'
MON_AGENT_SERVICE_DOWN_MESSAGE='monitoring agent service is down'
MON_AGENT_SERVICE_STARTED_MESSAGE='monitoring agent service started successfully'
MON_AGENT_SERVICE_STOPPED_MESSAGE='monitoring agent service stopped successfully'

MON_AGENT_START_COMMAND = MON_AGENT_BOOT_FILE+' '+MON_AGENT_START
MON_AGENT_STOP_COMMAND = MON_AGENT_BOOT_FILE+' '+MON_AGENT_STOP
MON_AGENT_STATUS_COMMAND = MON_AGENT_BOOT_FILE+' '+MON_AGENT_STATUS
MON_AGENT_RESTART_COMMAND = MON_AGENT_BOOT_FILE+' '+MON_AGENT_RESTART
MON_AGENT_DETAILS_COMMAND = AgentConstants.AGENT_SCRIPTS_DIR + '/agentdetails.sh'
MON_AGENT_WATCHDOG_DETAILS_COMMAND = AgentConstants.AGENT_SCRIPTS_DIR + '/agentwatchdogdetails.sh'

DETAILS_COMMAND_LIST = []
DETAILS_COMMAND_LIST.append(MON_AGENT_DETAILS_COMMAND)
DETAILS_COMMAND_LIST.append(MON_AGENT_WATCHDOG_DETAILS_COMMAND)

TERMINATE_WATCHDOG = False
TERMINATE_WATCHDOG_NOTIFIER = threading.Event()

WatchdogConfig = None
#print('PATH : ',sys.path)

AGENT_CONFIG = configparser.RawConfigParser()
AGENT_CONFIG.read(AgentConstants.AGENT_CONF_FILE)

UPDATE_INTERVAL = 3600

RESTART_TIME = None

AGENT_MEMORY_THRESHOLD = 5

AGENT_CPU_THRESHOLD = 25

AGENT_THREAD_THRESHOLD = 50

AGENT_ZOMBIES_THRESHOLD = 200

SYSCLOCK_INTERVAL = 60

AGENT_PID = None

SITE24X7_AGENT_HEARTBEAT_TIME = 0

SITE24X7_AGENT_HEARTBEAT_TIME_LATEST = 0

str_osname = platform.system()
str_architecture = platform.architecture()[0] 
if str_osname.lower() == AgentConstants.LINUX_OS_LOWERCASE:
    AgentConstants.OS_NAME = AgentConstants.LINUX_OS
else:
    AgentConstants.OS_NAME = str_osname.lower()

def main():    
    try:
        initialize()
        CLOCK_MONITOR = SysClockMonitor()
        CLOCK_MONITOR.setDaemon(True)
        CLOCK_MONITOR.start()
        watchdogServiceThread = WatchdogService()
        watchdogServiceThread.start()     
        while not TERMINATE_WATCHDOG:                      
            TERMINATE_WATCHDOG_NOTIFIER.wait(MON_AGENT_WATCHDOG_SLEEP_INTERVAL)                
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,' *************************** Exception while starting watchdog service *************************** '+ repr(e))
        traceback.print_exc()

def initialize():
    global WatchdogConfig, MON_AGENT_WATCHDOG_SLEEP_INTERVAL,AGENT_CPU_THRESHOLD,AGENT_MEMORY_THRESHOLD,AGENT_THREAD_THRESHOLD,AGENT_ZOMBIES_THRESHOLD,UPDATE_INTERVAL, SYSCLOCK_INTERVAL
    AgentLogger.initialize(AgentConstants.WATCHDOG_LOGGING_CONF_FILE, AgentConstants.AGENT_LOG_DIR)
    from com.manageengine.monagent.util.AgentUtil import write_pid_to_pidfile
    AgentLogger.log(AgentLogger.STDOUT,'========================== STARTING MONITORING AGENT WATCHDOG ================================ \n\n')
    if os.path.exists(AgentConstants.AGENT_LOG_DETAIL_DIR+'/monagent_watchdog_pid'):
        AgentLogger.log(AgentLogger.STDOUT,' monagent_watchdog_pid file exists deleting the same \n')
        os.remove(AgentConstants.AGENT_LOG_DETAIL_DIR+'/monagent_watchdog_pid')
    write_pid_to_pidfile(AgentConstants.AGENT_LOG_DETAIL_DIR+'/monagent_watchdog_pid')
    WatchdogConfig = configparser.RawConfigParser()
    WatchdogConfig.read(MON_AGENT_WATCHDOG_CONF_FILE)
    if not os.path.exists(MON_AGENT_LOG_DIR):
        os.makedirs(MON_AGENT_LOG_DIR)
    if not os.path.exists(MON_AGENT_DETAILS_LOG_DIR):
        os.makedirs(MON_AGENT_DETAILS_LOG_DIR)
    if WatchdogConfig.has_section('WATCHDOG_PARAMS'):
        MON_AGENT_WATCHDOG_SLEEP_INTERVAL = int(WatchdogConfig.get('WATCHDOG_PARAMS','WATCHDOG_INTERVAL'))
    AgentLogger.log(AgentLogger.STDOUT,'WATCHDOG CONSTANTS :')            
    list_sections = WatchdogConfig.sections()
    for sec in list_sections:
        for key, value in WatchdogConfig.items(sec):
            AgentLogger.log(AgentLogger.STDOUT,key+' : '+repr(value))
    if WatchdogConfig.has_section('AGENT_THRESHOLD'):
        AGENT_CPU_THRESHOLD = float(WatchdogConfig.get('AGENT_THRESHOLD','CPU'))
        AGENT_MEMORY_THRESHOLD = float(WatchdogConfig.get('AGENT_THRESHOLD','MEMORY'))
        AGENT_THREAD_THRESHOLD = int(WatchdogConfig.get('AGENT_THRESHOLD','THREADS'))
        AGENT_ZOMBIES_THRESHOLD = int(WatchdogConfig.get('AGENT_THRESHOLD','ZOMBIES'))     
        UPDATE_INTERVAL = int(WatchdogConfig.get('AGENT_THRESHOLD','UPDATE_INTERVAL'))
        SYSCLOCK_INTERVAL = int(WatchdogConfig.get('AGENT_THRESHOLD','SYSCLOCK_INTERVAL', fallback=60))

def is_hybrid_agent_running():
    cmd = "ps auxww | grep MonitoringAgent.py | grep -v grep | awk '/ / {print $2}'"
    _status, _output = executeCommand(cmd)
    return _status, _output

def is_agent_running():
    cmd = "ps -eo pid,comm,args | grep Site24x7Agent | grep -v grep | grep -v Site24x7AgentWatchdog | awk '{print $1}'"
    _status, _output = executeCommand(cmd)
    return _status, _output
    
def TerminateWatchdogService():
    global TERMINATE_WATCHDOG
    if not TERMINATE_WATCHDOG:
        AgentLogger.log(AgentLogger.STDOUT,'TERMINATE WATCHDOG : ======================================== SHUTTING DOWN WATCHDOG SERVICE ========================================')
        TERMINATE_WATCHDOG = True
        TERMINATE_WATCHDOG_NOTIFIER.set()# checking interval in seconds

def executeCommand(str_command, int_timeout=14):    
    bool_isSuccess = False
    str_CommandOutput = None
    int_timeoutCounter = 0
    isTerminated = False
    def captureOutput(process):
        isSuccess = False
        out, err = process.communicate()
        if process.returncode is not None:
            AgentLogger.debug(AgentLogger.STDOUT,'Return code : '+str(process.returncode)+' Command \''+str(str_command)+'\' executed successfully')
            isSuccess = True
            output = out
        else:
            AgentLogger.log(AgentLogger.STDOUT,'Return code : '+str(process.returncode)+' Error while executing the command \''+str(str_command)+'\'')
            isSuccess = False
            output = err    
        return isSuccess, output
    list_commandArgs = [str_command]
    proc = subprocess.Popen(list_commandArgs, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, env={"COLUMNS":"500"} if not str_command == HYBRID_AGENT_UPGRADE_SCRIPT else {"COLUMNS":"500", "PYTHON_VENV_BIN_PATH":AgentConstants.AGENT_VENV_BIN_PYTHON,"MON_AGENT_HOME":"{}".format(AgentConstants.AGENT_WORKING_DIR)})
    processId = proc.pid    
    try:
        while int_timeoutCounter <= int_timeout:      
            int_timeoutCounter +=.5                
            time.sleep(.5)
            AgentLogger.debug(AgentLogger.STDOUT,'Polling process, return code : '+str(proc.poll()))
            if proc.poll() is not None:
                bool_isSuccess, byte_CommandOutput = captureOutput(proc)
                str_CommandOutput = byte_CommandOutput.decode('UTF-8')
                isTerminated = True
                break
        if not isTerminated:
            AgentLogger.log(AgentLogger.STDOUT,'Process failed to terminate, Hence issuing \'kill\' command')
            os.kill(processId, signal.SIGKILL)              
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,'***************************** Exception while executing command : '+str(str_command)+' *****************************')
        traceback.print_exc()        
    return bool_isSuccess, str_CommandOutput


def handle_hybrid_upgrade():
    AgentConstants.WATCHDOG_UPGRADE_MSG = ""
    if os.path.isfile(MON_AGENT_UPGRADE_FLAG_FILE):
        try:
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "init-1|"
            is_success, str_output = executeCommand(MON_AGENT_STOP_COMMAND)
            if is_success and MON_AGENT_SERVICE_STOPPED_MESSAGE in str_output:
                AgentLogger.log(AgentLogger.STDOUT, 'UPGRADE : Monitoring agent service stopped successfully for upgrade')
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "mgstp-1|"
            else:
                AgentLogger.log(AgentLogger.STDOUT, 'UPGRADE : Monitoring agent service not stopped hence quitting')
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "mgstp-0|"
            os.chmod(HYBRID_AGENT_UPGRADE_SCRIPT, 0o755)
            # subprocess.Popen(HYBRID_AGENT_UPGRADE_SCRIPT) [the issue causing source agent upgrade failure randomly
            is_success, str_output = executeCommand(HYBRID_AGENT_UPGRADE_SCRIPT)
            if is_success:
                AgentLogger.log(AgentLogger.STDOUT, "monagent start command {}".format(MON_AGENT_START_COMMAND))
                subprocess.Popen(MON_AGENT_START_COMMAND, shell=True, env={"COLUMNS":"500"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                time.sleep(5)
                _status, _output = is_hybrid_agent_running()
                if _status and _output:
                    AGENT_PID = _output
                    AgentLogger.log(AgentLogger.STDOUT,'MONITOR SERVICE : ======================= Agent service started successfully ==========================')
                    AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "mgstd-1|"
                    try:
                        file_obj = open(AgentConstants.MON_AGENT_UPGRADED_FLAG_FILE,'w')
                        file_obj.write('')                  
                    except:
                        AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "mgupf-2|"
                        AgentLogger.log(AgentLogger.STDOUT,'POST UPGRADE : ************************* Exception while creating MonAgent Upgraded Flag File : '+AgentConstants.MON_AGENT_UPGRADED_FLAG_FILE+' ************************* ')
                        traceback.print_exc()
                    finally:        
                        if not file_obj == None:
                            file_obj.close()
                    os.remove(MON_AGENT_UPGRADE_FLAG_FILE)
                else:
                    AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "mgstd-0|"
                    AgentLogger.log(AgentLogger.STDOUT,'MONITOR SERVICE : ======================= Agent service not running ==========================')
        except Exception as e:
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "hdhup-2|"
            AgentLogger.log(AgentLogger.STDOUT, "***** Exception while handling hybrid upgrade :: Error - {} *****".format(e))
            traceback.print_exc()
    else:
        AgentLogger.log(AgentLogger.STDOUT, "upgrade file not present")
    if AgentConstants.WATCHDOG_UPGRADE_MSG != "":
        from com.manageengine.monagent.util.AgentUtil import writeMonagentUpgMsg
        writeMonagentUpgMsg(AgentConstants.AGENT_UPGRADE_STATUS_MSG_FILE,AgentConstants.WATCHDOG_UPGRADE_MSG)
        AgentConstants.WATCHDOG_UPGRADE_MSG = ""
    
class WatchdogService(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.name = 'WatchdogServiceThread'
        self.first_check = True
    def run(self):                
        try:
            time.sleep(20)
            while not TERMINATE_WATCHDOG:
                try:
                    if not AgentConstants.IS_VENV_ACTIVATED: 
                        handleUpgrade()
                    else:
                        handle_hybrid_upgrade()
                    if self.first_check:
                        TERMINATE_WATCHDOG_NOTIFIER.wait(300)
                        self.first_check = False
                    else:
                        TERMINATE_WATCHDOG_NOTIFIER.wait(MON_AGENT_WATCHDOG_SLEEP_INTERVAL) # This wait is before monitorService() to avoid the race condition in starting agent service via /etc/init.d
                    monitorService()     
                except Exception as e:
                    AgentLogger.log(AgentLogger.STDOUT,' *************************** Exception while running watchdog service thread *************************** '+ repr(e))
                    traceback.print_exc()                           
        except Exception as e:
            AgentLogger.log(AgentLogger.STDERR,' *************************** Exception while executing watchdog service thread *************************** '+ repr(e))
            traceback.print_exc()

def get_agent_pid(str_output):
    global AGENT_PID
    try:
        str_output_list = str_output.strip().split("\n")
        AGENT_PID = str_output_list[2].split(" ")[0]
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.STDOUT,'exception while getting agent process id ')
        isSuccess, pid_output = executeCommand(AgentConstants.AGENT_PID_COMMAND)
        AGENT_PID = pid_output.strip()
        AgentLogger.log(AgentLogger.STDOUT,'agent process id  via command --> '+repr(pid_output))


def monitorService():
    str_output = None
    global AGENT_PID
    try:
        AgentLogger.debug(AgentLogger.STDOUT,'MONITOR SERVICE : ======================================== MONITORING AGENT SERVICE ========================================')
        if os.path.exists(AgentConstants.AGENT_RESTART_FLAG_FILE):
            AgentLogger.log(AgentLogger.STDOUT,'Restarting Agent - Flag file : '+repr(AgentConstants.AGENT_RESTART_FLAG_FILE))
            subprocess.Popen(MON_AGENT_RESTART_COMMAND, shell=True, env={"COLUMNS":"500"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(5)
            _status, _output = is_agent_running() if not AgentConstants.IS_VENV_ACTIVATED else is_hybrid_agent_running()
            if _status and _output:
                AGENT_PID = _output
                AgentLogger.log(AgentLogger.STDOUT,'RESTART SERVICE : ======================= Agent service started successfully ==========================')
                AgentLogger.log(AgentLogger.STDOUT,'RESTART SERVICE : Deleting agent restart flag file : '+repr(AgentConstants.AGENT_RESTART_FLAG_FILE))
                os.remove(AgentConstants.AGENT_RESTART_FLAG_FILE)
            else:
                AgentLogger.log(AgentLogger.STDOUT,'RESTART SERVICE : *********************** Failed to restart monitoring agent service ***********************')
        else:
            isSuccess, str_output = executeCommand(MON_AGENT_STATUS_COMMAND)
            if MON_AGENT_SERVICE_DOWN_MESSAGE in str_output:
                AgentLogger.log(AgentLogger.STDOUT,'MONITOR SERVICE : Agent service is DOWN, Hence starting it!! ')    
                subprocess.Popen(MON_AGENT_START_COMMAND, shell=True, env={"COLUMNS":"500"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                time.sleep(5)
                _status, _output = is_agent_running() if not AgentConstants.IS_VENV_ACTIVATED else is_hybrid_agent_running()
                if _status and _output:
                    AGENT_PID = _output
                    AgentLogger.log(AgentLogger.STDOUT,'MONITOR SERVICE : ======================= Agent service started successfully ==========================')                
            else:           
                AgentLogger.log(AgentLogger.STDOUT,'MONITOR SERVICE : ======================= Agent service running {}=========================='.format(str_output))
                get_agent_pid(str_output)
            AgentLogger.log(AgentLogger.STDOUT,'MONITOR SERVICE : Agent status message : '+repr(str_output))
        
        if AGENT_CONFIG.has_option('AGENT_INFO','installer') and AGENT_CONFIG.get('AGENT_INFO','installer') == 'kubernetes':
            AgentConstants.IS_KUBE_AGENT = True
        
        if AgentConstants.OS_NAME == AgentConstants.LINUX_OS and not AgentConstants.IS_KUBE_AGENT:
            check_applog_process()
            #checkZombieProcessCount()
            #check_applog_defunct_process()
            checkDetails()
            #check_file_collector_working()
        else:
            AgentLogger.log(AgentLogger.STDOUT,'Agent threshold monitoring not triggered')
        check_agent_heartbeat()
    except Exception as e:
            AgentLogger.log(AgentLogger.STDERR,' *************************** Exception while monitoring agent service *************************** '+ repr(e))
            traceback.print_exc()

def check_agent_heartbeat():
    global SITE24X7_AGENT_HEARTBEAT_TIME,SITE24X7_AGENT_HEARTBEAT_TIME_LATEST
    try:
        heartbeat_text_file_content = ""
        if os.path.isfile(AgentConstants.AGENT_HEART_BEAT_FILE):
            with open(AgentConstants.AGENT_HEART_BEAT_FILE)as fp:
                heartbeat_text_file_content = fp.read()
            matcher = AgentConstants.SITE24X7_AGENT_HEARTBEAT_REGEX.search(heartbeat_text_file_content)
            if matcher and SITE24X7_AGENT_HEARTBEAT_TIME == 0:
                SITE24X7_AGENT_HEARTBEAT_TIME = matcher.groupdict()["time"]
            elif matcher:
                SITE24X7_AGENT_HEARTBEAT_TIME_LATEST = matcher.groupdict()["time"]
                if int(SITE24X7_AGENT_HEARTBEAT_TIME) < int(SITE24X7_AGENT_HEARTBEAT_TIME_LATEST):
                    AgentLogger.log(AgentLogger.STDOUT," heartbeat up | time :: {} :: latest :: {}".format(SITE24X7_AGENT_HEARTBEAT_TIME,SITE24X7_AGENT_HEARTBEAT_TIME_LATEST))
                    SITE24X7_AGENT_HEARTBEAT_TIME = SITE24X7_AGENT_HEARTBEAT_TIME_LATEST
                    pass
                else:
                    AgentLogger.log(AgentLogger.STDOUT," heartbeat failure | time :: {} :: latest :: {}".format(SITE24X7_AGENT_HEARTBEAT_TIME,SITE24X7_AGENT_HEARTBEAT_TIME_LATEST))
                    invokeRestart()
            else:
                AgentLogger.log(AgentLogger.STDOUT,"heartbeat failure | time :: {} :: latest :: {}".format(SITE24X7_AGENT_HEARTBEAT_TIME,SITE24X7_AGENT_HEARTBEAT_TIME_LATEST))
                AgentLogger.log(AgentLogger.STDOUT,"heartbeat failure | matcher object not found for content :: {}".format(heartbeat_text_file_content))
                #invokeRestart()
        else:
            AgentLogger.log(AgentLogger.STDOUT,"heartbeat.txt not found in monagent!!")
    except Exception as e:
        traceback.print_exc()

def check_file_collector_working():
    file_obj=None
    try:
        file_obj=open(AgentConstants.FILE_COLLECTOR_UPLOAD_CHECK, "r")
        file_collector_time = int(file_obj.read())
        current_time = int(round(time.time()*1000))
        delta_time = current_time - file_collector_time
        if delta_time > 3600000:
            invokeRestart()
        AgentLogger.log(AgentLogger.STDOUT,'file collector time -- {0} {1} {2}'.format(file_collector_time,current_time,delta_time))
    except Exception as e:
        traceback.print_exc()
    finally:
        if file_obj:
            file_obj.close()

def check_applog_defunct_process():
    try:
        APPLOG_DEFUNCT_PROCESS_CHECK_CMD = 'ps -eo args,comm,command,pid,ppid | grep -v grep | grep -i "\[Site24x7Applog\] <defunct>" | wc -l'
        isSuccess, str_output = executeCommand(APPLOG_DEFUNCT_PROCESS_CHECK_CMD, 10)
        AgentLogger.log(AgentLogger.STDOUT,'applog defunct process command run : ' + str_output)
        if isSuccess:
            if str_output:
                defunct_count = 0
                try:
                    defunct_count = int(str_output)
                except Exception as e:
                    AgentLogger.log(AgentLogger.STDOUT,' Unknown string returned while fetching applog defunct process : ' + str_output)
                    traceback.print_exc()
                if defunct_count >=1:
                    AgentLogger.log(AgentLogger.STDOUT,'applog defunct process exists !!!!  '+repr(defunct_count))
                    invokeRestart()
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,' Exception occured while fetching applog defunct process : ' + str_output)
        traceback.print_exc()
        
def check_applog_process():
    applog_process_check_command = "ps -eo pid,comm,args | grep Site24x7Applog | grep -v grep | awk '{print $1}'"
    try:
        boolIsSuccess, processId = executeCommand(applog_process_check_command)
        if processId:
            AgentLogger.log(AgentLogger.STDOUT,'applog process id  : '+str(processId))
            process_id = int(processId)
            p = AgentConstants.PSUTIL_OBJECT.Process(pid=process_id)
            cpu_percent = p.cpu_percent(interval=0.5)
            mem_percent = p.memory_percent()
            thread_count = p.num_threads()
            handle_count = p.num_fds()
            if cpu_percent > AGENT_CPU_THRESHOLD or  mem_percent > AGENT_MEMORY_THRESHOLD or thread_count > AGENT_THREAD_THRESHOLD:
                AgentLogger.log(AgentLogger.STDOUT,' threshold violation for applog process ')
                AgentLogger.log(AgentLogger.STDOUT,' cpu -- {0} | mem -- {1} | thread -- {2}'.format(cpu_percent,mem_percent,thread_count))
                os.kill(process_id, signal.SIGKILL)
                time.sleep(2)
                if os.path.isfile(AgentConstants.APPLOG_EXEC_PATH):
                    AgentConstants.APPLOG_PROCESS = subprocess.Popen(AgentConstants.APPLOG_EXEC_PATH, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    time.sleep(5)
                    if AgentConstants.APPLOG_PROCESS.poll() is None: 
                        AgentLogger.log(AgentLogger.STDOUT,'start : Applog Agent Started Successfully')
                    else:
                        AgentLogger.log(AgentLogger.STDOUT,'start : Applog Agent Already running')
                else:
                    AgentLogger.log(AgentLogger.STDOUT,'start : Applog Agent file not present')                
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,' *************************** Exception while checking applog process details *************************** '+ repr(e))
        traceback.print_exc()
        
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

def checkDetails():
    global AGENT_CPU_THRESHOLD,AGENT_MEMORY_THRESHOLD,AGENT_THREAD_THRESHOLD
    isSuccess=False
    try:
        for each_command in DETAILS_COMMAND_LIST:
            isSuccess, strOutput = executeCommand(each_command, 10)
            if isSuccess:
                if strOutput:
                    dictProcessDetails = parseProcDetails(strOutput)
                    AgentLogger.debug(AgentLogger.STDOUT,'agent process check :: {}'.format(dictProcessDetails))
                    if ( (float(dictProcessDetails['pcpu']) > AGENT_CPU_THRESHOLD) or (float(dictProcessDetails['pmem']) > AGENT_MEMORY_THRESHOLD) or (float(dictProcessDetails['threads']) > AGENT_THREAD_THRESHOLD)):
                        AgentLogger.log(AgentLogger.STDOUT,' output of '+each_command+' --> ' + strOutput)
                        AgentLogger.log(AgentLogger.STDOUT,'Agent consumption threshold violated !!!!')
                        silentRestart()
                else:
                    AgentLogger.log(AgentLogger.STDOUT,'monagent process is not running.. ')
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,'*************************** Exception while checking agent details by watchdog ***************************')
        traceback.print_exc()

def checkZombieProcessCount():
    global AGENT_ZOMBIES_THRESHOLD,AGENT_PID
    try:
        ZOMBIE_PROCESS_COUNT_COMMAND = 'ps -eo args,comm,command,pid,ppid | grep -v grep | grep -i "\[sh\] <defunct>" | grep '+AGENT_PID+' | wc -l'
        isSuccess, strOutput = executeCommand(ZOMBIE_PROCESS_COUNT_COMMAND, 10)
        AgentLogger.debug(AgentLogger.STDOUT,'zombie process count command run by agent watchdog ' + strOutput)
        if isSuccess:
            if strOutput:
                zCount = 0
                try:
                    zCount = int(strOutput)
                except Exception as e:
                    AgentLogger.log(AgentLogger.STDOUT,' Unknown string returned while fetching zombie process count by watchdog: ' + strOutput)
                    traceback.print_exc()
                if zCount > AGENT_ZOMBIES_THRESHOLD:
                    AgentLogger.log(AgentLogger.STDOUT,'zombie process count threshold violation !!!!  '+repr(zCount))
                    zombieDict = {'zombies': zCount}
                    invokeRestart()
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,' Exception occured while fetching zombie process count by watchdog: ' + strOutput)
        traceback.print_exc()
                
def invokeRestart():                
    global RESTART_TIME
    if not RESTART_TIME==None: 
        current_time = time.time()
        if current_time - RESTART_TIME > UPDATE_INTERVAL:
            AgentLogger.log(AgentLogger.STDOUT,' current time ' + repr(current_time))
            AgentLogger.log(AgentLogger.STDOUT,' restart time ' + repr(RESTART_TIME))
            silentRestart()
            RESTART_TIME = time.time()
    else:
        RESTART_TIME = time.time()
        silentRestart()
        AgentLogger.log(AgentLogger.STDOUT,' initial restart time ' + repr(RESTART_TIME))
    
def silentRestart():
    global AGENT_PID
    try:
        AgentLogger.log(AgentLogger.STDOUT,'=======================================SILENTLY RESTARTING AGENT : CREATING WATCHDOG RESTART FLAG =======================================')
        str_uninstallTime = 'Restart : '+repr(datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S"))
        file_obj = open(AgentConstants.AGENT_WATCHDOG_SILENT_RESTART_FLAG_FILE,'w')
        file_obj.write(str_uninstallTime)
        if not file_obj == None:
            file_obj.close()
        AgentLogger.log(AgentLogger.STDOUT,'Restarting Agent - Flag file : '+repr(AgentConstants.AGENT_WATCHDOG_SILENT_RESTART_FLAG_FILE))
        subprocess.Popen(MON_AGENT_RESTART_COMMAND, shell=True, env={"COLUMNS":"500"})
        time.sleep(5)
        _status, _output = is_agent_running() if not AgentConstants.IS_VENV_ACTIVATED else is_hybrid_agent_running()
        if _status and _output:
            AGENT_PID = _output
            AgentLogger.log(AgentLogger.STDOUT,'RESTART SERVICE : ======================= Agent service started successfully ==========================')
        else:
            AgentLogger.log(AgentLogger.STDOUT,'RESTART SERVICE : *********************** Failed to restart monitoring agent service ***********************')
    except Exception as e:        
        AgentLogger.log(AgentLogger.STDERR,' ************************* Exception while creating silent watchdog restart flag file!!! ************************* '+ repr(e))
        traceback.print_exc()

def handleUpgrade():
    try:        
        monAgentUpgrader = MonAgentUpgrader()
        monAgentUpgrader.setLogger(AgentLogger)   
        monAgentUpgrader.upgrade()
        if monAgentUpgrader.isUpgradeSuccess():
            AgentLogger.log(AgentLogger.STDOUT, "deleting file {}".format(MON_AGENT_UPGRADE_FLAG_FILE))
            os.remove(MON_AGENT_UPGRADE_FLAG_FILE)            
        else:
            if os.path.exists(MON_AGENT_UPGRADE_FLAG_FILE):
                AgentLogger.log(AgentLogger.STDOUT,'*************************** Failed to upgrade monitoring agent service ***************************')
                os.remove(MON_AGENT_UPGRADE_FLAG_FILE)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,' *************************** Exception while handling upgrade *************************** '+ repr(e))
        traceback.print_exc()
    finally:
        dict_upgradeProps = None
        monAgentUpgrader = None

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
    
class Upgrader(object):
    def __init__(self):
        self.bool_isSuccess = False
        self.bool_inProgress = False
        self.str_upgradeFile = None
        self.logger = None
        self.dict_upgradeProps = None
    def setIsUpgradeSuccess(self, bool_isSuccess):
        self.bool_isSuccess = bool_isSuccess
    def isUpgradeSuccess(self):
        return self.bool_isSuccess
    def initiateUpgrade(self):
        return self.bool_initiateUpgrade
    def setUpgradeFile(self, str_upgradeFile):
        self.str_upgradeFile = str_upgradeFile
    def getUpgradeFile(self):
        return self.str_upgradeFile
    def setUpgradeProps(self, dict_upgradeProps):
        self.dict_upgradeProps = dict_upgradeProps
    def getUpgradeProps(self):
        return self.dict_upgradeProps
    def setLogger(self, logger):
        self.logger = logger
    def getLogger(self):
        return self.logger
    def log(self, str_message):
        if self.logger:
            self.logger.log(self.logger.STDOUT, str_message)
    def setIsUpgradeInProgress(self, bool_inProgress):
        self.bool_inProgress = bool_inProgress
    def isUpgradeInProgress(self):
        return self.bool_inProgress
    def upgrade(self):
        raise NotImplementedError
    def preUpgrade(self):
        raise NotImplementedError
    def postUpgrade(self):
        raise NotImplementedError
    def upgradeAction(self):
        raise NotImplementedError

class MonAgentUpgrader(Upgrader):
    def __init__(self):
        super(MonAgentUpgrader, self).__init__()
    # Check if upgrade_flag_file exists and read it to fetch upgrade file name.
    def initiateUpgrade(self):
        bool_isSuccess = True
        file_obj = None
        str_upgradeFileName = None
        str_upgradeFilePath = None
        try:
            if os.path.exists(MON_AGENT_UPGRADE_FLAG_FILE):
                file_obj = open(MON_AGENT_UPGRADE_FLAG_FILE, 'r')                
                str_upgradeFileName = file_obj.read()
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "init-1|"
                self.log('INITIATE UPGRADE : Upgrade file name fetched from upgrade_flag_file : '+str(str_upgradeFileName))
                if str_upgradeFileName:
                    str_upgradeFilePath = MON_AGENT_UPGRADE_DIR+'/'+str_upgradeFileName
                    self.setUpgradeFile(str_upgradeFilePath)
                    self.setIsUpgradeInProgress(True)
                    AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "upgfl-1|"
                    self.log('UPGRADE : =========================== UPGRADE INITIATED ============================')
                else:
                    self.setIsUpgradeInProgress(False)
                    self.setIsUpgradeSuccess(False)
                    bool_isSuccess = False
                    AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "upgfl-0|"
                    self.log('INITIATE UPGRADE : Cannot initiate upgrade since upgrade file name is : '+str(str_upgradeFileName))
            else:
                self.setIsUpgradeInProgress(False)
                self.setIsUpgradeSuccess(False)
                bool_isSuccess = False
                self.log('INITIATE UPGRADE : Cannot initiate upgrade since upgrade flag file : '+str(MON_AGENT_UPGRADE_FLAG_FILE)+' does not exist')
        except Exception as e:
            self.setIsUpgradeInProgress(False)
            self.setIsUpgradeSuccess(False)
            bool_isSuccess = False
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "init-2|"
            self.log('INITIATE UPGRADE : *********************** Exception while trying to initiate upgrade *****************************')
            traceback.print_exc()
        finally:
            if not file_obj == None:
                file_obj.close()
        return bool_isSuccess
    # Stop monitoring agent service
    def preUpgrade(self):
        global MON_AGENT_STOP_RETRY_COUNT
        bool_isSuccess = True
        int_monAgentStopTryCount = 0
        try:     
            while int_monAgentStopTryCount < MON_AGENT_STOP_RETRY_COUNT:  
                int_monAgentStopTryCount+=1  
                isSuccess, str_output = executeCommand(MON_AGENT_STATUS_COMMAND)
                self.log('PRE UPGRADE : Monitoring agent status : '+str(str_output))

                isSuccess, str_output = executeCommand(MON_AGENT_STOP_COMMAND)
                if isSuccess and (MON_AGENT_SERVICE_STOPPED_MESSAGE in str_output or MON_AGENT_SERVICE_DOWN_MESSAGE in str_output):
                    self.log('PRE UPGRADE : Monitoring agent service stopped successfully for upgrade')
                    if os.path.exists(AgentConstants.MONAGENT_PID_FILE):
                        os.remove(AgentConstants.MONAGENT_PID_FILE)
                        self.log('PRE UPGRADE : Force removal of monagent pid file')
                    break
                else:
                    time.sleep(5)
                    self.log('PRE UPGRADE : ***************************** Monitoring agent service is up. Will retry to stop it after 5 seconds to start upgrade *****************************')
            isSuccess, str_output = executeCommand(MON_AGENT_STATUS_COMMAND)
            self.log('PRE UPGRADE : Monitoring agent status : '+str(str_output))
            if MON_AGENT_SERVICE_DOWN_MESSAGE in str_output:
                self.log('PRE UPGRADE : Monitoring agent service is down. Proceed with upgrade')
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "mgstp-1|"
            else:
                self.setIsUpgradeInProgress(False)
                self.setIsUpgradeSuccess(False)
                bool_isSuccess = False
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "mgstp-0|"
                AgentConstants.UPGRADE_USER_MESSAGE = "mgstp-0"
                self.log('PRE UPGRADE : *********************** Error while stopping monitoring agent service for upgrade *****************************')
        except Exception as e:
            self.setIsUpgradeInProgress(False)
            self.setIsUpgradeSuccess(False)
            bool_isSuccess = False
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "preupg-2|"
            self.log('PRE UPGRADE : *********************** Exception while trying to stop monitoring agent service for upgrade *****************************')
            traceback.print_exc() 
        return bool_isSuccess
    # Extract Agent upgrade file
    def upgradeAction(self):
        bool_isSuccess = True
        try:
            self.log('UPGRADE : Extracting upgrade tar file : '+repr(self.getUpgradeFile()))  
            tarHandle = AgentArchiver.getArchiver(AgentArchiver.TAR)
            tarHandle.setFile(self.getUpgradeFile())
            tarHandle.setPath(MON_AGENT_WORKING_DIR)
            tarHandle.setMode('r:gz')
            tarHandle.decompress()
            tarHandle.close()
            self.log('UPGRADE : Tar Extraction Successful')
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "mgtar-1|"
        except Exception as e:
            self.setIsUpgradeInProgress(False)
            self.setIsUpgradeSuccess(False)
            bool_isSuccess = False
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "mgtar-2|"
            self.log('UPGRADE : *********************** Exception while extracting Tar file *****************************')
            traceback.print_exc() 
        return bool_isSuccess
    # Start monitoring agent service
    def postUpgrade(self):
        global AGENT_PID
        bool_isSuccess = True
        try:  
            def createMonAgentUpgradedFlagFile():
                bool_toReturn = True
                file_obj = None
                try:
                    file_obj = open(AgentConstants.MON_AGENT_UPGRADED_FLAG_FILE,'w')
                    file_obj.write('')
                    AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "mgupf-1|"
                except:
                    self.log('POST UPGRADE : ************************* Exception while creating MonAgent Upgraded Flag File : '+AgentConstants.MON_AGENT_UPGRADED_FLAG_FILE+' ************************* ')
                    AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "mgupf-2|"
                    traceback.print_exc()
                    bool_toReturn = False
                finally:        
                    if not file_obj == None:
                        file_obj.close()
                return bool_toReturn
            createMonAgentUpgradedFlagFile()
            os.chmod(MON_AGENT_UPGRADE_SCRIPT, 0o755)
            isSuccess, str_output = executeCommand(MON_AGENT_UPGRADE_SCRIPT,30)
            self.log('POST UPGRADE : Upgrade script result : {} and output : {}'.format(isSuccess,str_output))
            if not isSuccess:
                self.log('POST UPGRADE : retrying upgrade script')
                isSuccess, str_output = executeCommand(MON_AGENT_UPGRADE_SCRIPT,45)
                self.log('POST UPGRADE : Retry Upgrade script result : {} and output : {}'.format(isSuccess,str_output))
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "mgups-1|" if isSuccess else AgentConstants.WATCHDOG_UPGRADE_MSG + "mgups-0|"
            self.log("monagent start command {}".format(MON_AGENT_START_COMMAND))
            subprocess.Popen(MON_AGENT_START_COMMAND, shell=True, env={"COLUMNS":"500"})
            time.sleep(5)
            _status, _output = is_agent_running()
            if _status:
                AGENT_PID = _output
                self.log('POST UPGRADE : Site24x7Agent Started Successfully')
                self.setIsUpgradeInProgress(False)
                self.setIsUpgradeSuccess(True)
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "mgstr-1|"
                self.log('POST UPGRADE : ======================= MONITORING AGENT UPGRADE SUCCESSFUL ==========================')                
            else:
                self.log('POST UPGRADE : Site24x7Agent not started')
                self.setIsUpgradeInProgress(False)
                self.setIsUpgradeSuccess(False)
                bool_isSuccess = False
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "mgstr-0|"
                AgentConstants.UPGRADE_USER_MESSAGE = "mgstr-0"
                self.log('POST UPGRADE : *************************** Failed to start monitoring agent service after upgrade ***************************')            
        except Exception as e:
            self.setIsUpgradeInProgress(False)
            self.setIsUpgradeSuccess(False)
            bool_isSuccess = False
            AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.WATCHDOG_UPGRADE_MSG + "posup-2|"
            self.log('POST UPGRADE : *********************** Exception while starting monitoring agent service after upgrade *****************************')
            traceback.print_exc() 
        return bool_isSuccess

    def clear_upgrade_files(self):
        try:
            import shutil
            if os.path.exists(MON_AGENT_UPGRADE_DIR):
                for content in os.listdir(MON_AGENT_UPGRADE_DIR):
                    if os.path.isdir(os.path.join(MON_AGENT_UPGRADE_DIR, content)):
                        shutil.rmtree(os.path.join(MON_AGENT_UPGRADE_DIR, content))
                    elif os.path.isfile(os.path.join(MON_AGENT_UPGRADE_DIR, content)):
                        os.remove(os.path.join(MON_AGENT_UPGRADE_DIR, content))
            if os.path.exists(MON_AGENT_BACKUP_DIR):
                for content in os.listdir(MON_AGENT_BACKUP_DIR):
                    if os.path.isdir(os.path.join(MON_AGENT_BACKUP_DIR, content)):
                        shutil.rmtree(os.path.join(MON_AGENT_BACKUP_DIR, content))
                    elif os.path.isfile(os.path.join(MON_AGENT_BACKUP_DIR, content)):
                        os.remove(os.path.join(MON_AGENT_BACKUP_DIR, content))
        except Exception as e:
            self.log('POST UPGRADE : *********************** Exception while clearing upgrade files *****************************')
            traceback.print_exc()

    def upgrade(self):
        AgentConstants.WATCHDOG_UPGRADE_MSG = ""
        if self.initiateUpgrade():
            if self.preUpgrade():
                if self.upgradeAction():
                    self.postUpgrade()
        if AgentConstants.WATCHDOG_UPGRADE_MSG != "":
            from com.manageengine.monagent.util.AgentUtil import writeMonagentUpgMsg
            if AgentConstants.UPGRADE_USER_MESSAGE == None:
                AgentConstants.WATCHDOG_UPGRADE_MSG = "##"+str(AgentConstants.WATCHDOG_UPGRADE_MSG)
            else:
                AgentConstants.WATCHDOG_UPGRADE_MSG = AgentConstants.UPGRADE_USER_MESSAGE +"##"+str(AgentConstants.WATCHDOG_UPGRADE_MSG)
            writeMonagentUpgMsg(AgentConstants.AGENT_UPGRADE_STATUS_MSG_FILE,AgentConstants.WATCHDOG_UPGRADE_MSG)
            AgentConstants.WATCHDOG_UPGRADE_MSG = ""
        self.clear_upgrade_files()

class SysClockMonitor(threading.Thread):
    def __init__(self,):
        threading.Thread.__init__(self)
        self.name = 'Sys Clock Monitor'
        self.__kill = False
    
    def stop(self):
        self.__kill = True
                
    def getThreadStatus(self):
        return self.__kill
        
    def run(self):
        past_time = time.time()
        AgentLogger.log(AgentLogger.STDOUT, 'Started sys clock monitor thread')
        
        while not self.__kill:
            try:
                diff = past_time - time.time()
                if abs(diff) > SYSCLOCK_INTERVAL:
                    AgentLogger.log(AgentLogger.STDOUT, 'System clock difference exceeded {}'.format(str(diff)))
                    # To restart watchdog after agent starts
                    with open(AgentConstants.AGENT_SILENT_RESTART_FLAG_FILE, 'w') as f:
                        f.write("Restart")
                    silentRestart()
                past_time = time.time()
                time.sleep(10)
            except Exception as e:
                traceback.print_exc()
        else:
            AgentLogger.log(AgentLogger.STDOUT,'System clock monitor thread stopped !!!')


main()
