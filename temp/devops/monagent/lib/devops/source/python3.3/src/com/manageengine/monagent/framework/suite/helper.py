'''
Created on 02-July-2017

@author: giri
'''

import json
import os
from contextlib import contextmanager
import traceback
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser
import re
from functools import reduce
from functools import partial
import operator 
import ast
import subprocess
import time,sys
import getpass
from pwd import getpwnam
from types import ModuleType
from types import FunctionType
from collections import namedtuple
from six.moves.urllib.parse import urlencode
import six.moves.urllib.request as urllib
from datetime import datetime
#s24x7 packages
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent import AgentConstants
from com.manageengine.monagent.framework.suite import id_guard

if 'com.manageengine.monagent.communication.CommunicationHandler' in sys.modules:
    CommunicationHandler = sys.modules['com.manageengine.monagent.communication.CommunicationHandler']
else:
    from com.manageengine.monagent.communication import CommunicationHandler

current_milli_time = lambda: int(round(time.time() * 1000))

def get_user_id(username=None):
    try:
        username = getpass.getuser() if username is None else username
        uid = getpwnam(username).pw_uid
    except KeyError as ke:
        uid = username
    except Exception as e:
        uid = username
    finally:
        return uid
        
def get_value_from_dict(data_dict, metric_position):
    _success_flag, _metric_value, _msg = False, None, ''
    try:
        map_list = re.split(r'(?<!\\)\.', metric_position)
        new_list = []
        for ele in map_list:
            try:
                new_list.append(int(ele))
            except Exception as e:
                ele = ele.replace("\\", "")
                new_list.append(ele)
        _metric_value = reduce(operator.getitem, new_list, data_dict)
        _success_flag = True
        _metric_value = type_conversion(_metric_value)[0]
    except Exception as e:
        _metric_value = "-"
    finally:
        return _success_flag, _metric_value, _msg
    
def eval_expression(metric_expression, do_templating=False, result_dict={}, conf_dict={}, metadata={}, iter_dict={}):
    _success_flag, _metric_value, _msg = False, metric_expression, ''
    _metric_value = manage_template(metric_expression, result_dict=result_dict, conf_dict=conf_dict, metadata_dict=metadata, iter_dict=iter_dict, get_variablename=True)
    try:
        _metric_value = _metric_value.replace("\\n","\n")
        _metric_value = _metric_value.replace("\\t","\t")
        exec(_metric_value if re.match("^contents=", _metric_value) else "contents="+_metric_value)
        _metric_value = locals()["contents"]
    except Exception as e:
        _metric_value = "-"
    finally:
        return _success_flag, _metric_value, _msg
    
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

@contextmanager
def read_file(file_path):
    try:
        with open(file_path, 'r') as fp:
            content = fp.read()
        success_flag, error = True, ''
    except Exception as e:
        content, success_flag, error = '', False, e
    finally:
        yield content, success_flag, error

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

def replace_template_with_dict(template_regex, dict_content={}, value=None, dict_type=None, get_variablename=False):
    try:
        success_flag, repl_value, msg = False, value, ''
        def replace_func(match):
            success_flag = True
            #bool_flag, *meta_data = False,
            bool_flag = False
            replace_dollars = re.sub(template_regex, r'\1', match.group())
            if get_variablename is True:
                replace_dots = re.split(r'(?<!\\)\.', replace_dollars)
                final_var = dict_type
                for i in replace_dots:
                    final_var += '["'+i+'"]'
                #bool_flag, *meta_data = True, final_var
                meta_data = [True, final_var]
            else:
                #bool_flag, *meta_data = get_value_from_dict(dict_content, replace_dollars)
                meta_data = get_value_from_dict(dict_content, replace_dollars)
            if meta_data[0]:
                return meta_data[1] if type(meta_data[1]) is str else str(meta_data[1])
                    
            else:
                return match.group()
        
        repl_value = re.sub(template_regex, replace_func, value)
        
    except Exception as e:
        AgentLogger.debug(AgentLogger.FRAMEWORK, "sasasas {} | {} | {}".format(template_regex, value, type(value)))
        traceback.print_exc()
        success_flag, repl_value, msg = False, value, e
    finally:
        return success_flag, repl_value, msg

def replace_template_with_any(template_regex, dict_content={}, value=None):
    try:
        success_flag, repl_value, msg = False, value, ''
        matcher = re.search(template_regex, value)
        if matcher:
            template_content = matcher.groupdict()["template_content"]
            template_content_list =  re.split(r'(?<!\\)\.', template_content)
            if template_content_list:
                #attr_name, *attr = template_content_list
                AgentLogger.debug(AgentLogger.FRAMEWORK, "dsffdsfdsdfsfdsf {}".format(template_content_list))
                attr_name, attr = template_content_list[0], template_content_list[1:]
                loaded_attr = locals()[attr_name] if attr_name in locals() else None if not attr_name in globals() else globals()[attr_name]
                if type(loaded_attr) is ModuleType:
                    success_flag = True
                    msg = '' if hasattr(loaded_attr, attr[0]) else '{} not present in module {}'.format(attr[0], attr_name)
                    repl_value = getattr(loaded_attr, attr[0]) if hasattr(loaded_attr, attr[0]) else value
                    if type(repl_value) is FunctionType:
                        repl_value = repl_value()
                elif type(loaded_attr) is dict:
                    repl_value = get_value_from_dict(loaded_attr, '.'.join(attr))
                    success_flag = True
                 
    except Exception as e:
        success_flag, repl_value, msg = False, value, e
    finally:
        return success_flag, repl_value, msg

