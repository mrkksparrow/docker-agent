#$Id$
import time
import platform
import os
import sys
import tempfile
import getpass
import traceback
from pwd import getpwnam
import pwd
import traceback
import re
#http://stackoverflow.com/questions/4189123/python-how-to-get-number-of-mili-seconds-per-jiffy
#KERNEL_CPU_SPEED = os.sysconf(os.sysconf_names['SC_CLK_TCK']) # kernel constant USER_HZ
#from os.path import expanduser

from com.manageengine.monagent import activepool

'''pool holders'''
thread_pool_handler = activepool.ActivePool()

'''import needed packages'''

try:
    from xmljson import badgerfish
    XMLJSON_BF = badgerfish
except Exception as e:
    XMLJSON_BF = None


try:
    import requests
    REQUEST_MODULE = requests
except Exception as e:
    REQUEST_MODULE = None

#scp module
try:
    import scp
    SCP_OBJECT = scp
except Exception as e:
    SCP_OBJECT = None
#psutil module
try:
    import psutil
    PSUTIL_OBJECT = psutil
except Exception as e:
    PSUTIL_OBJECT = None
#crypto module
try:
    import Crypto
    CRYPTO_MODULE = Crypto
except Exception as e:
    CRYPTO_MODULE = None

#docker module
try:
    import docker
    DOCKER_MODULE = docker
except Exception as e:
    DOCKER_MODULE = None

#websocket module
try:
    import websocket
    WEBSOCKET_MODULE = websocket
except Exception as e:
    WEBSOCKET_MODULE = None

try:
    try:
        AGENT_USER_NAME = pwd.getpwuid(os.getuid()).pw_name
        AGENT_USER_ID = os.getuid()
    except Exception as e:
        AGENT_USER_NAME = getpass.getuser()
        AGENT_USER_ID = getpwnam(AGENT_USER_NAME).pw_uid
except Exception:
    AGENT_USER_NAME = "nonroot"
    AGENT_USER_ID = 10

ISROOT_AGENT = True if AGENT_USER_NAME == 'root' else False
current_milli_time = lambda: int(round(time.time() * 1000))

def get_user_id(username=None):
    username = getpass.getuser() if not username else username
    uid = getpwnam(username).pw_uid
    return uid


PRODUCT_NAME='Site24x7'
PRODUCT_NAME_UPPERCASE='SITE24X7'
PRODUCT_NAME_LOWERCASE='site24x7'

AGENT_NAME = PRODUCT_NAME + ' Linux Agent'

#FreeBSD OS
FREEBSD_OS = 'FreeBSD'
FREEBSD_OS_LOWERCASE = 'freebsd'
OS_X = 'OSX'
AIX_OS = 'AIX'
SUN_OS = "sunos"
# Linux OS
LINUX_OS = 'Linux'
LINUX_OS_UPPERCASE = 'LINUX'
LINUX_OS_LOWERCASE = 'linux'
LINUX_DIST = None
REDHAT = 'RedHat'
SUSE = 'Suse'
MANDRAKE = 'Mandrake'
FEDORA = 'Fedora'
DEBIAN = 'Debian'
OTHER_OS = "Other"

# Mac OS
MACINTOSH_OS = 'Macintosh'
DARWIN_OS = 'Darwin'

# AIX OS
AIX_OS = 'AIX'
AIX_OS_LOWERCASE = 'aix'

THIRTY_TWO_BIT = '32bit'
SIXTY_FOUR_BIT = '64bit'

OS_VERSION_ARCH = None

SECONDARY_SERVER_NAME = 'plus2.site24x7.com'
SECONDARY_SERVER_IP_ADDRESS = 0
SECONDARY_SERVER_PORT = 443
SECONDARY_SERVER_PROTOCOL = 'https'
SECONDARY_SERVER_TIMEOUT = 15

SERVER_TIMEOUT = 30

AGENT_VERSION = None
# if platform.system() == 'Darwin':
#     AGENT_WORKING_DIR = os.getcwd()
# else:
AGENT_VENV_BIN_PYTHON = None
if not "watchdog" in sys.argv[0].lower():
    AGENT_SRC_CHECK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[0]))))
else:
    AGENT_SRC_CHECK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[0])))))
splitted_paths = os.path.split(AGENT_SRC_CHECK)
if splitted_paths[1].lower() == "com":
    IS_VENV_ACTIVATED = True
    AGENT_WORKING_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(AGENT_SRC_CHECK))))))
    AGENT_VENV_BIN_PYTHON = os.path.join(os.path.dirname(AGENT_WORKING_DIR), "venv", "bin", "python")
    AGENT_VENV_LIB_PYTHON = os.path.join(os.path.dirname(AGENT_WORKING_DIR), "venv", "lib")
    METRICS_EXECUTOR_PATH=AGENT_VENV_BIN_PYTHON +' '+os.path.dirname(os.path.realpath(sys.argv[0]))+'/metrics/metrics_agent.py'
    SOURCE_PKG = os.path.join(AGENT_WORKING_DIR,"lib/devops/source/python3.3/src/com/manageengine/monagent")
    if not os.path.isfile(AGENT_VENV_BIN_PYTHON):
        AGENT_VENV_BIN_PYTHON = None
else:
    IS_VENV_ACTIVATED = False
    AGENT_WORKING_DIR = os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[0])))
    METRICS_EXECUTOR_PATH=os.path.dirname(os.path.realpath(sys.argv[0]))+'/Site24x7MetricsAgent'
    if "32" in platform.architecture()[0]:
        SOURCE_PKG = os.path.join(AGENT_WORKING_DIR,"lib","lib/python3.3/com/manageengine/monagent")
    else:
        SOURCE_PKG = os.path.join(AGENT_WORKING_DIR,"lib","lib/com/manageengine/monagent")
AGENT_BIN_DIR = AGENT_WORKING_DIR + '/bin'

PYTHON_VERSION = sys.version_info[0]

#if platform.system() == 'Darwin':
#    AGENT_LOG_DIR = '/var/log/Site24x7_Agent'
#else:
AGENT_SOURCE_ZIP = "_".join([PRODUCT_NAME, "MonitoringAgent.tar.gz"])
AGENT_REQUIREMENTS_ZIP = "_".join([PRODUCT_NAME, "Dependency.tar.gz"])
AGENT_LOG_DIR = AGENT_WORKING_DIR + '/logs'
AGENT_LIB_DIR = os.path.join(AGENT_WORKING_DIR, "lib")
AGENT_LIB_LIB_DIR = os.path.join(AGENT_LIB_DIR, "lib")
AGENT_CERTIFI_DIR = os.path.join(AGENT_LIB_LIB_DIR, "certifi")
AGENT_BACKUP_DIR = os.path.join(AGENT_WORKING_DIR, "backup")
AGENT_BACKUP_DIR_LIB = os.path.join(AGENT_BACKUP_DIR, "lib")
AGENT_BACKUP_DIR_CONF = os.path.join(AGENT_BACKUP_DIR, "conf")
AGENT_BACKUP_DIR_SCRIPTS = os.path.join(AGENT_BACKUP_DIR, "scripts")
AGENT_BACKUP_DIR_BIN = os.path.join(AGENT_BACKUP_DIR, "bin")
AGENT_LOG_DETAIL_DIR = AGENT_LOG_DIR + '/details'
AGENT_PIP_INSTALL_LOG_DIR = os.path.join(AGENT_LOG_DIR, "pipinstall")
AGENT_CONF_DIR = AGENT_WORKING_DIR + '/conf'
AGENT_CONF_BACKUP_DIR = AGENT_CONF_DIR + '/backup'
AGENT_UPLOAD_DIR = AGENT_WORKING_DIR + '/upload'
SERVER_UPLOAD_DIR = AGENT_UPLOAD_DIR + '/001'
PLUGIN_UPLOAD_DIR = AGENT_UPLOAD_DIR + '/002'
KUBERNETES_UPLOAD_DIR = AGENT_UPLOAD_DIR + '/003'
SYSLOG_UPLOAD_DIR = AGENT_UPLOAD_DIR + '/004'
DOCKER_UPLOAD_DIR = AGENT_UPLOAD_DIR + '/005'
ZOOKEEPER_UPLOAD_DIR = AGENT_UPLOAD_DIR + '/006'
HADOOP_NAMENODE_UPLOAD_DIR = AGENT_UPLOAD_DIR + '/007'
HADOOP_DATANODE_UPLOAD_DIR = AGENT_UPLOAD_DIR + '/008'
HADOOP_YARN_UPLOAD_DIR = AGENT_UPLOAD_DIR + '/009'
SMARTDISK_UPLOAD_DIR = AGENT_UPLOAD_DIR + '/010'
DATABASE_UPLOAD_DIR = AGENT_UPLOAD_DIR + '/012'
ADDM_UPLOAD_DIR = AGENT_UPLOAD_DIR + '/015'
EBPF_UPLOAD_DIR = AGENT_UPLOAD_DIR + '/016'
KUBERNETES_RS_UPLOAD_DIR = AGENT_UPLOAD_DIR + '/017'
KUBE_YAML_UPLOAD_DIR = AGENT_UPLOAD_DIR + '/020'
AGENT_QUERY_CONF_DIR = AGENT_WORKING_DIR + '/queryconf'
AGENT_DATA_DIR = AGENT_WORKING_DIR + '/data'
SERVER_DATA_DIR = AGENT_DATA_DIR + '/001'
PLUGIN_DATA_DIR = AGENT_DATA_DIR + '/002'
KUBERNETES_DATA_DIR = AGENT_DATA_DIR + '/003'
SYSLOG_DATA_DIR = AGENT_DATA_DIR + '/004'
DOCKER_DATA_DIR = AGENT_DATA_DIR + '/005'
ZOOKEEPER_DATA_DIR = AGENT_DATA_DIR + '/006'
HADOOP_NAMENODE_DATA_DIR = AGENT_DATA_DIR + '/007'
HADOOP_DATANODE_DATA_DIR = AGENT_DATA_DIR + '/008'
HADOOP_YARN_DATA_DIR = AGENT_DATA_DIR + '/009'
SMARTDISK_DATA_DIR = AGENT_DATA_DIR + '/010'
DATABASE_DATA_DIR = AGENT_DATA_DIR + '/012'
ADDM_DATA_DIR = AGENT_DATA_DIR + '/015'
EBPF_DATA_DIR = AGENT_DATA_DIR + '/016'
KUBERNETES_RS_DATA_DIR = AGENT_DATA_DIR + '/017'
EBPF_PROCESS_DATA_DIR = AGENT_DATA_DIR + '/019'
KUBE_YAML_DATA_DIR = AGENT_DATA_DIR + '/020'
AGENT_SCRIPTS_DIR = AGENT_WORKING_DIR + '/scripts'
AGENT_CUSTOM_SCRIPTS_DIR = AGENT_WORKING_DIR + '/customscripts'
AGENT_UPGRADE_DIR = AGENT_WORKING_DIR + '/upgrade'
AGENT_UPGRADE_REQUIREMENTS_TXT_FILEPATH = os.path.join(AGENT_UPGRADE_DIR, "requirements.txt")
AGENT_UPGRADE_REQUIREMENTS_FALG_FILEPATH = os.path.join(AGENT_UPGRADE_DIR, "requirements_flag.txt")
if AGENT_VENV_BIN_PYTHON is None:
    AGENT_UPGRADE_PIP_INSTALL_COMMAND = None
else:
    AGENT_UPGRADE_PIP_INSTALL_COMMAND = "{} -m pip install -r {}".format(AGENT_VENV_BIN_PYTHON, AGENT_UPGRADE_REQUIREMENTS_TXT_FILEPATH)
