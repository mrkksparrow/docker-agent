'''
Created on 13-July-2017

@author: giri
'''

import traceback
import json
import collections
from functools import wraps
import os
import shlex
import time
import concurrent.futures
import threading
import sys
import pkgutil
#s24x7 packages
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.apps import persist_data as apps_data
if pkgutil.find_loader("docker"):
    from com.manageengine.monagent.apps.docker_daemon import worker as docker_worker
from com.manageengine.monagent.framework.suite.helper import readconf_file
from com.manageengine.monagent.framework.suite.helper import writeconf_file
from com.manageengine.monagent.framework.suite.helper import get_app_conf_file_path
from com.manageengine.monagent.framework.suite.helper import get_user_id
from com.manageengine.monagent.framework.suite import helper
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.handler import filetracker
from com.manageengine.monagent.framework.worker.worker_v1 import Worker
from com.manageengine.monagent.framework.suite.id_guard import Patrol as id_patrol

import six.moves.urllib.request as urlconnection


def agent_apps_handler():
    try:
        if not "Apps" in AgentConstants.thread_pool_handler.active:
            discover_apps = AppsManager()
            _status, _msg = discover_apps.load()
            if _status is True:
                discover_apps.work()
                AgentConstants.STORE_APPS_OBJ={}
                AgentConstants.STORE_APPS_OBJ['app_obj']=discover_apps
                _appshandler = threading.Thread(name="APPSHANDLER", target=discover_apps.run)
                _appshandler.setDaemon(True)
                _appshandler.start()
                AgentConstants.thread_pool_handler.make_active("Apps", discover_apps)
        else:
            AgentLogger.log(AgentLogger.APPS, "APPS thread already initialized ")
    except Exception as e:
        AgentLogger.log(AgentLogger.MAIN, "Problem while starting apps thread | Exception {}".format(e))
        traceback.print_exc()

def obj_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            func_load = func(*args, **kwargs)
            with args[0].apps_lock:
                for app_name, obj in args[0].available_apps_store.copy().items():
                    if app_name in args[0].yellow_pages_content:
                        obj.debug_mode = args[0].yellow_pages_content[app_name].get("debug", "0")
                    parent_app_name = app_name.split("_")[0]
                    conf_file = get_app_conf_file_path(app_name)
                    conf_file_contents = {}
                    with readconf_file(conf_file) as fp:
                        conf_file_contents, status, error_msg = fp
                    if not parent_app_name in conf_file_contents:
                        conf_file_contents[parent_app_name] = {}
                    if app_name == "docker":
                        obj.base_url = conf_file_contents[parent_app_name].get("base_url", "unix://var/run/docker.sock")
                    obj.scheduler_duration = int(conf_file_contents[parent_app_name].get("interval", 300))*1000
                    obj.mid = -1 if conf_file_contents[parent_app_name].get("mid", "0").lower() in ["0", app_name, parent_app_name, "-1"] else conf_file_contents[parent_app_name]["mid"]
                    obj.enabled = conf_file_contents[parent_app_name].get("enabled", "1")
                    obj.is_registered = False if obj.mid == -1 else True
                    if obj.enabled == "1":
                        if obj.is_registered is True:
                            status = obj.get_attendance()
                            if "_" in app_name:
                                if not status:
                                    del args[0].available_apps_store[app_name]
                            AgentLogger.debug(AgentLogger.APPS, "app already registered -- {}".format(app_name))
                        else:
                            if obj.get_attendance():
                                reg_status, app_key = helper.apps_registration(parent_app_name, obj.get_regparams())
                                obj.is_registered = reg_status
                                obj.mid = app_key
                                conf_dict = {}
                                conf_dict[parent_app_name] = {}
                                conf_dict[parent_app_name]["mid"] = obj.mid
                                with writeconf_file(conf_file, conf_dict) as fp:
                                    _persist_status, _persist_error = fp
                            if not obj.get_attendance() and not args[0].one_time_job: AgentLogger.log(AgentLogger.APPS, "{} app attendance absent".format(app_name))
                            if not obj.is_registered: 
                                del args[0].available_apps_store[app_name]
                                args[0].enabled_apps.remove(app_name)
                                AgentLogger.log(AgentLogger.APPS,'app not registered | available apps -- {} enabled apps -- {}'.format(args[0].available_apps_store,args[0].enabled_apps))
                    else:
                        AgentLogger.log(AgentLogger.APPS, "{} app disabled".format(app_name))
                        del args[0].available_apps_store[app_name]
                        if not app_name in args[0].disabled_apps:
                            args[0].disabled_apps.append(app_name)
        except Exception as e:
            AgentLogger.log(AgentLogger.APPS, "checks adding  {}".format(e))
            traceback.print_exc()
            return False
    return wrapper

