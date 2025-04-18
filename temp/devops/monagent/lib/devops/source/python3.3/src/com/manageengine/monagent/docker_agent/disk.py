'''
Created on 22-Jan-2018

@author: giri
'''
#python packages
from __future__ import division
import shlex
import traceback
import json
#s24x7 packages
from com.manageengine.monagent.docker_agent.collector import Metrics
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.framework.suite.helper import s247_commandexecutor
from com.manageengine.monagent.framework.suite.helper import handle_counter_values
from com.manageengine.monagent.docker_agent import constants as da_constants
    
class Disk(Metrics):  
    
    PREV_COUNTER_HOLDER = {"DiskReadBytesPersec" : 0, "DiskWriteBytesPersec" : 0}
        
    def handle_disk_utilization(self):
        self.total_disk_space = 0
        self.total_disk_used = 0
        self.script_disk_names = []
        try:
            with s247_commandexecutor(da_constants.DA_DISK_COMMAND, env=da_constants.ENV_DICT) as op:
                _output, _returncode, _errormsg, _outputtype = op
            AgentLogger.debug(AgentLogger.DA, "Disk command output "+repr(_output))
            disk_list = _output.splitlines()
            for each_disk in disk_list:
                temp_dict = {}
                each_disk = each_disk.split(' :: ')
                disks_config = da_constants.CONFIG_DICT.get("disks", [])
                id_list = list(map(lambda x : x["id"] if x["dn"] == str(each_disk[0]) else None, disks_config))
                id_list = list(filter(lambda x : x, id_list))
                temp_dict["id"] = id_list[0] if id_list else "None"
                temp_dict["Name"] = each_disk[0]
                temp_dict["FileSystem"] = each_disk[2]
                total_space = float(each_disk[3])/(1024*1024)
                free_space = float(each_disk[4])/(1024*1024)
                used_space = total_space - free_space
                temp_dict["Size"] = total_space
                temp_dict["FreeSpace"] = free_space
                temp_dict["UsedSpace"] = used_space
                self.total_disk_space += total_space
                self.total_disk_used += used_space
                temp_dict["UsedDiskPercent"] = int(round(((used_space/total_space)*100),0))
                temp_dict["FreeDiskPercent"] = 100 - temp_dict["UsedDiskPercent"]
                self.result_dict["Disk Utilization"]["Disk Utilization"].append(temp_dict)
                self.script_disk_names.append(temp_dict["Name"])

            #psutil old flow for maintaining status quo
            self.disk_util_metrics = AgentConstants.DOCKER_PSUTIL.disk_partitions(all=False)
            for part in self.disk_util_metrics:
                if part.mountpoint in self.script_disk_names:
                    continue
                temp_dict = {}
                usage = AgentConstants.DOCKER_PSUTIL.disk_usage(part.mountpoint)
                disks_config = da_constants.CONFIG_DICT.get("disks", [])
                id_list = list(map(lambda x : x["id"] if x["dn"] == str(part.mountpoint) else None, disks_config))
                id_list = list(filter(lambda x : x, id_list))
                temp_dict["id"] = id_list[0] if id_list else "None"
                temp_dict["Name"] = str(part.mountpoint)
                temp_dict["Size"] = int(usage.total/(1024*1024))
                self.total_disk_space += temp_dict["Size"]
                temp_dict["FreeSpace"] = int(usage.free/(1024*1024))
                temp_dict["UsedSpace"] = temp_dict["Size"] - temp_dict["FreeSpace"]
                self.total_disk_used += temp_dict["UsedSpace"]
                temp_dict["UsedDiskPercent"] = int(usage.percent)
                temp_dict["FreeDiskPercent"] = 100 - temp_dict["UsedDiskPercent"]
                temp_dict["FileSystem"] = part.fstype
                self.result_dict["Disk Utilization"]["Disk Utilization"].append(temp_dict)            
        except:
            traceback.print_exc()
    
    def handle_disk_statistics(self):
        self.disk_stats_metrics = AgentConstants.DOCKER_PSUTIL.disk_io_counters()
        self.result_dict["Disk Statistics"]["Disk Statistics"][0]["Name"] = "Disk I/O bytes"
        self.result_dict["Disk Statistics"]["Disk Statistics"][0]["DiskReadBytesPersec"] = str(self.disk_stats_metrics.read_bytes)
        self.result_dict["Disk Statistics"]["Disk Statistics"][0]["DiskWriteBytesPersec"] = str(self.disk_stats_metrics.write_bytes)
        handle_counter_values(self.result_dict["Disk Statistics"]["Disk Statistics"][0], Disk.PREV_COUNTER_HOLDER)
        for key, value in self.result_dict["Disk Statistics"]["Disk Statistics"][0].items():
            if key in list(Disk.PREV_COUNTER_HOLDER.keys()):
                self.result_dict["Disk Statistics"]["Disk Statistics"][0][key] = int(value)/AgentConstants.MONITORING_INTERVAL
    
    def construct(self):
        self.handle_disk_utilization()
        self.handle_disk_statistics()
    
    def collect(self):
        self.construct()
        self.parse(self.final_dict)
        self.handle_extra_data()
        
    def handle_extra_data(self):
        '''disk stats calculation'''
        self.final_dict["dreads"] = self.result_dict["Disk Statistics"]["Disk Statistics"][0]["DiskReadBytesPersec"]
        self.final_dict["dwrites"] = self.result_dict["Disk Statistics"]["Disk Statistics"][0]["DiskWriteBytesPersec"]
        self.final_dict["diskio"] = int(self.final_dict['dreads'])+int(self.final_dict['dwrites'])
        self.final_dict["duper"] = str(int(self.total_disk_used/self.total_disk_space*100))
        self.final_dict["duper"] = '1' if self.final_dict["duper"] == '0' else self.final_dict["duper"]
        self.final_dict["dfper"] = str(100 - int(self.final_dict["duper"]))
        self.final_dict["dused"] = self.total_disk_used
        self.final_dict["dfree"] = self.total_disk_space - self.total_disk_used
        