AGENT_TEMP_DIR = AGENT_WORKING_DIR + '/temp'
AGENT_TEMP_RAW_DATA_DIR = AGENT_TEMP_DIR + '/raw_data'
AGENT_TEMP_RCA_DIR = AGENT_TEMP_DIR + '/rca'
AGENT_TEMP_SYS_LOG_DIR = AGENT_TEMP_DIR + '/syslog'
AGENT_TEMP_RCA_REPORT_DIR = AGENT_TEMP_RCA_DIR + '/report'
AGENT_TEMP_RCA_REPORT_BACKUP_DIR = AGENT_TEMP_RCA_DIR + '/backup'
AGENT_TEMP_RCA_REPORT_UPLOADED_DIR = AGENT_TEMP_RCA_DIR + '/uploaded'
AGENT_TEMP_RCA_REPORT_NETWORK_DIR = AGENT_TEMP_RCA_DIR + '/networkreport'
AGENT_TEMP_RCA_RAW_DATA_DIR = AGENT_TEMP_RCA_DIR + '/raw'
AGENT_DOCKER_CONF_FILE = AGENT_CONF_DIR + '/dockerconf.cfg'
AGENT_APPS_ID_FILE = os.path.join(AGENT_CONF_DIR, "site24x7id")
SCRIPTS_FILE_NAME = "script.sh"
SCRIPTS_FILE_PATH = os.path.join(AGENT_SCRIPTS_DIR, SCRIPTS_FILE_NAME)
AGENT_FILE_MONITORING_SCRIPT = AGENT_SCRIPTS_DIR + '/fileMonitoring.sh'
AGENT_NFS_MONITORING_SCRIPT = AGENT_SCRIPTS_DIR + '/nfs_check.sh'
AGENT_IGNORED_PLUGINS_FILE = AGENT_TEMP_DIR+'/ignored_plugins.txt'
SCRIPTS_TEMPLATE_FILE_PATH = os.path.join(AGENT_SCRIPTS_DIR, "script_template.sh")
AGENTMANAGER_FILE = os.path.join(AGENT_SCRIPTS_DIR, "AgentManager.sh")
MONITORSGROUP_TEMPLATE_FILE_PATH = os.path.join(AGENT_CONF_DIR, "monitorsgroup_template.json")
CUSTOM_MONITORSGROUP_TEMPLATE_FILE_PATH = os.path.join(AGENT_CONF_DIR, "custom_monitorsgroup_template.json")
MONITORS_TEMPLATE_FILE_PATH =os.path.join(AGENT_CONF_DIR, "monitors_template.xml")
CUSTOM_MONITORS_TEMPLATE_FILE_PATH = os.path.join(AGENT_CONF_DIR, "custom_monitors_template.xml")
AGENT_LOCK_FILE = AGENT_TEMP_DIR + '/lockfile.txt'
AGENT_WATCHDOG_LOCK_FILE = AGENT_TEMP_DIR + '/watchdoglockfile.txt'
AGENT_STATUS_UPDATE_SERVER_LIST_FILE = AGENT_CONF_DIR +'/failover.json'
AGENT_INSTANCE_METADATA_CONF_FILE = AGENT_CONF_DIR +'/cloudplatform.json'
AGENT_CHECK_SERVER_LIST_FILE = AGENT_CONF_DIR +'/server_domains.json'
AGENT_VERSION_FILE = AGENT_WORKING_DIR + '/version.txt'
AGENT_BUILD_NUMBER_FILE = AGENT_WORKING_DIR + '/bno.txt'
AGENT_PROFILE_FILE = AGENT_WORKING_DIR + '/.agent_profile'
AGENT_PRODUCT_PROFILE_FILE = AGENT_WORKING_DIR + '/.product_profile'
AGENT_CONF_FILE = AGENT_CONF_DIR + '/monagent.cfg'
WATCHDOG_CONF_FILE = AGENT_CONF_DIR + '/monagentwatchdog.cfg'
AGENT_UPLOAD_PROPERTIES_FILE = AGENT_CONF_DIR + '/upload_properties.cfg'
AGENT_CHECKS_CONF_FILE = AGENT_CONF_DIR + '/checks.cfg'
AGENT_CONF_BACKUP_FILE = AGENT_CONF_BACKUP_DIR + '/monagent.cfg'
AGENT_PARAMS_FILE = AGENT_CONF_DIR + '/agentparams.txt'
AGENT_PROCESS_LIST_FILE = AGENT_QUERY_CONF_DIR + '/processlist.txt'
AGENT_PROCESS_STATUS_LIST_FILE = AGENT_QUERY_CONF_DIR + '/processStatuslist.txt'
AGENT_PROCESS_DETAILS_LIST_FILE = AGENT_QUERY_CONF_DIR + '/processDetailslist.txt'
AGENT_MONITORS_GROUP_FILE = AGENT_CONF_DIR+'/monitorsgroup.json'
AGENT_CUSTOM_MONITORS_GROUP_FILE = AGENT_CONF_DIR+'/custom_monitorsgroup.json'
AGENT_EVENT_HISTORY_FILE = AGENT_CONF_DIR+'/eventHistory.json'
AGENT_LOGGING_CONF_FILE = AGENT_CONF_DIR + '/logging.xml'
AGENT_MONITORS_FILE = AGENT_CONF_DIR+'/monitors.xml'
AGENT_CUSTOM_MONITORS_FILE = AGENT_CONF_DIR+'/custom_monitors.xml'
AGENT_UPGRADE_STATUS_MSG_FILE = AGENT_TEMP_DIR+'/agentUpgradeStatus.txt'
AGENT_UNINSTALL_FILE = AGENT_BIN_DIR + '/uninstall'
AGENT_UNINSTALL_FLAG_FILE = AGENT_TEMP_DIR + '/uninstall.txt'
AGENT_SHUTDOWN_FLAG_FILE = AGENT_TEMP_DIR + '/shutdown.txt'
AGENT_HEART_BEAT_FILE = AGENT_TEMP_DIR + '/heartbeat.txt'
AGENT_HEART_BEAT_QUOTES_FILE = '"' + AGENT_TEMP_DIR + '/heartbeat.txt"'
AGENT_UPTIME_FLAG_FILE = AGENT_TEMP_DIR + '/uptime.txt'
AGENT_RESTART_FLAG_FILE = AGENT_TEMP_DIR + '/restart.txt'
AGENT_WATCHDOG_SILENT_RESTART_FLAG_FILE = AGENT_TEMP_DIR + '/watchdogsilentrestart.txt' #watchdog restarts agent
AGENT_SILENT_RESTART_FLAG_FILE = AGENT_TEMP_DIR + '/agentsilentrestart.txt' #Agent restarts watchdog
KUBERNETES_CONF_XML_FILE = AGENT_CONF_DIR+'/apps/kubernetes/kubernetesDCConfig.xml'
KUBERNETES_PERF_XML_FILE = AGENT_CONF_DIR+'/apps/kubernetes/kubernetesDCPerf.xml'
KUBERNETES_API_PERF_XML_FILE = AGENT_CONF_DIR+'/apps/kubernetes/kubernetesDCAPIPerf.xml'
KUBERNETES_DYNAMIC_METRICS_XML_FILE = AGENT_CONF_DIR+'/apps/kubernetes/kubernetesDCDynamicMetric.xml'
KUBERNETES_CADVISOR_XML_FILE = AGENT_CONF_DIR+'/apps/kubernetes/KubernetesCAdvisor.xml'
KUBERNETES_NPC_CONF_XML_FILE = AGENT_CONF_DIR+'/apps/kubernetes/KubernetesNPCConfig.xml'
KUBERNETES_NPC_PERF_XML_FILE = AGENT_CONF_DIR+'/apps/kubernetes/KubernetesNPCPerf.xml'
KUBERNETES_RESOURCE_DEPENDENCY_XML_FILE = AGENT_CONF_DIR+'/apps/kubernetes/KubernetesResourceDependency.xml'
KUBERNETES_CONF_FILE = AGENT_CONF_DIR+'/apps/kubernetes/kubernetes.conf'
MON_AGENT_UPGRADED_FLAG_FILE = AGENT_TEMP_DIR + '/monagent_upgraded.txt'
VENV_UPGRADE_REQUEST_FLAG_FILE = AGENT_TEMP_DIR + "/venv_upgrade_request.txt"
MON_AGENT_VENV_ATTENDANCE_FILE = AGENT_TEMP_DIR + '/monagent_venv.txt'
MON_AGENT_VENV_UPGRADE_SCRIPT = os.path.join(AGENT_BIN_DIR, "venv_upgrade.sh")
MON_AGENT_UPGRADE_NOTIFIER_FILE = os.path.join(AGENT_TEMP_DIR, "upgrade_notifier")
UPGRADE_DISABLE_FLAG_FILE = AGENT_TEMP_DIR + '/disable_upgrade.txt'
PS_UTIL_FLOW_FILE = AGENT_TEMP_DIR + "/psutil_flow.txt"
CA_CERT_FILE = os.path.join(AGENT_LIB_LIB_DIR, 'certifi', 'cacert.pem')
CA_CERT_PATH = None
AGENT_CERTIFI_CERT = None
if not IS_VENV_ACTIVATED:
    AGENT_CERTIFI_CERT = os.path.join(AGENT_LIB_LIB_DIR, 'certifi', 'cacert.pem')
else:
    try:
        import certifi
        AGENT_CERTIFI_CERT = certifi.where()
    except Exception as e:
        pass
if IS_VENV_ACTIVATED is True:
    _file_obj = None
    try:
        with open(MON_AGENT_VENV_ATTENDANCE_FILE, "w") as fp:
            fp.write("{} {}".format(AGENT_VENV_BIN_PYTHON, os.path.realpath(sys.argv[0])))
    except Exception as e:
        traceback.print_exc()

AGENT_SYS_LOG_FILTERS_FILE = AGENT_CONF_DIR+'/syslogfilters.json'
AGENT_UDP_LOG_FILE = AGENT_LOG_DETAIL_DIR + '/udp.txt'
AGENT_UDP_RAW_LOG_FILE = AGENT_LOG_DETAIL_DIR + '/udp_raw.txt'


AGENT_SYS_LOG_CONF_FILE = '/etc/rsyslog.d/07-site24x7.conf'
AGENT_SYS_LOG_SERVICE_RESTART_COMMAND = 'service rsyslog restart'
AGENT_SYS_LOG_EXECUTABLE=os.path.join(AGENT_BIN_DIR, "monagentsyslog")
AGENT_REGISTRATION_SERVLET = '/plus/RegisterAgent?'
AGENT_FILE_COLLECTOR_SERVLET = '/plus/FileCollector?'
DATA_AGENT_HANDLER_SERVLET = '/plus/DataAgentHandlerServlet?'
DOWNLOAD_FILE_SERVLET = '/plus/dl/DownloadFileServlet?'
AGENT_STATUS_UPDATE_SERVLET = '/plus/StatusUpdateServlet?'
PEER_HANDLER_SERVLET = '/plus/PeerCommunicationServlet?'
AGENT_SYSLOG_STATS_SERVLET = '/plus/SysLogMonitoringServlet?'
SYSLOG_GET_DETAILS_SERVLET = '/plus/GetSysLogFilterDetails?'
SERVER_INSTANT_NOTIFIER_SERVLET = '/plus/ServerInstantNotifier?'
APPLICATION_DISCOVERY_SERVLET = '/plus/ApplicationDiscoveryServlet?'
DISCOVERY_SERVLET='/plus/cdiscover/ChildDiscoveryServlet?'
APPLICATION_COLLECTOR_SERVLET = '/plus/LinuxAppsDataReceiver?'
HADOOP_DATA_COLLECTOR_SERVLET = '/plus/HadoopDataCollector?'
KUBE_DATA_COLLECTOR_SERVLET = '/dp/kb/KubernetesDataReceiver?'
KUBE_DATA_DISCOVERY_SERVLET = '/dp/kb/KubernetesDiscoveryServlet?'
KUBE_RS_DATA_COLLECTOR_SERVLET = '/dp/kb/KubeDependencyServlet?'
KUBE_YAML_UPLOAD_SERVLET = '/dp/kb/KubeYamlUploadServlet?'
KUBE_ACTION_SERVLET = '/dp/kb/KubeActionServlet?'
DATABASE_DATA_COLLECTOR_SERVLET = '/plus/db/DatabaseDataReceiver?'
PLUS_DOWNLOAD_SERVLET = '/plus/PlusDownloader.do?'
FILE_DOWNLOAD_SERVLET = '/login/downloadRecorder.do?'
AGENT_CONFIG_SERVLET = '/plus/ConfigurationServlet?'
WMS_ACK_SERVLET = '/plus/WMSResponseServlet?'
SCRIPT_RESULT_SERVLET = '/plus/ScriptResultServlet?'
LIVE_TERMINAL_SERVLET = "/plus/rt-term/TerminalResult?"
AGENT_LISTEN_ACTIVATION_SERVLET = '/plus/StatusActionCheckServlet?'
PLUGIN_REGISTER_SERVLET='/plugin/PluginServlet?'
PLUGIN_DATA_POST_SERVLET='/plugin/PluginDataCollector?'
AGENT_WATCHDOG_SERVLET='/plus/WatchDogDataReceiver?'
REAL_TIME_MONITORING_SERVLET='/plus/rt-chart/LiveChart?'
COMMAND_EXECUTION_SERVLET='/plus/rt-tool/CommandExecutionResult?'
CLUSTER_CONFIG_SERVLET='/plus/ClusterConfigServlet?'
EBPF_DATA_COLLECTOR_SERVLET='/platform/discovery/ADDMeBPFDataCollector?'
ADDM_NETSTAT_SERVLET='/platform/discovery/ADDMNetstatDataCollector?'

# Buffers
FILES_TO_UPLOAD_BUFFER = 'FILES_TO_UPLOAD_BUFFER'
FILES_TO_ZIP_BUFFER = 'FILES_TO_ZIP_BUFFER'
WMS_REQID_SERVED_BUFFER = 'WMS_REQID_SERVED_BUFFER'
SYS_LOG_BUFFER = 'SYS_LOG_BUFFER'
ALERT_BUFFER = 'ALERT_BUFFER'

AGENT_DOCKER_INSTALLED = 1
AGENT_DOCKER_ENABLED = 1
AGENT_MACHINE_REBOOT = False
AGENT_PREVIOUS_TIME_DIFF = 0
AGENT_MACHINE_START_TIME = round((time.time() - 30)*1000) # in millis
AGENT_MACHINE_TIME_DIFF_BASED_SHUTDOWN_TIME = 0
AGENT_MACHINE_TIME_DIFF_BASED_START_TIME = round((time.time() - 30)*1000) # in millis
AGENT_MACHINE_SHUTDOWN_TIME = 0
AGENT_START_TIME = round(time.time()*1000)
AGENT_REGISTRATION_TIME = -1
AGENT_TIME_DIFF_BASED_REGISTRATION_TIME = -1
AGENT_TIME_ZONE = time.tzname
AGENT_TIME_DIFF_FROM_GMT = time.strftime("%z")
NTP_SERVER_ADDRESSES = ['0.pool.ntp.org', '1.pool.ntp.org', '2.pool.ntp.org', '3.pool.ntp.org']
AGENT_WARM_START = True
AGENT_WARM_SHUTDOWN = True
MON_AGENT_UPGRADED = False
APPLOG_AGENT_ENABLED = 1
MIDSERVER_ENABLED = False
APPLOG_UPGRADE_INPROGRESS = False

