'''
Created on 20-September-2017

@author: giri
'''
import os
import json
import traceback
import threading
#s24x7packages
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.logger import AgentLogger

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class Patrol(object):
    __metaclass__ = Singleton
    APPS_ID_DICT = {}
    def __init__(self):
        self._id_dict = {}
        self.lock = threading.Lock()
    
    @property
    def apps_id_dict(self):
        return self._id_dict
    
    @apps_id_dict.setter
    def apps_id_dict(self, value):
        if type(value) is dict:
            self._id_dict = value
        else:
            try:
                self._id_dict = json.loads(value)
            except Exception as e:
                pass            
    
    def gather(self):
        if os.path.isfile(AgentConstants.AGENT_APPS_ID_FILE):
            with open(AgentConstants.AGENT_APPS_ID_FILE, "r") as fp:
                self.apps_id_dict = fp.read()
        APPS_ID_DICT = self.apps_id_dict
        
    def commit(self, app, dict_data):
        dict_data = dict_data if type(dict_data) is dict else json.loads(dict_data)
        s24x7_id_dict = {}
        s24x7_id_dict[app] = dict_data
        try:
            temp_dict ={}
            if os.path.isfile(AgentConstants.AGENT_APPS_ID_FILE):
                with open(AgentConstants.AGENT_APPS_ID_FILE, "r") as fp:
                    temp_dict = json.loads(fp.read())
                if type(temp_dict) is dict:
                    temp_dict[app] = dict_data 
                    s24x7_id_dict = temp_dict
            with self.lock:
                save_status = AgentUtil.writeDataToFile(AgentConstants.AGENT_APPS_ID_FILE, s24x7_id_dict)
                if not save_status:
                    AgentLogger.log(AgentLogger.APPS, "Unable to update id file")
        except Exception as e:
            traceback.print_exc()
            AgentLogger.log(AgentLogger.APPS, "Unable to update id file {}".format(e))
        
