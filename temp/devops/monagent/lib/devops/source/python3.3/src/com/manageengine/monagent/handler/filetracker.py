'''
Created on 20-Sep-2017

@author: giri
'''

import traceback
import json
from com.manageengine.monagent import AgentConstants

try:
    import configparser
except Exception as e:
    import ConfigParser as configparser
import os
#s24x7 packages
from com.manageengine.monagent.logger import AgentLogger

def read_id(key, filepath):
    id_dict = {}
    try:
        with open(filepath, "r") as fp:
            data = fp.read()
        id_dict = json.loads(data)
    except Exception as e:
        id_dict = {}
    finally:
        return id_dict.get(key, {})

def write_config(file_size_dict, filepath):
    try:
        config = configparser.RawConfigParser()
        config.read(filepath)
        for section in file_size_dict:
            for key,value in file_size_dict[section].items():
                config.set(section, str(key), value)
        with open(filepath, 'w') as configfile:
            config.write(configfile)
    except Exception as e:
        AgentLogger.log(AgentLogger.APPS, "{} Exception while saving data".format(e))
        traceback.print_exc()

def migrate_site24x7id(filepath):
    id_dict = {}
    try:
        with open(filepath, "r") as fp:
            data = fp.read()
        id_dict = json.loads(data)
        if AgentConstants.PYTHON_VERSION == 2:
            if type(id_dict) is unicode and not "docker" in id_dict:   
                id_dict = json.loads(id_dict)
        else:
            if type(id_dict) is str and not "docker" in id_dict:   
                id_dict = json.loads(id_dict)
    except Exception as e:
        id_dict = {}
    finally:
        return id_dict