class AppsManager(object): 
    def __init__(self):
        self.yellow_pages_content = {}
        self.present_apps = {}
        self.brief_present_apps = {}
        self.apps_obj_relation = {"docker": docker_worker.DataCollector() if pkgutil.find_loader("docker") else None} 
        self.apps_lock = threading.Lock()
        self.available_apps_store = {}
        self.suspended_apps_store = {}
        self.shutdown = threading.Event()
        self.skip_data_collection = False
        self.enabled_apps = []
        self.disabled_apps = []
        self.one_time_job = False
        
    @property
    def yellow_pages_content(self):
        return self._yellow_pages_content if hasattr(self, "_yellow_pages_content") else {}
    
    @yellow_pages_content.setter
    def yellow_pages_content(self, value):
        self._yellow_pages_content = {}
        try:
            if type(value) in [dict, collections.OrderedDict]:
               self._yellow_pages_content = value
            elif type(value) is str:
                self._yellow_pages_content = json.loads(value)
        except Exception as e:
            AgentLogger.log(AgentLogger.APPS, "invalid data {} yellow pages".format(e))
            
       
    def load(self):
        _status, _msg = True, ""
        try:
            if not os.path.isfile(AgentConstants.APPS_YELLOW_PAGES_FILE):
                _status, _msg = False, "{} file not present" .format(AgentConstants.APPS_YELLOW_PAGES_FILE)
            else:
                AgentLogger.log(AgentLogger.APPS, "APPS_YELLOW_PAGES file present location {}".format(AgentConstants.APPS_YELLOW_PAGES_FILE))
                with readconf_file(AgentConstants.APPS_YELLOW_PAGES_FILE) as fp:
                    self.yellow_pages_content, status, error_msg = fp
                AgentLogger.log(AgentLogger.APPS, "Supported Site24x7 Apps : file content --> {} | status --> {} | error_msg {}".format(json.dumps(self.yellow_pages_content), status, error_msg))
                apps_conf_list = self.yellow_pages_content["APPS"] if "APPS" in self.yellow_pages_content else []
                get_enable_apps = lambda app_name : app_name if apps_conf_list[app_name] == '1' else ''
                self.enabled_apps = list(map(get_enable_apps, apps_conf_list))
                self.enabled_apps = list(filter(None, self.enabled_apps)) # fastest
                AgentLogger.log(AgentLogger.APPS, "Enabled apps {}".format(self.enabled_apps))
        except Exception as e:
            _status, _msg = False, e
        finally:
            return _status, _msg
    
    @staticmethod
    def persist_app_conf(app_name, app_key_value, app_enabled_value, _custom_conf_data):
        _persist_status, _persist_error = True, ""
        try:
            splitted_app_name = app_name.split("_")
            _conf_dict = {}
            _conf_dict[splitted_app_name[0]] = {}
            _conf_dict[splitted_app_name[0]]["mid"] = app_key_value
            _conf_dict[splitted_app_name[0]]["enabled"] = app_enabled_value
            _conf_dict[splitted_app_name[0]]["migrated"] = 1
            _conf_dict[splitted_app_name[0]]["interval"] = 300
            for key, value in _custom_conf_data.items():
                if key not in _conf_dict:
                    _conf_dict[key] = value
                else:
                    if type(_conf_dict[key]) is dict:
                        _conf_dict[key].update(value)
            with writeconf_file(get_app_conf_file_path(app_name), _conf_dict) as fp:
                _persist_status, _persist_error = fp
        except Exception as e:
            _persist_status, _persist_error = False, e
        finally:
            return _persist_status, _persist_error
    
    @staticmethod
    def is_migration_needed(app_name):
        _is_needed = True 
        try:
            file_path = get_app_conf_file_path(app_name)
            with readconf_file(file_path) as fp:
                _content, _success_flag, _error = fp
            if app_name in _content:
                _is_needed = False if _content[app_name]["migrated"] == "1" else True if "migrated" in _content[app_name] else True
        except Exception as e:
            pass
        finally:
            return _is_needed
    
    @staticmethod
    def migrate_idfile(app_name):
        site24x7_id_dict = filetracker.migrate_site24x7id(AgentConstants.AGENT_APPS_ID_FILE)
        new_dict = {}
        new_dict[app_name] = site24x7_id_dict
        AgentUtil.writeDataToFile(AgentConstants.AGENT_APPS_ID_FILE, new_dict)
    
    @staticmethod
    def app_key_migration(app_name):
        _status, _msg = True, ""
        _app_key_value, _app_enabled_value, _custom_conf_data = 0, 1, {}
        try:
            conf_file_contents = {}
            app_key = app_name+"_key"
            app_enabled = app_name+"_enabled"
            with readconf_file(AgentConstants.AGENT_CONF_FILE) as fp:
                conf_file_contents, status, error_msg = fp
            if conf_file_contents and type(conf_file_contents) is dict:
                if "APPS_INFO" in conf_file_contents:
                    _app_key_value = conf_file_contents["APPS_INFO"][app_key] if app_key in conf_file_contents["APPS_INFO"] else 0
                    _app_enabled_value = conf_file_contents["APPS_INFO"][app_enabled] if app_enabled in conf_file_contents["APPS_INFO"] else 1 
                    AgentUtil.AGENT_CONFIG.remove_section('APPS_INFO')
                    AgentUtil.persistAgentInfo()
        except Exception as e:
            AgentLogger.log(AgentLogger.APPS, "Error in app_key_migration | Reason : {}".format(e))
            _status, _msg = False, e
        finally:
           #persist data
           if app_name == "docker":
               _custom_conf_data["docker"] = {}
               _custom_conf_data["docker"]["base_url"] = "unix://var/run/docker.sock"
           _status, _msg = AppsManager.persist_app_conf(app_name, _app_key_value, _app_enabled_value, _custom_conf_data)
           AppsManager.migrate_idfile(app_name)
           return _status, _msg
        
    def handle_conf_file_persistence(self, app):
        conf_file = get_app_conf_file_path(app)
        if not os.path.isfile(conf_file):
            namenode_port,datanode_port=self.port_checker()
            AppsManager.persist_app_conf(app, 0, 1, {"namenode":{"protocol":"http", "url":AgentConstants.HOST_NAME, "port":namenode_port},\
                                                     "datanode":{"protocol":"http", "url":AgentConstants.HOST_NAME, "port":datanode_port}})
    
    def port_checker(self):
        name_nd_port="50070"
        data_nd_port="50075"
        name_node_ports_to_check = ["9870","50070"]
        data_node_ports_to_check = ["50075","9868"]
        for each in name_node_ports_to_check:
            try:
                request_url = "http://"+AgentConstants.HOST_NAME+":"+each+"/jmx?qry=Hadoop:service=NameNode,name=NameNodeInfo"
                req = urlconnection.Request(request_url, None, {})
                response = urlconnection.urlopen(req,timeout=30)
                if response:
                    name_nd_port = each
                    break
            except Exception as e:
                AgentLogger.log(AgentLogger.APPS,'exception during port check')
                traceback.print_exc()
                
        for each in data_node_ports_to_check:
            try:
                request_url = "http://"+AgentConstants.HOST_NAME+":"+each+"/jmx?qry=Hadoop:service=DataNode,name=DataNodeInfo"
                req = urlconnection.Request(request_url, None, {})
                response = urlconnection.urlopen(req,timeout=30)
                if response:
                    data_nd_port = each
                    break
            except Exception as e:
                AgentLogger.log(AgentLogger.APPS,'exception during port check')
                traceback.print_exc()
        return name_nd_port,data_nd_port

    def construct_object(self, app_list):
        for app in app_list:
            if app == "docker":
                if not pkgutil.find_loader("docker"):
                    AgentLogger.log(AgentLogger.APPS, "docker module not installed hence cannot monitor docker")
                docker_obj = self.apps_obj_relation["docker"]
                conf_file = get_app_conf_file_path("docker")
                if os.path.isfile(conf_file):
                    if AppsManager.is_migration_needed("docker") is True:
                        AgentLogger.log(AgentLogger.APPS, "migration needed for {} | Conf file {} present".format("docker", conf_file))
                        AppsManager.app_key_migration("docker")
                    else:
                        if not self.one_time_job: AgentLogger.log(AgentLogger.APPS, "{} already migrated".format("docker"))
                else:
                    AgentLogger.log(AgentLogger.APPS, "migration needed for {} | Conf file {} not present".format("docker", conf_file))
                    AppsManager.app_key_migration("docker")
                if docker_obj:
                    self.available_apps_store["docker"] = docker_obj
            else:
                self.handle_conf_file_persistence(app)
                self.available_apps_store[app] = Worker(app)
   
    @obj_decorator
    def work(self, app_list=[], rediscover=False):
        if rediscover:
            self.construct_object(app_list)
        else:
            self.construct_object(self.enabled_apps)
    
    def handle_callback(self, future):
        try:
            obj = future.result()
            obj.finish_time = int(AgentUtil.getCurrentTimeInMillis())
            status, file_path = apps_data.save(obj.app_name, obj.result_data)
            #apps_data.zip_apps_data([file_path], obj.app_name)
            AgentLogger.log(AgentLogger.APPS, "{} app monitoring data collected | Persist Status : {} | File path : {}".format(obj.app_name, status, file_path))
        except Exception as e:
            AgentLogger.log(AgentLogger.APPS, "Exception for {} app monitoring data collected |  Exception : {}".format(obj.app_name, e))
    
    def check_for_apps(self):
        available_app_set = set(self.available_apps_store)
        enabled_app_set = set(self.enabled_apps)
        disabled_app_set = set(self.disabled_apps)
        suspended_app_set = set(self.suspended_apps_store)
        apps_to_be_discovered = enabled_app_set - available_app_set - disabled_app_set - suspended_app_set
        if apps_to_be_discovered:
            self.work(apps_to_be_discovered, True)
        self.one_time_job = True
        
    def run(self):
        try:
            while not self.shutdown.is_set():
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    with self.apps_lock:
                        for app, obj in self.available_apps_store.items():
                            if not obj.start_time == 0:
                                if not obj.finish_time > obj.start_time:
                                    continue
                            if not obj.finish_time == 0:
                                obj.next_schedule_time = obj.finish_time + obj.scheduler_duration
                                if obj.next_schedule_time >= int(AgentUtil.getCurrentTimeInMillis()):
                                    continue
                            obj.start_time = int(AgentUtil.getCurrentTimeInMillis())
                            f = executor.submit(obj.run,)
                            f.add_done_callback(self.handle_callback)
                            AgentLogger.log(AgentLogger.APPS, "{} app monitoring job submitted".format(app)+'\n')
                            time.sleep(1)
                    time.sleep(5)
                if self.available_apps_store:
                    time.sleep(2)
                else:
                    time.sleep(180)
                self.check_for_apps()
            AgentConstants.thread_pool_handler.make_inactive("Apps")
        except Exception as e:
            traceback.print_exc()
            AgentLogger.log(AgentLogger.APPS, " exception occurred while thread pool initialization ")
    
    @staticmethod
    def update_conf_file(str_mtype, app_status, action):
        _persist_status, _conf_file_contents = False, {}
        try:
            parent_app_name = str_mtype.split("_")[0]
            conf_file = get_app_conf_file_path(parent_app_name)
            with readconf_file(conf_file) as fp:
                _conf_file_contents, status, error_msg = fp
            if not parent_app_name in _conf_file_contents:
                _conf_file_contents[parent_app_name] = {}
            _conf_file_contents[parent_app_name]["enabled"] = app_status
            if action == "Deleting" : _conf_file_contents[parent_app_name]["mid"] = 0
            with writeconf_file(conf_file, _conf_file_contents) as fp:
                _persist_status, _persist_error = fp
        except Exception as e:
            _persist_status, _conf_file_contents = False, {}
            AgentLogger.log(AgentLogger.APPS, "Exception in update_conf_file | Reason : {}".format(e))
            traceback.print_exc()
        finally:
            return _persist_status, _conf_file_contents
        
    @staticmethod
    def controller(action, app_status, dict_task):
        try:
            thread_obj = AgentConstants.thread_pool_handler.active["Apps"] if "Apps" in AgentConstants.thread_pool_handler.active else None
            with thread_obj.apps_lock:
                str_mtype = dict_task['mtype'].lower() if "mtype" in dict_task else None 
                if thread_obj and str_mtype == 'apps':
                    for app_name in thread_obj.available_apps_store.items():
                        thread_obj.available_apps_store.pop(app_name, None)
                        _persist_status, _conf_file_contents = AppsManager.update_conf_file(app_name, app_status, action)
                        AgentLogger.log(AgentLogger.MAIN , "{} all apps | Appname : {} | status : {} | content  : {}".format(action, app_name, _persist_status, _conf_file_contents))
                elif thread_obj and str_mtype:
                    if str_mtype in thread_obj.available_apps_store:
                        thread_obj.available_apps_store.pop(str_mtype, None)
                    _persist_status, _conf_file_contents = AppsManager.update_conf_file(str_mtype, app_status, action)
                    AgentLogger.log(AgentLogger.MAIN , "{} | Appname : {} | status : {} | content  : {}".format(action, str_mtype, _persist_status, _conf_file_contents))
        except Exception as e:
            traceback.print_exc()

    @staticmethod
    def suspend(dict_task={}):
        AppsManager.controller("Suspending", 0, dict_task)
    
    @staticmethod
    def delete(dict_task={}):
        AppsManager.controller("Deleting", 0, dict_task)
        if os.path.isfile(AgentConstants.AGENT_APPS_ID_FILE):
            os.remove(AgentConstants.AGENT_APPS_ID_FILE)
    
    @staticmethod
    def activate(dict_task={}):
        str_mtype = dict_task['mtype']
        _persist_status, _conf_file_contents = AppsManager.update_conf_file(str_mtype.lower(), 1, "activate")
        if _persist_status:
            thread_obj = AgentConstants.thread_pool_handler.active["Apps"] if "Apps" in AgentConstants.thread_pool_handler.active else None
            if thread_obj: 
                if str_mtype in thread_obj.disabled_apps:
                    thread_obj.disabled_apps.remove(str_mtype)
                    AgentLogger.log(AgentLogger.MAIN, "App : {} removed from disabled apps list ".format(str_mtype))
            AgentLogger.log(AgentLogger.MAIN, "Activation Done in conf file for app | {}".format(str_mtype)+'\n')