call_templating = lambda func, dict_content, value : func(dict_content=dict_content, value=value)

def load_template(get_variablename=False):
    conf_template = partial(replace_template_with_dict, "\${3}([\w.]+?)\${3}", dict_type="conf_dict", get_variablename=get_variablename)
    iter_template = partial(replace_template_with_dict, "\${2}(?P<template_content>it?)\${2}", dict_type="iter_dict", get_variablename=get_variablename)
    ancestor_template = partial(replace_template_with_dict, "\${2}(?P<template_content>[\w.]+?)\${2}", dict_type="result_dict", get_variablename=get_variablename)
    var_template = partial(replace_template_with_any, "(\${1}(?P<template_content>[\w.]+?)\${1})")
    return conf_template, iter_template, ancestor_template, var_template
    
def manage_template(value, result_dict={}, conf_dict={}, iter_dict={}, metadata_dict={}, get_variablename=False):
    try:
        if get_variablename:
            templates = load_template(get_variablename=get_variablename)
        else:
            templates = load_template()
        dict_list = [conf_dict, iter_dict, result_dict, metadata_dict]
        for fun_templates, dict_cont in zip(templates, dict_list): 
            bool_flag, value, msg = call_templating(fun_templates, dict_content=dict_cont, value=value)
            if bool_flag:
                break
    except Exception as e:
        value = "-"
    finally:
        return value

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
        
def timeit(func):

    def timed(*args, **kwargs):
        ts = time.time()
        result = func(*args, **kwargs)
        te = time.time()
        print ('%r (%r, %r) %2.2f sec' % \
              (func.__name__, args, kwargs, te-ts))
        return result

    return timed

def get_default_reg_params():
    request_params = {}
    request_params["agentKey"] = AgentUtil.AGENT_CONFIG.get('AGENT_INFO', 'agent_key')
    request_params['CUSTOMERID'] = AgentConstants.CUSTOMER_ID
    request_params['bno'] = AgentConstants.AGENT_VERSION
    request_params['REDISCOVER'] = "TRUE"
    return request_params

get_app_conf_file_path = lambda app_name: os.path.join(AgentConstants.APPS_FOLDER, app_name.split("_")[0]+".conf")

def apps_registration(app_name, requset_params={}):
    reg_status, app_key = False, None
    try:
        parent_app_name = app_name.split("_")[0]
        with readconf_file(get_app_conf_file_path(parent_app_name)) as fp:
            content, status, error_msg = fp
        app_key = content[parent_app_name]["mid"] if "mid" in content[parent_app_name] else "0" if parent_app_name in content else "0"
        if app_key.lower() in (parent_app_name, "0", ):
            if requset_params:
                str_requestParameters = urlencode(requset_params)
                str_url = AgentConstants.APPLICATION_DISCOVERY_SERVLET + str_requestParameters
                AgentLogger.log(AgentLogger.APPS, "app registration call {}".format(str_url))
            requestInfo = CommunicationHandler.RequestInfo()
            requestInfo.set_loggerName(AgentLogger.STDOUT)
            requestInfo.set_method(AgentConstants.HTTP_GET)
            requestInfo.set_url(str_url)
            requestInfo.set_dataType('application/json')
            requestInfo.add_header("Content-Type", 'application/json')
            requestInfo.add_header("Accept", "text/plain")
            requestInfo.add_header("Connection", 'close')
            (bool_isSuccess, errorCode, dict_responseHeaders, dict_responseData) = CommunicationHandler.sendRequest(requestInfo)
            if dict_responseHeaders and parent_app_name+"key" in dict_responseHeaders:
                app_key = dict_responseHeaders[parent_app_name+"key"]
            if bool_isSuccess and not app_key.lower() in (parent_app_name, "0", ):
                reg_status = True
                AgentLogger.log(AgentLogger.APPS, "App {} is registered successfully | App id : {} | Registration Status : {} ". format(parent_app_name, app_key, reg_status))
            else:
                AgentLogger.log(AgentLogger.APPS, "App {} is not registered successfully  | App id : {} | Registration Status : {} ". format(parent_app_name, app_key, reg_status))
        else:
            reg_status = True
            AgentLogger.log(AgentLogger.APPS, "App {} is already registered | App id : {} | Registration Status : {} ". format(parent_app_name, app_key, reg_status))
    except Exception as e:
        AgentLogger.log(AgentLogger.APPS, "App {} is not registered successfully  | Registration Status : {} | Exception : {} ". format(parent_app_name, reg_status, e))
        traceback.print_exc()
    finally:
        return reg_status, app_key
    
def iso_to_millis(iso_datetime):
    if "." in iso_datetime:
        iso_datetime = iso_datetime.split(".")[0]
    else:
        iso_datetime = iso_datetime.split("Z")[0]
    utc_time = datetime.strptime(iso_datetime, "%Y-%m-%dT%H:%M:%S")         
    epoch_time = (utc_time - datetime(1970, 1, 1)).total_seconds()
    return epoch_time*1000

def handle_counter_values(curr_value_dict, prev_value_dict):
    try:
        temp_prev_dict = curr_value_dict.copy()
        for key in curr_value_dict:
            if key not in prev_value_dict:
                del temp_prev_dict[key]
        for key, val in prev_value_dict.items():
            curr_value_dict[key] = str(int(float(curr_value_dict[key])) - int(float(val)))
        prev_value_dict.update(temp_prev_dict)
    except Exception as e:
        traceback.print_exc()
    
