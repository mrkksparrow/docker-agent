#$Id$
'''
Created on Feb 17, 2015

@author: root
'''

import os
import json
try:
    from distutils.version import StrictVersion
except Exception:
    pass
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent import AgentConstants 
import traceback

DOCKER_DEFAULT_BASE_URL = "unix://var/run/docker.sock"
DEFAULT_CONTAINER_COLLECTION_SIZE = 100


def updateAllowedContainer(size):
    '''
    This function will retrieve docker conf file in dictionary 
    
    and add the allowed container and save it again.
    '''
    
    dict_data = {}
    bool_status = False
    if os.path.isfile(AgentConstants.AGENT_DOCKER_CONF_FILE) :
        bool_status, dict_data = AgentUtil.loadDataFromFile(AgentConstants.AGENT_DOCKER_CONF_FILE)
    if not bool_status:
        dict_data = {}
    
    dict_data["allowed"] = size
    AgentUtil.writeDataToFile(AgentConstants.AGENT_DOCKER_CONF_FILE, dict_data)
    
    
def getAllowedContainerSize():
    ''' This function will retrieve the allowed container collection size.
    
    if it wouldn't get the data from conf file the it will return default value
    '''
     
    allowed_contaner_size = DEFAULT_CONTAINER_COLLECTION_SIZE
    bool_status = False
    if os.path.isfile(AgentConstants.AGENT_DOCKER_CONF_FILE) :
        bool_status, dict_data = AgentUtil.loadDataFromFile(AgentConstants.AGENT_DOCKER_CONF_FILE)
    if bool_status :
        if "allowed" in dict_data :
            allowed_contaner_size = dict_data["allowed"]
    return allowed_contaner_size


def getSite24X7IdDict(str_IdType):
    bool_FileLoaded = False
    try :
        if os.path.isfile(AgentConstants.AGENT_DOCKER_SITE24X7ID):
            bool_FileLoaded, str_TempIdDict =  AgentUtil.loadDataFromFile(AgentConstants.AGENT_DOCKER_SITE24X7ID)
        if bool_FileLoaded :
            dict_TempIdDict = json.loads(str_TempIdDict)
            if dict_TempIdDict and str_IdType in dict_TempIdDict :
                return dict_TempIdDict[str_IdType];
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Exception in gettigng site 24x7 id : {0}".format(e));
    return None

def updateSite24X7Ids(dict_Site24X7Id):
    ''' Function will update site24X7 id in the site247id file '''
    AgentLogger.log(AgentLogger.COLLECTOR, "arunagiri aaa")
    AgentLogger.log(AgentLogger.COLLECTOR, "GIRI_LOG id {}".format(str(type(dict_Site24X7Id)))+";;;;;;"+str(dict_Site24X7Id))
    bool_FileSavesd = AgentUtil.writeDataToFile(AgentConstants.AGENT_DOCKER_SITE24X7ID, dict_Site24X7Id);
    if(not bool_FileSavesd):
        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG" + "Unable to update id file")
        
def addSite24X7Ids(str_Id, dict_Data, dict_TempIdDict):
    try :
        if dict_TempIdDict is not None :
            if str_Id not in dict_TempIdDict:
                dict_Data["cid"] = -1  
            else :
                dict_Data["cid"] = dict_TempIdDict[str_Id]
                #del dict_TempIdDict[str_Id]
        else:
            dict_Data["cid"] = -1 
    except Exception as e :
        AgentLogger.log([AgentLogger.COLLECTOR,AgentLogger.STDERR], "DOCKER_LOG: " +  "Exception in add site id : "+repr(e))
        traceback.print_exc()
def _updateBlkioStats(stats):
    if stats and isinstance(stats, list):
        for elementDict in stats:
            if "value" in elementDict:
                elementDict["value"] = str(elementDict["value"] / 1048576)
        

def updateBlkioStats(blkioStats):
    stats = ["sectors_recursive", 
             "io_service_bytes_recursive",
             "io_serviced_recursive",
             "io_queue_recursive",
             "io_service_time_recursive",
             "io_wait_time_recursive",
             "io_merged_recursive",
             "io_time_recursive"
            ]
    if blkioStats:
        for key in stats :
            if key in blkioStats:
                _updateBlkioStats(blkioStats[key])
                
            
def updateNetworkStats(networkStats):
    if "rx_bytes" in networkStats and "tx_bytes" in networkStats :
        networkStats["traffic"] = str((networkStats["rx_bytes"] + networkStats["tx_bytes"] ) / 1024)
        
    if "rx_bytes" in networkStats:
        networkStats["rx_bytes"] = str(networkStats["rx_bytes"] / 1024)
    if "tx_bytes" in networkStats:
        networkStats["tx_bytes"] = str(networkStats["tx_bytes"] / 1024)


