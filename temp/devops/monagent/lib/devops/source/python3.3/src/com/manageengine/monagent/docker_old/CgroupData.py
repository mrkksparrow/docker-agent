#$Id$
'''
Created on Feb 17, 2015

@author: root
'''

import json
import os
import re

from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.docker_old import DockUtils

class BlkioGroup :
    
    def _getBlkioStat(self, path):
        blkioStats =[]
        f = None
        
        try :
            if not os.path.isfile(path) :
                AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "File does not exist: {0}".format(path))
                return blkioStats
            f = open(path, "r")
            for line in f:
                fields = re.split('\\:|\\ ', line)
                if len(fields) < 3 :
                    if len(fields) == 2 and fields[0] == "Total" :
                        #skip total line
                        continue
                    else:
                        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Invalid line found while parsing {0}: {1}".format(path, line))
                        return blkioStats
                    
                major = int(fields[0])
                minor = int(fields[1])
                op = ""
                valueField = 2
                if len(fields) == 4 :
                    op = fields[2]
                    valueField = 3
                v = int(fields[valueField])
                blkioStats.append({"major": major, "minor": minor, "op": op, "value": v})
        except IOError as ie:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Unable to open file  {0}".format(ie))
        except LookupError as le:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Accessing invalid index {0}".format(le))
        except EOFError as ee:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "EOF Error occurred {0}".format(ee))
        except TypeError as te:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Invalid operation {0}".format(te))
        except ValueError as ve:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Inappropriate value {0}".format(ve))
        except OSError as oe:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "There is some error in system operation {0}".format(oe))
        finally:
            if f:
                f.close()      
        return blkioStats
       


    def _getCFQStats(self, path, stats ):
        stats["sectors_recursive"] = self._getBlkioStat(os.path.join(path, "blkio.sectors_recursive"))
        stats["io_service_bytes_recursive"] = self._getBlkioStat(os.path.join(path, "blkio.io_service_bytes_recursive"))
        stats["io_serviced_recursive"] = self._getBlkioStat(os.path.join(path, "blkio.io_serviced_recursive"))
        stats["io_queue_recursive"] = self._getBlkioStat(os.path.join(path, "blkio.io_queued_recursive"))
        stats["io_service_time_recursive"] = self._getBlkioStat(os.path.join(path, "blkio.io_service_time_recursive"))
        stats["io_wait_time_recursive"] = self._getBlkioStat(os.path.join(path, "blkio.io_wait_time_recursive"))
        stats["io_merged_recursive"] = self._getBlkioStat(os.path.join(path, "blkio.io_merged_recursive"))
        stats["io_time_recursive"] = self._getBlkioStat(os.path.join(path, "blkio.time_recursive"))
      

    def _getBlkioStats(self, path, stats):
        stats["io_service_bytes_recursive"] = self._getBlkioStat(os.path.join(path, "blkio.throttle.io_service_bytes"))
        stats["io_serviced_recursive"] = self._getBlkioStat(os.path.join(path, "blkio.throttle.io_serviced"))
       
    

    def getBlkioStats(self, path):
        stats={
               "sectors_recursive" :[], 
               "io_service_bytes_recursive" : [],
               "io_serviced_recursive" : [],
               "io_queue_recursive" : [],
               "io_service_time_recursive" : [],
               "io_wait_time_recursive" : [],
               "io_merged_recursive" : [],
               "io_time_recursive" : []
        }
        blkioStats = self._getBlkioStat(os.path.join(path, "blkio.io_serviced_recursive"))
        if len(blkioStats) != 0:
            self._getCFQStats(path, stats)
        else:
            self._getBlkioStats(path, stats)
        return stats
        
        
                       
class MemoryGroup:
    
      
    def getMemoryStats(self, path):
        #Set stats from memory.stat.
        stats = {"stats"  : {}, "usage" : 0, "max_usage" : 0, "failcnt" : 0, "limit" :0}
        f = None
        try :
            absPath = os.path.join(path, "memory.stat")
            if not os.path.isfile(absPath) :
                AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "File does not exist: {0}".format(absPath))
                return
            f = open(absPath)
            for line in f:
                fields = line.split()
                if len(fields) == 2:
                    stats["stats"][fields[0]] = int(fields[1])
            
            # Set memory usage and max historical usage.
            stats["usage"] = DockUtils.getFileContent(path, "memory.usage_in_bytes")
            stats["max_usage"] = DockUtils.getFileContent(path, "memory.max_usage_in_bytes")
            stats["failcnt"] = DockUtils.getFileContent(path, "memory.failcnt")
            stats["limit"] = DockUtils.getTotalMemoryLimit()
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Exception in memory data collection : {0}".format(e))
        finally:
            if f:
                f.close()
                
        return stats
    
    


    
