# $Id$
import copy
import os
import sys
import shutil
import codecs
import time
import threading
import traceback
import json
import subprocess
import ast
from contextlib import contextmanager

import six.moves.urllib.request as urlconnection
from six.moves.urllib.parse import urlencode

import com
import six.moves.urllib.request as urllib
from collections import namedtuple
from com.manageengine.monagent.util import AgentUtil,MetricsUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil,ZipUtil
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants,AppConstants
from com.manageengine.monagent.apps import persist_data as apps_data
from com.manageengine.monagent.scheduler import AgentScheduler
from xml.etree import ElementTree
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

if 'com.manageengine.monagent.communication.CommunicationHandler' in sys.modules:
    CommunicationHandler = sys.modules['com.manageengine.monagent.communication.CommunicationHandler']
else:
    from com.manageengine.monagent.communication import CommunicationHandler
    
UACFG_VS_TASK = {}

def type_conversion(output):
    try:
        _output, _type_conv_status, _output_type = output, False, str
        _output = _output.decode("utf-8") if type(_output) is bytes else _output
        _output, _type_conv_status = json.loads(_output), True
    except Exception as e:
        try:
            _output, _type_conv_status = ast.literal_eval(_output), True
        except Exception as e:
            _output, _type_conv_status = _output, False
    finally:
        _output_type = type(_output)
        return _output, _type_conv_status, _output_type

@contextmanager
def s247_commandexecutor(command, env={}, timeout=10):
    try:
        _output, _outputtype, _returncode, _errormsg = None, None, None, None
        is_shell = False if type(command) is list else True
        _output, _returncode = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=is_shell, env=env).decode("utf-8"), 0
    except Exception as e:
        _errormsg = e
    finally:
        _output, _typeconv_status, _outputtype  = type_conversion(_output)
        yield _output, _returncode, _errormsg, _outputtype


def read_hadoop_xml_file(conf_file):
    xml_content = {}
    try:
        if os.path.exists(conf_file):
            _output = conf_file
        else:
            _output = None
        if _output:
            input_file_name = _output.strip()
            dom = ElementTree.parse(input_file_name)
            property = dom.findall('property')
            for p in property:
                name = p.find('name').text
                value = p.find('value').text
                xml_content[name]=value
    except Exception as e:
        traceback.print_exc()
    finally:
        return xml_content

def check_for_apps(app_name):
    port = None
    hostname = AgentConstants.HOST_NAME
    try:
        if app_name == "hadoop_namenode":
            with s247_commandexecutor("ps auxww | grep java | grep -i org.apache.hadoop.hdfs.server.namenode.namenode | grep -v grep") as op:
                _output, _returncode, _errormsg, _outputtype = op
        elif app_name == "hadoop_datanode":
            with s247_commandexecutor("ps auxww | grep java | grep -i org.apache.hadoop.hdfs.server.datanode.datanode | grep -v grep") as op:
                _output, _returncode, _errormsg, _outputtype = op                
        elif app_name == "zookeeper":
            with s247_commandexecutor("ps auxww | grep java | grep -i org.apache.zookeeper.server.quorum.QuorumPeerMain | grep -v grep") as op:
                _output, _returncode, _errormsg, _outputtype = op
        elif app_name == "hadoop_yarn":
            with s247_commandexecutor("ps auxww | grep java | grep -i org.apache.hadoop.yarn.server.resourcemanager.ResourceManager | grep -v grep") as op:
                _output, _returncode, _errormsg, _outputtype = op
                if not _output:
                    xml_content = read_hadoop_xml_file(AppConstants.hadoop_yarn_locate_xml)
                    AgentLogger.log(AgentLogger.APPS,'configuration of {} :: {}'.format(app_name,json.dumps(xml_content))+'\n')
                    if 'yarn.resourcemanager.hostname' in xml_content:
                        hostname = xml_content['yarn.resourcemanager.hostname']
                        _output = True
        if _output:
            if app_name == AppConstants.zookeeper_app:
                port = 2181
            else:
                port = port_checker(AppConstants.port_checker[app_name],AppConstants.app_checker[app_name],hostname)
    except Exception as e:
        AgentLogger.log(AgentLogger.APPS, "Error in check_for_apps {}".format(e))
        traceback.print_exc()
    finally:
        return hostname , port 
        
def port_checker(ports_list,url,host_name):
    port = None
    for each in ports_list:
        try:
            request_url = "http://"+host_name+":"+each+url
            req = urlconnection.Request(request_url, None, {})
            response = urlconnection.urlopen(req,timeout=30)
            if response:
                port = each
                AgentLogger.log(AgentLogger.APPS,'application discovered :: {}'.format(request_url)+'\n')
                break
        except Exception as e:
            AgentLogger.log(AgentLogger.STDERR,'exception during port check :: {}'.format(request_url))
            traceback.print_exc()
    return port

