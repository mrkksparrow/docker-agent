#$Id$

import json
import os
import traceback
import time
import subprocess
import platform
import socket
import re

from six.moves.urllib.parse import urlencode
import com
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil
from com.manageengine.monagent.scheduler import AgentScheduler
from collections import OrderedDict

SYSTEM_SOFTWARE_PACKAGES_DICT={}

SYSTEM_HARDWARE_INFO_PATH='/sys/class/dmi/id/'

SERVER_INVENTORY_DICT=OrderedDict()

SERVER_INVENTORY_CT=None

METRIC_FILE_MAP={'SERIAL_NO':'product_serial','BIOS_VENDOR':'bios_vendor','MODEL':'product_name','BIOS_VERSION':'bios_version','MANUFACTURER':'sys_vendor'}

COMMANDS_MAP={"boot_time":"who -b ","nicc":"netstat -i | sort -u -k 1,1 | wc -l" ,"dpc":"df -l | wc -l"}

BIOS_COMMAND_MAP={'MODEL':"ioreg -l | grep -w 'product-name' | head -n 1",'MANUFACTURER':"ioreg -l | grep -w 'manufacturer' | head -n 1"}

''' @attention:  use ordered dict to store inventory data - since we use string comparison by generating hashid .. otherwise it will create a mismatch in every poll.'''


def inventory_data_collector():
    global SERVER_INVENTORY_CT
    try:
        SERVER_INVENTORY_CT = AgentUtil.getTimeInMillis()
        get_server_info()
        get_server_os_info()
        if AgentConstants.OS_NAME in [AgentConstants.OS_X, AgentConstants.FREEBSD_OS]:
            get_server_hardware_info()
        elif not AgentConstants.OS_NAME == AgentConstants.SUN_OS:
            linux_get_server_hardware_info()
        get_command_map_data()
        get_dns_ip()
        get_agent_inventory()
        get_server_roles()
        if change_in_inventory():
            upload_server_inventory()
        save_server_inventory()
    except Exception as e:
        traceback.print_exc()


def get_agent_inventory():
    try:
        SERVER_INVENTORY_DICT['server_inventory']['path']=AgentConstants.AGENT_WORKING_DIR
        SERVER_INVENTORY_DICT['server_inventory']['user']=AgentConstants.AGENT_USER_NAME
    except Exception as e:
        traceback.print_exc()

def get_server_roles():
    try:
        hostname = subprocess.check_output(["hostnamectl"], universal_newlines=True)
        m = re.search('Chassis: (.+?)\n', hostname)
        chassisType = m.group(1)
    except :
        chassisType = "vm"
    
    try:
        systemd = subprocess.check_output(["systemd-detect-virt"], universal_newlines=True, shell=True, stderr=subprocess.DEVNULL)
    except :
        systemd = ""
    
    if os.path.isfile('/sys/class/dmi/id/chassis_type'):
        with open('/sys/class/dmi/id/chassis_type') as f:
            chassisNumber = f.read().strip()
    else:
        chassisNumber=""
    
    if chassisNumber == "1" and chassisType in ("vm", "container") and systemd != "none":
        SERVER_INVENTORY_DICT['server_inventory']['SERVER_ROLES'] = "Virtual Machine"
    else:
        SERVER_INVENTORY_DICT['server_inventory']['SERVER_ROLES'] = "Physical Machine"
        
def get_dns_ip():
    ip_list = []
    try:
        if os.path.isfile('/etc/resolv.conf'):
            with open('/etc/resolv.conf', 'r') as fp:
                content = fp.readlines()
            for line in content:
                if line.startswith('nameserver'):
                    line = line.split()[1]
                    ip_list.append(line)
        SERVER_INVENTORY_DICT['server_inventory']['dns_ip']=','.join(ip_list)
    except Exception as e:
        traceback.print_exc()

