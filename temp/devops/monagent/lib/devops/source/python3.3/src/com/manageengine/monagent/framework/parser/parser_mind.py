'''
Created on 21-Jun-2017

@author: giri
'''
import abc
import operator
import os
from functools import reduce
import re
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.framework.suite.helper import read_file, readconf_file
from com.manageengine.monagent.logger import AgentLogger


class Parser:
    __metaclass__ = abc.ABCMeta
    @property
    @abc.abstractmethod
    def app_name(self):
        return
  
    @property
    def conf_file_path(self):
        if not hasattr(self, "_conf_file_path"):
            _conf_file_path = self.app_name
            with readconf_file(AgentConstants.APPS_YELLOW_PAGES_FILE) as fp:
                dict_content, status, error_msg = fp
            if self.app_name in dict_content:
                _conf_file_path = dict_content[self.app_name]["conf_file"]  if "conf_file" in dict_content[self.app_name] else self.app_name.split("_")[0]+".conf"
            self._conf_file_path = os.path.join(AgentConstants.APPS_FOLDER, _conf_file_path)
            if not os.path.splitext(self._conf_file_path)[1] == ".conf":
                self._conf_file_path = self._conf_file_path+".conf"
        return self._conf_file_path

    @conf_file_path.setter
    def conf_file_path(self, value):
        self._conf_file_path = self.app_name
        with readconf_file(AgentConstants.APPS_YELLOW_PAGES_FILE) as fp:
            dict_content, status, error_msg = fp
        if self.app_name in dict_content:
            self._conf_file_path = dict_content[self.app_name]["conf_file"]  if "conf_file" in dict_content[self.app_name] else self.app_name.split("_")[0]+".conf"
        self._conf_file_path = os.path.join(AgentConstants.APPS_FOLDER, self._conf_file_path)
        if not os.path.splitext(self._conf_file_path)[1] == ".conf":
            self._conf_file_path = self._conf_file_path+".conf"
            
    def load_conf_contents(self):
        with readconf_file(self.conf_file_path) as fp:
            self.conf_file_contents = fp[0]
    
    @property
    @abc.abstractmethod
    def conf_file_contents(self):
        return
    
    @property
    def metric_file_path(self):
        if not hasattr(self, "_metric_file_path"):
            _metric_file_path = self.app_name
            with readconf_file(AgentConstants.APPS_YELLOW_PAGES_FILE) as fp:
                dict_content, status, error_msg = fp
            if self.app_name in dict_content:
                _metric_file_path = dict_content[self.app_name]["metric_file"]  if "metric_file" in dict_content[self.app_name] else  reduce(os.path.join, self.app_name.split("_"))+".xml"
            self._metric_file_path = os.path.join(AgentConstants.APPS_FOLDER, _metric_file_path)
            if not os.path.splitext(self._metric_file_path)[-1] == ".xml":
                self._metric_file_path = self._metric_file_path+".xml"
        return self._metric_file_path
        

    @metric_file_path.setter
    def metric_file_path(self, value):
        self._metric_file_path = self.app_name
        with readconf_file(AgentConstants.APPS_YELLOW_PAGES_FILE) as fp:
            dict_content, status, error_msg = fp
        if self.app_name in dict_content:
            self._metric_file_path = dict_content[self.app_name]["metric_file"]  if "metric_file" in dict_content[self.app_name] else reduce(os.path.join, self.app_name.split("_"))+".xml"

        self._metric_file_path = os.path.join(AgentConstants.APPS_FOLDER, self._metric_file_path)
        if not os.path.splitext(self._metric_file_path)[-1] == ".xml":
            self._metric_file_path = self._metric_file_path+".xml"
    
    def load_metric_contents(self):
        with read_file(self.metric_file_path) as fp:
            self.metric_file_contents = fp[0]         
    
    @property
    @abc.abstractmethod
    def metric_file_contents(self):
        return
    
    @property
    def is_valid_metricfile(self):
        if hasattr(self, '_is_valid_metricfile'):
            return self._is_valid_metricfile
        else:
            if hasattr(self, 'metric_file_contents'):
                if self.metric_file_contents:
                    return True
        return False

    @is_valid_metricfile.setter
    def is_valid_metricfile(self, value):
        self._is_valid_metricfile = True

    @staticmethod
    def get_key(dataDict, metric_position):
        _metric_value = None
        key_list = re.split(r'(?<!\\)\.', metric_position)
        new_list = []
        for ele in key_list:
            try:
                new_list.append(int(ele))
            except Exception as e:
                new_list.append(ele)
            try:
                _metric_value = reduce(operator.getitem, new_list, dataDict)
            except Exception as e:
                _metric_value = None
        return _metric_value
    
    @property
    def is_conf_file_present(self):
        if os.path.isfile(self.conf_file_path):
            return True
        return False
    
    @property
    def is_metric_file_present(self):
        if os.path.isfile(self.metric_file_path):
            return True
        return False
    