# $Id$

from com.manageengine.monagent.logger import AgentLogger
from .container_stats import DockerStats
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent import AgentConstants

import traceback

class ContainerManagement(object):
    def __init__(self):
        self.docker_client = DockerStats.get_docker_connection()
        
    def start_container(self, container_id):
        _status, _msg = True, "success"
        try:
            containers_list = self.docker_client.containers.list(all)
            for container in containers_list:
                if container_id == container.id:
                    container.start()
                    break
        except Exception as e:
            _status, _msg = False, e
        finally:
            return _status, _msg
    
    def stop_container(self, container_id):
        _status, _msg = True, "success"
        try:
            containers_list = self.docker_client.containers.list(all)
            for container in containers_list:
                if container_id == container.id:
                    container.stop()
                    break
        except Exception as e:
            _status, _msg = False, e
        finally:
            return _status, _msg
    
    def restart_container(self, container_id):
        _status, _msg = True, "success"
        try:
            containers_list = self.docker_client.containers.list(all)
            for container in containers_list:
                if container_id == container.id:
                    container.restart()
                    break
        except Exception as e:
            _status, _msg = False, e
        finally:
            return _status, _msg
        
def execute(dict_task):
    try:
        if AgentUtil.is_module_enabled(AgentConstants.MANAGEMENT_SETTING):
            container_mgmt_obj = ContainerManagement()
            if dict_task['ACTION'] == 'start':
                container_mgmt_obj.start_container(dict_task['CID'])
            if dict_task['ACTION'] == 'stop':
                container_mgmt_obj.stop_container(dict_task['CID'])
            if dict_task['ACTION'] == 'restart':
                container_mgmt_obj.restart_container(dict_task['CID'])
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN,'exception occurred in management action :: {} :: cid :: {}'.format(dict_task['ACTION'],dict_task['CID']))
        traceback.print_exc()