def get_command_map_data():
    try:
        for metric , command in COMMANDS_MAP.items():
            executorObj = AgentUtil.Executor()
            executorObj.setTimeout(30)
            executorObj.setCommand(command)
            executorObj.executeCommand()
            stdout = executorObj.getStdOut()
            if stdout:
                stdout = stdout.strip()
                if metric == 'boot_time':
                    stdout = stdout.replace("system boot", "" ).strip('.')
                    stdout = stdout.strip("reboot   ~")
                if metric == 'nicc' and not int(stdout):
                    if AgentConstants.IS_DOCKER_AGENT=='1':
                        stdout = len(AgentConstants.PSUTIL_OBJECT.net_if_stats())
                    else:
                        if AgentConstants.NETWORKS_LIST: 
                            stdout = len(AgentConstants.NETWORKS_LIST)
                        else:
                            stdout = int(stdout) - 2 if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS] else int(stdout) - 1
                if metric == 'dpc' and not int(stdout):
                    stdout = int(stdout) - 1
            SERVER_INVENTORY_DICT['server_inventory'][metric] = stdout
    except Exception as e:
        traceback.print_exc()

def save_server_inventory():
    try:
        fileObj = get_server_inventory_file_obj()
        SERVER_INVENTORY_DICT.pop('collection_time',1)
        fileObj.set_data(SERVER_INVENTORY_DICT)
        fileObj.set_mode('wb')
        bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
    except Exception as e:
        traceback.print_exc()

def get_server_inventory_file_obj():
    fileObj = None
    try:
        fileObj = AgentUtil.FileObject()
        fileObj.set_filePath(AgentConstants.SERVER_INVENTORY_DATA_FILE)
        fileObj.set_dataType('json')
        fileObj.set_mode('rb')
        fileObj.set_dataEncoding('UTF-8')
        fileObj.set_loggerName(AgentLogger.STDOUT)
        fileObj.set_logging(False)
    except Exception as e:
        traceback.print_exc()
    finally:
        return fileObj
    
def change_in_inventory():
    change_in_inventory=False
    try:
        if os.path.exists(AgentConstants.SERVER_INVENTORY_DATA_FILE):
            fileObj=get_server_inventory_file_obj()
            bool_toReturn, dict_inv_data = FileUtil.readData(fileObj)
            str_json = json.dumps(dict_inv_data)
            str_current_json = json.dumps(SERVER_INVENTORY_DICT)
            if AgentUtil.get_hash_id(str_json) != AgentUtil.get_hash_id(str_current_json):
                AgentLogger.log(AgentLogger.STDOUT,' change in inventory data -- {0}'.format(json.dumps(SERVER_INVENTORY_DICT)))
                change_in_inventory=True
        else:
            change_in_inventory=True
    except Exception as e:
        traceback.print_exc()
    finally:
        return change_in_inventory

def linux_get_server_hardware_info():
    try:
        for metric in METRIC_FILE_MAP:
            if not AgentConstants.ISROOT_AGENT and metric == 'SERIAL_NO':
                continue
            file_name = SYSTEM_HARDWARE_INFO_PATH + METRIC_FILE_MAP[metric]
            if os.path.exists(file_name):
                with open(file_name, 'r') as file_obj:
                    value = file_obj.read()
                SERVER_INVENTORY_DICT['server_inventory'][metric] = value.strip() 
    except Exception as e:
        traceback.print_exc()
        
def get_server_hardware_info():
    for metric , command in BIOS_COMMAND_MAP.items():
        try:
            executorObj = AgentUtil.Executor()
            executorObj.setTimeout(30)
            executorObj.setCommand(command)
            executorObj.executeCommand()
            stdout = executorObj.getStdOut()
            stderr = executorObj.getStdErr()
            retVal = executorObj.getReturnCode()
            if stdout:
                stdout=stdout.replace(',','.')
                SERVER_INVENTORY_DICT['server_inventory'][metric]=stdout[stdout.find('<')+2:stdout.find('>')-1]
        except Exception as e:
            traceback.print_exc()
               
def get_server_software_packages():
    query_to_get_packages=None
    packages_output = None
    try:
        if AgentConstants.DPKG_UTILITY_PRESENT:
            query_to_get_packages = AgentConstants.DPKG_QUERY
        if AgentConstants.RPM_UTILITY_PRESENT:
            query_to_get_packages = AgentConstants.RPM_QUERY
        if query_to_get_packages:
            packages_output = execute_query_for_soft_packages(query_to_get_packages)
        else:
            AgentLogger.log(AgentLogger.MAIN,' both dpkg and rpm not present ')
        if packages_output:
            parse_soft_packages_info(packages_output)
    except Exception as e:
        traceback.print_exc()
        
