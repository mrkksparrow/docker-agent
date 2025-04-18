'''
Created on 29-Jun-2017

@author: giri
'''
from xml.etree.ElementTree import tostring
import traceback
import json
import gzip
import copy
import time
import os
#s24x7 packages
from com.manageengine.monagent.framework.suite import helper
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.framework.parser.xml_parser import XMLParser
from com.manageengine.monagent.framework.parser.parser_mind import Parser 
from com.manageengine.monagent.framework.actions.restapi import RestApi
from com.manageengine.monagent.framework.suite.output import handle_s247server_request
from com.manageengine.monagent.framework.suite import constants as framework_constants
from com.manageengine.monagent.framework.suite.helper import get_default_reg_params
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util import AgentBuffer
from com.manageengine.monagent.framework.suite import logutil
from com.manageengine.monagent.framework.suite import constants
from com.manageengine.monagent.framework.suite.helper import s247_commandexecutor
from com.manageengine.monagent.handler import filetracker
from com.manageengine.monagent.communication import CommunicationHandler

def check_defaults(func):
    def wrapped(*args, **kwargs):
        if args[0].parser.metric_file_contents:
            func(*args, **kwargs)
        else:
            AgentLogger.debug(AgentLogger.FRAMEWORK, "metric content --> {} is empty | metric file path {}".format(args[0].parser.metric_file_contents,\
                                                                                                                  args[0].parser.metric_file_path))
    return wrapped


