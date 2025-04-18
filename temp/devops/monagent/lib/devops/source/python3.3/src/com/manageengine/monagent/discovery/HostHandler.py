# $Id$
# Command To Fetch IpAddress From eth0 - /sbin/ifconfig eth0 | grep 'inet addr:' | cut -d: -f2 | awk '{ print $1}'
import os
import platform
import socket
import struct
import traceback
import subprocess
from shutil import copyfile
import random

from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent import ifaddrs
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.collector import DataCollector
from com.manageengine.monagent import AppConstants
from com.manageengine.monagent.container import container_stats
from com.manageengine.monagent.cloud import metadata

def fetchDomainNameForLinux():
    try:
        executorObj = AgentUtil.Executor()
        executorObj.setTimeout(2)
        executorObj.setCommand('dnsdomainname')
        executorObj.executeCommand()
        output = executorObj.getStdOut()
        AgentLogger.log(AgentLogger.STDOUT,'Domain Name '+repr(output))
        if not output == None and output!='':
            AgentConstants.DOMAIN_NAME = output.rstrip("\n")
        else:
            AgentLogger.log(AgentLogger.CRITICAL,'Domain Name not found '+repr(output))
    except Exception as e:
        AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.STDERR],'Exception Occured while fetching dns domain name ')
        traceback.print_exc()
 
def get_docker_host_name(default_hostname="localhost"):
    _status = True
    try:
        if os.environ and "NODE_NAME" in os.environ:
            AgentConstants.HOST_FQDN_NAME = AgentConstants.HOST_NAME = os.environ["NODE_NAME"]
            return
        is_gcp_platform, json, _ = metadata.check_gcp_platform()
        if is_gcp_platform:
            AgentLogger.log(AgentLogger.MAIN, "Identified GCP cloud environment")
            hostname = metadata.get_hostname_for_gcp_vms()
            if hostname:
                AgentConstants.HOST_FQDN_NAME = AgentConstants.HOST_NAME = hostname
                return
        import docker
        if container_stats.DockerStats.check_if_podman():
            AppConstants.docker_base_url=AppConstants.podman_base_url
        docker_client = docker.DockerClient(base_url=AppConstants.docker_base_url, version="auto")
        docker_info = docker_client.info()
        hostname = docker_info.get("Name", None)
        da_os_name = docker_info.get("OperatingSystem", "Linux")
        da_architecture = docker_info.get("Architecture", "x86_64")
        if hostname:
            AgentConstants.HOST_FQDN_NAME = AgentConstants.HOST_NAME = hostname
        AgentConstants.DA_OPERATING_SYSTEM_NAME = da_os_name
        AgentConstants.DA_OS_ARCHITECTURE = da_architecture
    except Exception as e:
        _status = False
        AgentLogger.log(AgentLogger.COLLECTOR,'exception occurred while getting docker host name')
        import platform
        AgentConstants.DA_OS_ARCHITECTURE = platform.architecture()[0]
        bool_status , host_name = AgentUtil.get_hostname_from_etc()
        AgentConstants.HOST_FQDN_NAME = AgentConstants.HOST_NAME = host_name 
        import distro
        AgentConstants.DA_OPERATING_SYSTEM_NAME = distro.like()
        traceback.print_exc()
    finally:
        return _status

def get_docker_host_ipaddr(default_ipaddr="127.0.0.1"):
    try:
        if os.environ and "NODE_IP" in os.environ:
            AgentConstants.IP_ADDRESS = os.environ["NODE_IP"]
            return
        if AgentConstants.IS_VENV_ACTIVATED:
            AgentConstants.IP_ADDRESS = socket.gethostbyname(AgentConstants.HOST_FQDN_NAME)
        else:
            AgentConstants.IP_ADDRESS = getHostIpAddress()
    except Exception as e:
        AgentConstants.IP_ADDRESS = default_ipaddr
        traceback.print_exc()
        
def get_docker_host_gateway(default_gwaddr="127.0.0.1"):
    _status = True
    try:
        gateway_path = os.path.join(AgentConstants.PROCFS_PATH, "net", "route")
        with open(gateway_path) as f:
            for line in f.readlines():
                fields = line.strip().split()
                if fields[1] == '00000000':
                    AgentConstants.GATEWAY_ADDRESS = socket.inet_ntoa(struct.pack('<L', int(fields[2], 16)))
                    break
    except Exception as e:
        _status = False
        AgentConstants.GATEWAY_ADDRESS = default_gwaddr
        traceback.print_exc()
    finally:
        return _status

