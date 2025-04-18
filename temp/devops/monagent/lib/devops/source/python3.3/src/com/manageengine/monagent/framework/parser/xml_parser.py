'''
Created on 21-Jun-2017

@author: giri
'''

import collections
from xml.etree.ElementTree import Element, tostring, fromstring
from com.manageengine.monagent.framework.parser.parser_mind import Parser
from com.manageengine.monagent import AgentConstants
import traceback
from collections import OrderedDict
from com.manageengine.monagent.logger import AgentLogger


class XMLParser(Parser):
    def __init__(self, app_name):
        self.app_name = app_name
        
    @property
    def app_name(self):
        return self._app_name if hasattr(self, '_app_name') else None
    
    @app_name.setter
    def app_name(self, value):
        if value:
            self._app_name = str(value)
        else:
            self._app_name = None
    
    @property
    def conf_file_contents(self):
        return self._conf_file_contents if hasattr(self, '_conf_file_contents') else {}

    @conf_file_contents.setter
    def conf_file_contents(self, value):
        self._conf_file_contents = value if value and type(value) in [collections.OrderedDict, dict] else {}
    
    @property
    def metric_file_contents(self):
        return self._metric_file_contents if hasattr(self, '_metric_file_contents') else None

    @metric_file_contents.setter
    def metric_file_contents(self, value):
        try:
            self._metric_file_contents = AgentConstants.XMLJSON_BF.data(fromstring(value)) if value else {}
        except Exception as e:
            traceback.print_exc()
            self._metric_file_contents = None
    
    @property
    def categories(self):
        return self._categories if self._categories else []
    
    @categories.setter
    def categories(self, value):
        if type(value) is list:
            self._categories = value
        elif type(value) in [dict, OrderedDict]:
            self._categories = [value]
        else:
            self._categories = []
        
        