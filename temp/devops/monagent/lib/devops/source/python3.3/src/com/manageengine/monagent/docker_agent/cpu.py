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
from com.manageengine.monagent.util import AgentUtil
    
class Cpu(Metrics):

    PREV_COUNTER_HOLDER_TEMPLATE = {"user" : "0", "nice" : "0", "system" : "0", "idle" : "0", "iowait" : "0", "irq" : "0", "softirq" : "0", "steal" : "0", "guest" : "0", "guest_nice" : "0"}
    
    PREV_COUNTER_HOLDER = {}
        
    @staticmethod
    def cpu_count():
        return AgentConstants.DOCKER_PSUTIL.cpu_count()
    
    def handle_cpu_monitoring(self, curr, vcpu, percore, name=None):
        value_dict = {}
        for key in Cpu.PREV_COUNTER_HOLDER_TEMPLATE.keys():
            try:
                value_dict[key] = getattr(curr, key)
            except Exception as e:
                value_dict[key] = 0
        if not name in Cpu.PREV_COUNTER_HOLDER:
            Cpu.PREV_COUNTER_HOLDER[name] = Cpu.PREV_COUNTER_HOLDER_TEMPLATE.copy()
        handle_counter_values(value_dict, Cpu.PREV_COUNTER_HOLDER[name])
        
        total_cpu = sum(int(val) for key, val in value_dict.items() if key not in ["guest", "guest_nice"])
        total_idle = sum(int(val) for key, val in value_dict.items() if key in ["idle", "iowait"])
        fraction = vcpu / total_cpu * 100
        total_usage = (total_cpu - total_idle)*fraction
        for key in Cpu.PREV_COUNTER_HOLDER_TEMPLATE.keys():
            try:
                value_dict[key] = round(int(value_dict[key])*fraction, 2)
            except Exception as e:
                value_dict[key] = 0
                traceback.print_exc()
        value_dict["idle"] = 100.0 - total_usage - value_dict["iowait"]
        if name == "all":
            self.result_dict["CPU_Monitoring"]["CPU_Monitoring"][0]["Output"] = "{} us, {} sy, {} ni, {} id, {} wa, {} hi, {} si, {} st, {} cper".format(value_dict["user"], value_dict["system"], value_dict["nice"], value_dict["idle"], value_dict["iowait"], value_dict["irq"], value_dict["softirq"], value_dict["steal"], total_usage)
        else:
            temp_dict = {}
            temp_dict["Name"] = str(name)
            temp_dict["PercentProcessorTime"] = str(round(total_usage, 2))
            self.result_dict["CPU Cores Usage"]["CPU Cores Usage"].append(temp_dict)
     
    def construct(self):
        self.cpu_monitoring_metrics = AgentConstants.DOCKER_PSUTIL.cpu_times()
        self.cpu_monitoring_percpu_metrics = AgentConstants.DOCKER_PSUTIL.cpu_times(percpu=True)
        self.handle_cpu_monitoring(self.cpu_monitoring_metrics, 1, False, "all")
        for index in range(len(self.cpu_monitoring_percpu_metrics)):
            self.handle_cpu_monitoring(self.cpu_monitoring_percpu_metrics[index], Cpu.cpu_count(), True, index)

    def collect(self):
        self.construct()
        self.parse(self.final_dict)
        self.handle_extra_data()
    
    def handle_extra_data(self):
        csv_values_list = self.result_dict["CPU_Monitoring"]["CPU_Monitoring"][0]["Output"].split(",")
        for val in csv_values_list:
            val = list(filter(lambda x : x, val.split(" ")))
            value, key = val
            self.final_dict[key] = value
        cpu_contx_switches = AgentConstants.DOCKER_PSUTIL.cpu_stats()
        self.final_dict["ctxtsw"] = AgentUtil.get_counter_value("ctx_switches", getattr(cpu_contx_switches, "ctx_switches"), True)
        self.final_dict["interrupts"] = AgentUtil.get_counter_value("interrupts", getattr(cpu_contx_switches, "interrupts"), True)