def updateLatestNetworkStats(networkLatestStats):
    networkStats={}
    networkStats["rx_bytes_num"]=0
    networkStats["tx_bytes_num"]=0
    try:
        for eachNetwork,eachNetworkVal in networkLatestStats.items():
            if "rx_bytes" in eachNetworkVal:
                networkStats["rx_bytes_num"]=networkStats["rx_bytes_num"]+eachNetworkVal["rx_bytes"]
            if "tx_bytes" in eachNetworkVal:
                networkStats["tx_bytes_num"]=networkStats["tx_bytes_num"]+eachNetworkVal['tx_bytes']
        if "rx_bytes_num" in networkStats and "tx_bytes_num" in networkStats :
            networkStats["traffic"]= str((networkStats["rx_bytes_num"] + networkStats["tx_bytes_num"])/1024)
        networkStats["rx_bytes"]=str(networkStats["rx_bytes_num"]/1024)
        networkStats["tx_bytes"]=str(networkStats["tx_bytes_num"]/1024)
    except Exception as e:
        traceback.print_exc()
    return networkStats

def updateMemoryStats(memoryStats):
    if "stats" in memoryStats:
        stats = memoryStats["stats"]
        if "active_anon" in stats:
            stats["active_anon"] = str(stats["active_anon"] / 1048576)
        if "inactive_anon" in stats:
            stats["inactive_anon"] = str(stats["inactive_anon"] / 1048576)
        if "active_file" in stats:
            stats["active_file"] = str(stats["active_file"] / 1048576)
        if "inactive_file" in stats:
            stats["inactive_file"] = str(stats["inactive_file"] / 1048576)
        if "cache" in stats:
            stats["cache"] = str(stats["cache"] / 1048576)
        if "rss" in stats:
            stats["rss"] = str(stats["rss"] / 1048576)
        if "unevictable" in stats:
            stats["unevictable"] = str(stats["unevictable"] / 1048576)
        
def calculateMemoryPercentage(dictMemory):
    memoryPercent = 0.0
    try :
        if "usage" in dictMemory and "limit" in dictMemory:
            memoryPercent = (dictMemory["usage"] / dictMemory["limit"] ) * 100
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG" + "Error in Memory percentage calculation : {0}".format(e))
    return memoryPercent

def calcuateCpuPercent(previousCpu, previousSystem, v ):
    cpuPercent = 0.0
    if "cpu_usage" in v and "system_cpu_usage" in v and "total_usage" in v["cpu_usage"] and "percpu_usage" in v["cpu_usage"]:
        #calculate the change for the cpu usage of the container in between readings
        cpuDelta = v["cpu_usage"]["total_usage"] - previousCpu
        #calculate the change for the entire system between readings
        systemDelta = v["system_cpu_usage"] - previousSystem
    
        if systemDelta > 0.0 and cpuDelta > 0.0 :
            cpuPercent = (cpuDelta / systemDelta) * len(v["cpu_usage"]["percpu_usage"]) * 100.0

    return cpuPercent


def getTotalMemoryLimit():
    # take as default value
    memoryTotal = 8326963200
    path = "/proc/meminfo"
    f = None
    try :
        if not os.path.isfile(path) :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "File does not exist: {0}".format(path))
            return 0
        f = open(path)
        for line in f:
            fields = line.split()
            if len(fields) < 3 or fields[2] != "kB":
                continue
            if fields[0] == "MemTotal:" :
                memoryTotal = int(fields[1].strip()) * 1024
                break;
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR, "Exception in total memory limit collection  : {0}".format(e))
    finally:
        if f:
            f.close()
    return memoryTotal



def getFileContents(cgroupPath, file):
    f = None
    try :
        absPath = os.path.join(cgroupPath, file)
        if not os.path.isfile(absPath) :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "File does not exist: {0}".format(absPath))
            return None
        f = open(absPath, "r")
        for line in f:
            #yield line
            pass
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "File read error: {0} : {1}".format(absPath, e))
    finally:
        if f:
            f.close()    
def getFileContent(cgroupPath, file):
    
    try :
        absPath = os.path.join(cgroupPath, file)
        if not os.path.isfile(absPath) :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "File does not exist: {0}".format(absPath))
            return 0
        with open(absPath, 'r') as content_file:
            content = content_file.read()
        if content != "":
            return int(content.strip())
    except Exception :
        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Exception in file read {0}".format(absPath))
    
    return 0