class CpuacctGroup:
    
    def _getCpuUsageBreakdown(self, cgroupPath, fileName) :
        nanosecondsInSecond = 1000000000
        clockTicks = DockUtils.getClockTicks()
        userModeUsage = 0
        kernelModeUsage = 0
        f = None
        try :
            absPath = os.path.join(cgroupPath, fileName)
            if not os.path.isfile(absPath) :
                AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "File does not exist: {0}".format(absPath))
                return (0, 0)
            f = open(absPath)
            for line in f:
                fields = line.split()
                if len(fields) == 2:
                    if fields[0] == "system" :
                        kernelModeUsage = int(fields[1].strip())
                    elif fields[0] == "user" :
                        userModeUsage = int(fields[1].strip())
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Exception in cpu acc data collection : {0}".format(e))
        finally:
            if f:
                f.close()
        return ( int((userModeUsage * nanosecondsInSecond) / clockTicks), int((kernelModeUsage * nanosecondsInSecond) / clockTicks))


    def _getPercpuUsage(self, cgroupPath, fileName) :
        percpuUsage = []
        f = None
        try :
            absPath = os.path.join(cgroupPath, fileName)
            if not os.path.isfile(absPath) :
                AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "File does not exist: {0}".format(absPath))
                return []
            f = open(absPath)
            for line in f:
                fields = line.split()
                for field in fields:
                    percpuUsage.append(int(field.strip()))
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Exception in Per cpu uses data collection : {0}".format(e))
        finally:
            if f:
                f.close()           
        return percpuUsage
    
    def _getCpuacctStats(self, cgroupPath):
        stats = {}
        (userModeUsage, kernelModeUsage) = self._getCpuUsageBreakdown(cgroupPath, "cpuacct.stat")
        totalUsage = DockUtils.getFileContent(cgroupPath,"cpuacct.usage")
        percpuUsage = self._getPercpuUsage(cgroupPath, "cpuacct.usage_percpu")
        
        stats["total_usage"] = totalUsage
        stats["percpu_usage"] = percpuUsage
        stats["usage_in_kernelmode"] = kernelModeUsage
        stats["usage_in_usermode"] = userModeUsage
        return stats


class CpuGroup:
    
    def _getCpuStat(self, cgroupPath):
        stats = {"periods" : 0, "throttled_periods" : 0, "throttled_time" : 0}
        f = None
        try :
            absPath = os.path.join(cgroupPath, "cpu.stat")
            if not os.path.isfile(absPath) :
                AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "File does not exist: {0}".format(absPath))
                return (0, 0)
            f = open(absPath)
            for line in f:
                fields = line.split()
                if len(fields) == 2:
                    if fields[0] == "nr_periods" :
                        stats["periods"] = int(fields[1].strip())
                    elif fields[0] == "nr_throttled" :
                        stats["throttled_periods"] = int(fields[1].strip())  
                    elif fields[0] == "throttled_time" :
                        stats["throttled_time"] = int(fields[1].strip())
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Exception in cpu acc data collection : {0}".format(e))
        finally:
            if f:
                f.close()
        return stats



class CpuStats(CpuacctGroup, CpuGroup):
    def __init__(self, cpu_cgroup, cpuacct_cgroup):
        self.cpu_cgroup = cpu_cgroup
        self.cpuacct_cgroup = cpuacct_cgroup
        
    def _getSystemCpuUsage(self):
        nanosecondsInSecond = 1000000000
        clockTicks = DockUtils.getClockTicks()
        path = "/proc/stat"
        totalCpuUses = 0
        f = None
        try :
            if not os.path.isfile(path) :
                AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "File does not exist: {0}".format(path))
                return 0
            f = open(path)
            for line in f:
                fields = line.split()
                if len(fields) < 1:
                    continue;
                if fields[0] == "cpu":
                    if len(fields) < 8:
                        AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "invalid number of cpu fields")
                        return 0
                    
                    for field in fields[1:8]:
                        totalCpuUses += int(field.strip())
                    break;
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Exception in system cpu data collection : {0}".format(e))
        finally:
            if f:
                f.close()
        return (totalCpuUses * nanosecondsInSecond) / clockTicks

    
    def getCpuStats(self):
        stats = {
                 "cpu_usage": self._getCpuacctStats(self.cpuacct_cgroup),
                 "system_cpu_usage" : self._getSystemCpuUsage(),
                 "throttling_data" : self._getCpuStat(self.cpu_cgroup)
                 }
        return stats
    
    