APPLICATION_LOCK = None
WATCHDOG_APPLICATION_LOCK = None

AGENT_BOOT_STATUS = ''
AGENT_DOWN='AGENT_DOWN'
SUSPECTED_CRASH='SUSPECTED_CRASH'

AGENT_SERVICE_RESTART_MESSAGE = 'Agent service restart'
AGENT_MACHINE_RESTART_MESSAGE = 'Agent machine restart'
AGENT_MACHINE_CRASH_AND_REBOOT_MESSAGE = 'Agent machine might have crashed and rebooted'

AGENT_START = 'start'
AGENT_STOP = 'stop'
AGENT_STATUS = 'status'
AGENT_RESTART = 'restart'

UPGRADE_FILE = None
AGENT_REGISTRATION_KEY = None
AGENT_UPGRADE_CONTEXT = None
DEFAULT_DOCKER_KEY = 'DOCKER'
#DOCKER_KEY = None

UPGRADE_FILE_NAME = None
AGENT_UPGRADE_FILE_NAME = None
WATCHDOG_UPGRADE_FILE_NAME = None
AGENT_UPGRADE_FILE = None
AGENT_UPGRADE_URL = None
UPGRADE_FILE_URL_NAME = None
AGENT_UPGRADE_FLAG_FILE = AGENT_UPGRADE_DIR + '/upgrade.txt'

WATCHDOG_UPGRADE_FILE = None
AGENT_UPGRADER_BIN = os.path.join(AGENT_BIN_DIR, "monagentupgrade")
AGENT_VENV_UPGRADER_BIN = os.path.join(AGENT_BIN_DIR, "hybrid_monagent_upgrade")
WATCHDOG_UPGRADE_WAIT_TIME = 60
# Host details

HOST_NAME = None
HOST_FQDN_NAME = None
DOMAIN_NAME = None
IP_ADDRESS = None
MAC_ADDRESS = None
OS_NAME = None
OS_FLAVOR = None
OS_ARCHITECTURE = None

DEFAULT_IPV4_ADDRESS = '-'
DEFAULT_IPV6_ADDRESS = '-'
FILES_TO_ZIP_BUFFER_APPS = None
#DEFAULT_IPV4_ADDRESS = -1
#DEFAULT_IPV6_ADDRESS = -1

IP_LIST=[]

AGENT_SHUTDOWN_LISTENER_IP_ADDRESS = '127.0.0.1'
AGENT_SHUTDOWN_LISTENER_PORT = 2244

MAX_FILE_ID = 2000000000
MIN_ICMP_PACKET_ID = 1000
MAX_ICMP_PACKET_ID = 32768
ICMP_REQUEST_TIMEOUT = 2000 #  milliseconds

FILE_ACCESS_CHECK = 2001
FILE_META_CHECK = 2002
FILE_SIZE_CHECK = 2003
FILE_MODIFY_CHECK = 2004
FILE_CONTENT_CHECK = 2005
DIRECTORY_ACCESS_CHECK = 3001
DIRECTORY_META_CHECK = 3002
DIRECTORY_SIZE_CHECK = 3003
DIRECTORY_FILE_CHECK = 3004
DIRECTORY_SUBDIR_CHECK = 3005
FILE_COUNT_CHECK = 3006
DIR_COUNT_CHECK = 3007
DEFAULT_GREP_TIMEOUT = 1 #seconds
DEFAULT_FILE_CHECK_TIMEOUT = 30
DEFAULT_SCRIPT_TIMEOUT = 10
AGENT_REGISTRATION_RETRY_COUNT = 10
AGENT_REGISTRATION_RETRY_INTERVAL = 60 #seconds
FILE_UPLOAD_INTERVAL = 1 #seconds
FILE_UPLOAD_NEW_INTERVAL = 3 #seconds
FILE_UPLOAD_EXCEPTION_INTERVAL = 60 #seconds # CHANGED FROM 300 -> 60 (UPLOAD FAILED FOR ANY ZIP NEXT UPLOAD WAIT TIME)
FILE_ZIPPER_INTERVAL = 1
FILE_CLEAN_UP_INTERVAL = 60
STATUS_UPDATE_INTERVAL = 45 #seconds
MAX_FILES_IN_ZIP = 1000
DEFAULT_MONITORING_INTERVAL = 300 #seconds
MIN_MONITORING_INTERVAL = 60 #seconds
AGENT_HEART_BEAT_INTERVAL = 10 #seconds
STOP_DATA_COLLECTION_INTERVAL = 18000 #seconds (5 hrs)
NETWORK_STATUS_CHECK_INTERVAL = 300 #seconds
APPROXIMATE_MACHINE_BOOT_TIME = 600 #seconds
MAX_SIZE_OF_SYS_LOG_BUFFER = 1000
MAX_SIZE_ZIP_BUFFER  = 100
MAX_SIZE_UPLOAD_BUFFER = 1000
MAX_WMS_REQID_BUFFER = 10
SYSLOG_FETCHING_INTERVAL = 300 #seconds
MIN_ALERT_TIME_INTERVAL = 120 #seconds
CPU_SAMPLE_VALUES = 1 #samples in 5 minutes
MIN_CHECK_ALERT_INTERVAL = 60000 #in milli seconds

AGENT_SCHEDULER_NO_OF_WORKERS = 10
AGENT_SCHEDULER_NO_OF_PLUGIN_WORKERS = 5
AGENT_SCHEDULER_NO_OF_K8s_WORKERS = 1

REQUEST_SERVER_INTERVAL_PULL_MODEL = 10
REQUEST_SERVER_INTERVAL_PUSH_MODEL = 30
REQUEST_DMS_TIMEOUT = 30
AGENT_SHUTDOWN_NOTIFICATION_TIMEOUT = 15
AGENT_SLEEP_INTERVAL = 36000 # This 10 hrs sleep interval holds the main thread and prevents agent shutdown

CONTENT_CHECK = 'content_check'
LAST_MODIFICATION_CHECK = 'lastModification_check'
FILESIZE_CHECK = 'fileSize_check'
FILECOUNT_CHECK='fc'
DIRCOUNT_CHECK='dc'

HTTPS_PROTOCOL = 'https'
HTTP_PROTOCOL = 'http'
HTTP_GET = 'GET'
HTTP_POST = 'POST'
DOWNLOAD_FILE = 'DOWNLOAD_FILE'

AGENT_SERVICE_UP_MESSAGE='monitoring agent service is up'
AGENT_SERVICE_DOWN_MESSAGE='monitoring agent service is down'
AGENT_SERVICE_STARTED_MESSAGE='monitoring agent service started successfully'
AGENT_SERVICE_STOPPED_MESSAGE='monitoring agent service stopped successfully'

AGENT_WATCHDOG_BOOT_FILE=AGENT_BIN_DIR+'/monagentwatchdog'
AGENT_WATCHDOG_START_COMMAND = AGENT_WATCHDOG_BOOT_FILE+' '+AGENT_START
AGENT_WATCHDOG_STOP_COMMAND = AGENT_WATCHDOG_BOOT_FILE+' '+AGENT_STOP
AGENT_WATCHDOG_STATUS_COMMAND = AGENT_WATCHDOG_BOOT_FILE+' '+AGENT_STATUS
AGENT_WATCHDOG_RESTART_COMMAND = AGENT_WATCHDOG_BOOT_FILE+' '+AGENT_RESTART

AGENT_WATCHDOG_SERVICE_UP_MESSAGE='monitoring agent watchdog service is up'
AGENT_WATCHDOG_SERVICE_DOWN_MESSAGE='monitoring agent watchdog service is down'
AGENT_WATCHDOG_SERVICE_STARTED_MESSAGE='monitoring agent watchdog service started successfully'
AGENT_WATCHDOG_SERVICE_STOPPED_MESSAGE='monitoring agent watchdog service stopped successfully'

# Notifiers
NOTIFIER = 'Notifier'
SHUTDOWN_NOTIFIER = 'ShutdownNotifier'
UDP_NOTIFIER = 'UdpNotifier'

# Listeners
SHUTDOWN_LISTENER = 'ShutdownListener'
UDP_PACKET_LISTENER = 'UdpPacketListener'

# UDP Server Details
UDP_SERVER_IP = '127.0.0.1'
UDP_PORT = '8822'

PORT_MONITOR_SERVER_IP = '127.0.0.1'
PORT_MONITOR_SERVER_NAME = 'localhost'
URL_HTTPS_PORT = '443'
URL_HTTP_PORT = '80'
# WMS Details
DMS="dms"
DMS_SERVER = 'dms.csez.zohocorpin.com'
DMS_PORT = '443'
DMS_REGISTER_SERVLET = '/register?'
DMS_REQUEST_EVENTS_SERVLET = '/wmsevent?'
DMS_PRODUCT_CODE = 'SI'
DMS_CONFIG_VALUE = '16'
DMS_UID = None
DMS_SID = None
DMS_NNAME = None
DMS_ZUID = None

SHUTDOWN_AGENT='SHUTDOWN_AGENT'
BOOL_AGENT_UPGRADE=False
WATCHDOG_UPGRADE_MSG=None
UPGRADE_USER_MESSAGE=None
UPGRADE_ACK_MSG="Agent Upgrade Request Received"
LOCAL_SSL_CONTEXT=None

#Request Types
REGISTER_AGENT_DISCOVER_PROCESSES_AND_SERVICES = 'REGISTER_AGENT_DISCOVER_PROCESSES_AND_SERVICES'
DISCOVER_PROCESSES_AND_SERVICES = 'DISCOVER_PROCESSES_AND_SERVICES'
PROCESS_AND_SERVICE_DETAILS='PROCESS_AND_SERVICE_DETAILS'
PROCESS_MONITORING='Process_Monitoring'
UPDATE_SERVICE_AND_PROCESS_DETAILS = 'UPDATE_SERVICE_AND_PROCESS_DETAILS'
UPDATE_PROCESS_DETAILS = 'UPDATE_PROCESS_DETAILS'
METADATA = 'Metadata'
TEST_MONITOR = 'TEST_MONITOR'
EXECUTE_TASK = 'EXECUTE_TASK'
UNINSTALL_EBPF_AGENT = 'UNINSTALL_EBPF_AGENT'
INSTALL_EBPF_AGENT = 'INSTALL_EBPF_AGENT'
UPGRADE_EBPF_AGENT = 'UPGRADE_EBPF_AGENT'
STOP_EBPF_AGENT = 'STOP_EBPF_AGENT'
START_EBPF_AGENT = 'START_EBPF_AGENT'
UPDATE_FILES_FROM_PATCH = 'UPDATE_FILES_FROM_PATCH'
UPLOAD_PLUGIN = 'UPLOAD_PLUGIN'
UPDATE_CONF_JSON_FILE = 'UPDATE_CONF_JSON_FILE'
GET_LOG_FILE = 'GET_LOG_FILE'
SHARE_LOGS_REQUEST = "3001"
TEST_WMS = 'TEST_WMS'
STOP_MONITORING='STOP_MONITORING'
START_MONITORING='START_MONITORING'
DELETE_MONITORING='DELETE_MONITORING'
INITIATE_AGENT_UPGRADE='INITIATE_AGENT_UPGRADE'
INITIATE_PATCH_UPGRADE= '1109'
UPDATE_METADATA_URL= 'UPDATE_METADATA_URL'
EDIT_STATUS_SCHEDULE='EDIT_STATUS_SCHEDULE'
SUSPEND_DATA_COLLECTION = '5'
ACTIVATE_DATA_COLLECTION = '4'
UNINSTALL_AGENT = '3'
DISABLE_AGENT_SERVICE='DISABLE_AGENT_SERVICE'
SUSPEND_MONITORING = 'SUSPEND_MONITORING'
TOP_PROCESS_ON_CPU = 'TOP_PROCESS_ON_CPU'
TOP_PROCESS_ON_MEMORY = 'TOP_PROCESS_ON_MEMORY'
TOP_COMMAND_CHECK = True
TOP_PROCESS_ARGUMENT_LENGTH = 2000
DISCOVER_PROCESS_ARGUMENT_LENGTH = 25000
WMS_FAILED_REQ = 'WMS_FAILED_REQ'
RESTART_SERVICE = 'RESTART_SERVICE'
INITIATE_PEER_SERVICE = 'PEER_CHECK'
PEER_STOP = 'PEER_STOP'
PEER_VALIDATE = 'PEER_VALIDATE'
PEER_SCHEDULE = 'PEER_SCHEDULE'
GET_PEER_CHECK = 'GET_PEER_CHECK'
PEER_CHECK_RESULT = 'PEER_CHECK_RESULT'
PEER_UP_NOTIFY = 'PEER_UP_NOTIFY'
PEER_DOWN_NOTIFY = 'PEER_DOWN_NOTIFY'
PING_SUCCESS = 'PING_SUCCESS'
PING_FAILURE = 'PING_FAILURE'
PROCESS_NOTIFY = 'PROCESS_NOTIFY'
YET_TO_PING = 'YET_TO_PING'
PING_UNKNOWN_HOST = 'Unknown host'
PING_REQUEST_TIME_OUT = 'Request time out'
PING_UNABLE_TO_SEND_PACKET = 'Unable to send packet'
PING_UNABLE_TO_RECEIVE_PACKET = 'Unable to receive packet'
PING_PACKET_MISMATCH = 'ICMP request, response packet mismatch'
PING_LOG_INTERVAL = 300000 # time in milliseconds(5 minutes)
RCA_REPORT = 'RCA_REPORT'
GENERATE_RCA = 'GENERATE_RCA'
GENERATE_CPU_RCA = 'GENERATE_CPU_RCA'
UPLOAD_RCA = 'UPLOAD_RCA'
UPTIME_CORRECTION = 'UPTIME_CORRECTION'
SAVE_RCA_RAW = 'SAVE_RCA_RAW'
SAVE_RCA_REPORT = 'SAVE_RCA_REPORT'
SAVE_AND_UPLOAD_RCA_REPORT = 'SAVE_AND_UPLOAD_RCA_REPORT'
GENERATE_NETWORK_RCA = 'GENERATE_NETWORK_RCA'
MESSAGE_REPEATED_WARNING = 'last message repeated'
NETWORK_CONNECTIVITY_PROBLEM = 'NETWORK_CONNECTIVITY_PROBLEM'
ADD_SYSLOG_FILTER = 'ADD_SYSLOG_FILTER'
MODIFY_SYSLOG_FILTER = 'MODIFY_SYSLOG_FILTER'
EDIT_SYSLOG_SERVICE = 'EDIT_SYSLOG_SERVICE'
DELETE_SYSLOG_SERVICE = 'DELETE_SYSLOG_SERVICE'
FAILOVER = 'FAILOVER'
DOCKER_DATA_COLLECTOR_REPONSE = 'DOCKER_DATA_COLLECTOR_REPONSE'
HADOOP_DATA_COLLECTOR_REPONSE = "HA_DC_NODES_RES"
CHANGE_CPU_SAMPLES = 'CHANGE_CPU_SAMPLES'
CHANGE_MONITORING_INTERVAL = 'UPDATE_SERVER_DC_INTERVAL'
UPDATE_CONTAINER_INTERVAL='UPDATE_CONTAINER_INTERVAL'
SCRIPT_RUN = 'SCRIPT_RUN'
SUSPEND_UPLOAD_FLAG = 'SUSPEND_UPLOAD_FLAG'
RESUME_UPLOAD_FLAG = 'RESUME_UPLOAD_FLAG'
MAX_ZIPS_IN_CURRENT_BUFFER = 'MAX_ZIPS_IN_CURRENT_BUFFER_COUNT'
MAX_ZIPS_IN_FAILED_BUFFER = 'MAX_ZIPS_IN_FAILED_BUFFER_COUNT'
GROUPED_ZIPS_SLEEP_INTERVAL = 'GROUPED_ZIPS_SLEEP_INTERVAL_TIME'
UPDATE_LOG_LEVEL = 'UPDATE_LOG_LEVEL'