@contextmanager
def readconf_file(file_path):
    _content, _success_flag, _error = {}, False, ""
    try:
        if os.path.isfile(file_path):
            config = configparser.RawConfigParser()
            config.read(file_path)
            _content, _success_flag, _error = config._sections, True, ''
            _content = json.loads(json.dumps(_content))
        else:
            _error = "{} file not present".format(file_path)
    except Exception as e:
        _content, _success_flag, _error = {}, False, e
        AgentLogger.log(AgentLogger.APPS, "app key content exception :: {} ".format(e))
    finally:
        yield _content, _success_flag, _error

@contextmanager
def writeconf_file(file_path, dict_content, overwrite=False):
    _success_flag, _error = False, ""
    try:
        config = configparser.RawConfigParser()
        if os.path.isfile(file_path) and overwrite is False:
            config.read(file_path)
        for section in dict_content:
            if not config.has_section(section):
                config.add_section(section)
            for key, value in dict_content[section].items():
                config.set(section, key, value)
        with open(file_path, 'w') as fp:
            config.write(fp)
        _success_flag = True
    except Exception as e:
        _success_flag, _error = False, e
    finally:
        yield _success_flag, _error

get_app_conf_file_path = lambda app_name: os.path.join(AgentConstants.APPS_FOLDER,app_name.split('_')[0],AppConstants.app_conf_file_name[app_name])

def persist_app_conf(app_name, app_key_value, app_enabled_value, custom_conf_data):
    _persist_status, _persist_error = True, ""
    try:
        conf_dict = {}
        conf_dict[app_name] = {}
        conf_dict[app_name]["mid"] = app_key_value
        conf_dict[app_name]["enabled"] = app_enabled_value
        conf_dict[app_name]["interval"] = 300
        for key, value in custom_conf_data.items():
            if key not in conf_dict:
                conf_dict[key] = value
            else:
                if type(conf_dict[key]) is dict:
                    conf_dict[key].update(value)
        app_path=get_app_conf_file_path(app_name)
        with writeconf_file(get_app_conf_file_path(app_name),conf_dict) as fp:
            _persist_status, _persist_error = fp
    except Exception as e:
        _persist_status, _persist_error = False, e
        traceback.print_exc()
    finally:
        return _persist_status, _persist_error

