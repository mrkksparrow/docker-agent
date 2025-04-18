#$Id$
import copy
import ssl
import traceback
import time
import os, sys
from datetime import datetime
import json
import struct
from six.moves.urllib.parse import urlencode
import threading
import platform
from . import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
import com.manageengine.monagent.notify
from com.manageengine.monagent.util import AgentUtil,MetricsUtil,DatabaseUtil,eBPFUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil
from com.manageengine.monagent.discovery import HostHandler
from com.manageengine.monagent.scheduler import AgentScheduler
from com.manageengine.monagent.collector import DataCollector,server_inventory
from com.manageengine.monagent.collector import DataConsolidator
from com.manageengine.monagent.communication import CommunicationHandler, DMSHandler, AgentStatusHandler, BasicClientHandler, applog
from com.manageengine.monagent.upgrade import AgentUpgrader
from com.manageengine.monagent.network.AgentPingHandler import PingUtil
import com.manageengine.monagent.network
import com.manageengine.monagent.util.rca
from com.manageengine.monagent.docker_agent import *
from com.manageengine.monagent.security import AgentCrypt
from com.manageengine.monagent.hardware import HardwareMonitoring
from com.manageengine.monagent.actions import checksum_validator
from com.manageengine.monagent.actions import FileChangeNotifier,AgentAction
from com.manageengine.monagent.cloud import metadata
from com.manageengine.monagent.kubernetes import KubeGlobal

isInstance = False
instanceDict = {}
metadata_dict = {}

def handle_docker_agent():
    _status = False
    try:
        import psutil
        AgentConstants.DOCKER_PSUTIL = psutil
        AgentConstants.DOCKER_PROCESS_OBJECT=Process()
        if AgentConstants.IS_DOCKER_AGENT == "1":
            psutil.PROCFS_PATH = AgentConstants.PROCFS_PATH
            AgentConstants.DOCKER_COLLECTOR_OBJECT = Metrics()
            AgentConstants.DOCKER_SYSTEM_OBJECT = System
            AgentConstants.DOCKER_HELPER_OBJECT = helper
            _status = True
    except Exception as e:
        psutil = None
        traceback.print_exc()
        if AgentConstants.IS_DOCKER_AGENT=="1":
            AgentLogger.log(AgentLogger.MAIN, "Cannot import psutil. Hence quitting!!!")
            sys.exit(1)
        else:
            AgentLogger.log(AgentLogger.MAIN, "Cannot import psutil")

def update_terminal_width():
    try:
        if not isAgentRegistered():
            AgentLogger.log(AgentLogger.STDOUT, "agent installing for first time \n")
            if not os.path.exists(AgentConstants.COLUMN_EXTEND_FILE):
                AgentUtil.create_file(AgentConstants.COLUMN_EXTEND_FILE)
    except Exception as e:
        traceback.print_exc()

def initialize():
    global isInstance,instanceDict
    AgentUtil.isWarmShutdown()
    if not loadAgentConfiguration():
        return False
    check_and_set_start_delay()
    load_proxy_key()
    load_customer_id()
    CommunicationHandler.set_ssl_context()
    AgentLogger.debug(AgentLogger.MAIN,'customer id :: {}'.format(AgentConstants.CUSTOMER_ID))
    AgentLogger.log(AgentLogger.STDOUT, 'is production setup :: {}'.format(AgentConstants.IS_PRODUCTION))
    if AgentConstants.IS_PRODUCTION == 1:
        domainDecider()
    if not evaluateAgentParameters():
        AgentLogger.log(AgentLogger.CRITICAL,' ************************* Exception While Evaluating Agent Parameters ************************* ')
        return False
    handle_docker_agent()
    com.manageengine.monagent.communication.initialize()
    com.manageengine.monagent.actions.initialize()
    AgentStatusHandler.HEART_BEAT_THREAD = AgentStatusHandler.HeartBeatThread()
    AgentStatusHandler.HEART_BEAT_THREAD.setDaemon(True)
    AgentStatusHandler.HEART_BEAT_THREAD.start()
    AgentUtil.handle_license()
    AgentUtil.checkSystemUtilities()
    AgentUtil.getProcessorName()
    AgentUtil.getSystemUUID()
    AgentUtil.get_hdd_names()
    bool_return,version = AgentUtil.getAgentVersion()
    AgentUtil.get_server_ram_size()
    CommunicationHandler.getCaCertPath()
    if not AgentConstants.IS_DOCKER_AGENT:
        CommunicationHandler.checkNetworkStatus()
    if not isAgentRegistered() and not CommunicationHandler.isServerReachable(5, 60,AgentLogger.MAIN):# Trying to reach server for a day if the agent is not registered
        AgentLogger.log(AgentLogger.MAIN,'Agent not registered and server not reachable.\n')
        return False
    if not HostHandler.initialize():
        return False
    AgentUtil.calculateNoOfCpuCores()
    AgentLogger.log(AgentLogger.MAIN,'Monitoring Agent Version - {0}'.format(version)+'\n')
    AgentLogger.log(AgentLogger.MAIN,'Machine Architecture - {0}'.format(platform.machine())+'\n')
    AgentLogger.log(AgentLogger.MAIN,'OpenSSL Version - {0}'.format(ssl.OPENSSL_VERSION)+'\n')
    AgentLogger.log(AgentLogger.MAIN,'Python Version - {0}.{1}.{2}'.format(sys.version_info[0],sys.version_info[1],sys.version_info[2])+'\n')
    if AgentConstants.OS_NAME == AgentConstants.LINUX_OS:
        isInstance,instanceDict = getInstanceMetadata()
        update_terminal_width()
    AgentLogger.log(AgentLogger.MAIN,'Cloud Instance - {0}'.format(isInstance)+'\n')
    AgentUtil.setCpuFormula(instanceDict)
    AgentUtil.handleCpuDataCollection()

    if not isAgentRegistered():
        if not registerAgent():
            AgentLogger.log(AgentLogger.MAIN,' ************************* Agent Registration Fails ************************* ')
            return False
        AgentUtil.reinit_childs()
    else:
        if not reRegisterAgent():
            AgentLogger.log(AgentLogger.MAIN,' ************************* Agent Re-Registration Fails ************************* ')
            return False
    
    
    #check the order of status update here.
    checksum_validator.initialize(AgentConstants.AGENT_FILES_CHECKSUM_LIST)
    update_encrypted_device_key(AgentConstants.CUSTOMER_ID)
    if AgentUtil.is_module_enabled(AgentConstants.HEARTBEAT_KEY):
        if not AgentStatusHandler.initialize():
            AgentLogger.log(AgentLogger.MAIN,'Status Updater - Failure.\n')
            return False
    if not initializeAgentModules():
        AgentLogger.log(AgentLogger.MAIN,'Agent Modules Initialized | Status - Failure.\n')
        return False
    if not isAgentProfileExist():
        AgentLogger.log(AgentLogger.STDOUT,'Agent Profile Not Exist | Status - Failure.\n')
        return False
    AgentLogger.log(AgentLogger.STDOUT,'Agent Profile Exist | Status - Success.\n')
    if not AgentUpgrader.initialize():
        AgentLogger.log(AgentLogger.MAIN,'Upgrade Module - Failure.\n')
        return False
    AgentLogger.log(AgentLogger.MAIN,'Upgrade Module - Success.\n')
    AgentLogger.log(AgentLogger.MAIN,'Status Updater - Success.\n')
    if os.path.exists(AgentConstants.AGENT_UPGRADE_STATUS_MSG_FILE):
        AgentAction.ackAgentUpgradeStatus(None,"PRIOR_UPGRADE")
    AgentUtil.handleSpecialTasks()
    #PingUtil.getPeerCheck() - will get it in response header
    if AgentConstants.OS_NAME == AgentConstants.LINUX_OS and isInstance:
        sendinstanceMetadata()
    #azure start status update
    try:
        if AgentUtil.AGENT_CONFIG.has_section('AGENT_INFO') and ((AgentUtil.AGENT_CONFIG.get('AGENT_INFO','agent_instance_type')==AgentConstants.AZURE_INSTANCE) or (AgentUtil.AGENT_CONFIG.get('AGENT_INFO','agent_instance_type')==AgentConstants.AZURE_INSTANCE_CLASSIC)):
            AgentUtil.do_status_report('Agent Startup','success',0,'Agent started successfully')
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT, AgentLogger.STDERR],' Exception While updating agent start status ')
        traceback.print_exc()
    if AgentConstants.DOCKER_COLLECTOR_OBJECT and not KubeGlobal.fargate and not KubeGlobal.gkeAutoPilot and not KubeGlobal.nonMountedAgent:
        AgentConstants.DOCKER_COLLECTOR_OBJECT.collect()
    DataCollector.executePlugins()
    if AgentConstants.OS_NAME!=AgentConstants.LINUX_OS:
        FileUtil.deleteFile(AgentConstants.COLUMN_EXTEND_FILE)
    MetricsUtil.initialize()
    eBPFUtil.initialize()
    FileChangeNotifier.initialize()
    AgentLogger.log(AgentLogger.STDOUT,'Initializaton for agent completed')
    if os.path.exists(AgentConstants.AGENT_SILENT_RESTART_FLAG_FILE):
        AgentLogger.log(AgentLogger.STDOUT,'============ RESTARTING WATCHDOG AGENT ============')
        AgentUtil.restartWatchdog()
    if os.path.exists(AgentConstants.AGENT_WATCHDOG_SILENT_RESTART_FLAG_FILE):
        os.remove(AgentConstants.AGENT_WATCHDOG_SILENT_RESTART_FLAG_FILE)
    return True