class NetworkGroup:
    def _readSysfsNetworkStats(self, ethInterface, statsFile ):
        fullPath = os.path.join("/sys/class/net", ethInterface, "statistics")
        return DockUtils.getFileContent(fullPath, statsFile)
        
    def _getVethInterface(self, contId):
        fullPath = "/var/lib/docker/execdriver/native/{0}/state.json".format(contId)
        try :
            if not os.path.isfile(fullPath) :
                AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "{0} : File does not exist: Please upgrade ur docker docker".format(fullPath))
                return ""
            with open(fullPath, 'r') as file:
                data = file.read()
            if data:
                objData = json.loads(data)
                if "network_state" in objData :
                    if "veth_host" in objData["network_state"]:
                        return objData["network_state"]["veth_host"]
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " + "Exception in veth searching: {0}".format(e))
        return ""
    
    def getNetworkState(self, contId):
        stats = {}
        netStats = ["tx_bytes", "tx_packets", "tx_errors", "tx_dropped", "rx_bytes", "rx_packets", "rx_errors", "rx_dropped"]
        ethInterface = self._getVethInterface(contId)
        if ethInterface == "" :
            return { "rx_packets": 0, "tx_bytes": 0, "rx_errors": 0, "rx_dropped": 0, "tx_dropped": 0,  "rx_bytes": 0, "tx_errors": 0, "tx_packets": 0 }
        for file in netStats :
            stats[file] = self._readSysfsNetworkStats(ethInterface, file)
        return stats
    
    
    
CGROUP_MATRIX = ['memory', 'cpuacct','cpu','blkio']
DOCKER_ROOT = "/"
 
class CgroupDataCollection:

    def __init__(self):
        self._mount_points = {}
        self._cgroup_file_path_pattern = ""
        self._initialize()
        
    
    def _initialize(self):
             
        self._initializeMountPoints()
        self._initFilePathPattern()
    
    
    def _initializeMountPoints(self):
        ''' Initialize cgroups mount point for performance matrix collection'''
        
        try :
            global CGROUP_MATRIX
            for cgroup in CGROUP_MATRIX :
                self._mount_points[cgroup] = self._getMountPoints(cgroup)
        except Exception as e :
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Unable to initialize mount points Exception: {0}".format(e))


    def _getMountPoints(self, group_name):
        '''Return the mount point for specific cgroup'''
        
        global DOCKER_ROOT
        fp = None
        try:
            fp = open(os.path.join(DOCKER_ROOT, '/proc/mounts'))       
            
            mounts = map(lambda x : x.split(), fp.read().splitlines())  # form map from the data available in /proc/mount 
            cgroup_mounts = list(filter(lambda x : x[2] == 'cgroup', mounts))  # form a list from the map for cgroups
            
            if len(cgroup_mounts) == 0 :
                AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  'Unabale to find the mount point for the {0}'.format(group_name))
            if len(cgroup_mounts) == 1 :                                   
                return os.path.join(DOCKER_ROOT, cgroup_mounts[0][1])
            for _, mount_point, _, desc, _, _ in cgroup_mounts :               
                if desc.endswith(group_name) :  # find mount point the specified description
                    return os.path.join(DOCKER_ROOT, mount_point)
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Exception in finding mountPoints :{0}".format(e))
        finally:
            if fp :
                fp.close()
        return None


    def _initFilePathPattern(self):
        '''Update the cgroup path pattern according to type of containers'''

        try :
            if self._mount_points :
                for mount_point in self._mount_points.values():
                    if mount_point == None:
                        continue
                    if os.path.exists(os.path.join(mount_point, "lxc")): # path exit or not
                        self._cgroup_file_path_pattern = '{mountpoint}/lxc/{id}'
                        break
                    elif os.path.exists(os.path.join(mount_point, "docker")):
                        self._cgroup_file_path_pattern = '{mountpoint}/docker/{id}'
                        break
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Unable to initialize path pattern, Exception: {0} ".format(e)) 
    

    def _buildFilePath(self, cgroup, cont_id):
        ''' build the file path for the specific cgroup file'''
        
        try :
            if not self._cgroup_file_path_pattern:
                self._cgroup_file_path_pattern = self._initFilePathPattern()
                if self._cgroup_file_path_pattern == None :
                    AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Error in building file path for file ")
                    return None
                
            if self._mount_points[cgroup] :
                return self._cgroup_file_path_pattern.format(mountpoint=self._mount_points[cgroup],
                                                      id=cont_id)
            else :
                return None    
        except Exception as e:
            AgentLogger.log(AgentLogger.COLLECTOR, "DOCKER_LOG: " +  "Error in building absolute file path  Exception : {0}".format( e))
    
    
    def getContPerfData(self, contId):
        
        stats = {}
        stats["network"] = NetworkGroup().getNetworkState(contId)
        cpuStat = CpuStats(self._buildFilePath('cpu', contId), self._buildFilePath('cpuacct', contId))
        stats["cpu_stats"] = cpuStat.getCpuStats()
        stats['memory_stats'] = MemoryGroup().getMemoryStats(self._buildFilePath('memory', contId))
        stats['blkio_stats'] = BlkioGroup().getBlkioStats(self._buildFilePath('blkio', contId))
    
        return stats

