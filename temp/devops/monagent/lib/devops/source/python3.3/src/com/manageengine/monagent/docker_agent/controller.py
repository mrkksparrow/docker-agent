'''
Created on 14-Feb-2018

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
from com.manageengine.monagent.docker_agent import constants

METRICS_LIST = ["SYSTEM", "CPU", "DISK", "NETWORK", "MEMORY", "PROCESS"]

def add_instance_attributes(cls_name, locals):
    locals.update(constants.NEEDED_INSTANCE_ATTRS)
    if not cls_name == "Metrics":
        locals["result_dict"] = copy.deepcopy(getattr(constants, "_".join([cls_name.upper(), "PARENT_RESULT_DICT"])))
        locals["final_dict"] = copy.deepcopy(getattr(constants, "_".join([cls_name.upper(), "PARENT_FINAL_DICT"])))

def logging(func, cls_name):
    def wrapper(*args, **kwargs):
        try:
            value = func(*args, **kwargs)
            return value
        except Exception as e:
            AgentLogger.log(AgentLogger.DA, "Exception in function {} in class {}".format(func.__name__, cls_name))
            traceback.print_exc()
    return wrapper
    
class Master(type):
    def __new__(cls, name, base, locals):
        for key, value in locals.items():
            if callable(value):
                locals[key] = logging(value, name)
        add_instance_attributes(name, locals)
        return type.__new__(cls, name, base, locals)
    