def load_customer_id():
    customer_id = None
    try:
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','customer_id'):
            customer_id = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','customer_id')
        if AgentConstants.CRYPTO_MODULE:
            if not customer_id:
                encrypted_customer_id = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','encrypted_customer_id')
                customer_id = AgentCrypt.decrypt_with_proxy_key(encrypted_customer_id)
        if "-automation" in customer_id:
            AgentLogger.log(AgentLogger.STDOUT,'customer id contains automation param so stripping it')
            customer_id = customer_id.split("-automation")[0].strip()
        AgentConstants.CUSTOMER_ID = customer_id
    except Exception as e:
        traceback.print_exc()

def update_encrypted_device_key(customer_id):
    try:
        if customer_id and AgentConstants.CRYPTO_MODULE:
            encrypted_customer_id = AgentCrypt.encrypt_with_proxy_key(customer_id)
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'encrypted_customer_id', str(encrypted_customer_id))
            AgentUtil.AGENT_CONFIG.remove_option('AGENT_INFO', 'customer_id')
            AgentUtil.persistAgentInfo()
    except Exception as e:
        traceback.print_exc()

def load_proxy_key():
    install_time = 0
    try:
        if os.path.exists(AgentConstants.AGENT_INSTALL_TIME_FILE):
            status,install_time = AgentUtil.get_agent_install_time()
        else:
            install_time = str(int(time.time()))
            AgentUtil.update_agent_install_time(install_time)
            if AgentUtil.AGENT_CONFIG.has_option('PROXY_INFO', 'proxy_password'):
                proxy_password = AgentUtil.AGENT_CONFIG.get('PROXY_INFO','proxy_password')
                AgentLogger.debug(AgentLogger.MAIN,'proxy password -- {0}'.format(proxy_password))
                if proxy_password!='0':
                    decrypted_password = AgentCrypt.decrypt(proxy_password)
                    AgentUtil.AGENT_CONFIG.set('PROXY_INFO', 'proxy_password',decrypted_password)
                    AgentUtil.persistAgentInfo()
        AgentConstants.AGENT_PS_KEY = install_time+AgentConstants.AGENT_UPGRADE_FOLDER_IN_PLUS
        AgentLogger.debug(AgentLogger.MAIN,'agent proxy secret key -- {0}'.format(AgentConstants.AGENT_PS_KEY))
    except Exception as e:
        traceback.print_exc()

def domainDecider():
    try:
        device_key = str(AgentConstants.CUSTOMER_ID)
        (bool_status, list_dict) = AgentUtil.loadDataFromFile(AgentConstants.AGENT_CHECK_SERVER_LIST_FILE)
        domain_in_key = AgentConstants.PRIMARY_DC
        if bool_status:
            prefix = '_'.join(device_key.split('_')[:-1])
            if prefix in list_dict.keys():
                domain_in_key = prefix
        else:
            AgentLogger.log(AgentLogger.STDOUT,'Loading from {} failed'.format(AgentConstants.AGENT_CHECK_SERVER_LIST_FILE))
        AgentLogger.log(AgentLogger.STDOUT,'Prefix of device key: {}'.format(domain_in_key))
        persistDomains(list_dict[domain_in_key])
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,' ************************* Exception while choosing domain for agent ************************* '+ repr(e))
        traceback.print_exc()
        