def apps_registration(app_name, request_params={}):
    reg_status, app_key = False, None
    try:
        with readconf_file(get_app_conf_file_path(app_name)) as fp:
            content, status, error_msg = fp
        app_key = content[app_name]["mid"] if "mid" in content[app_name] else "0" if app_name in content else "0"
        if app_key.lower() in (app_name, "0", ):
            if request_params:
                str_requestParameters = urlencode(request_params)
                str_url = AgentConstants.APPLICATION_DISCOVERY_SERVLET + str_requestParameters
                AgentLogger.log(AgentLogger.APPS, "application registration call {}".format(str_url))
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.STDOUT)
            requestInfo.set_method(AgentConstants.HTTP_GET)
            requestInfo.set_url(str_url)
            requestInfo.set_dataType('application/json')
            requestInfo.add_header("Content-Type", 'application/json')
            requestInfo.add_header("Accept", "text/plain")
            requestInfo.add_header("Connection", 'close')
            (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
            CommunicationHandler.handleResponseHeaders(dict_responseHeaders, dict_responseData, 'ADS')
            AgentLogger.log(AgentLogger.APPS, "application {} :: response headers {} :: error code :: {}".format(app_name,dict_responseHeaders,errorCode)+'\n')
            if dict_responseHeaders and app_name.split('_')[0]+"key" in dict_responseHeaders:
                app_key = dict_responseHeaders[app_name.split('_')[0]+"key"]
            if bool_isSuccess and not app_key.lower() in (app_name.split('_')[0], "0", ):
                reg_status = True
                AgentLogger.log(AgentLogger.APPS, "App {} is registered successfully | App id : {} | Registration Status : {} ". format(app_name, app_key, reg_status)+'\n')
            else:
                AgentLogger.log(AgentLogger.APPS, "App {} is not registered successfully  | App id : {} | Registration Status : {} ". format(app_name, app_key, reg_status)+'\n')
        else:
            reg_status = True
            AgentLogger.log(AgentLogger.APPS, "App {} is already registered | App id : {} | Registration Status : {} ". format(app_name, app_key, reg_status)+'\n')
    except Exception as e:
        AgentLogger.log(AgentLogger.APPS, "App {} is not registered successfully  | Registration Status : {} | Exception : {} ". format(app_name, reg_status, e)+'\n')
        traceback.print_exc()
    finally:
        return reg_status, app_key
    
@contextmanager
def handle_request(dict_data):
    try:
        resp_data = namedtuple("ResponseData", "bool_flag data headers status_code msg")
        proxy_handler = urllib.ProxyHandler(dict_data["proxies"])
        opener = urllib.build_opener(proxy_handler)
        opener.addheaders = dict_data["headers"]
        if dict_data["request_type"] == "get":
            resp = opener.open(dict_data["url"], timeout=100)
            resp_data.data = resp.read()
            resp_data.status_code = resp.getcode()
            resp_data.headers = dict(resp.headers)
            resp.close()
        elif dict_data["request_type"] == "post":
            resp = opener.open(dict_data["url"], dict_data["data"], timeout=100)
            resp_data.data = resp.read()
            resp_data.status_code = resp.getcode()
            resp_data.headers = dict(resp.headers)
            resp.close()
        else:
            resp_data.bool_flag = False
            resp_data.msg = "unsupported request type"
            
        if resp_data.status_code == 200:
            if resp_data.bool_flag:
                try:
                    resp_data.data = type_conversion(resp_data.data)[0]
                except Exception as e:
                    pass
        else:
            resp_data.bool_flag = False

    except Exception as e:
        resp_data.bool_flag = False
        resp_data.data = {}
        resp_data.msg = e
    finally:
        yield resp_data
        
def get_default_params():
    dict_data={}
    dict_data['proxies'] = {}
    dict_data["headers"] = {}
    dict_data["request_type"] = 'get'
    return dict_data

def mergeDict(metrics_dict): 
    super_dict = {}
    for d in metrics_dict:
        for k, v in metrics_dict[d].items():
            super_dict[k] = v            
    return super_dict

def suspend_application(dict_task):
    try:
        mtype = dict_task['mtype']
        if '_' in mtype:
            app_name = mtype.split('_')[1]
        else:
            app_name = mtype
        app_name = app_name.lower()
        conf_file_path=get_app_conf_file_path(app_name)
        app_conf_object = None
        with readconf_file(conf_file_path) as fp:
            app_conf_object, status, error_msg = fp
        if app_conf_object:
            app_conf_object[app_name]['enabled']=0
        scheduleInfo=AgentScheduler.ScheduleInfo()
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName(dict_task['mid'])
        AgentScheduler.deleteSchedule(scheduleInfo)
        with writeconf_file(conf_file_path, app_conf_object) as fp:
            _persist_status, _persist_error = fp
    except Exception as e:
        traceback.print_exc()
        
def delete_application(dict_task):
    try:
        mtype = dict_task['mtype']
        if '_' in mtype:
            app_name = mtype.split('_')[1]
        else:
            app_name = mtype
        app_name = app_name.lower()
        conf_file_path = os.path.join(AgentConstants.APPS_FOLDER,app_name.split('_')[0],app_name+".conf")
        app_conf_object = None
        with readconf_file(conf_file_path) as fp:
            app_conf_object, status, error_msg = fp
        if app_conf_object:
            app_conf_object[app_name]['enabled']=0
            app_conf_object[app_name]['mid']=0
        scheduleInfo=AgentScheduler.ScheduleInfo()
        scheduleInfo.setSchedulerName('AgentScheduler')
        scheduleInfo.setTaskName(dict_task['mid'])
        AgentScheduler.deleteSchedule(scheduleInfo)
        with writeconf_file(conf_file_path, app_conf_object) as fp:
            _persist_status, _persist_error = fp
        if app_name == AppConstants.namenode_app:
            for each in list(AppConstants.app_vs_mids):
                list_of_ids = AppConstants.app_vs_mids.pop(each)
                for id in list_of_ids:
                    scheduleInfo=AgentScheduler.ScheduleInfo()
                    scheduleInfo.setSchedulerName('AgentScheduler')
                    scheduleInfo.setTaskName(id)
                    AgentScheduler.deleteSchedule(scheduleInfo)
    except Exception as e:
        traceback.print_exc()

def activate_application(dict_task):
    try:
        mtype = dict_task['mtype']
        if '_' in mtype:
            app_name = mtype.split('_')[1]
        else:
            app_name = mtype
        app_name = app_name.lower()
        conf_file_path = os.path.join(AgentConstants.APPS_FOLDER,app_name.split('_')[0],app_name+".conf")
        app_conf_object = None
        with readconf_file(conf_file_path) as fp:
            app_conf_object, status, error_msg = fp
        if app_conf_object:
            app_conf_object[app_name]['enabled']=1
        with writeconf_file(conf_file_path, app_conf_object) as fp:
            _persist_status, _persist_error = fp
        temp_dict = {}
        temp_dict[app_name] = AppConstants.APPS_CLASS_VS_METHOD.pop(app_name)
        do_app_discovery(temp_dict)
    except Exception as e:
        traceback.print_exc()

def rediscover_application():
    AgentLogger.log(AgentLogger.APPS, "Rediscovering application")
    AgentConstants.APPS_CONFIG_DATA = {}
    FileUtil.deleteFile(AgentConstants.AGENT_APP_ID_FILE)
    do_app_discovery(AppConstants.APPS_CLASS_VS_METHOD, True)

def do_app_discovery(APPS_FOR_DISCOVERY,DISCOVERY_ARGS=None):
    for key,val in APPS_FOR_DISCOVERY.items():
        file_to_be_invoked = sys.modules[val['path']]
        method_name = val['method_name']
        dis_result=getattr(file_to_be_invoked,method_name)(DISCOVERY_ARGS)
        
def persist_apps_data(app_name,app_data,dir_prop):
    try:
        status, file_path = apps_data.save(dir_prop, app_data,AgentLogger.APPS)
        if dir_prop['instant_zip']:
            ZipUtil.zipFilesAtInstance([[file_path]], dir_prop)
        AgentLogger.log(AgentLogger.APPS, "{} app monitoring data collected | Persist Status : {} | File path : {}".format(app_name, status, file_path)+'\n')
    except Exception as e:
        AgentLogger.log(AgentLogger.APPS, "Exception while persisting {} app data collected |  Exception : {}".format(app_name, e))
                    
def get_error_data(app_name,pkey):
    error_data = {}
    try:
        error_data['mid']=-1
        error_data['availability']=0
        error_data['ct']=AgentUtil.getTimeInMillis()
        error_data['type']=app_name
        error_data['err']=AppConstants.API_FAILURE
        error_data['id']=pkey
    except Exception as e:
        traceback.print_exc()
    finally:
        return error_data

def update_a_content(content,content_file):
    myfile=None
    try:
        FileUtil.deleteFile(content_file)
        AgentUtil.create_file(content_file)
        if os.path.exists(content_file):
            with open(content_file, "a") as myfile:
                myfile.write(content)
    except Exception as e:
        traceback.print_exc()
    finally:
        if not myfile == None:
            myfile.close()
            
def read_a_content(content_file):
    myfile=None
    content=None
    try:
        if os.path.exists(content_file):
            with open(content_file, "r") as myfile:
                content = myfile.read()
    except Exception as e:
        traceback.print_exc()
    finally:
        if not myfile == None:
            myfile.close()
    return content

def update_app_id(app, dict_data):
    dict_data = dict_data if type(dict_data) is dict else json.loads(dict_data)
    s24x7_id_dict = {}
    s24x7_id_dict[app] = dict_data
    try:
        temp_dict ={}
        if os.path.isfile(AgentConstants.AGENT_APP_ID_FILE):
            with open(AgentConstants.AGENT_APP_ID_FILE, "r") as fp:
                temp_dict = json.loads(fp.read())
            if type(temp_dict) is dict:
                if app in temp_dict:
                    existing_dict = temp_dict[app]
                    existing_dict.update(dict_data)
                    temp_dict[app] = existing_dict
                else:
                    temp_dict[app] = dict_data
            s24x7_id_dict = temp_dict
        save_status = AgentUtil.writeDataToFile(AgentConstants.AGENT_APP_ID_FILE, s24x7_id_dict)
        if not save_status:
            AgentLogger.log(AgentLogger.APPS, "Unable to update id file")
    except Exception as e:
        traceback.print_exc()
        AgentLogger.log(AgentLogger.APPS, "Unable to update id file {}".format(e))

def read_app_id():
    try:
        if os.path.isfile(AgentConstants.AGENT_APP_ID_FILE):
            with open(AgentConstants.AGENT_APP_ID_FILE, "r") as fp:
                AgentConstants.APPS_CONFIG_DATA = json.loads(fp.read())
    except Exception as e:
        traceback.print_exc()

def invoke_app_only_update_config(args={}):
    global UACFG_VS_TASK
    if args and 'wait_interval' in args:
        time.sleep(args['wait_interval'])
    str_servlet = AgentConstants.AGENT_CONFIG_SERVLET
    dictRequestParameters = {}
    try:
        dictRequestParameters['CUSTOMERID'] = AgentConstants.CUSTOMER_ID
        dictRequestParameters['AGENTKEY'] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
        dictRequestParameters['bno'] = AgentConstants.AGENT_VERSION
        dictRequestParameters['apps_only'] = 'true'
        if not dictRequestParameters == None:
            str_requestParameters = urlencode(dictRequestParameters)
            str_url = str_servlet + str_requestParameters
        AgentLogger.log(AgentLogger.APPS,'================================= UPDATING APPS AGENT CONFIG DATA =================================\n')
        requestInfo = CommunicationHandler.RequestInfo()
        requestInfo.set_loggerName(AgentLogger.APPS)
        requestInfo.set_method(AgentConstants.HTTP_POST)
        requestInfo.set_url(str_url)
        requestInfo.add_header("Content-Type", 'application/json')
        requestInfo.add_header("Accept", "text/plain")
        requestInfo.add_header("Connection", 'close')
        (isSuccess, int_errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
        if isSuccess and dict_responseData:
            dictParsedData = json.loads(dict_responseData)
            AgentLogger.log(AgentLogger.APPS,'app only config data -- {}'.format(dictParsedData))
            if dictParsedData and 'apps' in dictParsedData: 
                update_app_config_data(dictParsedData)
        else:
            AgentLogger.log(AgentLogger.APPS,'app only config data failure \n')
    except Exception as e:
        traceback.print_exc()
    finally:
        if args:
            UACFG_VS_TASK = {}
            AgentLogger.log(AgentLogger.APPS,'========= UACFG_VS_TASK POST UPDATE ========'+repr(UACFG_VS_TASK))

def update_agent_apps_config():
    try:
        global UACFG_VS_TASK
        if not UACFG_VS_TASK:
            task = invoke_app_only_update_config
            taskArgs = {'wait_interval':60}
            scheduleInfo=AgentScheduler.ScheduleInfo()
            scheduleInfo.setSchedulerName('AgentScheduler')
            scheduleInfo.setTaskName('invoke_app_only_update_config')
            scheduleInfo.setTime(time.time())
            scheduleInfo.setTask(task)
            scheduleInfo.setTaskArgs(taskArgs)
            scheduleInfo.setLogger(AgentLogger.APPS)
            AgentScheduler.schedule(scheduleInfo)
            UACFG_VS_TASK['schedule']=scheduleInfo
            AgentLogger.log(AgentLogger.APPS,'========= UACFG_VS_TASK ========'+repr(UACFG_VS_TASK))
        else:
            AgentLogger.log(AgentLogger.APPS,'========= task running already =========')
    except Exception as e:
        traceback.print_exc()
        
def update_app_config_data(app_cfg_data):
    try:
        AgentConstants.APPS_CONFIG_DATA = app_cfg_data.get("apps")
        if "MYSQLDB" in AgentConstants.APPS_CONFIG_DATA:
            if 'com.manageengine.monagent.util.DatabaseUtil' in sys.modules:
                DatabaseUtil = sys.modules['com.manageengine.monagent.util.DatabaseUtil']
            else:
                from com.manageengine.monagent.util import DatabaseUtil
            DatabaseUtil.update_database_config_data('MYSQLDB', AgentConstants.APPS_CONFIG_DATA['MYSQLDB'])
                
        if "POSTGRESQL" in AgentConstants.APPS_CONFIG_DATA:
            from com.manageengine.monagent.database_executor.postgres import postgres_monitoring
            postgres_monitoring.update_database_config_data('POSTGRESQL', AgentConstants.APPS_CONFIG_DATA['POSTGRESQL'])
        
        if "ORACLE_DB" in AgentConstants.APPS_CONFIG_DATA:
            from com.manageengine.monagent.database_executor.oracle import oracledb_monitoring
            oracledb_monitoring.update_database_config_data(AgentConstants.ORACLE_DB, AgentConstants.APPS_CONFIG_DATA['ORACLE_DB'])

        if 'MYSQLNDB' in AgentConstants.APPS_CONFIG_DATA:
            from com.manageengine.monagent.database_executor.mysql import NDBCluster
            NDBCluster.UpdateConfigForNDB(AgentConstants.APPS_CONFIG_DATA['MYSQLNDB'])

        if "KUBERNETES" in AgentConstants.APPS_CONFIG_DATA:
            from com.manageengine.monagent.kubernetes.KubeUtil import update_kube_config_to_instant_discovery
            update_kube_config_to_instant_discovery(AgentConstants.APPS_CONFIG_DATA['KUBERNETES'])

        AgentUtil.writeDataToFile(AgentConstants.AGENT_APP_ID_FILE,AgentConstants.APPS_CONFIG_DATA)
    except Exception as e:
        traceback.print_exc()
