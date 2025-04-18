# $Id$

from com.manageengine.monagent import AppConstants,AgentConstants
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.framework.suite.helper import iso_to_millis
from six.moves.urllib.parse import urlencode

from com.manageengine.monagent.container.container_stats import DockerStats

from . import discovery_util
import traceback,sys,os,json

class ContainerDiscovery(object):    
    def __init__(self,request_args):
        self.docker_cnxn_obj = DockerStats.get_docker_connection()
        self.request_args = request_args
    
    def initialize_objects(self):
        self.page_number = 0
        self.total_pages = 0
        self.data_buffer = []
        self.size_of_data = 0
    
    def save_data_in_buffer(self,child_list):
        child_dict = {}
        try:
            AgentLogger.debug(AgentLogger.APPS,'child discovery data :: {}'.format(child_list))
            self.page_number += 1
            self.total_pages += 1
            child_dict['Data'] = child_list
            child_dict['pagenumber'] = self.page_number
            child_dict['request'] = self.request_args
            self.data_buffer.append(child_dict)
        except Exception as e:
            traceback.print_exc()
    
    def post_action(self,dummy):
        try:
            action = AgentConstants.CCD
            if self.request_args and self.request_args['AGENT_REQUEST_ID']=='-1':
                action = AgentConstants.CD
            for each_item in self.data_buffer[:]:
                each_item['totalpages'] = self.total_pages
                AgentLogger.debug(AgentLogger.APPS,'child discovery data :: {}'.format(each_item))
                discovery_util.post_discovery_result(each_item,AgentConstants.AGENT_UPLOAD_PROPERTIES_MAPPER['013'],action)
                self.data_buffer.remove(each_item)
        except Exception as e:
            traceback.print_exc()

    def discover(self):
        try:
            self.initialize_objects()
            containers_list=self.docker_cnxn_obj.containers.list()
            child_list = []
            for each in containers_list:
                if self.size_of_data > AppConstants.APP_DISCOVERY_DATA_SIZE:
                    self.save_data_in_buffer(child_list)
                    self.size_of_data=0
                    child_list = []
                attrs = each.attrs
                dict_c = {}
                dict_c['name'] = each.name
                dict_c['uid'] = each.id
                dict_c['image'] = str(attrs['Config']['Image'])
                dict_c['created_time'] = str(iso_to_millis(attrs['Created']))
                ip_address = str(attrs['NetworkSettings']['IPAddress'])
                if not ip_address:
                    ip_address='-'
                dict_c['ip_address']=str(ip_address)
                child_list.append(dict_c)
                self.size_of_data+=(len(dict_c['name'])+len(dict_c['uid'])+len(dict_c['image'])+len(dict_c['created_time'])+len(dict_c['ip_address']))
            if self.size_of_data!=0:
                self.save_data_in_buffer(child_list)
        except Exception as e:
            traceback.print_exc()