#poor code - increases open file count and memory problem - want to use change the logic       
def execute_query_for_soft_packages(query_to_get_packages):
    output = None
    file_to_write_data = '/opt/site24x7/monagent/temp/lo.txt'
    str_args = query_to_get_packages
    content = None
    try:
        proc = subprocess.Popen(query_to_get_packages.split(' '),stdout=open(file_to_write_data,'w'),stderr=open(file_to_write_data,'w'))
        time.sleep(7)
        with open(file_to_write_data,'r') as f:
             content = f.readlines()
             content = [x.strip('\'\n') for x in content]
        output = json.dumps(content)
    except Exception as e:
        traceback.print_exc()
    return content


def parse_soft_packages_info(packages_output):
    try:
        SERVER_INVENTORY_DICT.setdefault('software_packages',[])
        if packages_output:
            for each_pkg in packages_output:
                pkg_list = each_pkg.split(':::')
                SERVER_INVENTORY_DICT['software_packages'].append(pkg_list)
    except Exception as e:
        traceback.print_exc()

def get_server_os_info():
    try:
        SERVER_INVENTORY_DICT['server_inventory']['OS_ARCH'] = platform.processor()

        os_name = ''
        os_version = '-'

        if AgentConstants.IS_DOCKER_AGENT == '1': os_name = AgentConstants.DA_OPERATING_SYSTEM_NAME
        if AgentConstants.EXACT_OS: os_name = AgentConstants.EXACT_OS
        
        if os_name:
            re_obj = re.search(r'\d.*', os_name)
            os_version = os_name[re_obj.start() : ] if re_obj else "-"
        else:
            os_name = platform.platform().split('-')[0]

        SERVER_INVENTORY_DICT['server_inventory']['OS_NAME'] = os_name
        SERVER_INVENTORY_DICT['server_inventory']['OS_VERSION'] = os_version
        
    except Exception as e:
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], '*************************** Exception while collecting inventory OS *********************************')
        traceback.print_exc()
                       
def get_server_info():
    try:
        import multiprocessing
        SERVER_INVENTORY_DICT.setdefault('server_inventory',OrderedDict())
        SERVER_INVENTORY_DICT['server_inventory']['HOSTNAME']=platform.node() if AgentConstants.IS_DOCKER_AGENT != '1' else AgentConstants.HOST_NAME
        SERVER_INVENTORY_DICT['server_inventory']['FQDN']=socket.getfqdn()
        SERVER_INVENTORY_DICT['server_inventory']['KERNEL_VERSION']=platform.release()
        SERVER_INVENTORY_DICT['server_inventory']['TIME_ZONE']=time.tzname[0]
        SERVER_INVENTORY_DICT['server_inventory']['IP_ADDRESS'] = ', '.join(AgentConstants.IP_LIST) if AgentConstants.IP_LIST else AgentConstants.IP_ADDRESS
        SERVER_INVENTORY_DICT['server_inventory']['CPU_CORES'] = AgentConstants.NO_OF_CPU_CORES if AgentConstants.NO_OF_CPU_CORES else multiprocessing.cpu_count()
        SERVER_INVENTORY_DICT['server_inventory']['RAM_SIZE']=AgentConstants.RAM_SIZE
        SERVER_INVENTORY_DICT['server_inventory']['RAM_SIZE_MB']=AgentConstants.RAM_SIZE
        SERVER_INVENTORY_DICT['server_inventory']['CPU_PROCESSOR']=AgentConstants.PROCESSOR_NAME
        if AgentConstants.DOMAIN_NAME:
            SERVER_INVENTORY_DICT['server_inventory']['DOMAIN_NAME']=AgentConstants.DOMAIN_NAME
        else:
            socket_domain_name=socket.getfqdn()
            if '.' in socket_domain_name:
                SERVER_INVENTORY_DICT['server_inventory']['DOMAIN_NAME'] = socket_domain_name.split('.', 1)[1]
    except Exception as e:
        traceback.print_exc()
        
