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

class Memory(Metrics):
    
    PREV_COUNTER_HOLDER = {"PagesInputPersec": 0, "PagesOutputPersec": 0, "PageFaultsPersec":0}
    
    def handle_mem_util(self):
        self.virtual_memory = AgentConstants.DOCKER_PSUTIL.virtual_memory()
        self.swap_memory = AgentConstants.DOCKER_PSUTIL.swap_memory()
        self.result_dict["Memory Utilization"]["Memory Utilization"][0]["TotalVisibleMemorySize"] = str(round(self.virtual_memory.total/(1024*1024), 2))
        self.result_dict["Memory Utilization"]["Memory Utilization"][0]["FreePhysicalMemory"] = str(round(self.virtual_memory.available/(1024*1024)))
        self.result_dict["Memory Utilization"]["Memory Utilization"][0]["TotalVirtualMemorySize"] = str(round(self.swap_memory.total/(1024*1024)))
        self.result_dict["Memory Utilization"]["Memory Utilization"][0]["FreeVirtualMemory"] = str(round(self.swap_memory.free/(1024*1024)))
        self.result_dict["Memory Utilization"]["Memory Utilization"][0]["Caption"] = "Ubuntu 16.04.3 LTS"
        self.result_dict["Memory Utilization"]["Memory Utilization"][0]["FreePhyPercent"] = str(round(100-self.virtual_memory.percent, 2))
        self.result_dict["Memory Utilization"]["Memory Utilization"][0]["FreeVirtPercent"] = str(round(100-self.swap_memory.percent, 2))
    
    def handle_mem_stats(self):
        if AgentConstants.IS_DOCKER_AGENT == "1" and AgentConstants.OS_NAME == AgentConstants.LINUX_OS:
            with s247_commandexecutor("{} {}".format(AgentConstants.DOCKER_SCRIPT_PATH, "mem_stats"), env=da_constants.ENV_DICT) as op:
                _output, _returncode, _errormsg, _outputtype = op
        elif AgentConstants.OS_NAME == AgentConstants.SUN_OS.lower():
            with s247_commandexecutor("/usr/bin/vmstat 1 3") as op:
                _output, _returncode, _errormsg, _outputtype = op
        if "\n" in _output:
            output_list = _output.split("\n")
            filtered_list = filter(lambda line : line.split(" ")[0].strip() in ["pgpgin", "pgpgout", "pgfault"], output_list)
        key_map = {"pgpgin" : "PagesInputPersec", "pgpgout" : "PagesOutputPersec", "pgfault" : "PageFaultsPersec"}
        for line in filtered_list:
            dict_key = key_map.get(line.split(" ")[0], None)
            if dict_key:
                self.result_dict["Memory Statistics"]["Memory Statistics"][0][dict_key] = str(line.split(" ")[1])
        handle_counter_values(self.result_dict["Memory Statistics"]["Memory Statistics"][0], Memory.PREV_COUNTER_HOLDER)
        for key, value in self.result_dict["Memory Statistics"]["Memory Statistics"][0].items():
            if key in list(Memory.PREV_COUNTER_HOLDER.keys()):
                self.result_dict["Memory Statistics"]["Memory Statistics"][0][key] = int(float(value)/AgentConstants.MONITORING_INTERVAL)

    def construct(self):
        self.handle_mem_util()
        self.handle_mem_stats()
    
    def collect(self):
        self.construct()
        self.parse(self.final_dict)
        self.handle_extra_data()
        
    def handle_extra_data(self):
        self.final_dict["memory"]["uvism"] = int(self.final_dict["memory"]["tvism"]) - int(self.final_dict["memory"]["fvism"])
        self.final_dict["memory"]["uvirm"] = int(self.final_dict["memory"]["tvirm"]) - int(self.final_dict["memory"]["fvirm"])
        try:
            self.final_dict['memory']['swpmemper'] = ((self.final_dict["memory"]["tvirm"] - self.final_dict["memory"]["fvirm"])/self.final_dict["memory"]["tvirm"])*100
        except Exception as e:
            self.final_dict['memory']['swpmemper'] = 0
        try:
            self.final_dict['mper'] = str(round((((self.final_dict["memory"]["tvism"] - self.final_dict["memory"]["fvism"])/self.final_dict["memory"]["tvism"])*100),2))
        except Exception as e:
            self.final_dict['mper'] = "0"