def isAgentProfileExist():
    bool_toReturn = True
    try:
        if not os.path.exists(AgentConstants.AGENT_PROFILE_FILE):
            AgentConstants.AGENT_WARM_START = False
            AgentLogger.log(AgentLogger.STDOUT,'========================== Creating agent profile ======================== ')
            dict_profileData = {}
            if AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key') != '0' and AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_unique_id') != '0':
                dict_profileData['AGENT_KEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
                dict_profileData['AGENT_UNIQUE_ID'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_unique_id')
                bool_toReturn = AgentUtil.persistProfile(AgentConstants.AGENT_PROFILE_FILE, dict_profileData)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,' ************************* Exception while creating agent profile ************************* '+ repr(e))
        traceback.print_exc()
        bool_toReturn = False
    return bool_toReturn


def initializeAgentModules():
    AgentStatusHandler.init_wms_thread()
    if not AgentConstants.IS_VENV_ACTIVATED:
        #DMSHandler.initialize()
        if AgentUtil.is_module_enabled(AgentConstants.DMS):
            from com.manageengine.monagent.communication import dms_websocket
            dms_websocket.initialize()
    if AgentUtil.is_module_enabled(AgentConstants.RESOURCE_CHECK_SETTING):
        BasicClientHandler.initialize()
    AgentScheduler.initialize()
    DataConsolidator.updateAgentConfig(True,True)
    #AgentLogger.log(AgentLogger.MAIN,'before initialize database ')
    #DatabaseUtil.is_input_file_present()
    #AgentLogger.log(AgentLogger.MAIN,'after initialize database ')
    if not DataCollector.initialize():
        AgentLogger.log([AgentLogger.MAIN,AgentLogger.CRITICAL],'Agent Data Collection Initialized | Status - Failure \n')
        return False
    else:
        AgentConstants.FILES_TO_ZIP_BUFFER_APPS = DataCollector.FILES_TO_ZIP_BUFFER

    applog.start()

    AgentLogger.log(AgentLogger.MAIN,'Data Collection Module - Success \n')
    #To send inventory on each restart
    if os.path.exists(AgentConstants.SERVER_INVENTORY_DATA_FILE):
        os.remove(AgentConstants.SERVER_INVENTORY_DATA_FILE)
    AgentLogger.log([AgentLogger.STDOUT],'=============================== AGENT INITIALIZATION SUCCESSFUL ===============================')
    return True

def docker_agent_handler():
    try:
        if AgentUtil.AGENT_CONFIG.has_section("TYPE"):
            if AgentUtil.AGENT_CONFIG.has_option("TYPE", "docker_agent"):
                AgentConstants.IS_DOCKER_AGENT = AgentUtil.AGENT_CONFIG.get("TYPE", "docker_agent")
            if AgentUtil.AGENT_CONFIG.has_option("TYPE", "docker_host"):
                AgentConstants.DOCKER_HOST = AgentUtil.AGENT_CONFIG.get("TYPE", "docker_host")

        if AgentConstants.IS_DOCKER_AGENT == '1':
            AgentUtil.load_envs()
    except Exception as e:
        traceback.print_exc()

def ps_worker_handler():
    try:
        from com.manageengine.monagent.framework.suite.helper import readconf_file
        with readconf_file(AgentConstants.PS_WORKER_CONF_FILE) as fp:
            conf_file_contents, status, error_msg = fp
        if conf_file_contents and "worker" in conf_file_contents:
            AgentConstants.IS_PS_WORKER_ENABLED = conf_file_contents["worker"].get("enabled", "0")
            AgentConstants.PROCFS_PATH = conf_file_contents["worker"].get("procfs_path", "/proc")
            AgentConstants.SYSFS_PATH = conf_file_contents["worker"].get("sysfs_path", "/sys")
            from com.manageengine.monagent.docker_agent import constants
            constants.ENV_DICT = {"PROC_FOLDER":AgentConstants.PROCFS_PATH, "SYS_FOLDER":AgentConstants.SYSFS_PATH}
    except Exception as e:
        traceback.print_exc()

def ps_worker_checker():
    _status = True
    try:
        if AgentConstants.IS_PS_WORKER_ENABLED == "1":
            if not os.path.isdir(AgentConstants.PROCFS_PATH):
                _status = False
            if not os.path.isdir(AgentConstants.SYSFS_PATH):
                _status = False
    except Exception as e:
        _status = False
        traceback.print_exc()
    finally:
        return _status

def unix_os():
    if platform.system().lower().startswith("sun"):
        AgentLogger.log(AgentLogger.STDOUT, "Unix OS detected - sunos \n")
        AgentConstants.IS_DOCKER_AGENT = "1"

def loadAgentConfiguration():
    _status = True
    try:
        if not (os.path.exists(AgentConstants.AGENT_CONF_FILE)):
            AgentLogger.log(AgentLogger.MAIN,'************************* Missing agent configuration file : '+AgentConstants.AGENT_CONF_FILE+' ************************* \n')
            _status = False
        elif AgentUtil.readAgentInfo(): #returns true when monagent.cfg and backup/monagent.cfg is corrupted
            AgentLogger.log(AgentLogger.MAIN,'************************* Corrupted agent configuration file : '+AgentConstants.AGENT_CONF_FILE+' ************************* \n')
            _status = False
        else:
            AgentUtil.UPLOAD_CONFIG.read(AgentConstants.AGENT_UPLOAD_PROPERTIES_FILE)
            (bool_status, dataFromFile) = AgentUtil.loadDataFromFile(AgentConstants.AGENT_PARAMS_FILE)
            if bool_status:
                AgentUtil.AGENT_PARAMS = dataFromFile
                AgentLogger.log(AgentLogger.STDOUT,'Agent params loaded from '+AgentConstants.AGENT_PARAMS_FILE+' : '+repr(AgentUtil.AGENT_PARAMS))
            else:
                AgentLogger.log(AgentLogger.STDOUT,'Error while loading '+AgentConstants.AGENT_PARAMS_FILE+'. Setting AGENT_PARAMS to default values : '+repr(AgentUtil.AGENT_PARAMS))
            loadProductProfile()
            setAgentConstants()
            docker_agent_handler()
            #unix_os()
            ps_worker_handler()
            if "EKS_FARGATE" in os.environ and os.environ.get("EKS_FARGATE").lower()=="true" and "NODE_NAME" in os.environ:
                KubeGlobal.fargate=True  #For FARGATE we don't use volume mounts
                KubeGlobal.nodeName=os.environ.get("NODE_NAME")
                AgentLogger.log(AgentLogger.KUBERNETES, 'EKS Fargate environment identified')
            elif "GKE_AUTOPILOT" in os.environ and os.environ.get("GKE_AUTOPILOT").lower()=="true" and "NODE_NAME" in os.environ:
                KubeGlobal.gkeAutoPilot=True
                KubeGlobal.nodeName=os.environ.get("NODE_NAME")
                AgentLogger.log(AgentLogger.KUBERNETES, 'GKE Autopilot environment identified')
            elif "SERVERLESS" in os.environ and os.environ.get("SERVERLESS").lower()=="true" and "NODE_NAME" in os.environ:
                KubeGlobal.nonMountedAgent=True
                KubeGlobal.nodeName=os.environ.get("NODE_NAME")
                AgentLogger.log(AgentLogger.KUBERNETES, 'Non Mounted Agent identified')
            else:
                _status = ps_worker_checker()
            AgentLogger.log(AgentLogger.STDOUT,'module crypto present - {0}'.format(AgentConstants.CRYPTO_MODULE))
        #checkAzureInstance()
    except Exception as e:

        AgentLogger.log(AgentLogger.STDERR,' ************************* Exception while loading agent configuration ************************* '+ repr(e))
        traceback.print_exc()
        _status = False
    finally:
        return _status

def updateAgentConfiguration():
    isConfUpdated = False
    try:
        if AgentUtil.AGENT_CONFIG.has_option('DEFAULT', 'production'):
            AgentConstants.IS_PRODUCTION = int(AgentUtil.AGENT_CONFIG.get('DEFAULT', 'production'))
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Adding production value to conf file')
            AgentUtil.AGENT_CONFIG.set('DEFAULT', 'production', str(AgentConstants.IS_PRODUCTION))
            isConfUpdated = True
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO', 'status_update_interval'):
            AgentConstants.STATUS_UPDATE_INTERVAL = int(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'status_update_interval'))
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Adding status_update_interval to conf file')
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'status_update_interval', str(AgentConstants.STATUS_UPDATE_INTERVAL))
            isConfUpdated = True
        if AgentUtil.AGENT_CONFIG.has_section('APPS_INFO'):
            #AgentConstants.DOCKER_KEY = AgentUtil.AGENT_CONFIG.get('APPS_INFO', 'docker_key')
            if AgentUtil.AGENT_CONFIG.has_option('APPS_INFO', 'docker_enabled'):
                AgentConstants.AGENT_DOCKER_ENABLED = int(AgentUtil.AGENT_CONFIG.get('APPS_INFO', 'docker_enabled'))
            else:
                AgentUtil.AGENT_CONFIG.set('APPS_INFO', 'docker_enabled',AgentConstants.AGENT_DOCKER_ENABLED)
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Adding docker_info to conf file')
            AgentUtil.AGENT_CONFIG.add_section('APPS_INFO')
            AgentUtil.AGENT_CONFIG.set('APPS_INFO', 'docker_key', AgentConstants.DEFAULT_DOCKER_KEY)
            AgentUtil.AGENT_CONFIG.set('APPS_INFO', 'docker_enabled', AgentConstants.AGENT_DOCKER_ENABLED )
        if AgentUtil.AGENT_CONFIG.has_section('SECONDARY_SERVER_INFO'):
            AgentConstants.SECONDARY_SERVER_NAME = AgentUtil.AGENT_CONFIG.get('SECONDARY_SERVER_INFO', 'server_name')
            AgentConstants.SECONDARY_SERVER_IP_ADDRESS = AgentUtil.AGENT_CONFIG.get('SECONDARY_SERVER_INFO', 'server_ip_address')
            AgentConstants.SECONDARY_SERVER_PORT = AgentUtil.AGENT_CONFIG.get('SECONDARY_SERVER_INFO', 'server_port')
            AgentConstants.SECONDARY_SERVER_PROTOCOL = AgentUtil.AGENT_CONFIG.get('SECONDARY_SERVER_INFO', 'server_protocol')
            AgentConstants.SECONDARY_SERVER_TIMEOUT = AgentUtil.AGENT_CONFIG.get('SECONDARY_SERVER_INFO', 'server_timeout')
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Adding secondary_server_info to conf file')
            AgentUtil.AGENT_CONFIG.add_section('SECONDARY_SERVER_INFO')
            AgentUtil.AGENT_CONFIG.set('SECONDARY_SERVER_INFO', 'server_name', str(AgentConstants.SECONDARY_SERVER_NAME))
            AgentUtil.AGENT_CONFIG.set('SECONDARY_SERVER_INFO', 'server_ip_address', str(AgentConstants.SECONDARY_SERVER_IP_ADDRESS))
            AgentUtil.AGENT_CONFIG.set('SECONDARY_SERVER_INFO', 'server_port', str(AgentConstants.SECONDARY_SERVER_PORT))
            AgentUtil.AGENT_CONFIG.set('SECONDARY_SERVER_INFO', 'server_protocol', str(AgentConstants.SECONDARY_SERVER_PROTOCOL))
            AgentUtil.AGENT_CONFIG.set('SECONDARY_SERVER_INFO', 'server_timeout', str(AgentConstants.SECONDARY_SERVER_TIMEOUT))
            isConfUpdated = True
        if AgentUtil.AGENT_CONFIG.has_section('UDP_SERVER_INFO'):
            AgentConstants.UDP_SERVER_IP = AgentUtil.AGENT_CONFIG.get('UDP_SERVER_INFO', 'udp_server_ip')
            AgentConstants.UDP_PORT = AgentUtil.AGENT_CONFIG.get('UDP_SERVER_INFO', 'udp_server_port')
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Adding udp server ip info to conf file')
            AgentUtil.AGENT_CONFIG.add_section('UDP_SERVER_INFO')
            AgentUtil.AGENT_CONFIG.set('UDP_SERVER_INFO', 'udp_server_ip', AgentConstants.UDP_SERVER_IP)
            AgentUtil.AGENT_CONFIG.set('UDP_SERVER_INFO', 'udp_server_port', AgentConstants.UDP_PORT)
            isConfUpdated = True
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO', 'agent_instance_type'):
            AgentConstants.AGENT_INSTANCE_TYPE = str(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_instance_type'))
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Adding agent_instance_type to conf file')
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'agent_instance_type', str(AgentConstants.AGENT_INSTANCE_TYPE))
            isConfUpdated = True
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO', 'count'):
            AgentConstants.PLUGINS_COUNT = str(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'count'))
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Adding count(plugin) to conf file')
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'count', str(AgentConstants.PLUGINS_COUNT))
            isConfUpdated = True
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO', 'pl_zip_task_interval'):
            AgentConstants.PLUGINS_ZIP_INTERVAL = int(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'pl_zip_task_interval'))
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Adding pl_zip_task_interval count(plugin) to conf file')
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'pl_zip_task_interval', AgentConstants.PLUGINS_ZIP_INTERVAL)
            isConfUpdated = True
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO', 'pl_dc_task_interval'):
            AgentConstants.PLUGINS_DC_INTERVAL = int(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'pl_dc_task_interval'))
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Adding pl_dc_task_interval count(plugin) to conf file')
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'pl_dc_task_interval', AgentConstants.PLUGINS_DC_INTERVAL)
            isConfUpdated = True
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO', 'pl_dc_zip_count'):
            AgentConstants.PLUGINS_ZIP_FILE_SIZE = int(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'pl_dc_zip_count'))
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Adding dc_upload_interval count(plugin) to conf file')
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'pl_dc_zip_count', AgentConstants.PLUGINS_ZIP_FILE_SIZE)
            isConfUpdated = True
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO', 'dc_upload_interval'):
            AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['001']['zip_interval'] = int(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'dc_upload_interval'))
            AgentConstants.UPLOAD_CHECK_INTERVAL = int(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'dc_upload_interval'))
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Adding dc_upload_interval count(agent) to conf file')
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'dc_upload_interval', AgentConstants.UPLOAD_CHECK_INTERVAL)
            AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['001']['zip_interval'] = int(AgentConstants.UPLOAD_CHECK_INTERVAL)
            isConfUpdated = True
        if AgentUtil.AGENT_CONFIG.has_section('APPLOG_AGENT_INFO'):
            if AgentUtil.AGENT_CONFIG.has_option('APPLOG_AGENT_INFO', 'applog_enabled'):
                AgentConstants.APPLOG_AGENT_ENABLED = int(AgentUtil.AGENT_CONFIG.get('APPLOG_AGENT_INFO', 'applog_enabled'))
            else:
                AgentUtil.AGENT_CONFIG.set('APPLOG_AGENT_INFO', 'applog_enabled',AgentConstants.APPLOG_AGENT_ENABLED)
                isConfUpdated = True
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Adding Applog Agent info to conf file')
            AgentUtil.AGENT_CONFIG.add_section('APPLOG_AGENT_INFO')
            AgentUtil.AGENT_CONFIG.set('APPLOG_AGENT_INFO', 'applog_enabled', AgentConstants.APPLOG_AGENT_ENABLED )
            isConfUpdated = True
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO', 'plugin_time_out'):
            AgentConstants.PLUGIN_DEFAULT_TIME_OUT = str(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'plugin_time_out'))
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : plugin default time out value - {0}'.format(AgentConstants.PLUGIN_DEFAULT_TIME_OUT))
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Adding plugin default timeout to conf file')
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'plugin_time_out', str(AgentConstants.PLUGIN_DEFAULT_TIME_OUT))
            isConfUpdated = True
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO', 'dc_script_timeout'):
            AgentConstants.DC_SCRIPT_TIMEOUT = str(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'dc_script_timeout'))
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : dc script timeout value  - {0}'.format(AgentConstants.DC_SCRIPT_TIMEOUT))
        else:
            AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Adding dc script timeout value to conf file - {}'.format(AgentConstants.DC_SCRIPT_TIMEOUT))
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'dc_script_timeout', str(AgentConstants.DC_SCRIPT_TIMEOUT))
            isConfUpdated = True
        # top process arguments length trimming configurable object
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO', 'top_arg_length'):
            AgentConstants.TOP_PROCESS_ARGUMENT_LENGTH = int(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'top_arg_length'))
        else:
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'top_arg_length', str(AgentConstants.TOP_PROCESS_ARGUMENT_LENGTH))
            isConfUpdated = True
        # process discovery arg length configurable
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO', 'disc_prc_arg_length'):
            AgentConstants.DISCOVER_PROCESS_ARGUMENT_LENGTH = int(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'disc_prc_arg_length'))
        else:
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'disc_prc_arg_length', str(AgentConstants.DISCOVER_PROCESS_ARGUMENT_LENGTH))
            isConfUpdated = True
        upload_property_mapper_temp_dict = copy.deepcopy(AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER)
        for dir, dir_prop in upload_property_mapper_temp_dict.items():
            if AgentUtil.UPLOAD_CONFIG.has_section(dir):
                for option in ['max_zips_current_buffer', 'max_zips_failed_buffer', 'files_in_zip', 'zip_interval', 'upload_interval', 'grouped_zip_upload_interval']:
                    if AgentUtil.UPLOAD_CONFIG.has_option(dir,option):
                        value = AgentUtil.UPLOAD_CONFIG.get(dir,option)
                        if int(value) > AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[dir][option]:
                            AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER[dir][option] = AgentUtil.UPLOAD_CONFIG.get(dir,option)

        #if not AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO', 'location'):
        #    AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Adding location to conf file')
        #    AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'location', str(AgentConstants.LOCATION))
        #    isConfUpdated = True
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while updating agent configuration ************************* '+ repr(e))
        traceback.print_exc()
    finally:
        if isConfUpdated:
            AgentUtil.persistAgentInfo()

