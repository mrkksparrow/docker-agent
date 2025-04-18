'''
Created on 22-Jan-2018

@author: giri
'''
#python packages
from __future__ import division
import json
import shlex
import traceback
import re
#s24x7 packages
import com
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.framework.suite.helper import s247_commandexecutor
from com.manageengine.monagent.docker_agent.collector import Metrics
from com.manageengine.monagent.docker_agent import constants as da_constants


def handle_exception(func):
    def wrapper(*args, **kwargs):
        value = None
        try:
            value = func(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()
        finally:
            return value
    return wrapper

class Process(Metrics):  
    
    @staticmethod
    @handle_exception
    def handle_process_discovery(*args):
        dict_task = {}
        for arg in args:
            if isinstance(arg, dict):
                dict_task = arg
        result_dict = {}
        result_dict['NAME'] = AgentConstants.TEST_MONITOR
        result_dict['ACTION_TO_CALL'] = 'false'
        result_dict['AGENT_REQUEST_ID'] = dict_task["AGENT_REQUEST_ID"]
        ps_result_list = []
        try:
            for proc in AgentConstants.DOCKER_PSUTIL.process_iter():
                processed_data = {}
                pinfo = {}
                try:
                    pinfo = proc.as_dict(attrs=list(da_constants.PROCESS_DISCOVERY_DICT.keys()))
                except AgentConstants.DOCKER_PSUTIL.NoSuchProcess:
                    continue
                if pinfo:
                    for key, value in da_constants.PROCESS_DISCOVERY_DICT.items():
                        actual_value = pinfo[key]
                        if isinstance(actual_value, float):
                            actual_value = str(round(actual_value, 2))
                        elif isinstance(actual_value, str):
                            actual_value = actual_value.strip()
                        elif isinstance(actual_value, int):
                            actual_value = str(actual_value)
                        if key == "cmdline" and type(actual_value) is list:
                            actual_value = " ".join(actual_value).strip()
                        if actual_value in [None, ""]:
                            if key in ["cmdline", "exe"]:
                                actual_value = pinfo["name"]
                            else:
                                actual_value = "0"
                        processed_data[value] = actual_value
                    processed_data["CPU_UTILIZATION"] = str(round(proc.cpu_percent()))
                    ps_result_list.append(processed_data)
            result_dict["PROCESS_LOG_DATA"] = ps_result_list
            result_dict['DATACOLLECTTIME'] = str(AgentUtil.getTimeInMillis())
            result_dict['ERRORMSG'] = 'NO ERROR'
            result_dict['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        except Exception as e:
            AgentLogger.log(AgentLogger.STDERR,' exception while handling process discovery')
            traceback.print_exc()
        return result_dict
    
    @staticmethod
    def handle_proc_details_request(process_config, pinfo):
        _status = False 
        _details = None
        needed_pn = process_config.get("pn", None)
        pn = pinfo.get("name", None)
        if pn and needed_pn:
            if pn == needed_pn:
                _status = True
                _details = process_config
        return _status, _details
    
    @staticmethod
    def handle_proc_exe(config, pinfo):
        _status = False
        if not pinfo["exe"]:
            pinfo["exe"] = pinfo["name"]
        
        if pinfo["exe"] == config["pth"]:
            _status = True
        return _status

    @staticmethod
    def handle_proc_args(config, pinfo):
        try:
            _status = False
            compiled_regex = None
            pinfo["cmdline"] = (" ".join(pinfo["cmdline"])).strip() if type(pinfo["cmdline"]) is list else pinfo["cmdline"]
            if not pinfo["cmdline"]:
                pinfo["cmdline"] = pinfo["name"]
            
            if config.get("regex", "false") == "true":
                compiled_regex = re.compile(config["args"])
            
            if compiled_regex:
                matcher = compiled_regex.search(pinfo["cmdline"])
                if matcher:
                    _status = True
            else:
                if pinfo["cmdline"] == config["args"]:
                    _status = True
            return _status
        except Exception as e:
            traceback.print_exc()
    
    @staticmethod
    def handle_parsing(final_dict, unique_id):
        result_list = []
        id_up = []
        for key, values in final_dict.items():
            result_dict = {}
            result_dict["id"] = key
            id_up.append(key) 
            result_dict["status"] = 1
            result_dict.update(values[0])
            result_dict["instance"] = len(values)
            if result_dict["instance"] > 1:
                counter_dict = {}
                counter_dict["thread"] = []
                counter_dict["handle"] = []
                counter_dict["cpu"] = []
                counter_dict["memory"] = []
                for each_dict in values:
                    for key, value in counter_dict.items():
                        value.append(each_dict[key])
                for key, value in counter_dict.items():
                    if key in ["cpu", "memory"]:
                        result_dict[key] = round(float(sum(map(float, value))), 2)
                    else:
                        result_dict[key] = str(int(sum(map(float, value))))
                result_dict["cpu"] = round(float(result_dict["cpu"])/AgentConstants.DOCKER_PSUTIL.cpu_count(), 2)
            else:
                for key in ["pid", "thread", "handle"]:
                    result_dict[key] = str(result_dict[key])
                result_dict["cpu"] = round(float(result_dict["cpu"])/AgentConstants.DOCKER_PSUTIL.cpu_count(), 2)
                result_dict["memory"] = round(float(result_dict["memory"]), 2)
            result_list.append(result_dict)
        
        status_down_id = set(unique_id) - set(id_up)
        for each_id in status_down_id:
            result_dict = {}
            result_dict["id"] = each_id
            result_dict["status"] = 0
            result_list.append(result_dict)
        return result_list
    
    
    @staticmethod
    def handle_top_process(total_process, key):
        final_list = []
        process_count = len(total_process)
        filtered = filter(lambda a: a[key] is not None, total_process)
        sorted_list = sorted(filtered, key=lambda k:k[key], reverse=True)
        sorted_list = sorted_list[:5]
        for each_dict in sorted_list:
            result_dict = {}
            for key, value in da_constants.PROCESS_TOPMEMORY.items():
                if each_dict[key] is None:
                    result_dict[value] = "0"
                elif type(each_dict[key]) is list:
                    result_dict[value] = (" ".join(each_dict[key])).strip()
                else:
                    result_dict[value] = str(each_dict[key]) if not type(each_dict[key]) is float else str(round(each_dict[key], 2))
            result_dict["CPU Usage(%)"] = round(float(result_dict["CPU Usage(%)"]) / AgentConstants.DOCKER_PSUTIL.cpu_count(),2)
            result_dict["Avg. CPU Usage(%)"] = round(result_dict["CPU Usage(%)"],2)
            result_dict["Avg. Memory Usage(MB)"] = result_dict["Memory Usage(MB)"]
            if result_dict["Command Line Arguments"] == "":
                result_dict["Command Line Arguments"] = each_dict["name"]
            if len(result_dict["Command Line Arguments"]) > AgentConstants.TOP_PROCESS_ARGUMENT_LENGTH:
                result_dict["Command Line Arguments"] = str(result_dict["Command Line Arguments"])[0:AgentConstants.TOP_PROCESS_ARGUMENT_LENGTH]
            if result_dict["Path"] in [None, "", "0"]:
                result_dict["Path"] = each_dict["name"]
            final_list.append(result_dict)
        return final_list, process_count
                   
    def handle_process_details(self):
        total_process_list = []
        logged_in_users = []
        final_dict = {}
        process_config = da_constants.CONFIG_DICT.get("process", [])
        unique_id = [proc.get("id", None)  for proc in process_config]
        unique_id = list(filter(lambda x : x, unique_id))
        file_desc = 0
        for proc in AgentConstants.DOCKER_PSUTIL.process_iter():
            pinfo = {}
            try:
                pinfo = proc.as_dict(attrs=list(da_constants.PROCESS_DETAILED_DICT.keys()))
                total_process_list.append(pinfo)
                try:
                    logged_in_users.append(proc.terminal())
                except Exception as e:
                    pass
            except Exception as e:
                traceback.print_exc()
                continue
            if AgentConstants.ISROOT_AGENT:
                try:
                    file_desc += proc.num_fds()
                except:
                    AgentLogger.log(AgentLogger.CRITICAL,"Exception on summation of file desc of all process during access of /proc/{}/fd".format(proc['pid']))
                    traceback.print_exc()
            for config in process_config:
                _status, _config_details = Process.handle_proc_details_request(config, pinfo)
                if _status:
                    _status = Process.handle_proc_exe(_config_details, pinfo)
                    if _status:
                        _status = Process.handle_proc_args(_config_details, pinfo)
                        if _status:
                            pinfo["cpu_percent"] = proc.cpu_percent(interval=1)
                            for key in ["num_fds", "num_threads"]:
                                if not pinfo[key]:
                                    pinfo[key] = "0"
                            result_dict = {}
                            for key, value in da_constants.PROCESS_DETAILED_DICT.items():
                                result_dict[value] = pinfo[key]
                            if not _config_details["id"] in final_dict:
                                final_dict[_config_details["id"]] = [result_dict]
                            else:
                                final_dict[_config_details["id"]].append(result_dict)
        result_list = Process.handle_parsing(final_dict, unique_id)
        self.final_dict["TOPMEMORYPROCESS"], self.final_dict["totp"]  = Process.handle_top_process(total_process_list, "memory_percent")
        self.final_dict["TOPCPUPROCESS"] = Process.handle_top_process(total_process_list, "cpu_percent")[0]
        self.final_dict["lc"] = len(set(list(filter(lambda x : x, logged_in_users))))
        self.final_dict["process"] = result_list
        self.final_dict["fd"] = file_desc
        check_data_size = json.dumps(self.final_dict)
        if len(check_data_size) / 1000 > 1000:
            AgentConstants.PS_UTIL_PROCESS_DICT=None
            AgentLogger.log(AgentLogger.COLLECTOR, "top process size check violated -- {}".format(json.dumps(self.final_dict)))
        else:
            AgentConstants.PS_UTIL_PROCESS_DICT = self.final_dict
    
    def construct(self):
        if AgentConstants.OS_NAME in [AgentConstants.LINUX_OS, AgentConstants.OS_X, AgentConstants.FREEBSD_OS, AgentConstants.SUN_OS] and AgentConstants.DOCKER_PSUTIL:
            self.handle_process_details()
        else:
            self.final_dict['process']=com.manageengine.monagent.collector.aix_data_consolidator.get_process_metrics(self.final_dict)
        
    def collect(self):
        self.construct()
    
    @staticmethod
    def handle_free_process(dict_task={}):
        result_dict = {}
        result_dict['REQUEST_TYPE'] = AgentConstants.DISCOVER_PROCESSES_AND_SERVICES
        result_dict['AGENT_REQUEST_ID'] = '1'
        ps_result_list = []
        for proc in AgentConstants.DOCKER_PSUTIL.process_iter():
            ps_dict = {}
            pinfo = {}
            try:
                pinfo = proc.as_dict(attrs=list(da_constants.PROCESS_FREE_ADD_DICT.keys()))
            except AgentConstants.DOCKER_PSUTIL.NoSuchProcess:
                continue
            if pinfo:
                for key, value in pinfo.items():
                    if value is None:
                        if key == "exe":
                            ps_dict[da_constants.PROCESS_FREE_ADD_DICT[key]] = pinfo["name"]
                    elif key == "cmdline" and type(value) is list:
                        ps_dict[da_constants.PROCESS_FREE_ADD_DICT[key]] = (" ".join(value)).strip()
                        if not ps_dict[da_constants.PROCESS_FREE_ADD_DICT[key]]:
                            ps_dict[da_constants.PROCESS_FREE_ADD_DICT[key]] = pinfo["name"]
                    else:
                        ps_dict[da_constants.PROCESS_FREE_ADD_DICT[key]] = str(value)
                ps_result_list.append(ps_dict)
        result_dict["Process Details"] = ps_result_list
        result_dict['DATACOLLECTTIME'] = str(AgentUtil.getTimeInMillis())
        result_dict['ERRORMSG'] = 'NO ERROR'
        result_dict['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        return result_dict