#DocKER WMS EVENTS
DELETE_DOCKER_MONITORING = "2221"
SUSPEND_DOCKER_MONITORING = "2222"
ACTIVATE_DOCKER = "2223"
REDISCOVER_DOCKER = "2105"


#App Monitoring Events [as of now only one app for linux ]

SAM="SUSPEND_APP_MONITORING"
AAM="ACTIVATE_APP_MONITORING"
DAM="DELETE_APP_MONITORING"
INIT_HARDWARE_MONITORING="8000"
STOP_HARDWARE_MONITORING="8001"

#kubernetes wms events
KUBE_SEND_CONFIG = "kubeSendConf"
KUBE_SEND_PERF = "kubeSendPerf"
KUBE_CONFIG_DC_INTERVAL = "kubeConfInt"
KUBE_CHILD_COUNT = "KubeChildCount"
KUBE_API_SERVER_ENDPOINT = "KubeApiServerEndpoint"
KUBE_STATE_METRICS_URL = "KubeStateMetricsUrl"
KUBE_CLUSTER_DN = "KubeClusterDN"
SET_KUBE_SEND_CONFIG = "SET_KUBE_SEND_CONFIG"
SET_KUBE_SEND_PERF = "SET_KUBE_SEND_PERF"
SET_KUBE_CONFIG_DC_INT = "SET_KUBE_CONFIG_DC_INT"
SET_KUBE_CHILD_COUNT = "SET_KUBE_CHILD_COUNT"
SET_KUBE_API_SERVER_ENDPOINT_URL = "SET_KUBE_API_SERVER_ENDPOINT"
SET_KUBE_STATE_METRICS_URL = "SET_KUBE_STATE_METRICS_URL"
SET_KUBE_CLUSTER_DISPLAY_NAME = "SET_KUBE_CLUSTER_DN"
REDISCOVER_KUBE_STATE_METRICS_URL = "REDISCOVER_KUBE_STATE_METRICS_URL"
KUBE_INSTANT_DISCOVERY = "KUBE_INSTANT_DISCOVERY"
FARGATE = False
GKE_AUTOPILOT = False
SET_EVENTS_ENABLED = "EVENTS_ENABLED"

#Plugin WMS Events
SUSPEND_PLUGIN="2500"
DELETE_PLUGIN="2501"
ACTIVATE_PLUGIN="2502"
RELOAD_PLUGIN="2503"
REDISCOVER_PLUGINS="2504"
PLUGIN_DEPLOY="2505"
PLUGIN_DISABLE="2506"
PLUGIN_ENABLE="2507"
PLUGIN_COUNT_CONFIGURE="2508"

EXECUTE_ACTION_SCRIPT = 'EXECUTE_ACTION_SCRIPT'
VALIDATE_ACTION_SCRIPT = 'VALIDATE_ACTION_SCRIPT'
SCRIPT_ERROR_CODES = [1,2,3,126,127,128,130]

WRONG_PATH = 404
START_DOCKER_CONTAINER = 'ACTION_START'
STOP_DOCKER_CONTAINER = 'ACTION_STOP'
DELETE_PORT_MONITORS = 'DELETE_PORT_DETAILS'
ADD_PORT_MONITORS = 'ADD_PORT_DETAILS'
DELETE_URL_MONITORS = 'DELETE_URL_DETAILS'
ADD_URL_MONITORS = 'ADD_URL_DETAILS'
EDIT_URL_MONITORS = 'EDIT_URL_DETAILS'
PERSIST_INFO_ADD_COMMAND = 'ADD'
PERSIST_INFO_DELETE_COMMAND = 'DELETE'
PERSIST_INFO_EDIT_COMMAND = 'EDIT'


RSC_CHECK_UP = 'Up'
RSC_CHECK_DOWN = 'Down'
DEFAULT_PORT_TIMEOUT = 30
MIN_PORT_TIMEOUT = 1
MAX_PORT_TIMEOUT = 9
DEFAULT_NTP_TIMEOUT = 30
DEFAULT_URL_TIMEOUT = 30
PORT_VERIFY_TEXT = 'Port Details'
URL_VERIFY_TEXT = 'Url Details'
CHECKS_VERIFY_TEXT = 'url'
PORT_UPLOAD_PARAM = 'SERVER_PORT_MONITORING'
URL_UPLOAD_PARAM = 'SERVER_URL_MONITORING'
FILE_UPLOAD_PARAM = 'SERVER_FILE_MONITORING'
RESOURCE_UPLOAD_PARAM = 'SERVER_RESOURCE_MONITORING'
CLIENT_TYPE_DEFAULT = 'Default'
CLIENT_TYPE_CUSTOM = 'Custom'
UPDATE_AGENT_CONFIG = 'UPDATE_CONFIG'
UPDATE_AGENT_APPS_CONFIG = 'UPDATE_APP_CONFIG'
START_WATCHDOG = 'START_WATCHDOG'
NFS_IO_FILE='/proc/self/mountstats'


ICMP_ECHOREPLY  =    0
ICMP_ECHO       =    8
ICMP_MAX_RECV   = 2048

FOLDER_VS_CLEAN_UP_FILE_LIST = [(AGENT_TEMP_RAW_DATA_DIR,['Temp_Raw_Data'], 5000000),
                                (AGENT_TEMP_RCA_RAW_DATA_DIR,['Rca_Raw'], 10000000),
                                (AGENT_TEMP_RCA_REPORT_DIR,['Rca_Report'], 10000000),
                                (AGENT_TEMP_RCA_REPORT_BACKUP_DIR,['Rca_Report'], 10000000),
                                (AGENT_TEMP_RCA_REPORT_NETWORK_DIR,['_Rca_Report_Network'], 10000000),
                                (AGENT_TEMP_RCA_REPORT_UPLOADED_DIR,['_Rca_Report_Network', 'Rca_Report'], 10000000),
                                (AGENT_TEMP_SYS_LOG_DIR,['Agent_'], 10000000)
                                ]

# four formats of uptime is available
# 15:33:54 up 9 days,  3:23,  6 users,  load average: 0.66, 0.43, 0.38
# 12:16:55 up 9 days, 6 min,  6 users,  load average: 0.40, 0.43, 0.30
# 15:21:03 up 20:28,  2 users,  load average: 3.61, 3.64, 3.65
# 18:53:28 up 1 min,  1 user,  load average: 23.50, 7.37, 2.58
#UPTIME_COMMAND = "cat /proc/uptime | awk '{ print $1 }'"
UPTIME_COMMAND = "uptime | awk '{ for(k=1;k<=NF;k++){ if ((index($k, \"days\")) && (index($(k+1), \":\")) > 0) { d=($(k-1)*24*60*60); split($(k+1),a,\":\"); h=a[1]*60*60; m=a[2]*60; break; } else if ((index($k, \"days\")) && (index($(k+2), \"min\")) > 0) { d=($(k-1)*24*60*60); h=0; m=$(k+1)*60; break;} else if ((index($k, \"min\")) && (k==4) > 0) { d=0; h=0; m=$(k-1)*60; break;} else if ((index($k, \":\")) && (k==3) > 0) { d=0; split($k,a,\":\"); h=a[1]*60*60; m=a[2]*60; break;} } print(h+m+d) }'"
PREVIOUS_UPTIME_COMMAND = "cat "+AGENT_HEART_BEAT_FILE+" | awk -F'--->' '{print $4;}'"

UPTIME_PRETTY_COMMAND = "echo `uptime -p` | awk '{ print substr( $0, 4) }'"

UPTIME_CLIENT = "cat /proc/uptime | awk '{ print $1 }'"

PROCESS_STATUS_COMMAND = 'ps -eo args | grep -v grep | grep '

UPTIME_READ_COMMAND = "cat " + AGENT_UPTIME_FLAG_FILE

#BOOT_TIME_COMMAND
BOOT_TIME_COMMAND = "last -F reboot -n1 -n2 | awk 'BEGIN {ORS=\"\\n\";}{if(NR==1){print $6,$7,$8,$9}if(NR==2){print $12,$13,$14,$15}}'"

#Watchdog variables
WATCHDOG_LOGGING_CONF_FILE = AGENT_CONF_DIR + '/watchdog_logging.xml'

#SYSLOG_CONF_FILE_RULES_ARR = ["# "+PRODUCT_NAME+" syslog entry begins",
#                              "#### RULES ####",
#                              "#Kern.*        /dev/console",
#                              "*.info;mail.none;authpriv.none;cron.none       /var/log/messages",
#                              "authpriv.*     /var/log/secure",
#                              "mail.*         -/var/log/maillog",
#                              "cron.*         /var/log/cron",
#                              "*.emerg        *",
#                              "uucp,news.crit         /var/log/spooler",
#                              "local7.*       /var/log/boot.log",
#                              "*.*    @"+UDP_SERVER_IP+":"+UDP_PORT,
#                              "# "+PRODUCT_NAME+" syslog entry ends"
#                              ]

#Process monitor variables
#VIEW_PROCESSES_RUNNING_COMMAND = '/bin/ps -eo pid,fname,pcpu,pmem,nlwp,command,args | grep'
PROCESS_MONITOR = 'ProcessMonitoring'

SYSLOG_CONF_FILE_RULES_ARR = ["# "+PRODUCT_NAME+" syslog entry begins",
                              "*.*    @"+UDP_SERVER_IP+":"+UDP_PORT,
                              "# "+PRODUCT_NAME+" syslog entry ends"
                              ]

FILE_MON_SUPPORTED = ['Linux']
NFS_MON_SUPPORTED = ['Linux']
OS_SUPPORTED = ['Linux','FreeBSD']

def getAgentConstants():
    return globals()