def setAgentConstants():
    #product details
    str_productName = AgentUtil.AGENT_CONFIG.get('PRODUCT', 'product_name')
    AgentConstants.AGENT_REGISTRATION_KEY = AgentUtil.AGENT_CONFIG.get('PRODUCT_REGISTRATION_KEY', str_productName)
    #dms details
    AgentConstants.DMS_SERVER = AgentUtil.AGENT_CONFIG.get('DMS_INFO', 'dms_server_name')
    AgentConstants.DMS_PORT = AgentUtil.AGENT_CONFIG.get('DMS_INFO', 'dms_server_port')
    AgentConstants.DMS_PRODUCT_CODE = AgentUtil.AGENT_CONFIG.get('DMS_INFO', 'dms_product_code')
    if AgentUtil.AGENT_CONFIG.get('PRODUCT', 'product_name') == 'SITE24X7':
        AgentConstants.AGENT_UPGRADE_CONTEXT = 'sagent'
    AgentConstants.AGENT_PREVIOUS_TIME_DIFF = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'time_diff')
    updateAgentConfiguration()
    boolStatus, strAgentVersion = AgentUtil.getAgentBuildNumber()
    if boolStatus:
        AgentConstants.AGENT_VERSION = strAgentVersion


def checkAzureInstance():
    try:
        if AgentConstants.AGENT_INSTANCE_TYPE=='SERVER':
            if os.path.isfile(AgentConstants.AZURE_AGENT_PATH):
                AgentConstants.AGENT_INSTANCE_TYPE=AgentConstants.AZURE_INSTANCE
            elif os.path.exists(AgentConstants.AZURE_LIB_PATH):
                AgentConstants.AGENT_INSTANCE_TYPE=AgentConstants.AZURE_INSTANCE
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,' ************************* Exception while checking for azure instance ************************* '+ repr(e))
        traceback.print_exc()


def loadProductProfile():
    AgentConstants.LINUX_DIST = None
    file_obj = None
    if os.path.exists(AgentConstants.AGENT_PRODUCT_PROFILE_FILE):
        try:
            file_obj = open(AgentConstants.AGENT_PRODUCT_PROFILE_FILE,'r')
            str_data = file_obj.readline()
            str_linDist = str_data.split(';')[0]
            list_linDist = str_linDist.split('=')
            if list_linDist[0] == 'LINUX_DIST':
                AgentConstants.LINUX_DIST = list_linDist[1]
            AgentLogger.log(AgentLogger.STDOUT,'Linux distro from '+repr(AgentConstants.AGENT_PRODUCT_PROFILE_FILE)+' : '+repr(AgentConstants.LINUX_DIST));
            str_data = file_obj.readline()
            str_osVa = str_data.split(';')[0]
            list_osVa = str_osVa.split('=')
            if list_osVa[0] == 'OS_VERSION_ARCH':
                AgentConstants.OS_VERSION_ARCH = list_osVa[1]
            if AgentConstants.OS_VERSION_ARCH:
                AgentLogger.log(AgentLogger.STDOUT,'OS_Version_Arch from '+repr(AgentConstants.AGENT_PRODUCT_PROFILE_FILE)+' : '+repr(AgentConstants.OS_VERSION_ARCH));
        except:
            AgentLogger.log(AgentLogger.MAIN,'************************* Exception while reading the file '+AgentConstants.AGENT_PRODUCT_PROFILE_FILE+' ************************* \n')
            traceback.print_exc()
            bool_returnStatus = False
        finally:
            if not file_obj == None:
                file_obj.close()
    else:
        AgentLogger.log(AgentLogger.MAIN,'************************* Missing Conf File : '+AgentConstants.AGENT_PRODUCT_PROFILE_FILE+' ************************* \n')


def evaluateAgentParameters():
    bool_isAgentInfoModified = False
    AgentLogger.log(AgentLogger.STDOUT,'=========================== AGENT CONSTANTS ===========================')
    list_sections = AgentUtil.AGENT_CONFIG.sections()
    for sec in list_sections:
        for key, value in AgentUtil.AGENT_CONFIG.items(sec):
            if key not in AgentUtil.DONT_PRINT_CONSTANTS:
                AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : '+key+' : '+repr(value))
    AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : AGENT_TIME_ZONE : '+repr(AgentConstants.AGENT_TIME_ZONE))
    AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : AGENT_TIME_DIFF_FROM_GMT : '+repr(AgentConstants.AGENT_TIME_DIFF_FROM_GMT))
    AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : AGENT_REGISTRATION_KEY :  '+str(AgentConstants.AGENT_REGISTRATION_KEY))
    AgentLogger.log(AgentLogger.STDOUT,'=========================== AGENT CONSTANTS ===========================')
    # check and update agent version from $HOME/version.txt - version changes during upgrade.  
    bool_status, str_agentVersion = AgentUtil.getAgentVersion()
    if bool_status:
        if AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_version') == '0' or AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_version') != str_agentVersion:
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'agent_version', str(str_agentVersion))
            bool_isAgentInfoModified = True
    else:
        AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : Unable to obtain agent version from the file : '+AgentConstants.AGENT_VERSION_FILE)
        return False
    if AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_name') == '' or AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_name') == '0':
        AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : SERVER_NAME Is Empty. Agent Initialization Failed!!!')
        return False
    if AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_ip_address') == '':
        AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : SERVER_IP_ADDRESS Is Empty. Agent Initialization Failed!!!')
        return False
    if AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_port') == '' or AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_port') == '0':
        AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : SERVER_PORT Is Empty. Agent Initialization Failed!!!')
        return False
    if AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_protocol') == '' or AgentUtil.AGENT_CONFIG.get('SERVER_INFO', 'server_protocol') == '0':
        AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : SERVER_PROTOCOL Is Empty. Agent Initialization Failed!!!')
        return False
    if AgentUtil.AGENT_CONFIG.get('DMS_INFO', 'dms_server_name') == '' or AgentUtil.AGENT_CONFIG.get('DMS_INFO', 'dms_server_name') == '0':
        AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : DMS_SERVER_NAME Is Empty. Agent Initialization Failed!!!')
        return False
    if AgentUtil.AGENT_CONFIG.get('DMS_INFO', 'dms_server_port') == '' or AgentUtil.AGENT_CONFIG.get('DMS_INFO', 'dms_server_port') == '0':
        AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : DMS_SERVER_PORT Is Empty. Agent Initialization Failed!!!')
        return False
    if AgentUtil.AGENT_CONFIG.get('DMS_INFO', 'dms_product_code') == '' or AgentUtil.AGENT_CONFIG.get('DMS_INFO', 'dms_product_code') == '0':
        AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : DMS_PRODUCT_CODE Is Empty. Agent Initialization Failed!!!')
        return False
    if AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_unique_id') == '0':
        AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'agent_unique_id', str(AgentUtil.getUniqueId()))
        bool_isAgentInfoModified = True
        AgentLogger.log(AgentLogger.STDOUT,'AGENT CONSTANTS : AGENT_UNIQUE_ID Is Empty. Assigned Temporary Value : '+AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_unique_id'))
    if bool_isAgentInfoModified:
        AgentUtil.persistAgentInfo()
    CommunicationHandler.initialize()
    return True

def isAgentRegistered():
    if AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key') == '0':
        return False
    else:
        return True

def addRebootParam(dict_dataForAgentRegistration):
    try:
        for dirname, dirnames, filenames in os.walk(AgentConstants.AGENT_TEMP_DIR):
            for file in filenames:
                if 'reboot_' in file:
                    fileSplit = file.split('_')
                    dict_dataForAgentRegistration['ACTIONREBOOTTIME'] = fileSplit[1]+','+fileSplit[2]
                    AgentLogger.log(AgentLogger.STDOUT,'file name for reboot : '+repr(fileSplit))
                    os.remove(AgentConstants.AGENT_TEMP_DIR+'/'+file)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'exception while adding reboot param ')
        traceback.print_exc()

def format_headers_case(response_headers_data, response_header_attributes):
    for attr in response_header_attributes:
        if attr.lower() in response_headers_data:
            response_headers_data[attr] = response_headers_data[attr.lower()]
            response_headers_data.pop(attr.lower())