def compare_version(v1, v2):
    """Compare docker versions

    v1 = '1.9'
    v2 = '1.10'
    compare_version(v1, v2)
    1
    compare_version(v2, v1)
    -1
    compare_version(v2, v2)
    0
    """
    s1 = StrictVersion(v1)
    s2 = StrictVersion(v2)
    if s1 == s2:
        return 0
    elif s1 > s2:
        return -1
    else:
        return 1

def getClockTicks():
    return 100

def excCommand(cmd):
    ''' Execute the Linux command and return output of the command as a list '''
        
    lines = [] 
    pipe = None
    try:
        pipe = os.popen(cmd, "r")  # Run any command in the Linux shell
        while True:
            line = pipe.readline()  # Read output Line by line
            if not line:
                break
            lines.append(line)
    except OSError as e:
        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Error in executing command {0}".format(e))
    except EOFError as ee :
        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Error in reading data from the pipe : {0}".format(ee))
    finally:
        if pipe:
            pipe.close()
    return lines


def getDockerSockets():
    ''' This function will search for the Unix socket attached to the docker and return the list of sockets'''
        
    sock_path_list = ["unix:///var/run/docker.sock"]
    try :
        command = "ps -eF | grep docker"
        
        cmd_output = excCommand(command)
        
        for line in cmd_output :
            if "unix:" not in line:
                continue
            for sock_str in line.split() :
                if "unix:" in sock_str and sock_str != sock_path_list[0]:
                    sock_path_list.append(sock_str)
            
    except OSError  as oe :
        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Error in finding docker socket{0}".format(oe))
           
    return sock_path_list


def isDockerRunning():
    running = False
    try :
        sock_path_list = getDockerSockets()
        for sock_path in sock_path_list:
            ret_val = os.system("docker -H {0} info".format(sock_path))
            if not ret_val :
                running = True
                break
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Error in getting socket status : {0}".format(e))
    return running


def runningSocket():
    try :
        sock_path_list = getDockerSockets()
        for sock_path in sock_path_list:
            ret_val = os.system("docker -H {0} info".format(sock_path))
            if not ret_val :
                return sock_path
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Error in getting socket status : {0}".format(e))
    return None


def parseUrl(url):

    global DOCKER_DEFAULT_BASE_URL
    if not url or url.strip() == "unix://" :
        return DOCKER_DEFAULT_BASE_URL

    if url.startswith("unix://"):
        url_part = url.split(":")
        if len(url_part) != 2 :
            raise DockerException("Error in docker address format")
        return "unix://" + url_part[1].strip("/")
    elif url.startswith("/"):
        return "unix://" + url.strip("/")
    else :
        raise DockerException("Error in docker socket address ")


def _portBinding(binds):
    
    res = {}
    try :
        if isinstance(binds, dict) :
            if 'HostIp' in binds :
                res['HostIp'] = binds['HostIp']
            if 'HostPort' in binds :
                res['HostPort'] = binds['HostPort']
        elif isinstance(binds, tuple) :
            if len(binds) == 2:
                res['HostIp'] = binds[0]
                res['HostPort'] = binds[1]
            elif len(binds) == 1 and isinstance(binds[0],str) :
                res['HostIp'] = binds[0]
            else :
                res['HostPort'] = binds[0]
        else :
            res['HostPort'] = binds
        
        if res['HostPort'] is None:
            res['HostPort'] = ''
        else :
            res['HostPort'] = str(res['HostPort'])
    except IndexError as ie:
        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Error in parsing port bindings : {0}".format(ie))
    return res

       
def convertPortBinds(port_bindings):
    res = {}
    try:
        for key, val in port_bindings :
            key = str(key)
            if '/' not in key :
                key = key +'/tcp'
            if isinstance(val, list):
                res[key] = [_portBinding(b) for b in val]
            else :
                res[key] = [_portBinding(val)]
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Error in processing port bindings : {0}".format(e))
    return res


def parseDevices(devices):
    device_list = []
    try:
        for device in devices :
            device_part = device.split(",")
            if device_part:
                path_on_host = device_part[0]
            if len(device_part) > 1:
                path_on_container = device_part[1]
            else :
                path_on_container = path_on_host
            if len(device_part) > 2 :
                cgroup_permission = device_part[2]
            else :
                cgroup_permission = "mrw"
            device_list.append({ "PathOnHost": path_on_host, "PathInContainer": path_on_container, "CgroupPermissions": cgroup_permission})
    except Exception as e:
        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Error in processing devices : {0}".format(e))
    return device_list

    
class DockerException(Exception):
    pass   