AGENT_PLUGINS_DIR = AGENT_WORKING_DIR + '/plugins/'
AGENT_PLUGINS_SITE24X7ID = AGENT_CONF_DIR + '/pl_id_mapper'
AGENT_PLUGINS_CONF_FILE=AGENT_PLUGINS_DIR+"nagios_plugins.json"
AGENT_PLUGINS_NAGIOS_FILE='nagios_plugins.json'
AGENT_PLUGINS_LISTS_FILE = AGENT_CONF_DIR + '/pl_list.json'
AGENT_PLUGINS_ENABLED = 0
AGENT_PLUGINS_TMP_DIR=AGENT_SCRIPTS_DIR+'/tmp/'
AGENT_SERVICE_CMD='/etc/init.d/'
AGENT_VAR_LIB_DIR='/var/lib/'
AGENT_PORT_CHECK_CMD='netstat -lntp | grep'
PLUGINS_ZIP_FILE_SIZE=25
PLUGINS_COUNT=100
PLUGINS_SECTION='PLUGINS'
PLUGINS_ENABLED_KEY='plugins_enabled'
AGENT_INSTANCE_TYPE='SERVER'
AZURE_INSTANCE='azurevmextnlinuxserver'
AZURE_INSTANCE_CLASSIC='azurevmextnlinuxserverclassic'
AZURE_HANDLER_FILE=AGENT_CONF_DIR+'/'+'HandlerEnvironment.json'
AZURE_AGENT_PATH='/usr/sbin/waagent'
AZURE_LIB_PATH='/var/lib/waagent'
STATIC_SERVER_HOST='staticdownloads.site24x7.com'
IP_LIST = []

PING_COMMAND='ping -c 1'
TRACEROUTE_COMMAND='traceroute -T -q 3 -p 443 {} 40'
CLEAR_TRACE_ROUTE='4321'
UPTIME_MONITORING="false"

BONDING_INTERFACE_STATUS=False
ENABLE_BONDING_INTERFACE='ENABLE_BONDING_INTERFACE'
DISABLE_BONDING_INTERFACE='DISABLE_BONDING_INTERFACE'
GCR='GET_CONSOLIDATED_REQUESTS'
TEST_PING='TEST_PING'
PLUGIN_IGNORE_FILE='PLUGIN_IGNORED_ERROR.txt'
UPDATE_DEVICE_KEY='UPDATE_DEVICE_KEY'
UPDATE_AGENT_KEY='UPDATE_AGENT_KEY'
UTM='UPTIME_MONITORING'
RE_REGISTER_PLUGINS='RE_REGISTER_PLUGINS'
AGENT_PID_COMMAND='cat '+os.path.join(AGENT_LOG_DETAIL_DIR, "monagent_pid")
PROCESS_MONITORING_NAMES=None
PLUGIN_INVENTORY='plugin_inventory'
NO_OF_CPU_CORES=None
NO_OF_CPU_CORES_COMMAND="cat /proc/cpuinfo | grep -w 'processor' | wc -l"
NO_OF_CPU_CORES_COMMAND_OSX="sysctl -n hw.physicalcpu"
NO_OF_CPU_CORES_COMMAND_BSD="sysctl -n hw.ncpu"
NO_OF_CPU_CORES_COMMAND_SUNOS="psrinfo -p"
ENTROPY_AVAIL_COMMAND = "cat /proc/sys/kernel/random/entropy_avail"

'''Applog Configurations'''
APPLOG_INSTALL_AGENT = 'APPLOG_INSTALL_AGENT'
APPLOG_UPGRADE_AGENT = 'APPLOG_UPGRADE_AGENT'
APPLOG_START = 'APPLOG_START'
APPLOG_RESTART = 'APPLOG_RESTART'
APPLOG_STOP = 'APPLOG_STOP'
APPLOG_RESET = 'APPLOG_RESET'
APPLOG_ENABLE = 'APPLOG_ENABLE'
APPLOG_DISABLE = 'APPLOG_DISABLE'
APPLOG_CONFIGURATION = 'APPLOG_CONFIGURATION'
APPLOG_PROCESS = None
AGENT_APPLOG_UPGRADE_DIR = os.path.join(AGENT_WORKING_DIR, "temp", "applog_upgrade")
EBPF_AGENT_UPGRADE_DIR = os.path.join(AGENT_WORKING_DIR, "temp", "ebpf_upgrade")
EBPF_AGENT_UPGRADE_BACKUP_DIR = os.path.join(AGENT_WORKING_DIR, "temp", "ebpf_backup")
APPLOG_EXEC_HOME = os.path.join(AGENT_WORKING_DIR, "lib", "applog")
APPLOG_EXEC_PATH = os.path.join(APPLOG_EXEC_HOME, "Site24x7Applog" if IS_VENV_ACTIVATED is False else "applog_starter.py")
APPLOG_INDEX = os.path.join(AGENT_CONF_DIR, "applog", "applog_index.properties")

APPLOG_S247_DMS_DIR_PATH = os.path.join(AGENT_WORKING_DIR, "dms")
APPLOG_S247_DMS_FILE_PATH = os.path.join(APPLOG_S247_DMS_DIR_PATH, "conf.json")

EBPF_EXEC_HOME = os.path.join(AGENT_WORKING_DIR, "ebpf")
EBPF_EXEC_PATH = os.path.join(EBPF_EXEC_HOME, "Site24x7EbpfAgent")
EBPF_CONFIG_PATH = os.path.join(EBPF_EXEC_HOME, "ebpf_agent.cfg")

EBPF_PROCESS = None
EBPF_ENABLED = False

PLUGIN_INSTALL='INSTALL_SERVER_PLUGIN'
PLUGIN_FOLDER_DICT=None
DELETE_PLUGIN='DELETE_PLUGIN'
PROCESS_NAMES_TO_BE_MONITORED = []
APPS_CONFIG_DATA = {}
POLL_INTERVAL="300"
NO_OF_DC_FILES=5
CURRENT_DC_TIME=None
PREVIOUS_DC_TIME=None
S_V_DICT={}
FIVE_MIN_POLLING_INTERVAL="300"
ONE_MIN_POLLING_INTERVAL="60"
SYSTEM_UUID=None
SYSTEM_UUID_COMMAND="cat /sys/class/dmi/id/product_uuid"
PLUGINS_DC_INTERVAL=300
PLUGINS_ZIP_INTERVAL=60
PLUGINS_LOAD_INTERVAL=60
UPLOAD_CHECK_INTERVAL=300
LOCATION=0
UPDATE_TASK_INFO="UTI"
UPDATE_PLUGIN_INVENTORY=False
REBOOT_ACTION='REBOOT_ACTION'
ACTION_SCRIPT_CLEANUP='ACTION_SCRIPT_CLEANUP'
APPS_FOLDER = os.path.join(AGENT_CONF_DIR, "apps")
APPS_YELLOW_PAGES_FILE = os.path.join(APPS_FOLDER, 'yellowpages.conf')
BIN_SUPPORTED_OS = [LINUX_OS, FREEBSD_OS, OS_X,AIX_OS_LOWERCASE,SUN_OS]
MONITORS_FILE_NAME = "monitors.xml"
MONITORS_GROUP_JSON_FILE_NAME = "monitorsgroup.json"
IS_RUNNING_UNDER_DOCKER_CONTAINER = False
if os.path.isfile("/proc/self/cgroup"):
    with open("/proc/self/cgroup") as fp:
        if "docker" in fp.read():
            IS_RUNNING_UNDER_DOCKER_CONTAINER = True
REAL_TIME_MONITORING='9000'
GET_REAL_TIME_ATTRIBUTE='9001'
STOP_REAL_TIME_MONITORING='9002'

PS_UTIL_SUPPORTED=['Linux']
CPU_FORMULA='100-idle_time'
CPU_FORMULA_FILE='/opt/site24x7/monagent/scripts/cpu_formula'
PROCESSOR_NAME_COMMAND="grep -E 'model name' /proc/cpuinfo | awk -F':' 'NR==1{print $2}'"
PROCESSOR_NAME=None
IOSTAT_UTILITY_PRESENT=False
IOSTAT_COMMAND='iostat -xdy 1 1' #skip stats since boot and generate stats since last execution

#docker_agent
IS_DOCKER_AGENT = "0"
DOCKER_HOST = "0"
PS_WORKER_CONF_FILE = os.path.join(AGENT_CONF_DIR, "ps_worker.conf")

#kube agent
IS_KUBE_AGENT = False

#pipe_communication
DATABASE_PIPE_SENDER = os.path.join(AGENT_CONF_DIR, "metrics_pipe_receiver")
DATABASE_PIPE_RECEIVER = os.path.join(AGENT_CONF_DIR, "database_pipe_receiver")

#logger_time
LOG_MESSAGE_TIMER = {
    # index 1 -> log message to be written with time interval, index 2 -> to maintain last logged time [assign with 0]
    "001": [3600, 0],  # getCaCertPath() -> log ssl verfication failure certificate for plus domain ca-cert verification
}

#ps_worker
IS_PS_WORKER_ENABLED = "0"
PROCFS_PATH = "/proc"
SYSFS_PATH = "/sys"
GATEWAY_ADDRESS = None

#DOCKER_COLLECTOR
DOCKER_COLLECTOR_OBJECT = None
DOCKER_HELPER_OBJECT = None
DOCKER_SYSLOG_OBJECT = None
DOCKER_PSUTIL = None
DOCKER_SYSTEM_OBJECT = None
DOCKER_PROCESS_OBJECT = None
DOCKER_SCRIPT_PATH = os.path.join(AGENT_SCRIPTS_DIR, "docker_script.sh")
PS_UTIL_PROCESS_DICT = {}
TOP_PROCESS_METRICS = {'Name': 'Process Name',  'PID': 'Process Id',  'Path': 'Path',  'CPU': 'CPU Usage(%)',  'MEM': 'Memory Usage(MB)',  'thread_count': 'Thread Count',  'handle_count': 'Handle Count',  'cmd_line_arg': 'Command Line Arguments'}

#LIVE_TERMINAL
LIVE_TERMINAL = "LIVE_TERMINAL"
OPEN_TERMINAL = "OPEN_TERMINAL"
IS_LIVETERMINAL_SETUP_DONE = False
AGENT_LIVE_TERMINAL_CONF_FILE = os.path.join(AGENT_CONF_DIR, "live_terminal.cfg")
AGENT_SSH_KEY_FILE_PATH = os.path.join(AGENT_CONF_DIR, "s24x7rsa")
AGENT_SSH_KEY_PUB_FILE_PATH = os.path.join(AGENT_CONF_DIR, "s24x7rsa.pub")
SSH_KEYGEN_COMMAND = "su site24x7-agent -c \"ssh-keygen -f {} -t rsa -N ''\"".format(AGENT_SSH_KEY_FILE_PATH) if AGENT_USER_ID == 0 else "ssh-keygen -f {} -t rsa -N ''".format(AGENT_SSH_KEY_FILE_PATH)
LT_ALLOWED_SESSIONS = 1
LT_SESSIONS_DICT = {}
UNSUPPORTED_CMD_LIST = ["vim", "vi", "nano"]

#FREQUENT WMS CALL
WMS_SERVLET = '/plus/rt-msg/PlusMessageCollector?'
WMS_INTERVAL = 15

#module_obj
APPS_OBJECT = None
LIVE_TERMINAL_OBJECT = None
PS_UTIL_CHECK_FILE=os.path.join(AGENT_CONF_DIR, "process_psutil")
CPU_FORMULA_WITHOUT_STEAL='100-idle_time-steal_time'
ENABLE_PS_UTIL_PROCESS_DISCOVERY='5000'
DISABLE_PS_UTIL_PROCESS_DISCOVERY='4999'
VMSTAT_UTILITY_PRESENT=False
VMSTAT_COMMAND='vmstat'
MONITORING_INTERVAL = 60
DA_OPERATING_SYSTEM_NAME = None
DA_OS_ARCHITECTURE = None

#instance handling
META_INSTANCE_FILE_PATH = os.path.join(AGENT_TEMP_DIR, "instance_metadata")

#security related
SECURITY_ENABLED=True
SECURITY_CHECK="4005"
SSKEY=None

#inventory
INVENTORY_EXECUTE_INTERVAL=3600
INVENTORY_SERVLET='/plus/InventoryReceiver?'
NETWORKS_LIST=[]
DPKG_UTILITY_PRESENT=False
RPM_UTILITY_PRESENT=False
DPKG_QUERY="dpkg-query -W -f='${binary:Package}:::${Version}:::${Architecture}:::${binary:Summary}\n'"
RPM_QUERY="rpm -qa --qf '%{NAME}:::%{VERSION}:::%{RELEASE}:::%{ARCH}\n'"
PHYSICAL_SERVER='Physical Server'
VIRTUAL_MACHINE='Virtual Machine'

