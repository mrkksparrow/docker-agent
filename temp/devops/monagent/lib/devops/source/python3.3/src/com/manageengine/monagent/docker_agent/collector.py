'''
Created on 22-Jan-2018

@author: giri
'''
import copy
import json
import traceback
import threading
import time
import six
#s24x7 packages
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.framework.suite.helper import s247_commandexecutor
from com.manageengine.monagent.docker_agent.controller import Master 
from com.manageengine.monagent.docker_agent.helper import upload_collected_metrics, get_resource_checks
from com.manageengine.monagent.framework.suite.helper import get_value_from_dict
from com.manageengine.monagent.docker_agent import constants
from com.manageengine.monagent.docker_agent import helper
from com.manageengine.monagent.collector import DataConsolidator
from com.manageengine.monagent.scheduler import AgentScheduler

@six.add_metaclass(Master)
class Metrics:
    def __init__(self):
        if not self.__class__.__name__ == "Metrics":
            self.result_dict = copy.deepcopy(getattr(constants, "_".join([self.__class__.__name__.upper(), "PARENT_RESULT_DICT"])))
            self.final_dict = copy.deepcopy(getattr(constants, "_".join([self.__class__.__name__.upper(), "PARENT_FINAL_DICT"])))
        else:
            self.do_monitoring = True
     
    def construct(self):
        send_data = False
        while True:
            if self.do_monitoring:
                try:
                    self.result_dict = {}
                    for name, cls_object in self.metrics_list.items():
                        obj = cls_object()
                        obj.collect()
                        self.result_dict['MSPCUSTOMERID'] = AgentConstants.CUSTOMER_ID
                        self.result_dict['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
                        self.result_dict.update(obj.final_dict)
                    if 'tvism' in self.result_dict["memory"]:
                        self.result_dict["asset"]["ram"] = self.result_dict["memory"]["tvism"]
                    if 'totp' in self.result_dict:
                        self.result_dict["systemstats"]["totp"] = self.result_dict["totp"]
                        del self.result_dict["totp"]
                    if 'lc' in self.result_dict:
                        self.result_dict["systemstats"]["lc"] = self.result_dict["lc"]
                        del self.result_dict["lc"]
                    #adding syslog dc to be posted
                    AgentConstants.DOCKER_SYSLOG_OBJECT.collectSysLogData()
                    self.result_dict.update(get_resource_checks())
                    if DataConsolidator.SELF_MONITOR_DICT:
                        AgentLogger.log(AgentLogger.COLLECTOR, 'Agent self metrics added to FC\n')
                        self.result_dict.setdefault('agent', copy.deepcopy(DataConsolidator.SELF_MONITOR_DICT))
                        DataConsolidator.SELF_MONITOR_DICT.clear()
                    AgentLogger.debug(AgentLogger.DA, "data to be posted {}".format(json.dumps(self.result_dict)))
                    if self.result_dict:
                        upload_collected_metrics(self.result_dict, AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['001'], True)
                    helper.handle_configuration_assignment()
                    time.sleep(int(AgentConstants.POLL_INTERVAL))
                except Exception as e:
                    traceback.print_exc()
            else:
                AgentLogger.log(AgentLogger.DA, "monitoring in suspended state")  
                time.sleep(5)
            
    def collect(self):
        from com.manageengine.monagent.docker_agent.system import System
        from com.manageengine.monagent.docker_agent.network import Network
        from com.manageengine.monagent.docker_agent.memory import Memory
        from com.manageengine.monagent.docker_agent.disk import Disk
        from com.manageengine.monagent.docker_agent.cpu import Cpu
        from com.manageengine.monagent.docker_agent.process import Process
        from com.manageengine.monagent.communication import UdpHandler
        self.metrics_list["system"] = System
        self.metrics_list["network"] = Network
        self.metrics_list["memory"] = Memory
        self.metrics_list["disk"] = Disk
        self.metrics_list["cpu"] = Cpu
        self.metrics_list["process"] = Process
        AgentConstants.DOCKER_SYSLOG_OBJECT = UdpHandler.SysLogStatsUtil
        _collector = threading.Thread(name="METRICS_COLLECTOR", target=self.construct)
        _collector.start()
        
    def parse(self, result, iter=False):
        if iter:
            final_values = []
            if type(result[0]) is dict:
                iter_value = result[0].get("iter", "-")
                if not iter_value == "-":
                    del result[0]["iter"]
                    temp_value = get_value_from_dict(self.result_dict, iter_value)[1]
                    if not temp_value:
                        return final_values
                    iter_length = len(temp_value)
                    for i in range(iter_length):
                        temp_dict = {}
                        for key, value in result[0].items():
                            if "{}" in value:
                                value = value.format(i)
                            if "." in value:
                                temp_value = get_value_from_dict(self.result_dict, value)[1]
                                temp_dict[key] = temp_value if temp_value is not None else "None"
                            else:
                                temp_dict[key] = value
                        if "id" in temp_dict:
                            temp_dict["id"] = str(temp_dict["id"])
                        final_values.append(temp_dict)
            return final_values
        else:            
            for key, value in result.items():
                if type(value) is dict:
                    for inner_key, inner_value in value.items():
                        if not inner_value == "-":
                            temp_value = get_value_from_dict(self.result_dict, inner_value)[1]
                            result[key][inner_key] = temp_value if temp_value is not None else "None"
                elif type(value) is list:
                    result[key] = self.parse(value, iter=True)    

def schedule_agentSelfMetrics():
    try:
        interval = 300
        with open(AgentConstants.AGENT_MONITORS_GROUP_FILE, 'r') as f:
            monitors_dict = json.loads(f.read())
        if monitors_dict:
            interval = monitors_dict.get('MonitorGroup',{}).get('SelfMonitoring', {}).get('Interval', 300)
        task = DataConsolidator.agentSelfMetrics
        scheduleInfo = AgentScheduler.ScheduleInfo()
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName('SelfMonitoring')
        scheduleInfo.setTask(task)
        scheduleInfo.setIsPeriodic(True)
        scheduleInfo.setTime(time.time())
        scheduleInfo.setInterval(int(interval))
        scheduleInfo.setLogger(AgentLogger.COLLECTOR)
        AgentScheduler.schedule(scheduleInfo)
    except Exception as e:
        traceback.print_exc()