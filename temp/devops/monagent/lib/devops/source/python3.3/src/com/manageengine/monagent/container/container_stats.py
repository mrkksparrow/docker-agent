# $Id$

import json
import traceback
import time
import os
#s24x7 packages
from . import container_helper
from com.manageengine.monagent.framework.suite.helper import iso_to_millis
from com.manageengine.monagent.framework.suite.helper import get_value_from_dict
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent import AgentConstants,AppConstants
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.handler import filetracker

class DockerStats(object):    
    def __init__(self):
        self.metrics_key_dict = {"Cpuset" : "Config.CpusetCpus", "CpuShares" : "Config.CpuShares", "Driver" : "Driver", "ExposedPorts" : "Config.Exposed Ports", 
                                 "ImageName" : "Config.Image", "IPAddress" : "NetworkSettings.IPAddress", "MemoryLimit" : "HostConfig.Memory", "MemorySwap": "HostConfig.MemorySwap",\
                                  "Path" : "Path", "Ports" : "NetworkSettings.Ports", "PortBindings" : "HostConfig.PortBindings", "Running" : "State.Running", "Volumes" : "Mounts", \
                                  "Created" : "State.StartedAt" ,"Health":"State.Health.Status"}
        self.previous_data = {}
        self.docker_meta_data_include_list=['Containers','ContainersRunning','ContainersPaused','ContainersStopped','ServerVersion','MemTotal','Images']
        self.finish_time = 0
    
    def initialize_stats(self):
        self.id_dict = list(AgentConstants.APPS_CONFIG_DATA['DOCKER'].values())[0]['child_keys']
        AgentLogger.debug(AgentLogger.APPS,'id config :: {}'.format(self.id_dict))
        self.containers_dict = {}
        self.images_dict = {}
        self.parsed_events = []
    
    @staticmethod
    def get_docker_connection():
        if AppConstants.docker_client_cnxn_obj:
            return AppConstants.docker_client_cnxn_obj
        else:
            try:
                if DockerStats.check_if_podman():
                    AppConstants.docker_base_url=AppConstants.podman_base_url
                    AppConstants.docker_client_cnxn_obj = AgentConstants.DOCKER_MODULE.DockerClient(base_url=AppConstants.docker_base_url, version="auto")
                    AppConstants.isPodmanPresent = True
                    AgentLogger.log(AgentLogger.APPS, 'Podman Container runtime identified')
                else:
                    AppConstants.docker_client_cnxn_obj = AgentConstants.DOCKER_MODULE.from_env(version="auto")
                    AppConstants.docker_client_cnxn_obj.version()
            except Exception as e:
                AgentLogger.debug(AgentLogger.APPS, "Exception in set_auto_baseurl {}".format(e))
                #traceback.print_exc()
                try:
                    AppConstants.docker_client_cnxn_obj = AgentConstants.DOCKER_MODULE.DockerClient(base_url=AppConstants.docker_base_url, version="auto")
                    AppConstants.docker_client_cnxn_obj.version()
                except Exception as e:
                    AgentLogger.debug(AgentLogger.APPS, "Exception in set_baseurl {}".format(e))
                    #traceback.print_exc()
        return AppConstants.docker_client_cnxn_obj
    
    @property
    def allowed_containers_size(self):
        return 100
    
    @property
    def allowed_images_size(self):
        return 100

    @staticmethod
    def check_if_podman():
        try:
            if not os.path.exists("/var/run/podman/podman.sock"):
                return False
            if AgentConstants.DOCKER_MODULE.DockerClient(base_url=AppConstants.podman_base_url, version="auto"):
                return True
            return False
        except Exception as e:
            return False

    def make_false(self):
        try :
            for key in self.previous_data :
                self.previous_data[key]["flag"] = False
        except Exception as e:
            AgentLogger.log(AgentLogger.APPS, "DOCKER_LOG: Error in make False to previous data Reason")
    
    def collect_container_perf_metrics(self, data_dict, container, cont_id):
        try:
            if data_dict["Running"]:
                stats = next(container.stats())
                container_stats = json.loads(stats.decode())
                data_dict["BlkioPerf"] = container_stats.get("blkio_stats", {})
                data_dict["CpuPerf"] = container_stats.get("cpu_stats", {})
                data_dict["MemoryPerf"] = container_stats.get("memory_stats", {})
                data_dict["NetworkPerf"] = container_stats.get("networks", {})
                data_dict["tp"] = len(container.top()["Processes"])
                #self.containers_dict[container.id]['Process'] = data_dict['Process']  
                container_helper.collect_metrics(data_dict, cont_id, self.previous_data)
        except Exception as e:
            AgentLogger.log(AgentLogger.APPS, "error in collect_container_perf_metrics {}".format(e))
        
    def check_deleted(self, result_dict, stats_name):
        if self.id_dict and stats_name in self.id_dict:
                for id in self.id_dict[stats_name]:
                    if id not in result_dict:
                        result_dict[id]={}
                        result_dict[id]['cid'] = self.id_dict[stats_name][id]
                        result_dict[id]['deleted'] = True
                    
    def delete_old_data(self):
        try :
            for id in self.previous_data:
                if not self.previous_data[id]['flag'] : 
                    self.previous_data.pop(id, None)
        except Exception as e: 
            pass
    
    def parse_events(self, event, count,mid):
        try:
            event['_zl_timestamp'] = event['time'] * 1000 if "time" in event else int(AgentUtil.getTimeInMillis())
            if 'Type' in event:
                event['type'] = event.pop('Type')
            if event['type'] not in ['network','container','daemon','image']:
                return None
            if 'timeNano' in event:
                event.pop('timeNano',None)
            if 'status' in event:
                event.pop('status',None)
            if 'Action' in event:
                event['action']=event.pop('Action',None)
            if 'name' in event['Actor']['Attributes']:
                event['name'] = event['Actor']['Attributes']['name']
            else:
                event['name'] = "None"
            #event['ct'] = int(AgentUtil.getTimeInMillis()) + count
            if 'Actor' in event:
                event.pop('Actor',None)
            event['s247agentuid']=mid
        except Exception as e:
            AgentLogger.log(AgentLogger.APPS, "DOCKER_LOG: " +  "Exception in parsing events data: {}".format(e))
            traceback.print_exc()
        finally:
            return event
    
    def get_images_data(self, result_dict, value_list, add_stats, allowed_size, stats_name):
        try:
            if len(value_list) <= allowed_size:
                for value in value_list:
                    result_dict[value.id] = {}
                    try:
                        result_dict[value.id]["cid"] = self.id_dict[stats_name][value.id] if value.id in self.id_dict[stats_name] else -1 if stats_name in self.id_dict else -1
                    except Exception as e:
                        result_dict[value.id]["cid"] = -1
                    add_stats(value)
            else:
                count = 0
                new_stats_list = []
                for value in value_list:
                    if count > allowed_size:
                        break
                    if stats_name in self.id_dict and value.id in self.id_dict[stats_name]:
                        result_dict[value.id] = {}
                        result_dict[value.id]["cid"] = self.id_dict[stats_name][value.id]
                        add_stats(value)
                        count += 1
                    else:
                        new_stats_list.append(value)
                remaining_size = allowed_size - count
                new_stats_list = new_stats_list[:remaining_size]
                for each_val in new_stats_list:
                    result_dict[each_val.id] = {}
                    result_dict[each_val.id]["cid"] = -1
                    add_stats(each_val)
        except Exception as e:
            traceback.print_exc()
            AgentLogger.log(AgentLogger.APPS,"Error in collecting stats {}".format(e))
                
    def get_stats(self, result_dict, value_list, add_stats, allowed_size, stats_name):
        try:
            if 'SERVER_CONTAINER' in self.id_dict:
                container_ids = self.id_dict['SERVER_CONTAINER']
                if container_ids:
                    for cname,cid in container_ids.items():
                        try:
                            container = DockerStats.get_docker_connection().containers.get(cname)
                            result_dict[container.id]={}
                            result_dict[container.id]['cid'] = cid
                            add_stats(container)
                        except AgentConstants.DOCKER_MODULE.errors.NotFound:
                            result_dict[cid]={}
                            result_dict[cid]['cid'] = cid
                            result_dict[cid]['Running'] = 0 
                            result_dict[cid]['deleted'] = True
                            AgentLogger.log(AgentLogger.APPS, "Container Data not found :: {}".format(cname))
                        except Exception as e:
                            traceback.print_exc()
                else:
                    AgentLogger.log(AgentLogger.APPS, "No Container to Monitor ")        
        except Exception as e:
            traceback.print_exc()
            AgentLogger.log(AgentLogger.APPS,"Error in collecting stats {}".format(e))
    
    def get_docker_info(self):
        docker_info_data = {}
        try:
            docker_info = DockerStats.get_docker_connection().info()
            for each in docker_info:
                if each in self.docker_meta_data_include_list:
                    docker_info_data[each] = docker_info[each]
        except Exception as e:
            traceback.print_exc()
        return docker_info_data
    
    def get_containers_stats(self):
        try:
            self.containers_list = DockerStats.get_docker_connection().containers.list(all)
            self.make_false()
            self.get_stats(self.containers_dict, self.containers_list, self.add_container_stats, self.allowed_containers_size, "Containers")
            #self.check_deleted(self.containers_dict, "SERVER_CONTAINER")
            self.delete_old_data()
        except Exception as e:
            traceback.print_exc()
            AgentLogger.log(AgentLogger.APPS, "Exception while collecting container data {}".format(e))
        finally:
            return self.containers_dict
    
    def check_for_custom_network_ipaddr(self, container_data, container_attrs_dict):
        try:
            ip_address = container_data.get("IPAddress", None)
            if not ip_address:
                network_data = container_attrs_dict.get("NetworkSettings", {})
                network_data = network_data.get("Networks", {}) if type(network_data) is dict else {}
                if type(network_data) is list:
                    network_data = network_data[0]
                for name, data in network_data.items():
                    container_data["IPAddress"] = data.get("IPAddress", "")
                    break
        except Exception as e:
            pass
        
    def add_container_stats(self, container):
        try:
            attrs = container.attrs
            AgentLogger.debug(AgentLogger.APPS,'container data :: {}'.format(json.dumps(attrs)))
            self.containers_dict[container.id]["Id"] = container.id
            try:
                self.containers_dict[container.id]["ImageId"] = container.image.id
            except Exception as e:
                self.containers_dict[container.id]["ImageId"] = "-"
            self.containers_dict[container.id]["Name"] = container.name if len(container.name) < 96 else container.name[:96]+".."
            
            for metric_name, keys in self.metrics_key_dict.items():
                self.containers_dict[container.id][metric_name] = get_value_from_dict(attrs, keys)[1]
            
            if self.containers_dict[container.id]["ImageName"]:
                self.containers_dict[container.id]["ImageName"] = self.containers_dict[container.id]["ImageName"] if len(self.containers_dict[container.id]["ImageName"]) < 96 else self.containers_dict[container.id]["ImageName"][:96]+".."
            else:
                self.containers_dict[container.id]["ImageName"] = "-"
            self.check_for_custom_network_ipaddr(self.containers_dict[container.id], attrs)
            self.containers_dict[container.id]["Created"] =  iso_to_millis(self.containers_dict[container.id]["Created"])
            if self.containers_dict[container.id]["Cpuset"] is None:
                self.containers_dict[container.id]["Cpuset"] = ""
            if self.containers_dict[container.id]["CpuShares"] is None:
                self.containers_dict[container.id]["CpuShares"] = 0
            self.containers_dict[container.id]["Running"] = 1 if self.containers_dict[container.id]["Running"] is True else 0
            container_helper.parse_port_data(self.containers_dict[container.id])
            self.collect_container_perf_metrics(self.containers_dict[container.id], container, container.id)
        except Exception as e:
            AgentLogger.log(AgentLogger.APPS, "error in add_container_stats {}".format(e))
            traceback.print_exc()
        
    def add_image_stats(self, image):
        try:
            attrs = image.attrs
            remove_attrs = ["Labels", "RepoDigests", "Config", "GraphDriver", "ContainerConfig", "Metadata", "RootFS"]
            for key in remove_attrs:
                attrs.pop(key, None)
            attrs["RepoTags"] = ",".join(attrs["RepoTags"]) if "RepoTags" in attrs and type(attrs["RepoTags"]) is list else attrs["RepoTags"] if "RepoTags" in attrs and attrs["RepoTags"] else "-"
            image_id = attrs.get("Id") if "Id" in attrs else attrs.get("id") if "id" in attrs else attrs.get("ID") if "ID" in attrs else -1
            if image_id != -1:
                self.images_dict[image_id].update(attrs)
        except Exception as e:
            traceback.print_exc()
            AgentLogger.log(AgentLogger.APPS, "Exception in add_image_stats {}".format(e))
            
    def get_images_stats(self):
        try:
            self.images_list = DockerStats.get_docker_connection().images.list()
            self.get_images_data(self.images_dict, self.images_list, self.add_image_stats, self.allowed_images_size, "Images")
            self.check_deleted(self.images_dict, "Images")
            self.delete_old_data()
        except Exception as e:
            traceback.print_exc()
            AgentLogger.log(AgentLogger.APPS, "Exception while collecting images data {}".format(e))
        finally:
            return self.images_dict
        
    def get_events(self,mid):
        try:
            finish_time = int(round(time.time()))
            start_time_in_millis = 300 if self.finish_time == 0 else self.finish_time
            if not start_time_in_millis == 300:
                start_time =  int(round(start_time_in_millis/1000))
            else:
                start_time = finish_time - 300
            self.events = DockerStats.get_docker_connection().events(start_time, finish_time, decode=True)
            count = 0
            for event in self.events:
                count += 1000
                mod_event = self.parse_events(event, count,mid)
                if mod_event:
                    self.parsed_events.append(mod_event)
        except Exception as e:
            traceback.print_exc()
        finally:
            return self.parsed_events
        
    def collect_container_data(self,config):
        result = {}
        try:
            proceed_dc = DockerStats.get_docker_connection()
            if proceed_dc:
                if 'DOCKER' in AgentConstants.APPS_CONFIG_DATA:
                    self.initialize_stats()
                    result["Containers"] = self.get_containers_stats()
                    result["Images"] = self.get_images_stats()
                    result["Events"] = self.get_events(config['mid'])
                    result["ct"] = int(AgentUtil.getTimeInMillis())
                    result["HostName"] = AgentConstants.HOST_FQDN_NAME
                    result["DOCKER"] = self.get_docker_info()
                    result["DOCKER"]["availability"] = 1
                    result['mid'] = config['mid']
            else:
                result = {}; 
                result["DOCKER"] = {}; 
                result["DOCKER"]["availability"] = 0
                result["DOCKER"]["error_code"] = 19002
                result['mid'] = config['mid']
        except Exception as e:
            AgentLogger.log(AgentLogger.APPS,'exception in collect container data ')
            traceback.print_exc()
        finally:
            AppConstants.docker_client_cnxn_obj = None
        return result