def reRegisterAgent():
    bool_toReturn = True
    bool_isFirstTime = True
    bool_isAgentInfoModified = False
    str_servlet = AgentConstants.AGENT_REGISTRATION_SERVLET
    bool_retry = True
    int_retryCount = 0
    error_dict = {}
    dict_dataForAgentRegistration = {}
    agentKey = None
    try:
        AgentUtil.set_auid()
        #Hardcoded Registration Parameters        
        dict_dataForAgentRegistration['custID'] = AgentConstants.CUSTOMER_ID
        dict_dataForAgentRegistration['category'] = AgentUtil.AGENT_CONFIG.defaults().get('category')
        dict_dataForAgentRegistration['updateStatus'] = AgentUtil.AGENT_CONFIG.defaults().get('update_status')
        if os.path.exists(AgentConstants.AGENT_WATCHDOG_SILENT_RESTART_FLAG_FILE):
            AgentLogger.log(AgentLogger.STDOUT,'watcher restart file exists : ')
            dict_dataForAgentRegistration['updateStatus'] = 'no'

        addRebootParam(dict_dataForAgentRegistration)

        dict_dataForAgentRegistration['agentVersion'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_version')
        dict_dataForAgentRegistration['isMasterAgent'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'master_agent')

        dict_dataForAgentRegistration['monagentID'] = AgentConstants.HOST_NAME if AgentConstants.HOST_NAME else 'localhost'
        dict_dataForAgentRegistration['IpAddress'] = AgentConstants.IP_ADDRESS
        dict_dataForAgentRegistration['MACAddress'] = AgentConstants.MAC_ADDRESS
        dict_dataForAgentRegistration['bno'] = AgentConstants.AGENT_VERSION
        dict_dataForAgentRegistration['osName'] = "OSX" if AgentConstants.OS_NAME == AgentConstants.OS_X else AgentConstants.OS_NAME if  AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.FREEBSD_OS] else "Linux"
        dict_dataForAgentRegistration['monagentDNS'] = AgentConstants.HOST_NAME if AgentConstants.HOST_NAME else 'localhost'
        dict_dataForAgentRegistration['monagentKey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        dict_dataForAgentRegistration['agentUniqueID'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_unique_id')
        dict_dataForAgentRegistration['freeServiceFormat'] = 'json'
        dict_dataForAgentRegistration["md"] = "SOURCE_INSTALLATION - {} | USERNAME - {} | ACTUAL_OS - {} | IS_DOCKER_AGENT - {}".format(AgentConstants.IS_VENV_ACTIVATED, AgentConstants.AGENT_USER_NAME, AgentConstants.OS_NAME, AgentConstants.IS_DOCKER_AGENT)
        dict_dataForAgentRegistration['subtype'] = AgentConstants.OS_SUBTYPE_MAPPING.get(AgentConstants.OS_NAME,AgentConstants.OS_NAME)
        dict_dataForAgentRegistration['auid'] = AgentConstants.AUID
        dict_dataForAgentRegistration['auid_old'] = AgentConstants.AUID_OLD
        upTime,serverRestart,bootTime = AgentUtil.getBootTime()
        if not upTime==None:
            dict_dataForAgentRegistration['upTime'] = upTime

        if not serverRestart==None and serverRestart:
            dict_dataForAgentRegistration['serverRestart']='true'

        if not bootTime==None:
            dict_dataForAgentRegistration['bootTime']=bootTime

        if not AgentConstants.DOMAIN_NAME == None:
            dict_dataForAgentRegistration['DomainName'] = AgentConstants.DOMAIN_NAME

        if not AgentConstants.SYSTEM_UUID == None:
            dict_dataForAgentRegistration['uuid'] = AgentConstants.SYSTEM_UUID

        if 'monagentDNS' in dict_dataForAgentRegistration and 'monagentID' in dict_dataForAgentRegistration and dict_dataForAgentRegistration['monagentDNS']=='localhost' and dict_dataForAgentRegistration['monagentID']!='localhost':
            dict_dataForAgentRegistration['monagentDNS'] = dict_dataForAgentRegistration['monagentID']

        if 'monagentDNS' in dict_dataForAgentRegistration and 'monagentID' in dict_dataForAgentRegistration and dict_dataForAgentRegistration['monagentDNS']=='localhost.localdomain' and dict_dataForAgentRegistration['monagentID']!='localhost.localdomain':
            dict_dataForAgentRegistration['monagentDNS'] = dict_dataForAgentRegistration['monagentID']

        if isInstance:
            bool_to_return,id,existing_instance_data = getInstanceId(instanceDict)
            if bool_to_return and id is not None:
                dict_dataForAgentRegistration['instanceId'] = id
                if instanceDict['cloudPlatform'] == 'AWS':
                    if existing_instance_data and id != existing_instance_data['AWS']:
                        dict_dataForAgentRegistration['monagentKey'] = AgentConstants.AGENT_REGISTRATION_KEY
                        AgentLogger.log(AgentLogger.STDOUT,'AWS instance id differs - registering as new server agent')
                        AgentLogger.log(AgentLogger.STDOUT,'existing one :: {} | latest one :: {}'.format(existing_instance_data['AWS'],id))
            else:
                if existing_instance_data and instanceDict['cloudPlatform'] in existing_instance_data:
                    dict_dataForAgentRegistration['instanceId'] = existing_instance_data[instanceDict['cloudPlatform']]
            if 'cloudPlatform' in instanceDict.keys():
                dict_dataForAgentRegistration['cloudPlatform'] = instanceDict['cloudPlatform']
            if instanceDict['cloudPlatform'] == 'Azure':
                bool_result , resource_id = metadata.get_azure_resource_id()
                if bool_result:
                    dict_dataForAgentRegistration['resource_id'] = resource_id
        dict_dataForAgentRegistration['OsArch'] = AgentConstants.OS_ARCHITECTURE
        proxy_param = None
        if AgentUtil.AGENT_CONFIG.has_option('PROXY_INFO', 'proxy_server_name') and not AgentUtil.AGENT_CONFIG.get('PROXY_INFO','proxy_server_name')=='0':
            proxy_param = '1'
        if AgentUtil.AGENT_CONFIG.has_option('PROXY_INFO', 'encrypted_proxy_password') and not AgentUtil.AGENT_CONFIG.get('PROXY_INFO','encrypted_proxy_password')=='0':
            proxy_param= '2'
        if not proxy_param==None:
            dict_dataForAgentRegistration['pp'] = proxy_param
        if AgentConstants.AGENT_SETTINGS:
            dict_dataForAgentRegistration['settings'] = AgentConstants.AGENT_SETTINGS
        if AgentConstants.IPARAMS:
            dict_dataForAgentRegistration['iparams'] = AgentConstants.IPARAMS
        if KubeGlobal.fargate:
            dict_dataForAgentRegistration['EKS_FARGATE'] = "true"
            dict_dataForAgentRegistration['monagentDNS'] = "EKS_FARGATE_"+KubeGlobal.nodeName
            dict_dataForAgentRegistration['subtype'] = "EKS_FARGATE"
        if KubeGlobal.gkeAutoPilot:
            dict_dataForAgentRegistration['EKS_FARGATE'] = "true"
            dict_dataForAgentRegistration['monagentDNS'] = "GKE_AUTOPILOT_"+KubeGlobal.nodeName
            dict_dataForAgentRegistration['subtype'] = "GKE_AUTOPILOT"
        if KubeGlobal.nonMountedAgent:
            dict_dataForAgentRegistration['EKS_FARGATE'] = "true"
            dict_dataForAgentRegistration['monagentDNS'] = "OpenShift_"+KubeGlobal.nodeName
            dict_dataForAgentRegistration['subtype'] = "OpenShift"
        AgentLogger.log([AgentLogger.STDOUT],'================================= RE-REGISTER AGENT =================================')
        while bool_retry and not AgentUtil.TERMINATE_AGENT:
            bool_retry = False
            int_retryCount+=1
            if int_retryCount > AgentConstants.AGENT_REGISTRATION_RETRY_COUNT:
                bool_toReturn = False
                AgentUtil.RestartAgent()
                AgentLogger.log([AgentLogger.STDOUT, AgentLogger.MAIN],'************* Failed to re-register agent more than 10 times *************** Restarting Agent \n' )
                break
            elif not bool_isFirstTime:
                AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(AgentConstants.AGENT_REGISTRATION_RETRY_INTERVAL)
            elif bool_isFirstTime:
                bool_isFirstTime = False
            try:
                dict_dataForAgentRegistration['timeStamp'] = str(AgentUtil.getCurrentTimeInMillis())
                registration_params_copy = dict_dataForAgentRegistration.copy()
                if "custID" in registration_params_copy:
                    registration_params_copy.pop("custID")
                AgentLogger.log(AgentLogger.STDOUT,'Data For Registration : '+repr(registration_params_copy))
                str_url = None
                if not dict_dataForAgentRegistration == None:
                    str_requestParameters = urlencode(dict_dataForAgentRegistration)
                    str_url = str_servlet + str_requestParameters
                requestInfo = CommunicationHandler.RequestInfo()
                requestInfo.set_loggerName(AgentLogger.STDOUT)
                requestInfo.set_method(AgentConstants.HTTP_POST)
                requestInfo.set_url(str_url)
                requestInfo.add_header("Content-Type", 'application/json')
                requestInfo.add_header("Accept", "text/plain")
                requestInfo.add_header("Connection", 'close')
                (isSuccess, int_errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
                if AgentConstants.PYTHON_VERSION == 2 and dict_responseHeaders:
                    format_headers_case(dict_responseHeaders, ["FREE_SERVICE_DETAILS", "errorCode", "agentKey", "NSPORT", "timeDiff","customerid", "customername"])
                CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'REGISTER AGENT')
                if dict_responseData:
                    dict_responseData = json.loads(dict_responseData)
                    if dict_responseData and "ERROR_CODE" in dict_responseData:
                        error_dict = dict_responseData["ERROR_CODE"]
                        AgentLogger.log(AgentLogger.MAIN,'Agent Registration Failure due to Error Code : {}'.format(error_dict)+"\n")
                        bool_retry = True
                        continue
                    else:
                        error_dict = {}
                if not isSuccess:
                    AgentLogger.log(AgentLogger.MAIN,'*************************** Unable To Send Agent Registration Data To Server. Will Retry Registration After 30 seconds *************************** \n')
                    bool_retry = True
                elif isSuccess and dict_responseHeaders == None:
                    AgentLogger.log(AgentLogger.MAIN,'*************************** Registration Response From The Server Is None. Will Retry Registration After 30 seconds *************************** \n')
                    bool_retry = True
                else:
                    AgentLogger.log(AgentLogger.STDOUT,'Response Headers :'+repr(dict_responseHeaders))
                    if 'status' in dict_responseHeaders and dict_responseHeaders['status'] == 'failure' and 'errorCode' in dict_responseHeaders and dict_responseHeaders['errorcode'] == 'RETRY':
                        AgentLogger.log(AgentLogger.STDERR,' *************************** Register Agent FAILED and Server Has Requested For RETRY *************************** ')
                        bool_retry = True
                        continue
                    elif 'status' in dict_responseHeaders and dict_responseHeaders['status'] == 'failure' and 'errorCode' in dict_responseHeaders and dict_responseHeaders['errorcode'] == 'TERMINATE_AGENT':
                        AgentLogger.log(AgentLogger.STDERR,' *************************** Register Agent FAILED and Server Has Requested For TERMINATE_AGENT *************************** ')
                        AgentUtil.TerminateAgent()
                        return False
                    nsPort = None
                    timeDiff = None
                    customerId = None
                    customerName = None
                    if 'agentKey' in dict_responseHeaders:
                        agentKey = dict_responseHeaders['agentKey']
                        if not agentKey == '' and not agentKey == '0' and not agentKey == AgentConstants.AGENT_REGISTRATION_KEY and not agentKey == None:
                            old_key = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
                            AgentLogger.log(AgentLogger.MAIN, "Re-Register Agent key Update  : new_key {} | old_key {}".format(agentKey, old_key)+'\n')
                            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'agent_key', agentKey)
                            bool_isAgentInfoModified = True
                            if agentKey != old_key:
                                AgentUtil.reinit_childs()
                    else:
                        AgentLogger.log(AgentLogger.MAIN,'*************************** Unable To Send Agent Registration Data To Server. Will Retry Registration After 30 seconds *************************** \n')
                        bool_retry = True
                        continue
                    if 'NSPORT' in dict_responseHeaders:
                        nsPort = dict_responseHeaders['NSPORT']
                    if 'timeDiff' in dict_responseHeaders:
                        timeDiff = dict_responseHeaders['timeDiff']
                    if 'customerid' in dict_responseHeaders:
                        customerId = dict_responseHeaders['customerid']
                    if 'customername' in dict_responseHeaders:
                        customerName = dict_responseHeaders['customername']
                    if not nsPort == '' or not nsPort == None:
                        AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'ns_port', nsPort)
                        bool_isAgentInfoModified = True
                    if not timeDiff == '' or not timeDiff == None:
                        AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'time_diff', timeDiff)
                        bool_isAgentInfoModified = True
            except Exception as e:
                AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],'*************************** Exception While Re-Registering Agent *************************** '+ repr(e))
                traceback.print_exc()
                bool_retry = True
                bool_toReturn = False
        if (not agentKey or agentKey == '0' or agentKey == AgentConstants.AGENT_REGISTRATION_KEY):
            AgentLogger.log(AgentLogger.MAIN,'*************************** Agent Key Not Received From Server *************************** \n')
            bool_toReturn = False
        if bool_isAgentInfoModified:
            AgentUtil.persistAgentInfo()
    except Exception as e:
        AgentLogger.log([AgentLogger.STDOUT,AgentLogger.STDERR],'*************************** Exception While Re-Registering Agent *************************** '+ repr(e))
        traceback.print_exc()
        bool_toReturn = False
    finally:
        if bool_toReturn:
            AgentConstants.AGENT_REGISTRATION_TIME = AgentUtil.getCurrentTimeInMillis()
            AgentConstants.AGENT_TIME_DIFF_BASED_REGISTRATION_TIME = AgentUtil.getTimeInMillis(AgentConstants.AGENT_REGISTRATION_TIME)
        AgentLogger.log(AgentLogger.STDOUT,'AGENT_REGISTRATION_TIME : '+repr(AgentUtil.getFormattedTime(AgentConstants.AGENT_REGISTRATION_TIME))+' --> '+repr(AgentConstants.AGENT_REGISTRATION_TIME))
        AgentLogger.log(AgentLogger.STDOUT,'AGENT_TIME_DIFF_BASED_REGISTRATION_TIME : '+repr(AgentUtil.getFormattedTime(AgentConstants.AGENT_TIME_DIFF_BASED_REGISTRATION_TIME))+' --> '+repr(AgentConstants.AGENT_TIME_DIFF_BASED_REGISTRATION_TIME))
    return bool_toReturn