NAGIOS_PLUGIN_TYPE='nagios'
UPDATE_PLUGIN_CONFIG='7000'
AGENT_INSTALL_TIME_FILE=AGENT_TEMP_DIR+'/install_time'
AGENT_UPGRADE_FOLDER_IN_PLUS='sagent'
AGENT_PS_KEY=None
HADOOP_BULK_INSTALL = "INSTALL_AGENTS"
HADOOP_RC_FILEPATH = os.path.join(AGENT_BIN_DIR, "hadoop_rc")
MONITORING_AGENT_32bit_INSTALL_FILE = os.path.join(AGENT_SCRIPTS_DIR, "Site24x7_Linux_32bit.install")
MONITORING_AGENT_64bit_INSTALL_FILE = os.path.join(AGENT_SCRIPTS_DIR, "Site24x7_Linux_64bit.install")
MONITORING_AGENT_INSTALL_FILE = os.path.join(AGENT_SCRIPTS_DIR, "Site24x7MonitoringAgent.install")
HADOOP_DEST_RC_FILEPATH = "hadoop_rc"
HADOOP_RC_COMMAND = " ".join(["sh", HADOOP_DEST_RC_FILEPATH])
LICENSE_CONTENT=os.path.join(AGENT_WORKING_DIR,'scripts','tmp','license_content.txt')
LICENSE_FILE=os.path.join(AGENT_WORKING_DIR,'license.txt')
COLUMN_EXTEND_FILE=AGENT_CONF_DIR+'/terminal_columns.txt'
STOP_INVENTORY='5001'
START_INVENTORY='5002'
FILE_COLLECTOR_UPLOAD_CHECK=AGENT_CONF_DIR+'/'+'file_collector_time.txt'
PLUGIN_DEFAULT_TIME_OUT=30
PROXY_KEY='SKEY'
REQUEST_ID_VS_TIME_DICT={}
DMS_TASK_IGNORE_TIME=10*60*1000
STATIC_UPGRADE_CONTEXT='server'
AGENT_UPGRADE_SAGENT_URL=None
RAM_SIZE=None
SERVER_INVENTORY_DATA_FILE=os.path.join(AGENT_TEMP_DIR,'server_inventory.txt')
APPS_LIST=['docker']
STORE_APPS_OBJ=None
SCRIPT_DEPLOY='6100'
SD_RESULT='SCRIPT_DEPLOY_RESULT'
DS='success'
DF='failure'
OS_SUBTYPE_MAPPING={'aix':'AIX','sunos':'SunOS','osx':'OSX'}
AIX_PROCESS_COMMAND='/bin/ps -ef -o "pid ruser pri pcpu pmem thcount comm args"'
SUNOS_PROCESS_COMMAND='/bin/ps -eo pid,user,pri,pcpu,pmem,nlwp,comm,args'
STOP_DMS='STOP_DMS'
START_DMS='START_DMS'
UPDATE_MONAGENT_CONFIG='UMC'
SUN_OS_CPU_CORE_COMMAND='/usr/bin/mpstat'
REMOVE_DC_ZIPS='1110'
USE_DC_CMD_EXECUTOR=AGENT_WORKING_DIR+'/dc.txt'

#statsd
START="start"
STOP="stop"
RESTART="restart"
STATSD='STATSD'
PROMETHEUS='PROMETHEUS'
INIT_STATSD_MONITORING="8300"
START_STATSD_MONITORING="8301"
STOP_STATSD_MONITORING="8302"
UPDATE_STATSD_CONFIG="8333"

SUSPEND_MONITOR='9000'
DELETE_MONITOR='9001'
ACTIVATE_MONITOR='9003'
DELETE_METRICS='9002'

REMOVE_METRICS_DC_ZIPS='9010'
STOP_METRICS_AGENT='STOP_METRICS_AGENT'
STOP_PROMETHEUS='STOP_PROMETHEUS'
STOP_STATSD='STOP_STATSD'
START_METRICS_AGENT='START_METRICS_AGENT'
START_PROMETHEUS='START_PROMETHEUS'
START_STATSD='START_STATSD'
METRICS_START_COMMAND= METRICS_EXECUTOR_PATH+" "+START
METRICS_STOP_COMMAND=METRICS_EXECUTOR_PATH+" "+STOP
METRICS_RESTART_COMMAND= METRICS_EXECUTOR_PATH+" "+RESTART
METRICS_WORKING_DIRECTORY = os.path.join(AGENT_WORKING_DIR,'metrics')
METRIC_DATA_DIRECTORY = os.path.join(METRICS_WORKING_DIRECTORY,'data')
METRICS_DATA_ZIP_DIRECTORY=os.path.join(METRICS_WORKING_DIRECTORY,'upload')
STATSD_WORKING_DIR=os.path.join(METRICS_WORKING_DIRECTORY,'statsd')
STATSD_TEMP_CONF_FILE=os.path.join(AGENT_SCRIPTS_DIR,'tmp','statsd.cfg')
STATSD_CONF_FILE=os.path.join(METRICS_WORKING_DIRECTORY,'statsd','statsd.cfg')
PROMETHEUS_WORKING_DIR=os.path.join(METRICS_WORKING_DIRECTORY,'prometheus')
PROMETHEUS_TEMP_CONF_FILE=os.path.join(AGENT_SCRIPTS_DIR,'tmp','prometheus.cfg')
PROMETHEUS_CONF_FILE=os.path.join(METRICS_WORKING_DIRECTORY,'prometheus','prometheus.cfg')
PROMETHEUS_INPUT_FILE=os.path.join(AGENT_CONF_DIR,'prometheus_input')
REMOVE_PROMETHEUS_INSTANCE=os.path.join(AGENT_CONF_DIR,'remove_prometheus_instance')
UPDATE_PROMETHEUS_INSTANCE=os.path.join(AGENT_CONF_DIR,'update_prometheus_instance')
EDIT_PROMETHEUS_SCRAPE_INTERVAL=os.path.join(AGENT_CONF_DIR,'prometheus_scrape_interval')
ENABLE_PROMETHEUS_FLAG_FILE=os.path.join(AGENT_CONF_DIR,'enablePrometheus.txt')
DISABLE_PROMETHEUS_FLAG_FILE=os.path.join(AGENT_CONF_DIR,'disablePrometheus.txt')
STATSD_INPUT_FILE=os.path.join(AGENT_CONF_DIR,'statsd_input')
ENABLE_STATSD_FLAG_FILE=os.path.join(AGENT_CONF_DIR,'enableStatsd.txt')
DISABLE_STATSD_FLAG_FILE=os.path.join(AGENT_CONF_DIR,'disableStatsd.txt')
K8PROMETHEUS_WORKING_DIR=os.path.join(METRICS_WORKING_DIRECTORY,'k8sprometheus')
K8PROMETHEUS_TEMP_CONF_FILE=os.path.join(AGENT_SCRIPTS_DIR,'tmp','k8sprometheus.cfg')
K8PROMETHEUS_CONF_FILE=os.path.join(METRICS_WORKING_DIRECTORY,'k8sprometheus','k8sprometheus.cfg')
MONAGENT_DEFAULT_CONF=['discover_host', 'category', 'update_status']
DOCKER_AGENT_FOLDER=os.path.join(AGENT_WORKING_DIR,'docker_agent')
METRICS_ENABLED=False
METRICS_APPLICATIONS={
    'PROMETHEUS': {'conf_file':PROMETHEUS_CONF_FILE, 'working_dir':PROMETHEUS_WORKING_DIR, 'temp_conf_file':PROMETHEUS_TEMP_CONF_FILE},
    'STATSD': {'conf_file':STATSD_CONF_FILE, 'working_dir':STATSD_WORKING_DIR, 'temp_conf_file':STATSD_TEMP_CONF_FILE}
}

ZIP_POSTED=0

SERVER_ZIPS_TO_UPLOAD_BUFFER=[[],[]]
PLUGIN_ZIPS_TO_UPLOAD_BUFFER=[[],[]]
KUBERNETES_ZIPS_TO_UPLOAD_BUFFER=[[],[]]
SYSLOG_ZIPS_TO_UPLOAD_BUFFER=[[],[]]
DOCKER_ZIPS_TO_UPLOAD_BUFFER=[[],[]]
ZOOKEEPER_ZIPS_TO_UPLOAD_BUFFER=[[],[]]
HADOOP_NAMENODE_ZIPS_TO_UPLOAD_BUFFER=[[],[]]
HADOOP_DATANODE_ZIPS_TO_UPLOAD_BUFFER=[[],[]]
HADOOP_YARN_ZIPS_TO_UPLOAD_BUFFER=[[],[]]
SMARTDISK_ZIPS_TO_UPLOAD_BUFFER=[[],[]]
DATABASE_ZIPS_TO_UPLOAD_BUFFER=[[],[]]
EBPF_ZIPS_TO_UPLOAD_BUFFER=[[],[]]
ADDM_ZIPS_TO_UPLOAD_BUFFER=[[],[]]
KUBERNETES_RS_ZIPS_TO_UPLOAD_BUFFER=[[],[]]
KUBE_YAML_ZIPS_TO_UPLOAD_BUFFER=[[],[]]

