#To read configuration file
import traceback
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser
import logging
import os
from com.manageengine.monagent.metrics import metrics_constants
from com.manageengine.monagent.metrics import metrics_logger

#To Read configuration files
def get_config_data(conf_file):
    config=False
    try:
        config=configparser.RawConfigParser()
        config.optionxform=lambda option: option
        config.read(conf_file)
    except Exception as e:
        metrics_logger.errlog('Exception While reading conf file : {}'.format(e))
    finally:
        return config