def get_docker_host_macaddr(default_macaddr="00:00:00:00:00:00"):
    _status = True
    try:
        AgentConstants.MAC_ADDRESS = default_macaddr
    except Exception as e:
        _status = False
        traceback.print_exc()
    finally:
        return _status
    

def populateHostInfo():
    str_macAddress = '00:00:00:00:00:00'
    str_hostIpAddress = '127.0.0.1'
    computerNameWithDNS = None
    isDummyHostName = False
    if AgentConstants.IS_DOCKER_AGENT == "1" and not platform.system().lower().startswith("sun"):
        #get_host_name
        get_docker_host_name()
        #get_host_ip
        get_docker_host_ipaddr()
        #get_docker_host_gateway
        get_docker_host_gateway()
        #get_docker_host_macaddr
        get_docker_host_macaddr()
    
    else:
        try:
            (computerNameWithDNS, aliasList, ipList) = socket.gethostbyaddr(socket.gethostname())
        except Exception as e:
            AgentLogger.log(AgentLogger.CRITICAL, ' *************************** Exception While fetching host name in HostHandler *************************** '+ repr(e))
            traceback.print_exc()
            isDummyHostName = True
            try:
                computerNameWithDNS=str(subprocess.check_output("hostname",timeout=5).decode('UTF-8').rstrip('\n')) if AgentConstants.PYTHON_VERSION >= 3 else str(subprocess.check_output("hostname").decode('UTF-8').rstrip('\n'))
            except:
                AgentLogger.log(AgentLogger.CRITICAL, ' *************************** Exception While fetching host name in command execution ************************')
                traceback.print_exc()
                computerNameWithDNS=str(random.randint(1,99999))
        if not isDummyHostName: 
            AgentConstants.HOST_NAME = platform.node()
        else:
            AgentConstants.HOST_NAME = computerNameWithDNS
        AgentConstants.HOST_FQDN_NAME = computerNameWithDNS
        dict_hostIntfDetails = ifaddrs.getifaddrs()
        AgentLogger.log(AgentLogger.STDOUT,'Host Details Obtained From Native Library :'+repr(dict_hostIntfDetails))
        str_hostIpAddress = getHostIpAddress()
        AgentLogger.log(AgentLogger.STDOUT,'IP obtained :: {}'.format(str_hostIpAddress))
        if str_hostIpAddress == None and AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_ip_address') == '0' and AgentUtil.AGENT_CONFIG.defaults().get('discover_host') == 'false':
            AgentConstants.IP_ADDRESS = str_hostIpAddress
            AgentConstants.MAC_ADDRESS = str_macAddress
            return True        
        elif str_hostIpAddress == None and AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_ip_address') == '0':
            AgentLogger.log(AgentLogger.CRITICAL,' ********************* Unable To Populate Host Info Since Ip Address Is None ********************** ')
            return False
        elif not AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_ip_address') == '0':
            AgentConstants.IP_ADDRESS = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_ip_address')
            str_hostIpAddress = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_ip_address')
        for str_intfName in dict_hostIntfDetails:
            dict_addressDetails = dict_hostIntfDetails[str_intfName]
            if 2 in dict_addressDetails and 'addr' in dict_addressDetails[int('2')] and dict_addressDetails[int('2')]['addr'] == str_hostIpAddress:
                if 17 in dict_addressDetails and 'addr' in dict_addressDetails[int('17')]:
                    str_macAddress = dict_addressDetails[int('17')]['addr']
                AgentLogger.log(AgentLogger.STDOUT,'Host Primary Interface :'+str_intfName+', Ip Address : '+str_hostIpAddress+', MAC Address : '+str_macAddress)
                break
        if str_macAddress == None and AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_mac_address') == '0' and AgentUtil.AGENT_CONFIG.defaults().get('discover_host') == 'false':
            AgentConstants.MAC_ADDRESS = None
            return True
        elif str_macAddress == None and AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_mac_address') == '0':
            AgentLogger.log(AgentLogger.CRITICAL,' ********************* Unable To Populate Host Info Since MAC Address Is None ********************** ')
            return False
        elif not AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_mac_address') == '0':
            AgentConstants.MAC_ADDRESS = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_mac_address')
            str_macAddress = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_mac_address')
        else:
            AgentConstants.IP_ADDRESS = str_hostIpAddress
            AgentConstants.MAC_ADDRESS = str_macAddress
    return True

