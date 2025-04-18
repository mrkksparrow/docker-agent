'''
Created on 02-July-2017

@author: giri
'''

import re
import json
import traceback 
from functools import reduce
from functools import partial
from com.manageengine.monagent.framework.suite.helper import manage_template
from com.manageengine.monagent.framework.suite.helper import type_conversion
from com.manageengine.monagent.logger import AgentLogger

class CustomDict(object):

    def __init__(self, conf_dict={}, result_dict={}, dict_type="general", iter_var=None):
        self.data = {}
        self.conf_dict = conf_dict
        self.result_dict = result_dict
        self.dict_type = dict_type
        self.iter_dict = {}; self.iter_dict['it'] = iter_var
        self.data["iter_dict"] = self.iter_dict
        
    def __str__(self):
        return json.dumps(self.data)

    def __getitem__(self,item):
        return self.data[item]
    
    def get(self, item, defaultvalue=None):
        if item in self.data:
            return self.data[item]
        else:
            return defaultvalue
    
    def mould_apidict(self, idx, value, dict_list_conv_metrics=[]):
        try:
            if idx in dict_list_conv_metrics:
                self.data[idx] = json.loads(value) if type(value) in [str, int, float] else value
            else:
                self.data[idx] = value
        except Exception as e:
            self.data[idx] = value
    
    def __setitem__(self, idx, value):
        #Check if key or id has been templated
        try:
            idx = manage_template(idx, result_dict=self.result_dict, conf_dict=self.conf_dict, iter_dict=self.iter_dict)
            if idx == "Metric":
                value = value
            else:
                value = manage_template(json.dumps(value),  result_dict=self.result_dict, conf_dict=self.conf_dict, iter_dict=self.iter_dict) if type(value) in [list, dict] else\
                         manage_template(value,  result_dict=self.result_dict, conf_dict=self.conf_dict, iter_dict=self.iter_dict) if type(value) is str else value
            if self.dict_type == "restapi":
                self.mould_apidict(idx, value, dict_list_conv_metrics=["Metric", "proxies", "headers"])
            elif self.dict_type == "commandapi":
                self.mould_apidict(idx, value, dict_list_conv_metrics=["Metric", "ignore_lines", "command"])
            else:
                self.data[idx] = value
            if idx == "url":
                print(value)
        except Exception as e:
            traceback.print_exc()