def getInstanceId(instance_dict):
    try:
        result_dict = {}
        bool_to_return = True
        existing_instance_data = {}
        if os.path.exists(AgentConstants.META_INSTANCE_FILE_PATH):
            with open(AgentConstants.META_INSTANCE_FILE_PATH,'r') as fp:
                existing_instance_data = json.loads(fp.read())
        AgentLogger.log(AgentLogger.STDOUT,'existing instance data :: {}'.format(existing_instance_data))
        id = None
        unique_key = instance_dict['key']
        if unique_key in instance_dict:
            id = instance_dict[unique_key]
            result_dict[instance_dict['cloudPlatform']] = id
            with open(AgentConstants.META_INSTANCE_FILE_PATH, "w") as fp:
                fp.write(json.dumps(result_dict))
    except Exception as e:
        bool_to_return = False
        AgentLogger.log(AgentLogger.STDOUT,'****************************** Exception while getting the instance id ********************************** '+repr(e))
        traceback.print_exc()
    AgentLogger.log(AgentLogger.STDOUT,'Instance id of the server : '+str(id))
    return bool_to_return,id,existing_instance_data

def getInstanceMetadata():
    global metadata_dict
    try:
        resp_dict={}
        bool_To_Return = False
        AgentLogger.log(AgentLogger.STDOUT,'Loading the url to get the instance metaData')
        for k , v in AgentConstants.INSTANCE_METADATA_IMPL.items():
            file_to_be_invoked = sys.modules["com.manageengine.monagent.cloud.metadata"]
            method_name = v
            bool_To_Return, resp_dict, metadata_dict = getattr(file_to_be_invoked,method_name)()
            if bool_To_Return:
                if resp_dict:
                    if resp_dict.get('privateIp', None) and (not AgentConstants.IP_ADDRESS or AgentConstants.IP_ADDRESS == "127.0.0.1"):
                        AgentConstants.IP_ADDRESS = resp_dict['privateIp']
                    if not AgentConstants.HOST_NAME and 'hostname' in resp_dict and resp_dict['hostname']:
                        AgentConstants.HOST_NAME = AgentConstants.HOST_FQDN_NAME = resp_dict['hostname'].split()[0]
                break
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'****************************** Exception while getting the instance metaData ********************************** '+repr(e))
        traceback.print_exc()
    return bool_To_Return,resp_dict

def sendinstanceMetadata():
    dict_requestParameters = {}
    try:
        AgentLogger.debug(AgentLogger.STDOUT,'MetaData to send : ' + repr(metadata_dict))
        dict_requestParameters['custID'] = AgentConstants.CUSTOMER_ID
        dict_requestParameters['agentKey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
        dict_requestParameters['action'] = AgentConstants.METADATA
        str_requestParameters = urlencode(dict_requestParameters)
        str_servlet = AgentConstants.DATA_AGENT_HANDLER_SERVLET
        str_url = str_servlet + str_requestParameters
        str_jsonData = json.dumps(metadata_dict)
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.STDOUT)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.set_data(str_jsonData)
        requestInfo.add_header("Content-Type", 'application/json')
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        (isSuccess, int_errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
        if not isSuccess:
            AgentLogger.log(AgentLogger.STDOUT,'Sending Agent MetaData failed : Errorcode:'+repr(int_errorCode))
        else:
            AgentLogger.log(AgentLogger.STDOUT,'Agent MetaData sent successfully :'+repr(dict_responseData))
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'****************************** Exception while posting the instance metaData ********************************** '+repr(e))
        traceback.print_exc()

def persistDomains(list_domains):
    try:
        list_dict={}
        AgentUtil.AGENT_CONFIG.set('SERVER_INFO', 'server_name',list_domains[0])
        AgentUtil.AGENT_CONFIG.set('SECONDARY_SERVER_INFO', 'server_name',list_domains[1])
        list_dict['servers_list']=list_domains[2]
        AgentConstants.STATIC_SERVER_HOST=list_domains[3]
        AgentUtil.AGENT_CONFIG.set('DMS_INFO', 'dms_server_name',list_domains[4])
        AgentConstants.DMS_SERVER = AgentUtil.AGENT_CONFIG.get('DMS_INFO', 'dms_server_name')
        AgentUtil.persistAgentInfo()
        AgentUtil.writeDataToFile(AgentConstants.AGENT_STATUS_UPDATE_SERVER_LIST_FILE,list_dict)
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'****************************** Exception while persisting Domain info for registration ********************************** '+repr(e))
        traceback.print_exc()