class OSFactory:
    def __init__(self):
        AgentLogger.log(AgentLogger.STDOUT,"OS NAME ======> {0}".format(AgentConstants.OS_NAME))
        if AgentConstants.OS_NAME == AgentConstants.LINUX_OS:
            LinOS()
        elif AgentConstants.OS_NAME == AgentConstants.FREEBSD_OS:
            FreebsdOS()
        elif AgentConstants.OS_NAME == AgentConstants.OS_X:
            MacOs()
        else:
            AgentLogger.log(AgentLogger.STDOUT,"Different Os ======> {0}".format(AgentConstants.OS_NAME))
            Os()
        if AgentConstants.IS_VENV_ACTIVATED is True:
            AgentConstants.UPGRADE_FILE_URL_NAME = AgentConstants.UPGRADE_FILE_NAME = AgentConstants.PRODUCT_NAME+'_'+"Hybrid"+'_Upgrade.tar.gz'
            AgentConstants.AGENT_UPGRADE_FILE_NAME = ""
            AgentConstants.WATCHDOG_UPGRADE_FILE_NAME = "" 
            if not AgentConstants.OS_NAME == AgentConstants.LINUX_OS : Os.set_scripts_path()
            
class CollectorFactory:
    def __init__(self):
        if AgentConstants.OS_NAME == AgentConstants.LINUX_OS:
            DataCollector.COLLECTOR = DataCollector.UbuntuCollector(AgentConstants.LINUX_DIST)
        else:
            if not AgentConstants.IS_DOCKER_AGENT == "1":
                AgentLogger.log(AgentLogger.MAIN, "Collector factory for os {} initialized".format(AgentConstants.OS_NAME))
                DataCollector.COLLECTOR = DataCollector.CommonCollector(AgentConstants.OS_NAME)

class Os:
    def __init__(self):        
        AgentConstants.OS_FLAVOR = AgentConstants.OS_NAME
        Os.set_scripts_path()
    
    @staticmethod
    def set_scripts_path():
        #script.sh
        AgentConstants.SCRIPTS_FILE_NAME = "_".join([AgentConstants.OS_NAME.lower(), AgentConstants.SCRIPTS_FILE_NAME])
        AgentConstants.SCRIPTS_FILE_PATH = os.path.join(AgentConstants.AGENT_SCRIPTS_DIR, AgentConstants.SCRIPTS_FILE_NAME)
        if not os.path.isfile(AgentConstants.SCRIPTS_FILE_PATH):
            copyfile(AgentConstants.SCRIPTS_TEMPLATE_FILE_PATH, AgentConstants.SCRIPTS_FILE_PATH)
        Os.set_monitorsgroup_path()
        Os.set_custom_monitorsgroup_path()
        Os.set_monitorsxml_path()
        Os.set_custom_monitorsxml_path()
            
    @staticmethod
    def set_monitorsgroup_path():
        AgentConstants.AGENT_MONITORS_GROUP_FILE = os.path.join(AgentConstants.AGENT_CONF_DIR ,"_".join([AgentConstants.OS_NAME.lower(), "monitorsgroup.json"]))
        if not os.path.isfile(AgentConstants.AGENT_MONITORS_GROUP_FILE):
            copyfile(AgentConstants.MONITORSGROUP_TEMPLATE_FILE_PATH, AgentConstants.AGENT_MONITORS_GROUP_FILE)
    
    @staticmethod
    def set_custom_monitorsgroup_path():
        AgentConstants.AGENT_CUSTOM_MONITORS_GROUP_FILE = os.path.join(AgentConstants.AGENT_CONF_DIR ,"_".join([AgentConstants.OS_NAME.lower(), "custom_monitorsgroup.json"]))
        if not os.path.isfile(AgentConstants.AGENT_CUSTOM_MONITORS_GROUP_FILE):
            copyfile(AgentConstants.CUSTOM_MONITORSGROUP_TEMPLATE_FILE_PATH, AgentConstants.AGENT_CUSTOM_MONITORS_GROUP_FILE)
    
    @staticmethod
    def set_monitorsxml_path():
        AgentConstants.AGENT_MONITORS_FILE = os.path.join(AgentConstants.AGENT_CONF_DIR ,"_".join([AgentConstants.OS_NAME.lower(), "monitors.xml"]))
        if not os.path.isfile(AgentConstants.AGENT_MONITORS_FILE):
            copyfile(AgentConstants.MONITORS_TEMPLATE_FILE_PATH, AgentConstants.AGENT_MONITORS_FILE)
    
    @staticmethod
    def set_custom_monitorsxml_path():
        AgentConstants.AGENT_CUSTOM_MONITORS_FILE = os.path.join(AgentConstants.AGENT_CONF_DIR ,"_".join([AgentConstants.OS_NAME.lower(), "custom_monitors.xml"]))
        if not os.path.isfile(AgentConstants.AGENT_CUSTOM_MONITORS_FILE):
            copyfile(AgentConstants.CUSTOM_MONITORS_TEMPLATE_FILE_PATH, AgentConstants.AGENT_CUSTOM_MONITORS_FILE)
    

