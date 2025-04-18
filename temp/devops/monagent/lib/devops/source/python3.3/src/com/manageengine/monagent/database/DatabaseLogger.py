import logging
import os
import time
import sys
import traceback
from logging import handlers

import com
from com.manageengine.monagent.database import DBConstants

# Global variable for LoggerUtil class object
# Used for logging in database_monitoring project code
Logger = None



# looger class for database project
# combine both logger [windows/linux] decided at starting
class LoggerUtil(object):
    def __init__(self,os_type,log_obj):
        try:
            # if windows communication_framework logger is assinged for logger
            if os_type == DBConstants.WINDOWS_AGENT:
                self.OS = os_type
                self.CommonLogger = log_obj
            # if linux AgentLogger is assigned for logger
            elif os_type == DBConstants.LINUX_AGENT:
                from com.manageengine.monagent.logger import AgentLogger
                self.OS = os_type
                self.CommonLogger = AgentLogger
        except Exception as e:
            traceback.print_exc()


    # method which writes the log
    def log(self,log_msg,file_name=None):
        try:
            if self.OS == DBConstants.WINDOWS_AGENT:
                self.CommonLogger.info(log_msg)
            elif self.OS == DBConstants.LINUX_AGENT:
                if file_name == 'QUERY':
                    self.CommonLogger.log(self.CommonLogger.QUERY,log_msg)
                else:
                    self.CommonLogger.log(self.CommonLogger.DATABASE,log_msg)
        except Exception as e:
            traceback.print_exc()


    # debug only works for linux, reads "debug"="1" in main agent, logger object directly imported
    def debug(self,log_msg,file_name=None):
        try:
            if self.OS == DBConstants.WINDOWS_AGENT:
                self.CommonLogger.info(log_msg)
            elif self.OS == DBConstants.LINUX_AGENT:
                if file_name:
                    self.CommonLogger.debug(self.CommonLogger.file_name,log_msg)
                else:
                    self.CommonLogger.debug(self.CommonLogger.DATABASE,log_msg)
        except Exception as e:
            traceback.print_exc()


# logger class initialization
def initialize(os_type,log_obj):
    try:
        global Logger
        Logger = LoggerUtil(os_type,log_obj)
    except Exception as e:
        traceback.print_exc()
