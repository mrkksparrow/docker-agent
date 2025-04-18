'''
Created on 04-July-2017

@author: giri
'''

from com.manageengine.monagent.framework.actions.actions_mind import Actions
from com.manageengine.monagent.framework.suite.custom_dict import CustomDict
from com.manageengine.monagent.framework.suite.helper import handle_request
from com.manageengine.monagent.framework.suite.helper import get_value_from_dict
from com.manageengine.monagent.framework.suite.helper import eval_expression
from com.manageengine.monagent.framework.suite.helper import s247_commandexecutor
from com.manageengine.monagent.framework.suite.helper import type_conversion
import json
import traceback
import re
import ast
import shlex 
from functools import partial

class CommandApi(Actions):
    def __init__(self, metric_contents, result_dict, category_name, conf_dict, output_xml):
        self.metric_contents = metric_contents
        self.category_name = category_name
        self.result_dict = result_dict
        self.conf_dict = conf_dict
        self.jobs = []
    
    @property
    def response_type(self):
        try:
            _response_type = "str"
            if "@response_type" in self.metric_contents:
                if type(self.metric_contents["@response_type"]) is str:
                    _response_type = self.metric_contents["@response_type"]                
        except Exception as e:
            pass
        finally:
            return _response_type
    
    @property
    def command(self):
        try:
            _command = None
            if "@cmd" in self.metric_contents:
                _command = self.metric_contents["@cmd"] if type(self.metric_contents["@cmd"]) is str\
                            and "|" in self.metric_contents["@cmd"] else shlex.split(self.metric_contents["@cmd"]) if type(self.metric_contents["@cmd"]) is str \
                            and not "|" in self.metric_contents["@cmd"] else []
        except Exception as e:
            print(e)
        finally:
            return _command
    
    @property
    def ignore_lines(self):
        try:
            _ignore_lines = []
            if "@ignore_lines" in self.metric_contents:
                conv_ignore_lines, *conv_metadata = type_conversion(self.metric_contents["@ignore_lines"])
                _ignore_lines = conv_ignore_lines if type(conv_ignore_lines) in [list, tuple] else [self.metric_contents["@ignore_lines"]]\
                                if type(conv_ignore_lines) is int else []
        except Exception as e:
            _ignore_lines = [self.metric_contents["@ignore_lines"]]
        finally:
            return _ignore_lines
    
    @property
    def delimiter(self):
        _delimiter = self.metric_contents["@delimiter"] if "@delimiter" in self.metric_contents else ' '
        return _delimiter
    
    @property
    def split(self):
        _split = type_conversion(self.metric_contents["@split"] if "@split" in self.metric_contents else -1)[0]
        return _split
        
    def construct_dict(self, iter_var=None):
        worker_dict = CustomDict(self.conf_dict, self.result_dict, dict_type="commandapi", iter_var=iter_var)
        worker_dict["metrics_id"] = self.metrics_id
        worker_dict["command"] = self.command
        worker_dict["timeout"] = self.timeout
        worker_dict["storevalue"] = self.storevalue
        worker_dict["split"] = self.split
        worker_dict["delimiter"] = self.delimiter
        worker_dict["Metric"] = self.metric_list
        worker_dict["ignore_lines"] = self.ignore_lines
        worker_dict["response_type"] = self.response_type
        worker_dict["data"] = ""
        return worker_dict
    
    def load(self):
        if not self.is_iter:
           self.jobs.append(self.construct_dict(iter_var=None)) 
        else:
            for iter_var in self.iter_var:
                self.jobs.append(self.construct_dict(iter_var=iter_var)) 
    
    def work(self):
        for worker_dict in self.jobs:
            with s247_commandexecutor(worker_dict) as resp:
                _output, *_output_metadata = resp
            self.update_result(_output, worker_dict)        
                
    def update_result(self, _output, worker_dict):
        try:
            self.result_dict[self.category_name][worker_dict["metrics_id"]]={}
            if type(_output) is str:
                #load ignore_lines, and then split 
                _output = self.do_split_ignorelines(_output)
                for ind_metric in worker_dict["Metric"]:
                    _iter_output = iter(_output)
                    type_conv_format_value, *conv_format_value_metadata = type_conversion(ind_metric["@format"]) if "@format" in ind_metric else {}
                    type_conv_append_value, *conv_append_value_metadata = type_conversion(ind_metric["@append"]) if "@append" in ind_metric else False
                    self.result_dict[self.category_name][worker_dict["metrics_id"]][ind_metric["@id"]] = self.format_dict_value(ind_metric["@format"], _iter_output, _output, \
                                                                                                         append=type_conv_append_value) 
        except Exception as e:
            print(e)
            traceback.print_exc()
        finally:
            pass
   
    def format_dict_value(self, type_conv_format_value, _iter_output, _output, append):

        def token_replace_func(match, line=[], _output=[]):
            line_no = match.groupdict().get("line_no", None)
            token_no = match.groupdict().get("token_no", None)
            if line_no and token_no:
                line = _output[int(line_no)-1][int(token_no)-1]
            elif line_no:
                line = _output[int(line_no)-1]
            elif token_no:
                line = line[int(token_no)-1]
            return line
        
        format_regex = re.compile("(\$(?P<template_content>.*?)\$)")
        format_token_regex = re.compile("token=(?P<template_value>\d+)", re.IGNORECASE)
        if append:
            _appended_output = []
            for line in _iter_output:
                _appended_output.append(type_conversion(re.sub(r'\$token=(?P<token_no>\d+)\$', partial(token_replace_func, line=line, _output=_output), type_conv_format_value))[0])
        
            
#             format_output = {}
#             for key, value in type_conv_format_value.items():
#                 line_value, token_value = None, None
#                 matcher = format_regex.search(value)
#                 if matcher:
#                     template_content = matcher.groupdict()["template_content"]
#                 matcher = format_token_regex.search(template_content)
#                 if matcher:
#                     token_value = matcher.groupdict()["template_value"]
#                 if token_value:
#                     format_output[key] = line[int(token_value)-1]
#                 else:
#                     format_output[key] = line
        return _appended_output
            
    def do_split_ignorelines(self, _output):
        #ignore lines
        _output = _output.split("\n")
        for line_no in self.ignore_lines:
            if len(_output) >= line_no-1:
                _output[line_no-1] = ''
        _output = list(filter(None, _output))
        #split each line
        splitted_lines = []
        for line in _output:
            line = re.sub("\s+"," ", line)
            line = line.strip().split(' ', self.split) if not self.split == -1 and type(self.split) is int else line.split()
            splitted_lines.append(line)
        return splitted_lines
      