#         #monitors.xml
#         AgentConstants.MONITORS_FILE_NAME = "_".join([AgentConstants.OS_NAME.lower(), AgentConstants.MONITORS_FILE_NAME])
#         AgentConstants.AGENT_MONITORS_FILE = os.path.join(AgentConstants.AGENT_CONF_DIR, AgentConstants.MONITORS_FILE_NAME)
        
class LinOS:
    def __init__(self):        
        if hasattr(platform,'linux_distribution'):
            (osFlavor, osVersion, osId) = platform.linux_distribution()
        else:
            osFlavor = platform.system()    
        AgentConstants.OS_FLAVOR = osFlavor
        self.setUpgradeFileName()
    def setUpgradeFileName(self):
        AgentConstants.UPGRADE_FILE_NAME = AgentConstants.PRODUCT_NAME+'_'+AgentConstants.LINUX_OS+'_'+AgentConstants.OS_ARCHITECTURE+'_Upgrade.tar.gz'
        AgentConstants.UPGRADE_FILE_URL_NAME = ("arm/" + AgentConstants.UPGRADE_FILE_NAME) if str(platform.machine()) in ["arm64", "aarch64", "ARM", "Arm", "aarch"] else AgentConstants.UPGRADE_FILE_NAME
        AgentConstants.AGENT_UPGRADE_FILE_NAME = AgentConstants.PRODUCT_NAME+'_'+AgentConstants.LINUX_OS+'_'+AgentConstants.OS_ARCHITECTURE+'_Agent_Upgrade.tar.gz'
        AgentConstants.WATCHDOG_UPGRADE_FILE_NAME = AgentConstants.PRODUCT_NAME+'_'+AgentConstants.LINUX_OS+'_'+AgentConstants.OS_ARCHITECTURE+'_Watchdog_Upgrade.tar.gz'

