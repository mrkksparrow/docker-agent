'''
Created on 20-Oct-2016

@author: giri
'''
import os
import sys
import time
from com.manageengine.monagent.remoteinstaller import resultpool

AGENT_PARAMS = '1'

LOGGER_DICT = {}
RESULT_DICT = {}

TOTAL_MONITORS = []
START_TIME = None
IS_REMOTEINSTALLATION_FINISHED = False

PARENT_FOLDER = os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[0])))
EXEC_DIR_PATH = os.path.dirname(os.path.realpath(sys.argv[0]))
MONITORS_CONFIG = []
CURRENT_MILLI_TIME = lambda: int(round(time.time() * 1000))

LOG_DIR_PATH = os.path.join(os.path.dirname(PARENT_FOLDER), 'logs')
CONF_DIR_PATH = os.path.join(PARENT_FOLDER, 'installconfig')
INSTALL_DIR_PATH = os.path.join(PARENT_FOLDER, 'scripts')
INSTALLER_RESULT_FILE = os.path.join(os.path.dirname(PARENT_FOLDER), 'results.txt')
REMOTE_INSTALLER_HERATBEAT_FILE = os.path.join(PARENT_FOLDER, "heartbeat.txt")
BUILD_VERSION_FILE = os.path.join(PARENT_FOLDER, "version.txt")

CONFIGURATION_FILE = "configuration.properties"
CONFIGURATION_FILE_PATH = os.path.join(CONF_DIR_PATH, CONFIGURATION_FILE)

SERVER_DOMAINS_FILE = os.path.join(CONF_DIR_PATH, "server_domains.json")

REMOTE_MACHINE_DETAILS_FILE = "remote_machine_details.properties"
REMOTE_MACHINE_DETAILS_FILE_PATH = os.path.join(CONF_DIR_PATH, REMOTE_MACHINE_DETAILS_FILE)
LOG_FILE = "remoteinstall.log"
LOG_FILE_PATH = os.path.join(LOG_DIR_PATH, LOG_FILE)
STDOUT_LOG_FILE_PATH = os.path.join(LOG_DIR_PATH, "remoteinstall_stdout.log")
STDERR_LOG_FILE_PATH = os.path.join(LOG_DIR_PATH, "remoteinstall_error.log")

FORCE_INSTALL = 'True'
LOCAL_32BIT_INSTALLER_PATH = None
LOCAL_64BIT_INSTALLER_PATH = None

API_KEY = None

INSTALLFILE_32_BIT_NAME = "Site24x7_Linux_32bit.install"
INSTALLFILE_64_BIT_NAME = "Site24x7_Linux_64bit.install"

INSTALLFILE_32_BIT_PATH = os.path.join(INSTALL_DIR_PATH, INSTALLFILE_32_BIT_NAME)
INSTALLFILE_64_BIT_PATH = os.path.join(INSTALL_DIR_PATH, INSTALLFILE_64_BIT_NAME)
SCRIPTFILE_PATH = os.path.join(INSTALL_DIR_PATH, "os_platform.sh")

STATIC_DOMAIN = 'staticdownloads.site24x7.com'
STATIC_32BIT_URL = ''
STATIC_64BIT_URL = ''

CSVFILE_NAME_TXT = "servers.txt"
CSVFILE_PATH_TXT = os.path.join(CONF_DIR_PATH, CSVFILE_NAME_TXT)

HTTP_PROXY_URL = None
HTTPS_PROXY_URL = None

RESULT_CONFIG_PATH = os.path.join(os.path.dirname(PARENT_FOLDER), "result.properties")
REMOTE='remote'
INSTALL_PARAMS=None

IS_32BIT_DOWNLOADED = False
IS_64BIT_DOWNLOADED = False

IS_32BIT_DOWNLOAD_ATTEMPT = False
IS_64BIT_DOWNLOAD_ATTEMPT = False

AGENT_ALREADY_RUNNING_FLAG_FILE = os.path.join(PARENT_FOLDER, "agent_instance.txt")

REMOTE_INSTALL_STATS = os.path.join(PARENT_FOLDER, "stats.txt")

RESULTPOOL_HANDLER = resultpool.ResultPool()

PLUS_S24X7_URL = "https://plus.site24x7.com/plus/RemoteInstallerUsingSSH?custID="
#PLUS_S24X7_URL = "http://arun-3453.csez.zohocorpin.com:8081/plus/RemoteInstallerUsingSSH?custID="

IS_PROCESS_STARTED = False
PRINT_SSH_DATA = []
PRINT_DOWNLOAD_DATA = False
BUILD_VERSION = '1.0.0'