class Worker(object):
    
    class_director = {"@url": RestApi}
   
    def __init__(self, app_name):
        self.app_name = app_name
        self.is_app_present = False
        self.request_params = get_default_reg_params()
        self.reg_params_dict = {}
        self.mid = -1
        self.parser = None
        self.jobs = []
        self.result = {}; self.result[self.app_name] = {}
        self.output_xml = {}; self.output_xml[framework_constants.OUTPUT_XML_PARENT_ENTITY] = {}
        self.start_time = 0
        self.finish_time = 0
        self.next_schedule_time = 0
        self.result_data = {}
        self.ps_dict = {}
        self.prev_dict = {}
        self.counter_dict = {}
        
    def get_regparams(self):
        try:
            if self.is_app_present:
                AgentLogger.log(AgentLogger.APPS, "registration for application : {0} ".format(self.app_name))
                self.load_parser()
                self.parse_data()
                self.request_params.update(self.reg_params_dict)
        except Exception as e:
            AgentLogger.log(AgentLogger.APPS, "Exception in app registration {}".format(e))
            traceback.print_exc()
        finally:
            AgentLogger.log(AgentLogger.APPS, "registration data : {}".format(self.reg_params_dict))
            if self.reg_params_dict:
                if 'cluster_id' in self.reg_params_dict:
                    if self.reg_params_dict['cluster_id']=='-':
                        AgentLogger.log(AgentLogger.APPS, "cluster id obtained is not proper - api failure ")
                        return None
            return self.request_params
    
    def check_using_commands(self):
        _ps_headers_list, _status = [], False
        try:
            with s247_commandexecutor("ps auxww") as op:
                _output, _returncode, _errormsg, _outputtype = op
            if _output:
                ps_headers = _output.split("\n")[0]
                _ps_headers_list = list(filter(lambda x : x, ps_headers.split(" ")))
            if self.app_name == "hadoop_namenode":
                with s247_commandexecutor("ps auxww | grep java | grep -i org.apache.hadoop.hdfs.server.namenode.namenode | grep -v grep") as op:
                    _output, _returncode, _errormsg, _outputtype = op
            elif self.app_name == "hadoop_datanode":
                with s247_commandexecutor("ps auxww | grep java | grep -i org.apache.hadoop.hdfs.server.datanode.datanode | grep -v grep") as op:
                    _output, _returncode, _errormsg, _outputtype = op                
            if _output:
                output_lines = list(filter(lambda x :x, _output.split("\n")))
                if len(output_lines) > 1:
                    AgentLogger.log(AgentLogger.FRAMEWORK, "more than 2 instances detected hence skipping!!! {}".format(output_lines))
                    return
                else:
                    _output_list = output_lines[0].split(" ")
                    _output_list = list(filter(lambda x : x, _output_list))
                    _output_list[len(_ps_headers_list)-1] = " ".join(_output_list[len(_ps_headers_list)-1:])
                    
                self.ps_dict = dict(zip(_ps_headers_list, _output_list))
                if self.ps_dict.get("USER", "").endswith("+"):
                    pid = self.ps_dict.get("PID", "")
                    if pid:
                        with s247_commandexecutor("ps axo user:20,pid | grep {0} | grep -v grep".format(pid)) as op:
                            _output, _returncode, _errormsg, _outputtype = op
                    _output_lines = list(filter(lambda x :x, _output.split("\n")))
                    if len(_output_lines) == 1:
                        self.ps_dict["USER"] = _output_lines[0].strip().split(" ")[0]
                if self.ps_dict:
                    _status = True
        except Exception as e:
            AgentLogger.log(AgentLogger.FRAMEWORK, "Error in check_using_commands {}".format(e))
            traceback.print_exc()
        finally:
            return _status
    
    def get_attendance(self):
        if AgentConstants.PSUTIL_OBJECT:
            self.is_app_present = self.check_using_psutil()
        else:
            self.is_app_present = self.check_using_commands()
            if self.is_app_present:
                AgentLogger.debug(AgentLogger.APPS, "apps present {}".format(self.app_name))
            else:
                AgentLogger.debug(AgentLogger.APPS, "apps not present {}".format(self.app_name))
        return self.is_app_present

    @staticmethod
    def hadoop_storage_check(app_name, proc_dict, proc_check_name):
        _status = False
        try:
            if proc_dict["cmdline"]:
                cmdline = ' '.join(proc_dict["cmdline"] if type(proc_dict["cmdline"]) is list else [proc_dict["cmdline"]])
                parent_app_name, child_app_name = app_name.split("_", 1) if "_" in app_name else app_name, ""
                if proc_check_name in cmdline.lower():
                    if "java" in proc_dict["name"].lower():
                        AgentLogger.debug(AgentLogger.FRAMEWORK, "{} detected in hadoop_storage_check".format(app_name))
                        _status = True
        except Exception as e:
            AgentLogger.debug(AgentLogger.FRAMEWORK, "Error in hadoop_storage_check {}".format(e))
            traceback.print_exc()
        finally:
            return _status
    
    def apps_checker(self, proc_dict):
        try:     
            _status, _proc_dict = False, {}    
            if self.app_name:
                #hadoop_namenode 
                if self.app_name == "hadoop_namenode":
                    _status = Worker.hadoop_storage_check(self.app_name, proc_dict, "org.apache.hadoop.hdfs.server.namenode.namenode")
                #hadoop_datanode
                elif self.app_name == "hadoop_datanode":
                    _status = Worker.hadoop_storage_check(self.app_name, proc_dict, "org.apache.hadoop.hdfs.server.datanode.datanode")
                
        except Exception as e:
            traceback.print_exc()
        finally:
            return _status

    def check_using_psutil(self):
        _status = False
        try:
            for proc in AgentConstants.PSUTIL_OBJECT.process_iter():
                try:
                    proc_dict = proc.as_dict(attrs=["name", "username", "pid", "cmdline"])
                    _status = self.apps_checker(proc_dict)
                    if _status:
                        self.ps_dict["USER"] = proc["username"]
                        self.ps_dict["PID"] = proc["pid"]
                        self.ps_dict["COMMAND"] = " ".join(proc["cmdline"])
                        break
                except AgentConstants.PSUTIL_OBJECT.NoSuchProcess:
                    pass
        except Exception as e:
            traceback.print_exc()
        finally:
            return _status

    def load_parser(self):
        """A normal parser loader function."""
        self.parser = XMLParser(self.app_name)
        self.parser.load_conf_contents()
        self.parser.load_metric_contents()
        AgentLogger.debug(AgentLogger.FRAMEWORK, "App name {} | Conf file attendance {} | Metric file attendance {}".format(self.app_name, self.parser.is_conf_file_present,\
                                                                                                                          self.parser.is_metric_file_present))
    
    def load_metricdata(self, metrics, category_name):
        if not category_name in self.result[self.app_name]: 
            self.result[self.app_name][category_name] = {}
        class_name = Worker.class_director[framework_constants.CMD_XML_ATTRIBUTE] if framework_constants.CMD_XML_ATTRIBUTE in metrics else None if not framework_constants.URL_XML_ATTRIBUTE in metrics else Worker.class_director[framework_constants.URL_XML_ATTRIBUTE]
        if class_name:
            job = class_name(metrics, self.result[self.app_name], category_name, self.parser.conf_file_contents, self.output_xml["DC"], self.counter_dict)
            self.jobs.append(job)
    
    @check_defaults
    def parse_data(self):
        self.parser.categories = Parser.get_key(self.parser.metric_file_contents, framework_constants.CATEGORY_XML_PATH)
        for category in self.parser.categories:
            metrics = category.get(framework_constants.METRICS_XML_ENTITY_TAG, {})
            category_name = category.get(framework_constants.ID_XML_ATTRIBUTE, '')
            metrics_list = metrics if isinstance(metrics, list) else [metrics]
            register_call_in_xml = list(filter(lambda metrics : True if metrics["@id"].lower() == "s24x7registerapp" else False, metrics_list))
            for metrics in metrics_list:
                if category_name == '':
                    AgentLogger.debug(AgentLogger.FRAMEWORK, "Category name is empty which is not possible hence ignoring this category tag | \
                                                metric file {}".format(self.parser.metric_file_path))
                    break
                self.load_metricdata(metrics, category_name)
        self.run()
    
    @check_defaults
    def get_jobs(self):
        self.jobs = []
        self.parser.categories = Parser.get_key(self.parser.metric_file_contents, framework_constants.CATEGORY_XML_PATH)
        for category in self.parser.categories:
            metrics = category.get(framework_constants.METRICS_XML_ENTITY_TAG, {})
            category_name = category.get(framework_constants.ID_XML_ATTRIBUTE, '')
            metrics_list = metrics if isinstance(metrics, list) else [metrics]
            register_call_in_xml = list(filter(lambda metrics : True if metrics["@id"].lower() == "s24x7registerapp" else False, metrics_list))
            if register_call_in_xml:
                for value in register_call_in_xml:
                    metrics_list.remove(value)
            for metrics in metrics_list:
                self.load_metricdata(metrics, category_name)
    
    def run(self, action=None):
        try:
            if not action == "s24x7registerapp" and self.is_registered:
                self.output_xml[framework_constants.OUTPUT_XML_PARENT_ENTITY] = {}
                self.counter_dict = {}
                self.result_data = {}
                self.load_parser()
                self.get_jobs()
            for job in self.jobs:
                job.load()
                job.work()
                if job.metric_contents["@id"] == "S24x7RegisterApp":
                    for key, value in self.output_xml[framework_constants.OUTPUT_XML_PARENT_ENTITY].copy().items():
                        if key == "s247_app_register":
                            self.reg_params_dict = value[0]
                            del self.output_xml[framework_constants.OUTPUT_XML_PARENT_ENTITY][key]
                            return
            if self.counter_dict:
                if not self.prev_dict:
                    self.prev_dict = copy.deepcopy(self.counter_dict)
                    time.sleep(10)
                    self.run()
                    return
                for key, value in self.prev_dict.items():
                    out_val = self.output_xml["DC"].get(key, [])
                    for each_val in value:
                        pk_key = list(each_val["@pk"].keys())[0] if each_val.get("@pk", None) else None
                        pk_val = each_val["@pk"][pk_key] if pk_key else None
                        if pk_key and pk_val:
                            for each_out_val in out_val:
                                if each_out_val.get(pk_key) == pk_val:
                                    temp_result_dict = {}
                                    for key in each_val:
                                        if key in each_out_val:
                                            val1 = float(each_out_val[key]) if "." in each_out_val[key] else int(each_out_val[key])
                                            val2 = float(each_val[key]) if "." in each_val[key] else int(each_val[key])
                                            temp_result_dict[key] = str(round(val1-val2, 2))
                                    each_out_val.update(temp_result_dict)
                self.prev_dict = copy.deepcopy(self.counter_dict)
            
            temp_val = copy.deepcopy(self.output_xml["DC"]["DC"])
            if "DC" in self.output_xml["DC"]: del self.output_xml["DC"]["DC"]
            final_dict_output = []
            if self.app_name == "hadoop_namenode":
               final_dict_output.append(self.output_xml)
               self.output_xml["DC"]["@mid"] = self.mid
               self.output_xml["DC"]["@ct"] = int(AgentUtil.getTimeInMillis())
               self.output_xml["DC"]["@availability"] = "1"
               self.output_xml["DC"]["@type"] = "HADOOP"
               temp_val_dict = temp_val[0]
               if '@nld' in temp_val_dict:
                   self.output_xml["DC"]["@nld"]=temp_val_dict['@nld']
               if '@ndd' in temp_val_dict:
                   self.output_xml["DC"]["@ndd"]=temp_val_dict['@ndd']
               if '@state' in temp_val_dict:
                   self.result_data['state']=temp_val_dict['@state']
                   self.result_data['node']='namenode'
            elif self.app_name == "hadoop_datanode":
                self.result_data['node']='datanode'
            if not type(temp_val) is list:
                temp_val = [temp_val]
            for val in temp_val:
                temp_dict = {}
                temp_dict["DC"] = val
                final_dict_output.append(temp_dict)
            self.result_data[self.mid] = []
            for val in final_dict_output:
                result = AgentConstants.XMLJSON_BF.etree(val)
                self.result_data[self.mid].append(tostring(result[0]).decode('utf-8'))
            AgentLogger.log(AgentLogger.FRAMEWORK, "final xml data {}".format(self.result_data))
        except Exception as e:
            AgentLogger.log(AgentLogger.FRAMEWORK, "Error in worker_v1_run  {}".format(e))
            traceback.print_exc()
        finally:
            return self

    @staticmethod
    def do_bulk_install(entire_cluster=True, host_names=[], username=constants.HADOOP_USER_NAME):
        try:
            if entire_cluster:
                id_dict = filetracker.read_id("hadoop", AgentConstants.AGENT_APPS_ID_FILE)
                for key, value_dict in id_dict.items():
                    AgentLogger.log(AgentLogger.FRAMEWORK, "child name {} | {}".format(key, value_dict))
                    if key == "DataNodes":
                        nodes_list = list(value_dict.keys())
            else:
                nodes_list = host_names
            for each_node in nodes_list:
                try:
                    AgentLogger.log(AgentLogger.FRAMEWORK, "node name -- {} ".format(each_node,username)+'\n')
                    ssh = AgentConstants.PARAMIKO_OBJECT.SSHClient()
                    ssh.set_missing_host_key_policy(AgentConstants.PARAMIKO_OBJECT.AutoAddPolicy())
                    ssh.connect(each_node, username=username)
                    with AgentConstants.SCP_OBJECT.SCPClient(ssh.get_transport()) as scp_obj:
                        scp_obj.put(AgentConstants.HADOOP_RC_FILEPATH, AgentConstants.HADOOP_DEST_RC_FILEPATH)
                        AgentLogger.log(AgentLogger.FRAMEWORK, "OS checker Install File Copied Successfully to host :"+each_node+'\n')
                    stdin, stdout, stderr = ssh.exec_command(AgentConstants.HADOOP_RC_COMMAND, get_pty=True, timeout=60)
                    output_lines = stdout.readlines()
                    is_agent_installed, is_venv_needed, os_arch, user_id, prefix_cmd = list(map(lambda x : x.strip(), output_lines[0].split("|")))
                    AgentLogger.log(AgentLogger.FRAMEWORK, "agent installed -- {} is_venv_needed -- {} os_arch -- {} user id -- {} prefix_cmd-- {}".format(is_agent_installed,is_venv_needed,os_arch,user_id,prefix_cmd)+'\n')
                    if is_agent_installed == "0":
                        AgentLogger.log(AgentLogger.FRAMEWORK, "Agent not installed hence proceeding with installation \n")
                        if is_venv_needed == "1":
                            script_file_path = AgentConstants.MONITORING_AGENT_INSTALL_FILE
                        else:
                            script_file_path = AgentConstants.MONITORING_AGENT_64bit_INSTALL_FILE if os_arch == "64-bit" else AgentConstants.MONITORING_AGENT_32bit_INSTALL_FILE
                        if not os.path.isfile(script_file_path):
                            CommunicationHandler.downloadPlugin("/server/{}".format(os.path.split(script_file_path)[1]), script_file_path, AgentConstants.STATIC_SERVER_HOST, AgentLogger.FRAMEWORK)
                        with AgentConstants.SCP_OBJECT.SCPClient(ssh.get_transport()) as scp_obj:
                            scp_obj.put(script_file_path, os.path.split(script_file_path)[1])
                        if user_id != "0":
                            post_cmd = "-nr"
                        if CommunicationHandler.PROXY_INFO.getUrl():
                            proxy_cmd = CommunicationHandler.PROXY_INFO.getUrl().split('//')[1]
                            proxy_cmd = "-proxy="+proxy_cmd+""
                        cmd = " ".join([prefix_cmd, os.path.split(script_file_path)[1], "-i", "-key={}".format(AgentConstants.CUSTOMER_ID), post_cmd,proxy_cmd])
                        AgentLogger.log(AgentLogger.FRAMEWORK,'agent install command -- {0}'.format(cmd))
                        stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True, timeout=60)
                        AgentLogger.log(AgentLogger.FRAMEWORK, stdout.readlines())
                    else:
                        AgentLogger.log(AgentLogger.FRAMEWORK, "Agent already installed \n")
                except Exception as e:
                    AgentLogger.log(AgentLogger.FRAMEWORK, "exception while connecting to node -- {}".format(each_node)+'\n')
                    traceback.print_exc()
        except Exception as e:
            traceback.print_exc()
                
            