class FreebsdOS:
    def __init__(self):
        osDetails = os.uname()
        if osDetails:
            osFlavor = osDetails.sysname if AgentConstants.PYTHON_VERSION == 3 else osDetails[0]
            osVersion = osDetails.release  if AgentConstants.PYTHON_VERSION == 3 else osDetails[2]
        else:
            osFlavor = AgentConstants.FREEBSD_OS
        #(osFlavor, osVersion, osId) = platform.linux_distribution()    
        AgentConstants.OS_FLAVOR = osFlavor
        self.setUpgradeFileName()
        self.setUserAgentName()
    def setUpgradeFileName(self):
        if AgentConstants.OS_VERSION_ARCH:
            AgentConstants.UPGRADE_FILE_URL_NAME = AgentConstants.UPGRADE_FILE_NAME = AgentConstants.PRODUCT_NAME+'_'+AgentConstants.FREEBSD_OS+'_'+AgentConstants.OS_VERSION_ARCH+'_Upgrade.tar.gz'
            AgentConstants.AGENT_UPGRADE_FILE_NAME = AgentConstants.PRODUCT_NAME+'_'+AgentConstants.FREEBSD_OS+'_'+AgentConstants.OS_VERSION_ARCH+'_Agent_Upgrade.tar.gz'
            AgentConstants.WATCHDOG_UPGRADE_FILE_NAME = AgentConstants.PRODUCT_NAME+'_'+AgentConstants.FREEBSD_OS+'_'+AgentConstants.OS_VERSION_ARCH+'_Watchdog_Upgrade.tar.gz'
        else:
            AgentConstants.UPGRADE_FILE_URL_NAME = AgentConstants.UPGRADE_FILE_NAME = AgentConstants.PRODUCT_NAME+'_'+AgentConstants.FREEBSD_OS+'_bsd10_64bit_Upgrade.tar.gz'
            AgentConstants.AGENT_UPGRADE_FILE_NAME = AgentConstants.PRODUCT_NAME+'_'+AgentConstants.FREEBSD_OS+'_bsd10_64bit_Agent_Upgrade.tar.gz'
            AgentConstants.WATCHDOG_UPGRADE_FILE_NAME = AgentConstants.PRODUCT_NAME+'_'+AgentConstants.FREEBSD_OS+'_bsd10_64bit_Watchdog_Upgrade.tar.gz'
    def setUserAgentName(self):
        if AgentConstants.OS_NAME:
            AgentConstants.AGENT_NAME = AgentConstants.PRODUCT_NAME + ' ' + AgentConstants.FREEBSD_OS + ' Agent'

class MacOs:
    def __init__(self):        
        AgentConstants.OS_FLAVOR = AgentConstants.OS_X
        self.setUpgradeFileName()
    def setUpgradeFileName(self):
        AgentConstants.UPGRADE_FILE_URL_NAME = AgentConstants.UPGRADE_FILE_NAME = 'Site24x7_OS_X_Agent.zip'
        AgentConstants.AGENT_UPGRADE_FILE_NAME = 'Site24x7Agent.app'
        AgentConstants.WATCHDOG_UPGRADE_FILE_NAME = ''

class OSNotSupportedException(Exception):
    def __init__(self):
        self.message = 'OS Not Supported Exception'
    def __str__(self):
        return self.message

