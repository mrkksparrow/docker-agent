'''
Created on 22-Jan-2018

@author: giri
'''
#python packages
from __future__ import division
import shlex
import traceback
import json
import copy
import os
import time
#s24x7 packages
from com.manageengine.monagent.docker_agent.collector import Metrics
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.framework.suite.helper import s247_commandexecutor
from com.manageengine.monagent.framework.suite.helper import handle_counter_values
from com.manageengine.monagent.docker_agent import constants as da_constants
import platform
    
class System(Metrics):        
    PREV_COUNTER_DICT = {"Utime":0 , "IdleTime":0}
    
    @staticmethod
    def get_cpucore_count():
        return AgentConstants.DOCKER_PSUTIL.cpu_count()
    
    @staticmethod
    def get_boottime():
        return AgentConstants.DOCKER_PSUTIL.boot_time()
    
    @staticmethod
    def get_processorname():
        if AgentConstants.OS_NAME == AgentConstants.SUN_OS.lower():
            command = "isalist"
        else:
            command = da_constants.DA_PROCESSORNAME_COMMAND
        with s247_commandexecutor(command, env=da_constants.ENV_DICT) as op:
            _output, _returncode, _errormsg, _outputtype = op
        return _output.strip("\n").strip()
        
    @staticmethod
    def get_system_uuid():
        command = "cat /host/sys/class/dmi/id/product_uuid"
        command = shlex.split(command)
        with s247_commandexecutor(command) as op:
            _output, _returncode, _errormsg, _outputtype = op
        return _output
    
    def handle_no_of_cores(self):
        self.result_dict["Number Of Cores"]["Number Of Cores"] = [{"NumberOfCores":str(System.get_cpucore_count())}]
    
    def handle_os_arch(self):
        self.result_dict["OS Architecture"]["OS Architecture"] = [{"OSArchitecture":AgentConstants.DA_OS_ARCHITECTURE}]
    
    def handle_system_uptime(self):
        if AgentConstants.OS_NAME == AgentConstants.SUN_OS.lower():
            _output = str(time.time()-System.get_boottime())+" "+str(AgentConstants.DOCKER_PSUTIL.cpu_times(percpu=False).idle/1000)
        else:
            with s247_commandexecutor(da_constants.DA_SYSTEMUPTIME_COMMAND, env={"PROC_FOLDER":AgentConstants.PROCFS_PATH}) as op:
                _output, _returncode, _errormsg, _outputtype = op
        self.result_dict["System Uptime"]["System Uptime"][0]["Utime"] = _output.split(" ")[0].strip()
        self.result_dict["System Uptime"]["System Uptime"][0]["ActualUtime"] = _output.split(" ")[0].strip()
        self.result_dict["System Uptime"]["System Uptime"][0]["IdleTime"] = _output.split(" ")[1].strip()
        handle_counter_values(self.result_dict["System Uptime"]["System Uptime"][0], System.PREV_COUNTER_DICT)
    
    def handle_system_loadavg(self):
        if AgentConstants.OS_NAME == AgentConstants.SUN_OS.lower():
            output_list = list(os.getloadavg())
            output_list = [str(round(val, 2)) for val in output_list]
            output_list.append("3/2")
        else:
            with s247_commandexecutor(da_constants.DA_SYSTEMSTATS_COMMAND, env=da_constants.ENV_DICT) as op:
                _output, _returncode, _errormsg, _outputtype = op
            output_list = _output.split(" ")

        self.result_dict["System Stats"]["System Stats"][0]["Last 1 min Avg"] = output_list[0]
        self.result_dict["System Stats"]["System Stats"][0]["Last 5 min Avg"] = output_list[1]
        self.result_dict["System Stats"]["System Stats"][0]["Last 15 min Avg"] = output_list[2]
        self.result_dict["System Stats"]["System Stats"][0]["Process Count"] = output_list[3]
    
    def handle_processqueue_data(self):
        if AgentConstants.OS_NAME == AgentConstants.SUN_OS.lower():
            command = "/usr/bin/vmstat 1 3"
        else:
            command = da_constants.DA_PROCESSQUEUE_COMMAND
        with s247_commandexecutor(command, env=da_constants.ENV_DICT) as op:
                _output, _returncode, _errormsg, _outputtype = op
        output_lines = _output.split("\n")
    
        if len(output_lines) >= 2:
            self.result_dict["Process Queue"]["Process Queue"][0]["Procs Running"] = output_lines[0].strip().split(" ")[1] if AgentConstants.OS_NAME != AgentConstants.SUN_OS.lower() else output_lines[3].strip().split(" ")[0]  
            self.result_dict["Process Queue"]["Process Queue"][0]["Procs Blocked"] = output_lines[1].strip().split(" ")[1] if AgentConstants.OS_NAME != AgentConstants.SUN_OS.lower() else output_lines[3].strip().split(" ")[1]
            
    def construct(self):
        self.handle_no_of_cores()
        self.handle_os_arch()
        self.handle_system_uptime()
        self.handle_system_loadavg()
        self.handle_processqueue_data()
        
    def collect(self):
        self.construct()
        self.parse(self.final_dict)
        self.handle_extra_data()
    
    def handle_extra_data(self):
        self.final_dict["systemstats"]["cr"] = self.final_dict["systemstats"]["cr"].split("/")[0]
        self.final_dict["systemstats"]["it"] = int(float(self.result_dict["System Uptime"]["System Uptime"][0]["IdleTime"])/System.get_cpucore_count())
        self.final_dict["systemstats"]["bt"] = int(float(self.result_dict["System Uptime"]["System Uptime"][0]["Utime"]) - self.final_dict["systemstats"]["it"])
        self.final_dict['systemstats']['utt'] = AgentUtil.timeConversion(int(float(self.result_dict["System Uptime"]["System Uptime"][0]["ActualUtime"]))*1000)
        #self.final_dict["systemstats"]["lc"] = len(AgentConstants.DOCKER_PSUTIL.users())
        self.final_dict["asset"]["core"] = str(System.get_cpucore_count())
        self.final_dict["asset"]["cpu"] = System.get_processorname()
        self.final_dict["asset"]["instance"] = "SERVER"
        self.final_dict["asset"]["arch"] = self.result_dict["OS Architecture"]["OS Architecture"][0]["OSArchitecture"] if not platform.system().lower().startswith("sun") else platform.architecture()[0]
        self.final_dict["asset"]["ip"] = AgentConstants.IP_ADDRESS
        self.final_dict["asset"]["os"] = AgentConstants.DA_OPERATING_SYSTEM_NAME if not platform.system().lower().startswith("sun") else platform.system()
        self.final_dict["asset"]["hostname"] = AgentConstants.HOST_FQDN_NAME