AGENT_UPLOAD_PROPERTIES_MAPPER={
    '001': {
        'name': 'Server Data',
        'code': '001',
        'data_path': SERVER_DATA_DIR,
        'zip_path': SERVER_UPLOAD_DIR,
        'uri': AGENT_FILE_COLLECTOR_SERVLET,
        'buffer': SERVER_ZIPS_TO_UPLOAD_BUFFER,
        'param': [['AGENTUNIQUEID'], ['AGENTKEY'], ['bno'], ['FILENAME'], ['CUSTOMERID'], ['timeStamp'], ['auid'], ['auid_old'], ['sct'], ['installer'], ['ZIPS_IN_BUFFER']],
        'content_type': 'application/zip',
        'files_in_zip': 5,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 300,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':False,
        'instant_upload':False,
        'category':'serv'
    },
    '002': {
        'name': 'Plugin Data',
        'code': '002',
        'data_path': PLUGIN_DATA_DIR,
        'zip_path': PLUGIN_UPLOAD_DIR,
        'uri': PLUGIN_DATA_POST_SERVLET,
        'buffer': PLUGIN_ZIPS_TO_UPLOAD_BUFFER,
        'param': [['apikey'], ['agentkey'], ['bno'], ['zipname'], ['ZIPS_IN_BUFFER']],
        'content_type': 'application/zip',
        'files_in_zip': 25,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 60,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':False,
        'instant_upload':False,
        'category':'pl'
    },
    '003': {
        'name': 'Kubernetes Data',
        'code': '003',
        'data_path': KUBERNETES_DATA_DIR,
        'zip_path': KUBERNETES_UPLOAD_DIR,
        'uri': KUBE_DATA_COLLECTOR_SERVLET,
        'buffer': KUBERNETES_ZIPS_TO_UPLOAD_BUFFER,
        'param': [['APPNAME','kubernetes'], ['AGENTKEY'], ['CUSTOMERID'], ['AGENTUNIQUEID'], ['FILENAME'], ['bno']],
        'content_type': 'application/zip',
        'files_in_zip': 50,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 60,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':True,
        'instant_upload':False,
        'category':'app'
    },
    '004': {
        'name': 'Syslog Data',
        'code': '004',
        'data_path': SYSLOG_DATA_DIR,
        'zip_path': SYSLOG_UPLOAD_DIR,
        'uri': AGENT_SYSLOG_STATS_SERVLET,
        'buffer': SYSLOG_ZIPS_TO_UPLOAD_BUFFER,
        'param': [['AGENTKEY'], ['CUSTOMERID'], ['LASTUPDATETIME'], ['AGENT','Linux'], ['bno']],
        'content_type': 'application/zip',
        'files_in_zip': 10,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 60,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':True,
        'instant_upload':False,
        'category':'esl'
    },
    '005': {
        'name': 'Docker Data',
        'code': '005',
        'data_path': DOCKER_DATA_DIR,
        'zip_path': DOCKER_UPLOAD_DIR,
        'uri': APPLICATION_COLLECTOR_SERVLET,
        'buffer': DOCKER_ZIPS_TO_UPLOAD_BUFFER,
        'param': [['AGENTKEY'], ['CUSTOMERID'], ['AGENTUNIQUEID'], ['FILENAME'], ['bno'], ['APPNAME', 'docker']],
        'content_type': 'application/zip',
        'files_in_zip': 10,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 60,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':True,
        'instant_upload':False,
        'category':'app'
    },
    '006': {
        'name': 'Zookeeper Data',
        'code': '006',
        'data_path': ZOOKEEPER_DATA_DIR,
        'zip_path': ZOOKEEPER_UPLOAD_DIR,
        'uri': HADOOP_DATA_COLLECTOR_SERVLET,
        'buffer': ZOOKEEPER_ZIPS_TO_UPLOAD_BUFFER,
        'param': [['AGENTKEY'], ['CUSTOMERID'], ['AGENTUNIQUEID'], ['FILENAME'], ['bno'], ['APPNAME', 'zookeeper']],
        'content_type': 'application/zip',
        'files_in_zip': 10,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 60,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':True,
        'instant_upload':False,
        'category':'app'
    },
    '007': {
        'name': 'Hadoop Name Node Data',
        'code': '007',
        'data_path': HADOOP_NAMENODE_DATA_DIR,
        'zip_path': HADOOP_NAMENODE_UPLOAD_DIR,
        'uri': HADOOP_DATA_COLLECTOR_SERVLET,
        'buffer': HADOOP_NAMENODE_ZIPS_TO_UPLOAD_BUFFER,
        'param': [['AGENTKEY'], ['CUSTOMERID'], ['AGENTUNIQUEID'], ['FILENAME'], ['bno'], ['APPNAME', 'hadoop_namenode']],
        'content_type': 'application/zip',
        'files_in_zip': 10,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 60,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':True,
        'instant_upload':False,
        'category':'app'
    },
    '008': {
        'name': 'Hadoop Data Node Data',
        'code': '008',
        'data_path': HADOOP_DATANODE_DATA_DIR,
        'zip_path': HADOOP_DATANODE_UPLOAD_DIR,
        'uri': HADOOP_DATA_COLLECTOR_SERVLET,
        'buffer': HADOOP_DATANODE_ZIPS_TO_UPLOAD_BUFFER,
        'param': [['AGENTKEY'], ['CUSTOMERID'], ['AGENTUNIQUEID'], ['FILENAME'], ['bno'], ['APPNAME', 'hadoop_datanode']],
        'content_type': 'application/zip',
        'files_in_zip': 10,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 60,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':True,
        'instant_upload':False,
        'category':'app'
    },
    '009': {
        'name': 'Hadoop Yarn Data',
        'code': '009',
        'data_path': HADOOP_YARN_DATA_DIR,
        'zip_path': HADOOP_YARN_UPLOAD_DIR,
        'uri': HADOOP_DATA_COLLECTOR_SERVLET,
        'buffer': HADOOP_YARN_ZIPS_TO_UPLOAD_BUFFER,
        'param': [['AGENTKEY'], ['CUSTOMERID'], ['AGENTUNIQUEID'], ['FILENAME'], ['bno'], ['APPNAME', 'hadoop_yarn']],
        'content_type': 'application/zip',
        'files_in_zip': 10,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 60,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':True,
        'instant_upload':False,
        'category':'app'
    },
    '010': {
        'name': 'Smartdisk Data',
        'code': '010',
        'data_path': SMARTDISK_DATA_DIR,
        'zip_path': SMARTDISK_UPLOAD_DIR,
        'uri': APPLICATION_COLLECTOR_SERVLET,
        'buffer': SMARTDISK_ZIPS_TO_UPLOAD_BUFFER,
        'param': [['AGENTKEY'], ['CUSTOMERID'], ['AGENTUNIQUEID'], ['FILENAME'], ['bno'], ['APPNAME', 'smartdisk']],
        'content_type': 'application/zip',
        'files_in_zip': 10,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 60,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':True,
        'instant_upload':False,
        'category':'app'
    },
    '011': {
        'name': 'Resource Check Data',
        'code': '011',
        'data_path': None,
        'zip_path': None,
        'uri': None,
        'buffer': None,
        'param': [['agentKey'], ['custID'], ['dc'], ['bno'], ['action']],
        'content_type': 'application/json',
        'files_in_zip': 10,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 60,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':True,
        'instant_upload':True,
        'category':''
    },
    '012': {
        'name': 'Database Data',
        'code': '012',
        'data_path': DATABASE_DATA_DIR,
        'zip_path': DATABASE_UPLOAD_DIR,
        'uri': DATABASE_DATA_COLLECTOR_SERVLET,
        'buffer': DATABASE_ZIPS_TO_UPLOAD_BUFFER,
        'param': [['AGENTUNIQUEID'], ['AGENTKEY'], ['bno'], ['FILENAME'], ['CUSTOMERID'], ['ZIPS_IN_BUFFER']],
        'content_type': 'application/zip',
        'files_in_zip': 5,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 300,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':False,
        'instant_upload':False,
        'category':'app'
    },
    '013': {
        'name': 'Database Discovery Data',
        'code': '013',
        'data_path': None,
        'zip_path': None,
        'uri': DISCOVERY_SERVLET,
        'buffer': None,
        'param': [['agentKey'], ['custID'], ['bno'], ['action']],
        'content_type': 'application/json',
        'files_in_zip': 50,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 100,
        'max_zips_failed_buffer': 50,
        'zip_interval': 300,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':True,
        'instant_upload':True,
        'category':''
    },
    '014': {
        'name': 'Database Cluster Config Data',
        'code': '014',
        'data_path': None,
        'zip_path': None,
        'uri': CLUSTER_CONFIG_SERVLET,
        'buffer': None,
        'param': [['agentKey'], ['CUSTOMERID'], ['type']],
        'content_type': 'application/json',
        'files_in_zip': 50,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 100,
        'max_zips_failed_buffer': 50,
        'zip_interval': 300,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':True,
        'instant_upload':True,
        'category':''
    },
    '015': {
        'name': 'ADDM',
        'code': '015',
        'data_path': ADDM_DATA_DIR,
        'zip_path': ADDM_UPLOAD_DIR,
        'uri': ADDM_NETSTAT_SERVLET,
        'buffer': ADDM_ZIPS_TO_UPLOAD_BUFFER,
        'param': [['agentKey'], ['custID'], ['agentUniqueID'], ['bno']],
        'content_type': 'application/zip',
        'files_in_zip': 5,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 300,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':False,
        'instant_upload':False,
        'category':'',
        'no_backlog': True
    },
    '016': {
        'name': 'eBPF Agent Data',
        'code': '016',
        'data_path': EBPF_DATA_DIR,
        'zip_path': EBPF_UPLOAD_DIR,
        'uri': EBPF_DATA_COLLECTOR_SERVLET,
        'buffer': EBPF_ZIPS_TO_UPLOAD_BUFFER,
        'param': [['agentKey'], ['custID'], ['agentUniqueID'], ['bno']],
        'content_type': 'application/zip',
        'files_in_zip': 5,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 60,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':False,
        'instant_upload':False,
        'category':'serv',
        'no_backlog': True,
        'file_size': 40000
    },
    '017': {
        'name': 'Kubernetes Resource Dependency Data',
        'code': '017',
        'data_path': KUBERNETES_RS_DATA_DIR,
        'zip_path': KUBERNETES_RS_UPLOAD_DIR,
        'uri': KUBE_RS_DATA_COLLECTOR_SERVLET,
        'buffer': KUBERNETES_RS_ZIPS_TO_UPLOAD_BUFFER,
        'param': [['AGENTKEY'], ['CUSTOMERID'], ['AGENTUNIQUEID'], ['FILENAME'], ['bno']],
        'content_type': 'application/zip',
        'files_in_zip': 50,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 300,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':True,
        'instant_upload':False,
        'category':'app'
    },
    '018': {
        'name': 'Kubernetes Resource Discovery Data',
        'code': '018',
        'data_path': None,
        'zip_path': None,
        'uri': KUBE_DATA_DISCOVERY_SERVLET,
        'buffer': None,
        'param': [['AGENTKEY'], ['CUSTOMERID'], ['AGENTUNIQUEID'], ['bno']],
        'content_type': 'application/json',
        'files_in_zip': 50,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 60,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':True,
        'instant_upload':True,
        'category':'app'
    },
    '019': {
        'name': 'Ebpf Process Data',
        'code': '019',
        'data_path': EBPF_PROCESS_DATA_DIR,
        'zip_path': None,
        'uri': None,
        'buffer': None,
        'param': None,
        'content_type': 'application/json',
        'files_in_zip': 50,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 60,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':True,
        'instant_upload':True,
        'category':'app'
    },
    '020': {
        'name': 'Kubernetes YAML Data',
        'code': '020',
        'data_path': KUBE_YAML_DATA_DIR,
        'zip_path': KUBE_YAML_UPLOAD_DIR,
        'uri': KUBE_YAML_UPLOAD_SERVLET,
        'buffer': KUBE_YAML_ZIPS_TO_UPLOAD_BUFFER,
        'param': [['AGENTKEY'], ['CUSTOMERID'], ['AGENTUNIQUEID'], ['FILENAME'], ['bno']],
        'content_type': 'application/zip',
        'files_in_zip': 50,
        'zips_in_buffer': 0,
        'grouped_zip_upload_interval': 2,
        'max_zips_current_buffer': 10000,
        'max_zips_failed_buffer': 10000,
        'zip_interval': 300,
        'upload_interval': 5,
        'zip_modulo': 0,
        'upload_modulo':0,
        'instant_zip':True,
        'instant_upload':False,
        'category':'app'
    }
}

#Database
DATABASE_CONFIG_MAPPER={
    'mysql'             : {},
    'postgres'          : {},
    'oracledb'          : {},
    'mysql_replication' : {},
    'mysql_replication_seconds_behind_master' : {}
}
DATABASE_OBJECT_MAPPER={
    'mysql'         : {},
    'postgres'      : {},
    'oracledb'      : {}
}
DATABASE_PREVIOUS_DATA={
    'mysql'         : {}
}
AMAZON_LINUX_CMD = "(cat /etc/*-release | grep -iE 'amazon.linux' 2>/dev/null 1>2 && echo TRUE ) || echo FALSE"
#mysql
RESTART_MYSQL_MONITORING="RESTART_MYSQL_MONITORING"
RESTART_NDB_MONITORING="RESTART_NDB_MONITORING"
PERF_NODE_UPDATE="PERF_NODE_UPDATE"
UPLOAD_MYSQL_CONF_DATA="UPLOAD_MYSQL_CONF"
CONF_UPLOAD_FLAG=False
DATABASE_SETTING="database"
PYMYSQL_MODULE="0"
MYSQL_DB="mysql"
MYSQL_CONF_FOLDER=os.path.join(APPS_FOLDER, "mysql")
MYSQL_CONF_FILE=os.path.join(MYSQL_CONF_FOLDER, "mysql.cfg")
MYSQL_PROCESS_COMMAND='/bin/ps -eo pid,user,pri,fname,pcpu,pmem,nlwp,command,args | grep -v "\[sh] <defunct>" | grep -E "((mysqld)|(mariadbd))" | grep -v grep'
MYSQL_REPLICATION_SLAVE_STATUS_QUERY = "SHOW SLAVE STATUS"
MYSQL_REPLICATION_REPLICA_STATUS_QUERY = "SHOW REPLICA STATUS"
MYSQL_REPLICATION_MASTER_STATUS_QUERY = "SHOW MASTER STATUS"
MYSQL_REPLICATION_BINARY_LOG_STATUS_QUERY = "SHOW BINARY LOG STATUS"
MYSQL_VERSION_QUERY = "SELECT @@Version"
MYSQL_AURORA_VERSION_QUERY = "show global variables like 'aurora_version'"
MYSQL_INIT=False
MARIADB_DISCOVERY_PARAM_QUERY = "SHOW GLOBAL VARIABLES WHERE variable_name in ('server_id')"

#mongodb
MONGODB_DB="mongodb"
PSYCOPG2_MODULE="0"
MONGODB_CONF_FOLDER=os.path.join(APPS_FOLDER, "mongodb")
MONGODB_CONF_FILE=os.path.join(MONGODB_CONF_FOLDER, "mongodb.cfg")
MONGODB_INPUT_FILE=os.path.join(AGENT_CONF_DIR,'mongodb_input')
MONGODB_PID_COMMAND='netstat -nltp 2>/dev/null | grep -v "\[sh] <defunct>" | grep -E mongod | grep -v grep'
MONGODB_VERSION_COMMAND='mongo --version'

#postgres
RESTART_POSTGRESQL_MONITORING="RESTART_POSTGRESQL_MONITORING"
POSTGRES_DB="postgres"
PSYCOPG2_MODULE="0"
POSTGRES_CONF_FOLDER=os.path.join(APPS_FOLDER, "postgres")
POSTGRES_CONF_FILE=os.path.join(POSTGRES_CONF_FOLDER, "postgres.cfg")
POSTGRES_AURORA_VERSION_QUERY = "select * FROM aurora_version()"

#oracle
RESTART_ORACLE_MONITORING="RESTART_ORACLE_MONITORING"
ORACLE_DB="oracledb"
PYTHON_ORACLEDB_MODULE = "0"
ORACLE_DB_CONF_FOLDER=os.path.join(APPS_FOLDER, "oracledb")
ORACLE_DB_UPDATE_FILE=os.path.join(AGENT_CONF_DIR, "oracle_update")
ORACLE_DB_CONF_FILE=os.path.join(ORACLE_DB_CONF_FOLDER, "oracle.cfg")

db_ssl_config = "db_ssl_config"
db_ssl_terminal_response_file = os.path.join(AGENT_CONF_DIR,'db_ssl_terminal_response')