def initialize():
    bool_isSuccess = True
    bool_isAgentInfoModified = False
    try:        
        str_osName = platform.system()
        str_architecture = platform.architecture()[0] 
        AgentLogger.log(AgentLogger.STDOUT,'OPERATING SYSTEM : '+str_osName)
        if str_osName.lower() == AgentConstants.LINUX_OS_LOWERCASE:
            AgentConstants.OS_NAME = AgentConstants.LINUX_OS
        elif str_osName.lower() == AgentConstants.FREEBSD_OS_LOWERCASE:
            AgentConstants.OS_NAME = AgentConstants.FREEBSD_OS
        elif str_osName == 'Darwin':
            AgentConstants.OS_NAME = AgentConstants.OS_X
        else:
            AgentConstants.OS_NAME = str_osName.lower()
        
        if '32' in str_architecture:
            AgentConstants.OS_ARCHITECTURE = AgentConstants.THIRTY_TWO_BIT
        elif '64' in str_architecture:
            AgentConstants.OS_ARCHITECTURE = AgentConstants.SIXTY_FOUR_BIT
        else:
            AgentConstants.OS_ARCHITECTURE = platform.architecture()[0]
        OSFactory()
        CollectorFactory()
        if not populateHostInfo():
            return False
        if AgentConstants.OS_NAME == AgentConstants.LINUX_OS and AgentConstants.IS_DOCKER_AGENT == "0":
            fetchDomainNameForLinux()
        AgentLogger.log(AgentLogger.MAIN,'========================== HOST AND OS DETAILS ========================== \n')
        if AgentConstants.IP_ADDRESS == None or AgentConstants.IP_ADDRESS == '0':
            AgentConstants.IP_ADDRESS = '127.0.0.1'
        if AgentConstants.MAC_ADDRESS == None or AgentConstants.MAC_ADDRESS == '0':
            AgentConstants.MAC_ADDRESS = '00:00:00:00:00:00'
        AgentLogger.log(AgentLogger.MAIN,'HOST_NAME : '+repr(AgentConstants.HOST_NAME)+' HOST_FQDN_NAME : '+repr(AgentConstants.HOST_FQDN_NAME)+' IP_ADDRESS : '+repr(AgentConstants.IP_ADDRESS)+' MAC_ADDRESS : '+repr(AgentConstants.MAC_ADDRESS)+ ' OS_NAME : '+repr(AgentConstants.OS_NAME)+' OS_FLAVOR : '+repr(AgentConstants.OS_FLAVOR)+' OS_ARCHITECTURE : '+repr(AgentConstants.OS_ARCHITECTURE)+'\n')
        AgentLogger.debug(AgentLogger.MAIN,'CUSTOMER_ID : '+ str(AgentConstants.CUSTOMER_ID))
        if AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_ip_address') == '0':
            AgentLogger.log(AgentLogger.STDOUT,'Modifying AGENT_IP_ADDRESS '+repr(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_ip_address'))+' In Conf File To '+' : '+repr(AgentConstants.IP_ADDRESS))
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'agent_ip_address', AgentConstants.IP_ADDRESS)            
            bool_isAgentInfoModified = True
        if AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_mac_address') == '0':
            AgentLogger.log(AgentLogger.STDOUT,'Modifying AGENT_MAC_ADDRESS '+repr(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_mac_address'))+' In Conf File To '+' : '+repr(AgentConstants.MAC_ADDRESS))            
            AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'agent_mac_address', AgentConstants.MAC_ADDRESS)
            bool_isAgentInfoModified = True
        if bool_isAgentInfoModified:
            AgentUtil.persistAgentInfo()
        #AgentLogger.log(AgentLogger.MAIN,'==================================================================')
    except Exception as e:
        AgentLogger.log([AgentLogger.CRITICAL,AgentLogger.MAIN], ' *************************** Exception While Initializing HostHandler *************************** '+ repr(e))
        traceback.print_exc()
        bool_isSuccess = False
    return bool_isSuccess


def getHostIpAddress():
    hostIpAddress = '127.0.0.1'
    if hostIpAddress == None or hostIpAddress == '127.0.0.1' or hostIpAddress == '0.0.0.0':
        isSuccess, hostIpAddress = CommunicationHandler.pingServer(AgentLogger.MAIN)
        AgentLogger.log(AgentLogger.MAIN, 'Agent Ip Address Obtained By Pinging Server : '+repr(hostIpAddress)+'\n')
        if hostIpAddress == None or hostIpAddress == '127.0.0.1' or hostIpAddress == '0.0.0.0': 
            if AgentConstants.OS_NAME in AgentConstants.OS_SUPPORTED:
                hostIpAddress = get_ip_address()
                if not hostIpAddress == None and not hostIpAddress == '127.0.0.1' and not hostIpAddress == '0.0.0.0':
                    AgentLogger.log(AgentLogger.MAIN, 'Agent Ip Address Obtained From /sbin/ifconfig : '+repr(hostIpAddress))                    
    AgentLogger.log(AgentLogger.MAIN, 'Agent Ip Address From Conf File : '+repr(AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_ip_address')))
    ipAddressFromConf = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_ip_address')
    if hostIpAddress == ipAddressFromConf:
        AgentLogger.log(AgentLogger.MAIN,'IP address obtained and IP address present in config file are same'+'\n')
        hostIpAddress = ipAddressFromConf
    else:
        AgentLogger.log(AgentLogger.MAIN,'IP address obtained and IP address present in config file are not same'+'\n')
        AgentUtil.AGENT_CONFIG.set('AGENT_INFO', 'agent_ip_address',hostIpAddress)
        AgentUtil.persistAgentInfo()
    return hostIpAddress

def get_ip_address():
    str_ipAddress = '127.0.0.1'
    try:
        if AgentConstants.OS_NAME == AgentConstants.SUN_OS:
            str_ipAddress = AgentUtil.executeCommand("ifconfig $(netstat -rn | grep default | awk '{print $NF}') | grep inet | awk '{print $2}'")
        else:
            import ifcfg
            default = ifcfg.default_interface()
            if 'inet' in default:   
                str_ipAddress = default['inet']
    except Exception as e:
        traceback.print_exc()
    AgentLogger.debug(AgentLogger.MAIN,'IP Address using ifconfig command :: {}'.format(str_ipAddress))
    return str_ipAddress