def registerAgent():
    bool_toReturn = True
    bool_isFirstTime = True
    bool_isAgentRegistered = False
    str_servlet = AgentConstants.AGENT_REGISTRATION_SERVLET
    int_retryCount = 0
    error_dict = {}
    dict_dataForAgentRegistration = {}
    agentKey = None
    try:
        #Hardcoded Registration Parameters        
        dict_dataForAgentRegistration['custID'] = AgentConstants.CUSTOMER_ID
        dict_dataForAgentRegistration['category'] = AgentUtil.AGENT_CONFIG.defaults().get('category')
        dict_dataForAgentRegistration['updateStatus'] = AgentUtil.AGENT_CONFIG.defaults().get('update_status')
        dict_dataForAgentRegistration['agentVersion'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_version')
        dict_dataForAgentRegistration['isMasterAgent'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'master_agent')
        dict_dataForAgentRegistration['bno'] = AgentConstants.AGENT_VERSION
        #dict_dataForAgentRegistration['agentType'] = AgentConstants.OS_NAME
        dict_dataForAgentRegistration['monagentID'] = AgentConstants.HOST_NAME if AgentConstants.HOST_NAME else 'localhost'
        dict_dataForAgentRegistration['IpAddress'] = AgentConstants.IP_ADDRESS
        dict_dataForAgentRegistration['MACAddress'] = AgentConstants.MAC_ADDRESS
        #dict_dataForAgentRegistration['osFlavor'] = AgentConstants.OS_FLAVOR
        dict_dataForAgentRegistration['osName'] = "OSX" if AgentConstants.OS_NAME == AgentConstants.OS_X else AgentConstants.OS_NAME if  AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.FREEBSD_OS] else "Linux"
        #dict_dataForAgentRegistration["serverOs"] = AgentConstants.OS_NAME
        dict_dataForAgentRegistration['monagentDNS'] = AgentConstants.HOST_NAME if AgentConstants.HOST_NAME else 'localhost'
        dict_dataForAgentRegistration['monagentKey'] = AgentConstants.AGENT_REGISTRATION_KEY
        dict_dataForAgentRegistration['agentUniqueID'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_unique_id')
        dict_dataForAgentRegistration['freeServiceFormat'] = 'json'
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','service_manager'): 
            service_manager = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'service_manager')
        else:
            service_manager = '-'
        dict_dataForAgentRegistration["md"] = "SOURCE_INSTALLATION - {} | USERNAME - {} | ACTUAL_OS - {} | IS_DOCKER_AGENT - {} | SERVICE_MANAGER - {}".format(AgentConstants.IS_VENV_ACTIVATED, AgentConstants.AGENT_USER_NAME, AgentConstants.OS_NAME, AgentConstants.IS_DOCKER_AGENT, service_manager)
        installed_by_user = AgentUtil.get_installedby()
        if installed_by_user:
            dict_dataForAgentRegistration["md"] += " | INSTALLEDBY - {}".format(installed_by_user)
        dict_dataForAgentRegistration['subtype'] = AgentConstants.OS_SUBTYPE_MAPPING.get(AgentConstants.OS_NAME,AgentConstants.OS_NAME)
        #if str(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'location')) != "0":
        #    dict_dataForAgentRegistration['location'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'location')
        if not dict_dataForAgentRegistration['subtype'] == 'SunOS':
            upTime = AgentUtil.getUpTime()
            if not upTime == None:
                dict_dataForAgentRegistration['upTime']=upTime

        if not AgentConstants.DOMAIN_NAME == None:
            dict_dataForAgentRegistration['DomainName'] = AgentConstants.DOMAIN_NAME

        if not AgentConstants.SYSTEM_UUID == None:
            dict_dataForAgentRegistration['uuid'] = AgentConstants.SYSTEM_UUID


        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','display_name') and not AgentUtil.AGENT_CONFIG.get('AGENT_INFO','display_name')=='0':
            dict_dataForAgentRegistration['dn'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','display_name')

        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','group_name') and not AgentUtil.AGENT_CONFIG.get('AGENT_INFO','group_name')=='0':
            dict_dataForAgentRegistration['gn'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','group_name')

        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','threshold_profile') and not AgentUtil.AGENT_CONFIG.get('AGENT_INFO','threshold_profile')=='0':
            dict_dataForAgentRegistration['tp'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','threshold_profile')

        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','notification_profile') and not AgentUtil.AGENT_CONFIG.get('AGENT_INFO','notification_profile')=='0':
            dict_dataForAgentRegistration['np'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','notification_profile')

        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','resource_profile') and not AgentUtil.AGENT_CONFIG.get('AGENT_INFO','resource_profile')=='0':
            dict_dataForAgentRegistration['rp'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','resource_profile')

        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','installer') and not AgentUtil.AGENT_CONFIG.get('AGENT_INFO','installer')=='0':
            dict_dataForAgentRegistration['installer'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','installer')

        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','configuration_template') and not AgentUtil.AGENT_CONFIG.get('AGENT_INFO','configuration_template')=='0':
            dict_dataForAgentRegistration['ct'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','configuration_template')
        
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','alert_group') and not AgentUtil.AGENT_CONFIG.get('AGENT_INFO','alert_group')=='0':
            dict_dataForAgentRegistration['ag'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','alert_group')

        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','rule') and not AgentUtil.AGENT_CONFIG.get('AGENT_INFO','rule')=='0':
            dict_dataForAgentRegistration['rule'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','rule')

        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','tags') and not AgentUtil.AGENT_CONFIG.get('AGENT_INFO','tags')=='0':
            dict_dataForAgentRegistration['tags'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','tags')

        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','log_profile') and not AgentUtil.AGENT_CONFIG.get('AGENT_INFO','log_profile')=='0':
            dict_dataForAgentRegistration['lp'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','log_profile')
        
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','log_type') and not AgentUtil.AGENT_CONFIG.get('AGENT_INFO','log_type')=='0':
            dict_dataForAgentRegistration['lt'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','log_type')
        
        if AgentUtil.AGENT_CONFIG.has_option('AGENT_INFO','log_files') and not AgentUtil.AGENT_CONFIG.get('AGENT_INFO','log_files')=='0':
            dict_dataForAgentRegistration['lf'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO','log_files')
            
        if AgentConstants.AWS_TAGS:
            dict_dataForAgentRegistration['aws_tags'] = AgentConstants.AWS_TAGS

        if AgentConstants.AGENT_SETTINGS:
            dict_dataForAgentRegistration['settings'] = AgentConstants.AGENT_SETTINGS

        if AgentConstants.IPARAMS:
            dict_dataForAgentRegistration['iparams'] = AgentConstants.IPARAMS


        if 'monagentDNS' in dict_dataForAgentRegistration and 'monagentID' in dict_dataForAgentRegistration and dict_dataForAgentRegistration['monagentDNS']=='localhost' and dict_dataForAgentRegistration['monagentID']!='localhost':
            dict_dataForAgentRegistration['monagentDNS'] = dict_dataForAgentRegistration['monagentID']

        if 'monagentDNS' in dict_dataForAgentRegistration and 'monagentID' in dict_dataForAgentRegistration and dict_dataForAgentRegistration['monagentDNS']=='localhost.localdomain' and dict_dataForAgentRegistration['monagentID']!='localhost.localdomain':
            dict_dataForAgentRegistration['monagentDNS'] = dict_dataForAgentRegistration['monagentID']

        if KubeGlobal.fargate:
            dict_dataForAgentRegistration["EKS_FARGATE"] = "true"
            dict_dataForAgentRegistration['monagentDNS'] = "EKS_FARGATE_"+KubeGlobal.nodeName
            dict_dataForAgentRegistration['subtype'] = "EKS_FARGATE"

        if KubeGlobal.gkeAutoPilot:
            dict_dataForAgentRegistration['EKS_FARGATE'] = "true"
            dict_dataForAgentRegistration['monagentDNS'] = "GKE_AUTOPILOT_"+KubeGlobal.nodeName
            dict_dataForAgentRegistration['subtype'] = "GKE_AUTOPILOT"

        if KubeGlobal.nonMountedAgent:
            dict_dataForAgentRegistration['EKS_FARGATE'] = "true"
            dict_dataForAgentRegistration['monagentDNS'] = "OpenShift_"+KubeGlobal.nodeName
            dict_dataForAgentRegistration['subtype'] = "OpenShift"
        
        if AgentConstants.IS_DOCKER_AGENT == '1' and com.manageengine.monagent.kubernetes.KubeUtil.check_kube_presents():
            dict_dataForAgentRegistration['kubePresent'] = "true"
            dict_dataForAgentRegistration['kubeServerName'] = KubeGlobal.kubeServer
            AgentLogger.log(AgentLogger.MAIN, "*************** Kubernetes Environment Identified - Control plane {} ***************".format(KubeGlobal.kubeServer))

        # if os.environ and "DELAY_AGENT_START" in os.environ and AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key') == '0':
        #     dict_dataForAgentRegistration['agent_start_delayed'] = os.environ["DELAY_AGENT_START"]

        if isInstance:
            bool_to_return,id,existing_instance_data = getInstanceId(instanceDict)
            if bool_to_return and id is not None:
                dict_dataForAgentRegistration['instanceId'] = id
            if 'cloudPlatform' in instanceDict.keys():
                dict_dataForAgentRegistration['cloudPlatform'] = instanceDict['cloudPlatform']
            if instanceDict['cloudPlatform'] == 'Azure':
                bool_result , resource_id = metadata.get_azure_resource_id()
                if bool_result:
                    dict_dataForAgentRegistration['resource_id'] = resource_id

        dict_dataForAgentRegistration['OsArch'] = AgentConstants.OS_ARCHITECTURE
        proxy_param = None
        if AgentUtil.AGENT_CONFIG.has_option('PROXY_INFO', 'proxy_server_name') and not AgentUtil.AGENT_CONFIG.get('PROXY_INFO','proxy_server_name')=='0':
            proxy_param = '1'
        if AgentUtil.AGENT_CONFIG.has_option('PROXY_INFO', 'encrypted_proxy_password') and not AgentUtil.AGENT_CONFIG.get('PROXY_INFO','encrypted_proxy_password')=='0':
            proxy_param= '2'
        if not proxy_param==None:
            dict_dataForAgentRegistration['pp'] = proxy_param

        registration_params_copy = dict_dataForAgentRegistration.copy()
        if "custID" in registration_params_copy:
            registration_params_copy.pop("custID")

        AgentLogger.log(AgentLogger.STDOUT,' Data For Registration ======> {0}'.format(json.dumps(registration_params_copy)))
        while not bool_isAgentRegistered and not AgentUtil.TERMINATE_AGENT:
            int_retryCount+=1
            bool_isAgentInfoModified = False
            if int_retryCount > AgentConstants.AGENT_REGISTRATION_RETRY_COUNT:
                bool_toReturn = False
                AgentUtil.RestartAgent()
                AgentLogger.log([AgentLogger.STDOUT, AgentLogger.MAIN],'************* Failed to register agent more than 10 times *************** Restarting Agent \n' )
                break
            elif not bool_isFirstTime:
                AgentUtil.TERMINATE_AGENT_NOTIFIER.wait(AgentConstants.AGENT_REGISTRATION_RETRY_INTERVAL)
            elif bool_isFirstTime:
                bool_isFirstTime = False
            try:
                AgentLogger.log(AgentLogger.STDOUT,'REGISTER AGENT : =============================== TRYING TO REGISTER AGENT =============================== \n')
                dict_dataForAgentRegistration['timeStamp'] = str(AgentUtil.getCurrentTimeInMillis())
                str_url = None
                if not dict_dataForAgentRegistration == None:
                    str_requestParameters = urlencode(dict_dataForAgentRegistration)
                    str_url = str_servlet + str_requestParameters
                requestInfo = CommunicationHandler.RequestInfo()
                requestInfo.set_loggerName(AgentLogger.STDOUT)
                requestInfo.set_method(AgentConstants.HTTP_POST)
                requestInfo.set_url(str_url)
                requestInfo.add_header("Content-Type", 'application/json')
                requestInfo.add_header("Accept", "text/plain")
                requestInfo.add_header("Connection", 'close')
                (isSuccess, int_errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
                if dict_responseData:
                    AgentLogger.debug(AgentLogger.MAIN,'Response Data : {}'.format(dict_responseData)+"\n")
                    dict_responseData = json.loads(dict_responseData)
                    if dict_responseData and "ERROR_CODE" in dict_responseData:
                        error_dict = dict_responseData["ERROR_CODE"]
                        AgentLogger.log(AgentLogger.MAIN,'Agent Registration Failure due to Error Code : {}'.format(error_dict)+"\n")
                        continue
                    else:
                        error_dict = {}
                if AgentConstants.PYTHON_VERSION == 2 and dict_responseHeaders:
                    format_headers_case(dict_responseHeaders, ["FREE_SERVICE_DETAILS", "errorCode", "agentKey", "NSPORT", "timeDiff","customerid", "customername"])
                AgentLogger.debug(AgentLogger.STDOUT, 'dict_responseHeaders : '+repr(dict_responseHeaders))
                CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'REGISTER AGENT')
                if not isSuccess:
                    AgentLogger.log(AgentLogger.MAIN,'\n\n *************************** Unable To Send Agent Registration Data To Server. Will Retry Registration After '+str(AgentConstants.AGENT_REGISTRATION_RETRY_INTERVAL)+' seconds *************************** \n\n')
                elif isSuccess and dict_responseHeaders == None:
                    AgentLogger.log(AgentLogger.STDOUT,' *************************** Registration Response From The Server Is None. Will Retry Registration After '+str(AgentConstants.AGENT_REGISTRATION_RETRY_INTERVAL)+' seconds *************************** ')
                else:
                    AgentLogger.log(AgentLogger.STDOUT,'Response Headers :'+repr(dict_responseHeaders))
                    if 'status' in dict_responseHeaders and dict_responseHeaders['status'] == 'failure' and 'errorCode' in dict_responseHeaders and dict_responseHeaders['errorcode'] == 'RETRY':
                        AgentLogger.log(AgentLogger.STDOUT,' *************************** Register Agent FAILED and Server Has Requested For RETRY *************************** ')
                        continue
                    elif 'status' in dict_responseHeaders and dict_responseHeaders['status'] == 'failure' and 'errorCode' in dict_responseHeaders and dict_responseHeaders['errorcode'] == 'TERMINATE_AGENT':
                        AgentLogger.log(AgentLogger.STDOUT,' *************************** Register Agent FAILED and Server Has Requested For TERMINATE_AGENT *************************** ')
                        AgentUtil.TerminateAgent()
                        return False
                    elif 'status' in dict_responseHeaders and dict_responseHeaders['status'] == 'SUCCESS' and 'RETRY_NEEDED' in dict_responseHeaders and dict_responseHeaders['RETRY_NEEDED'] == "true" and 'RETRY_INTERVAL' in dict_responseHeaders:
                        retry_intrv = int(dict_responseHeaders["RETRY_INTERVAL"])
                        AgentLogger.log(AgentLogger.MAIN, "*********** Kube Cluster is in suspended state, So retry after {} mins ***********".format(retry_intrv))
                        int_retryCount = 0
                        time.sleep(retry_intrv * 60)
                        continue
                    CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'REGISTER AGENT')
                    nsPort = None
                    timeDiff = None
                    customerId = None
                    customerName = None
                    if 'agentKey' in dict_responseHeaders:
                        agentKey = dict_responseHeaders['agentKey']
                    if 'NSPORT' in dict_responseHeaders:
                        nsPort = dict_responseHeaders['NSPORT']
                    if 'timeDiff' in dict_responseHeaders:
                        timeDiff = dict_responseHeaders['timeDiff']
                    if 'customerid' in dict_responseHeaders:
                        customerId = dict_responseHeaders['customerid']
                    if 'customername' in dict_responseHeaders:
                        customerName = dict_responseHeaders['customername']
                    if not agentKey == '' and not agentKey == '0' and not agentKey == AgentConstants.AGENT_REGISTRATION_KEY and not agentKey == None:
                        AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'agent_key', agentKey)
                        bool_isAgentRegistered = True
                        AgentLogger.log(AgentLogger.MAIN,'Agent Registration with Server | Status - Success \n')
                        AgentLogger.log(AgentLogger.MAIN,'Agent Unique Key from Server : '+repr(agentKey)+'\n')
                        bool_isAgentInfoModified = True
                        bool_toReturn = True
                        if AgentConstants.AGENT_REGISTRATION_KEY == "SITE24X7NEW" or AgentUtil.AGENT_CONFIG.get('PRODUCT_REGISTRATION_KEY', 'site24x7') == "SITE24X7NEW":
                            AgentLogger.log(AgentLogger.MAIN, "Product Registration Key configured for New Monitor - {} :: {}".format(AgentConstants.AGENT_REGISTRATION_KEY, AgentUtil.AGENT_CONFIG.get('PRODUCT_REGISTRATION_KEY', 'site24x7')))
                            AgentUtil.AGENT_CONFIG.set('PRODUCT_REGISTRATION_KEY', 'site24x7', "SITE24X7")
                            AgentConstants.AGENT_REGISTRATION_KEY = "SITE24X7"
                        if not nsPort == '' and not nsPort == None:
                            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'ns_port', nsPort)
                            bool_isAgentInfoModified = True
                        if not timeDiff == '' and not timeDiff == None:
                            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'time_diff', timeDiff)
                            bool_isAgentInfoModified = True
                        if not customerId == '' and not customerId == None:
                            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'customer_id', customerId)
                            bool_isAgentInfoModified = True
                        if not customerName == '' and not customerName == None:
                            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'customer_name', customerName)
                            bool_isAgentInfoModified = True
                    else:
                        AgentLogger.log(AgentLogger.MAIN,'*************************** Unable To Send Agent Registration Data To Server. Will Retry Registration After 30 seconds *************************** \n')
            except Exception as e:
                AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR],'*************************** Exception While Registering Agent *************************** '+ repr(e))
                traceback.print_exc()
                bool_toReturn = False
        if (not agentKey or agentKey == '0' or agentKey == AgentConstants.AGENT_REGISTRATION_KEY):
            AgentLogger.log(AgentLogger.MAIN,'*************************** Agent Key Not Received From Server After Retrying {} Times *************************** \n'.format(AgentConstants.AGENT_REGISTRATION_RETRY_COUNT))
            bool_toReturn = False
        if bool_isAgentInfoModified:
            AgentUtil.persistAgentInfo()
    except Exception as e:
        AgentLogger.log(AgentLogger.CRITICAL,'*************************** Exception While Registering Agent *************************** '+ repr(e))
        traceback.print_exc()
        bool_toReturn = False
    return bool_toReturn

def getwmsdata():
    AgentLogger.log(AgentLogger.MAIN, "interactive wms thread started")
    try:
        from com.manageengine.monagent.communication import CommunicationHandler
        while True:
            import time
            CommunicationHandler.getConsolidatedWMSData()
            time.sleep(10)
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN, "interactive wms thread started exception {}".format(e))
        traceback.print_exc()

def check_and_set_start_delay():
    try:
        if os.environ and "DELAY_AGENT_START" in os.environ and AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key') == '0':
            delay_secs = int(os.environ["DELAY_AGENT_START"])
            AgentLogger.log(AgentLogger.MAIN, "******** Delaying Agent Registration for {} secs ********".format(delay_secs))
            time.sleep(delay_secs)
    except Exception as e:
        traceback.print_exc()
        