DB_CONSTANTS = {
    "mysql" :   {
        'APP_KEY'                   :   'mysql',
        'DISPLAY_NAME'              :   'MYSQL',
        'INPUT_FILE'                :   os.path.join(AGENT_CONF_DIR,'mysql_input'),
        'REMOVE_FILE'               :   os.path.join(AGENT_CONF_DIR,'mysql_remove'),
        'NDB_XML_QUERY_FILE_NAME'   :   'mysql_ndb_queries.xml',
        'TERMINAL_RESPONSE_FILE'    :   os.path.join(AGENT_CONF_DIR,'mysql_terminal_response'),
        'CONF_FOLDER'               :   MYSQL_CONF_FOLDER,
        'CONF_FILE'                 :   MYSQL_CONF_FILE,
        'ADD_INSTANCE_START_TIME'   :   None,
        'PID_COMMAND'               :   'netstat -nltp 2>/dev/null | grep -v "\[sh] <defunct>" | grep -E "((mysqld)|(mariadbd))" | grep -v grep',
        'VERSION_COMMAND'           :   "echo $(mysql -V 2>/dev/null) $(mariadb -V 2>/dev/null)",
        'DATABASE_PER_FILE'         :   25,
        'DISCOVERY_PARAM_QUERY'     :   "SHOW GLOBAL VARIABLES WHERE variable_name in ('server_uuid', 'version')",
        'CONFIG_LAST_CHANGE_TIME'   :   None
    },
    "postgres"  : {
        'APP_KEY'                   :   'postgres',
        'DISPLAY_NAME'              :   'POSTGRESQL',
        'INPUT_FILE'                :   os.path.join(AGENT_CONF_DIR,'postgres_input'),
        'REMOVE_FILE'               :   os.path.join(AGENT_CONF_DIR,'postgres_remove'),
        'XML_QUERY_FILE_NAME'       :   'postgres_queries.xml',
        'TERMINAL_RESPONSE_FILE'    :   os.path.join(AGENT_CONF_DIR,'postgres_terminal_response'),
        'CONF_FOLDER'               :   POSTGRES_CONF_FOLDER,
        'CONF_FILE'                 :   POSTGRES_CONF_FILE,
        'ADD_INSTANCE_START_TIME'   :   None,
        'PID_COMMAND'               :   'netstat -nltp 2>/dev/null | grep -v "\[sh] <defunct>" | grep -E postgres | grep -v grep',
        'VERSION_COMMAND'           :   'psql -V 2>/dev/null',
        'DATABASE_PER_FILE'         :   25,
        'DISCOVERY_PARAM_QUERY'     :   "select not pg_is_in_recovery() as isprimary,split_part(version(),' ',2) as version, system_identifier from pg_control_system()",
        'CONFIG_LAST_CHANGE_TIME'   :   None
    },
    "oracledb":{
        'APP_KEY'                   :   'oracledbmon',
        'DISPLAY_NAME'              :   'Oracle Database',
        'INPUT_FILE'                :   os.path.join(AGENT_CONF_DIR,'oracle_input'),
        'REMOVE_FILE'               :   os.path.join(AGENT_CONF_DIR,'oracle_remove'),
        'XML_QUERY_FILE_NAME'       :   'oracledb_queries.xml',
        'TERMINAL_RESPONSE_FILE'    :   os.path.join(AGENT_CONF_DIR,'oracledb_terminal_response'),
        'CONF_FOLDER'               :   ORACLE_DB_CONF_FOLDER,
        'CONF_FILE'                 :   ORACLE_DB_CONF_FILE,
        'ADD_INSTANCE_START_TIME'   :   None,
        'PID_COMMAND'               :   'netstat -nltp 2>/dev/null | grep -v "\[sh] <defunct>" | grep -E tnslsnr | grep -v grep |grep -v 5500 |grep -v 5501',
        # 'VERSION_COMMAND'           :   "runuser -u oracle -- bash -c '. ~/.bash_profile; sqlplus -V'",
        'VERSION_COMMAND'           :   "runuser -u oracle -- bash -c '. ~/.bash_profile; sqlplus -V' 2>/dev/null || sqlplus -V 2>/dev/null",
        'DATABASE_PER_FILE'         :   25,
        'DISCOVERY_PARAM_QUERY'     :   'select DATABASE_ROLE,VERSION,DBID,instance_number,instance_name,database_type,cdb from v$database,v$instance where rownum<2',
        'CONFIG_LAST_CHANGE_TIME'   :   None
    }
}

#agent ops
STOP_LOGGING = False

#dc bottlenecks
error_in_server =  {}
PROC_MOUNT_COMMAND='cat /proc/mounts'
AGENT_PARTITION_UTIL_CMD = "df -m "+AGENT_WORKING_DIR+" | tail -n 1 | awk '{print $4}'"

HDFS_CLUSTER_ID_FILE=os.path.join(AGENT_TEMP_DIR, "hdfs_clusterid")
NODE_COUNT_IN_DC = 10
SKIP_STANDBY_NODES = set()
AGENT_APP_ID_FILE = os.path.join(AGENT_CONF_DIR, "site24x7_app_id")
FILES_LIST_TO_DELETE = [os.path.join(APPS_FOLDER, 'hadoop/namenode.xml'),os.path.join(APPS_FOLDER, 'hadoop/datanode.xml'),os.path.join(APPS_FOLDER, 'hadoop.conf'),os.path.join(APPS_FOLDER,'docker.conf'),APPS_YELLOW_PAGES_FILE,os.path.join(AGENT_LIB_DIR,'Site24x7StatsdAgent'),os.path.join(AGENT_CONF_DIR,'statsd.cfg')]
AZURE_RESOURCEID_API='http://169.254.169.254/metadata/instance/compute?api-version=2019-03-11'
FORCE_LOAD_PLUGINS = False
PS_UTIL_DC = False
PS_UTIL_FLOW = False
CONFIG_FILES_CLEAN_UP=[os.path.join(APPS_FOLDER,'docker.conf'),AGENT_PLUGINS_DIR]
INSTALL_PARAMS_DICT={'display_name':'dn','group_name':'gn','threshold_profile':'tp','notification_profile':'np','resource_profile':'rp','installer':'installer','configuration_template':'ct','rule':'rule'}
AS='agent_settings'
PLUGIN_DEPLOY_CONFIG = None
CD='CHILD_DISCOVERY'
CCD='CLIENT_CHILD_DISCOVERY'
CONTAINER_MANAGEMENT_ACTION='CMA'
PREVIOUS_FILE_OBJ={}
PREVIOUS_FILE_OBJ_FILE = os.path.join(AGENT_TEMP_DIR,'checks_pdc.txt')
PRIMARY_DC='us'
NORMALIZED_LOAD_AVG='nlavg'
DC_SCRIPT_TIMEOUT=20
AUID_FILE=os.path.join(AGENT_TEMP_DIR,'auid.txt')
TOP_COMMAND_OUTPUT_FILE=os.path.join(AGENT_TEMP_DIR,'top.txt')
AUID=0
AUID_OLD=0
EXACT_OS=None
IS_PRODUCTION=1
EXCLUDE_BUFFER_VALUE="ebc"
HDD_NAMES_COMMAND = 'lsblk --noheadings --raw | grep -i disk'
HDD_NAMES=[]
ZOHO_ASSIST_RESOURCEID='/etc/ZohoAssist/Session.json'
DMS_PRIMARY_WS_HOST="us4-dms.zoho.com"
DMS_SECONDARY_WS_HOST="us3-dms.zoho.com"
SERVER_SETTINGS={}
VALIDATION_SERVLET='/plus/CheckSumValidator?'
AGENT_FILES_CHECKSUM_LIST=''
CHECKSUM='checksum'
AUTOMATION_SETTING='it_aut'
CHECKSUM_MISMATCH='checksum mismatch'
PLUGIN_NON_JSON_OUTPUT='Plugin Script Output is not in json format'
VALIDATE_CHECKSUM='VALIDATE_CHECKSUM'
INSTANCE_METADATA_IMPL = {"AWS":"check_aws_platform","Azure":"check_azure_platform","DigitalOcean":"check_digital_ocean_platform","UpCloud":"check_upcloud_platform","VMWare":"check_vmware_platform","GCP":"check_gcp_platform", "OCI": "check_oci_platform"}
METRICS_AGENT_TEMP_CONF_FILE=os.path.join(AGENT_SCRIPTS_DIR,'tmp','metrics_agent.cfg')
METRICS_AGENT_CONF_FILE=os.path.join(METRICS_WORKING_DIRECTORY,'metrics_agent.cfg')
CUSTOMER_ID = None
AUTOMATION_PKG = os.path.join(SOURCE_PKG,"automation")
PLUGINS_PKG = os.path.join(SOURCE_PKG,"plugins")
METRICS_PKG = os.path.join(SOURCE_PKG,"metrics")
DATABASE_PKG = os.path.join(SOURCE_PKG, "database_executor")
SOURCE_UPGRADE_PKG =  os.path.join(AGENT_UPGRADE_DIR,"monagent/lib/devops/source/python3.3/src/com/manageengine/monagent") if IS_VENV_ACTIVATED else os.path.join(AGENT_UPGRADE_DIR,"lib","lib/com/manageengine/monagent")
AUTOMATION_UPGRADE_PKG = os.path.join(SOURCE_UPGRADE_PKG,"automation")
PLUGINS_UPGRADE_PKG = os.path.join(SOURCE_UPGRADE_PKG,"plugins")
METRICS_UPGRADE_PKG=os.path.join(SOURCE_UPGRADE_PKG,"metrics")
DATABASE_UPGRADE_PKG=os.path.join(SOURCE_UPGRADE_PKG, "database_executor")
CONF_UPGRADE_PKG =  os.path.join(AGENT_UPGRADE_DIR,"conf")
HEARTBEAT_UPGRADE_PKG = os.path.join(CONF_UPGRADE_PKG,"heartbeat.zip")
APPS_UPGRADE_PKG = os.path.join(CONF_UPGRADE_PKG,"applications.zip")
DC_UPGRADE_PKG = os.path.join(CONF_UPGRADE_PKG,"dc.zip")
RSRC_CHECK_UPGRADE_PKG = os.path.join(CONF_UPGRADE_PKG,"resource_check.zip")
PROCESS_CHECK_UPGRADE_PKG = os.path.join(CONF_UPGRADE_PKG,"process_check.zip")
MGMT_CHECK_UPGRADE_PKG = os.path.join(CONF_UPGRADE_PKG,"mgmt_axn.zip")
UPDATE_SETTINGS = "U_S"
MODULES_TO_CHECK = ["it_aut","plugins"]
AGENT_SETTINGS_FILE = os.path.join(AGENT_CONF_DIR,'settings.cfg')
AGENT_SETTINGS={}
ETC_HOSTNAME_FILE_FOR_KUBE_AGENT='/host/etc/hostname'
MGMT_AXN_FILE = os.path.join(AGENT_CONF_DIR,'mgmt_axn.zip')
HEARTBEAT_SETTING_FILE = os.path.join(AGENT_CONF_DIR,'heartbeat.zip')
DC_SETTING_FILE = os.path.join(AGENT_CONF_DIR,'dc.zip')
APPS_SETTING_FILE = os.path.join(AGENT_CONF_DIR,'applications.zip')
RESOURCE_CHECK_SETTING_FILE = os.path.join(AGENT_CONF_DIR,'resource_check.zip')
PROCESS_CHECK_SETTING_FILE=os.path.join(AGENT_CONF_DIR,'process_check.zip')
PROCESS_DISCOVERY="proc_dis"
UPT="uptime"
HEARTBEAT_KEY="heartbeat"
RESOURCE_CHECK_SETTING="res_check"
APPS_SETTING="apps_dis"
METRICS_SETTING="metrics"
EBPF_SETTING="ebpf"
DC_SETTING="dc"
MANAGEMENT_SETTING="mgmt"
SETTINGS_MAP = {
                "automation":{"k":"it_aut","check":AUTOMATION_PKG,"upgrade_check":AUTOMATION_UPGRADE_PKG},
                "plugins":{"k":"plugins","check":PLUGINS_PKG,"upgrade_check":PLUGINS_UPGRADE_PKG},
                "heartbeat":{"k":"heartbeat","check":HEARTBEAT_SETTING_FILE,"upgrade_check":HEARTBEAT_UPGRADE_PKG},
                "applications":{"k":"apps_dis","check":APPS_SETTING_FILE,"upgrade_check":APPS_UPGRADE_PKG},
                "dc":{"k":"dc","check":DC_SETTING_FILE,"upgrade_check":DC_UPGRADE_PKG},
                "resource_check":{"k":"res_check","check":RESOURCE_CHECK_SETTING_FILE,"upgrade_check":RSRC_CHECK_UPGRADE_PKG},
                "metrics":{"k":"metrics","check":METRICS_PKG,"upgrade_check":METRICS_UPGRADE_PKG},
                "process":{"k":"proc_dis","check":PROCESS_CHECK_SETTING_FILE,"upgrade_check":PROCESS_CHECK_UPGRADE_PKG},
                "mgmt":{"k":"mgmt","check":MGMT_AXN_FILE,"upgrade_check":MGMT_CHECK_UPGRADE_PKG},
                "database":{"k":"database","check":DATABASE_PKG,"upgrade_check":DATABASE_UPGRADE_PKG},
               }
IPARAMS=None
APPLOG_NOTIFICATION_SERVLET="/applog/send_notification?"
APPLOG_NOT_FOUND="APPLOG_AGENT_NOTFOUND"
FAIL="failure"
AWS_TAGS = None
SITE24X7_AGENT_HEARTBEAT_REGEX = re.compile(r".*?---> (?P<time>\d+)(L)* ---> uptime")
MONAGENT_PID_FILE=os.path.join(AGENT_LOG_DETAIL_DIR, "monagent_pid")
MONAGENT_WATCHDOG_PID_FILE=os.path.join(AGENT_LOG_DETAIL_DIR,"monagent_watchdog_pid")
STATUS_UPDATE_TIMEOUT=10
RESPONSE_HEADERS_VIA_DMS=[RESTART_SERVICE,DELETE_MONITORING,STOP_INVENTORY,START_INVENTORY,STOP_MONITORING,START_MONITORING,SUSPEND_DATA_COLLECTION,START_MONITORING,STOP_DMS,START_DMS,REMOVE_DC_ZIPS,INIT_HARDWARE_MONITORING,STOP_HARDWARE_MONITORING,INIT_STATSD_MONITORING,STOP_STATSD_MONITORING,APPLOG_INSTALL_AGENT,APPLOG_UPGRADE_AGENT,APPLOG_START,APPLOG_STOP,SUSPEND_MONITOR,DELETE_MONITOR,ACTIVATE_MONITOR,DELETE_METRICS,REMOVE_METRICS_DC_ZIPS,STOP_METRICS_AGENT,STOP_PROMETHEUS,STOP_STATSD,START_METRICS_AGENT,START_PROMETHEUS,START_STATSD,KUBE_INSTANT_DISCOVERY]
