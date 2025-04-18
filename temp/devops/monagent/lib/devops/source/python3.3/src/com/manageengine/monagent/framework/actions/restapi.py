'''
Created on 02-July-2017

@author: giri
'''
import json
import traceback
import re
from collections import OrderedDict
import copy
#s24x7 packages
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.framework.actions.actions_mind import Actions
from com.manageengine.monagent.framework.suite.custom_dict import CustomDict
from com.manageengine.monagent.framework.suite.helper import handle_request
from com.manageengine.monagent.framework.suite.helper import get_value_from_dict
from com.manageengine.monagent.framework.suite.helper import manage_template
from com.manageengine.monagent.framework.suite.helper import eval_expression
from com.manageengine.monagent.framework.suite.output import handle_data

prefix_str = lambda xml_key : "" if xml_key == "s247_app_register" else "@"

class RestApi(Actions):
    def __init__(self, metric_contents, result_dict, category_name, conf_dict, output_xml, counter_dict):
        self.metric_contents = metric_contents
        self.result_dict = result_dict
        self.category_name = category_name
        self.conf_dict = conf_dict
        self.output_xml = output_xml
        self.jobs = []
        self.is_registered = False
        self.mid = -1
        self.counter_dict = counter_dict
        
    @property
    def url(self):
        try:
            _url = None
            if "@url" in self.metric_contents:
                if type(self.metric_contents["@url"]) is str:
                    _url = self.metric_contents["@url"]        
        except Exception as e:
            print(e)
        finally:
            return _url
    
    @property
    def headers(self):
        try:
            _headers = {}
            if "@headers" in self.metric_contents:
                if type(self.metric_contents["@headers"]) is str:
                    _headers = json.loads(self.metric_contents["@headers"])
                elif type(self.metric_contents["@headers"]) is dict:
                    _headers = self.metric_contents["@headers"]                
        except Exception as e:
            print(e)
        finally:
            return _headers

    @property
    def proxies(self):
        try:
            _proxies ={}
            if "@proxies" in self.metric_contents: 
                if type(self.metric_contents["@proxies"]) is str:
                    _proxies = json.loads(self.metric_contents["@proxies"])
                elif type(self.metric_contents["@proxies"]) is dict:
                    _proxies = self.metric_contents["@proxies"]
        except Exception as e:
            print(e)
        finally:
            return _proxies
    
    @property
    def request_type(self):
        try:
            _request_type = "get"
            if "@request_type" in self.metric_contents:
                if type(self.metric_contents["@request_type"]) is str:
                    _request_type = self.metric_contents["@request_type"]                
        except Exception as e:
            print(e)
        finally:
            return _request_type
    
    @property
    def response_type(self):
        try:
            _response_type = "json"
            if "@response_type" in self.metric_contents:
                if type(self.metric_contents["@response_type"]) is str:
                    _response_type = self.metric_contents["@response_type"]                
        except Exception as e:
            print(e)
        finally:
            return _response_type
    
    
    @property
    def iter_var(self):
        try:
            _iter_var = None
            if "@iter" in self.metric_contents:
                matcher = re.match("\${3}(?P<template_content>.*?)\${3}", self.metric_contents["@iter"])
                if matcher:
                    _iter_var = get_value_from_dict(self.conf_dict, matcher.groupdict()["template_content"])[1]
                else:
                    matcher = re.match("\${2}(?P<template_content>.*?)\${2}", self.metric_contents["@iter"])
                    if matcher:
                        _iter_var = get_value_from_dict(self.result_dict, matcher.groupdict()["template_content"])[1]
        except Exception as e:
            print(e)
        finally:
            return _iter_var

    @property
    def output_key(self):
        _output_key = self.metric_contents["@output"]  if "@output" in self.metric_contents else None
        return _output_key
    
    @property
    def on_error(self):
        if self.url is None:
            _on_error = True
        else:
            _on_error = self.metric_contents["@on_error"] if "@on_error" in self.metric_contents else True
        return _on_error 
    
    def get_mid(self):
        if not self.mid == -1:
            return self.mid
    
    def construct_dict(self, iter_var=None):
        worker_dict = CustomDict(self.conf_dict, self.result_dict, dict_type="restapi", iter_var=iter_var)
        worker_dict["metrics_id"] = self.metrics_id
        worker_dict["headers"] = self.headers
        worker_dict["url"] = self.url
        worker_dict["proxies"] = self.proxies
        worker_dict["timeout"] = self.timeout
        worker_dict["storevalue"] = self.storevalue
        worker_dict["Metric"] = self.metric_list
        worker_dict["request_type"] = self.request_type
        worker_dict["response_type"] = self.response_type
        worker_dict["data"] = ""
        worker_dict["output_xml"] = self.output_key
        worker_dict["on_error"] = self.on_error
        return worker_dict
    
    def load(self):
        if not self.is_iter:
           self.jobs.append(self.construct_dict(iter_var=None)) 
        else:
            if self.iter_var:
                for iter_var in self.iter_var:
                    self.jobs.append(self.construct_dict(iter_var=iter_var)) 
            else:
                AgentLogger.debug(AgentLogger.FRAMEWORK, "iter var value is empty for category {}".format(self.category_name))
            
    def work(self):
        for worker_dict in self.jobs:
            with handle_request(worker_dict) as resp:
                success_flag, response_data, status_code, msg = resp.bool_flag, resp.data, resp.status_code, resp.msg
            AgentLogger.debug(AgentLogger.FRAMEWORK, "askllslalas kpkpkkp {} | {} |{} | {}".format(response_data, worker_dict, success_flag, self.jobs))
            self.update_result(response_data, worker_dict, success_flag, msg)
                
    def update_result(self, response_data, worker_dict, success_flag, msg=" "):
        try:
            temp_xml = {}
            counter_xml = {}
            counter_status = False
            self.result_dict[self.category_name][worker_dict["metrics_id"]] = {}
            if not worker_dict["output_xml"] == "s247_app_register" : temp_xml['@cid'] = -1
            if self.on_error:
                for ind_metric in worker_dict["Metric"]:
                    id = manage_template(ind_metric["@id"], self.result_dict, self.conf_dict, worker_dict["iter_dict"])
                    result_dict_holder = self.result_dict[self.category_name][worker_dict["metrics_id"]]
                    if "@key" in ind_metric:
                        key = manage_template(ind_metric["@key"], result_dict=self.result_dict, conf_dict=self.conf_dict, iter_dict=worker_dict["iter_dict"])
                        result_dict_holder[id] = get_value_from_dict(response_data, key)[1]
                    elif "@expression" in ind_metric:
                        result_dict_holder[id] = eval_expression(ind_metric["@expression"], iter_dict=worker_dict["iter_dict"], \
                                                                      conf_dict=self.conf_dict, result_dict=self.result_dict)[1]
                    elif "@value" in ind_metric:
                        result_dict_holder[id] = manage_template(ind_metric["@value"], result_dict=self.result_dict,\
                                                                                                conf_dict=self.conf_dict, iter_dict=worker_dict["iter_dict"])
                    if "@output" in ind_metric and worker_dict["output_xml"]:
                        output_id = manage_template(ind_metric['@output'], self.result_dict, self.conf_dict, worker_dict["iter_dict"])
                        output_id = prefix_str(worker_dict['output_xml'])+output_id
                        if ind_metric.get("@type", None) == "counter":
                            counter_status = True
                        if type(result_dict_holder[id]) is str:
                            temp_xml[output_id] = result_dict_holder[id]
                        else:
                            temp_xml[output_id] = str(result_dict_holder[id])
                        if counter_status:
                            counter_xml[output_id] = temp_xml[output_id]
                            counter_status = False
                    if "@pk" in ind_metric:
                        counter_xml["@pk"] = {output_id:temp_xml[output_id]}
            else:
                if worker_dict["output_xml"]:
                    temp_xml["error"] = msg
            
            if worker_dict["output_xml"]:
                if not worker_dict["output_xml"] in self.output_xml:
                    self.output_xml[worker_dict["output_xml"]] = [temp_xml]
                else:
                    self.output_xml[worker_dict["output_xml"]].append(temp_xml)
                if counter_xml:
                    try:
                        self.counter_dict[worker_dict["output_xml"]].append(counter_xml)
                    except Exception as _:
                        self.counter_dict[worker_dict["output_xml"]] = [counter_xml]
                        
        except Exception as e:
            traceback.print_exc()
        finally:
            if worker_dict["output_xml"] == "s247_app_register" :
                AgentLogger.debug(AgentLogger.FRAMEWORK, "Fkfkfdkfdkfd {} | {}".format(result_dict_holder, temp_xml))
            return temp_xml
        