def get_server_network_interfaces():
    try:
        SERVER_INVENTORY_DICT.setdefault('server_network_interface',[])
        interface_list = AgentConstants.NETWORKS_LIST
        SERVER_INVENTORY_DICT['server_network_interface']=interface_list
    except Exception as e:
        traceback.print_exc()

def upload_server_inventory():
    dict_requestParameters = {}
    requestInfo = com.manageengine.monagent.communication.CommunicationHandler.RequestInfo()
    try:
        dict_requestParameters['agentKey'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        dict_requestParameters['CUSTOMERID'] = AgentConstants.CUSTOMER_ID
        dict_requestParameters['bno'] = AgentConstants.AGENT_VERSION
        SERVER_INVENTORY_DICT['collection_time'] = SERVER_INVENTORY_CT
        AgentLogger.log(AgentLogger.STDOUT, 'uploading server inventory =======> {0}'.format(json.dumps(SERVER_INVENTORY_DICT)))
        str_servlet = AgentConstants.INVENTORY_SERVLET
        if not dict_requestParameters == None:
            str_requestParameters = urlencode(dict_requestParameters)
            str_url = str_servlet + str_requestParameters
        str_dataToSend = json.dumps(SERVER_INVENTORY_DICT)
        str_contentType = 'application/json'
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.set_data(str_dataToSend)
        requestInfo.set_dataType(str_contentType)
        requestInfo.add_header("Content-Type", str_contentType)
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = com.manageengine.monagent.communication.CommunicationHandler.sendRequest(requestInfo)
        com.manageengine.monagent.communication.CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'SERVER_INVENTORY')
    except Exception as e:
        AgentLogger.log([AgentLogger.PLUGINS, AgentLogger.STDERR], ' *************************** Exception while uploading server inventory  *************************** ' + repr(e))
        traceback.print_exc()


def stop_inventory():
    try:
        scheduleInfo = AgentScheduler.ScheduleInfo()
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName('server_inventory')
        AgentScheduler.deleteSchedule(scheduleInfo)
        update_monitor_config_file('server_inventory','stop')
    except Exception as e:
        traceback.print_exc()
        
def start_inventory():
    try:
        update_monitor_config_file('server_inventory','start')
        task = inventory_data_collector
        scheduleInfo = AgentScheduler.ScheduleInfo()
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName('server_inventory')
        scheduleInfo.setTime(time.time()+180)
        scheduleInfo.setTask(task)
        scheduleInfo.setIsPeriodic(True)
        scheduleInfo.setInterval(AgentConstants.INVENTORY_EXECUTE_INTERVAL)
        scheduleInfo.setLogger(AgentLogger.STDOUT)
        AgentScheduler.schedule(scheduleInfo)
    except Exception as e:
        traceback.print_exc()

def update_monitor_config_file(config_key,action):
    #AgentLogger.log(AgentLogger.COLLECTOR,'stopping scheduler for inventory \n')
    try:
        fileObj = AgentUtil.FileObject()
        fileObj.set_filePath(AgentConstants.AGENT_MONITORS_GROUP_FILE)
        fileObj.set_dataType('json')
        fileObj.set_mode('rb')
        fileObj.set_dataEncoding('UTF-8')
        fileObj.set_loggerName(AgentLogger.COLLECTOR)
        fileObj.set_logging(False)
        bool_toReturn, dictCustomMonitors = FileUtil.readData(fileObj)
        if action=='start':
            dictCustomMonitors['MonitorGroup']['server_inventory'].pop('Schedule')
        else:
            dictCustomMonitors['MonitorGroup']['server_inventory']['Schedule']='false'
        fileObj.set_data(dictCustomMonitors)
        fileObj.set_mode('wb')
        bool_toReturn, str_filePath = FileUtil.saveData(fileObj)
        AgentLogger.log(AgentLogger.COLLECTOR,' updated monitoring configuration -- '+json.dumps(dictCustomMonitors)+'\n')
    except Exception as e:
        AgentLogger.log(AgentLogger.STDERR,' ************************** Exception while changing monitoring interval **************************** ')
        traceback.print_exc()
