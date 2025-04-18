#$Id$
import os
import sys
import time
import traceback
import threading
import errno
import shutil
import re
import json
import collections
import socket
import random
from com.manageengine.monagent.thirdPartyFile import pyinotify
from collections import deque, OrderedDict
import copy
from six.moves.urllib.parse import urlencode
from operator import itemgetter

from com.manageengine.monagent import AgentConstants,module_object_holder
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.util import AgentUtil
from com.manageengine.monagent.util import AppUtil,DatabaseUtil
from com.manageengine.monagent.util.AgentUtil import ZipUtil
from com.manageengine.monagent.util.AgentUtil import FileUtil
from com.manageengine.monagent.util.AgentUtil import FileZipAndUploadInfo
from com.manageengine.monagent.util.rca.RcaHandler import RcaUtil, RcaInfo
from com.manageengine.monagent.communication import CommunicationHandler
from com.manageengine.monagent.docker_old.DockerAgent import DockerDataCollector
from com.manageengine.monagent.scheduler import AgentScheduler
from com.manageengine.monagent.util import AgentBuffer
from com.manageengine.monagent.util import AgentParser
import com.manageengine.monagent.network
from com.manageengine.monagent.actions import ScriptHandler

from com.manageengine.monagent.communication import UdpHandler
from com.manageengine.monagent.communication import BasicClientHandler
from com.manageengine.monagent.actions import ScriptMonitoring

from com.manageengine.monagent.collector import DataConsolidator , server_inventory , ps_util_metric_collector
from com.manageengine.monagent.hardware import HardwareMonitoring
from com.manageengine.monagent.hadoop import hadoop_monitoring
from com.manageengine.monagent.hadoop import zookeeper_monitoring
from com.manageengine.monagent.container import container_monitoring

from com.manageengine.monagent.database_executor.mysql    import mysql_monitoring
#from com.manageengine.monagent.database_executor.mongodb import mongodb_monitoring
from com.manageengine.monagent.database_executor.postgres import postgres_monitoring
from com.manageengine.monagent.database_executor.oracle   import oracledb_monitoring

FILE_LIST_TO_MONITOR=[AgentConstants.AGENT_CONF_DIR+'/mysql_input', AgentConstants.AGENT_CONF_DIR+'/mysql_remove',AgentConstants.AGENT_CONF_DIR+'/postgres_input', AgentConstants.AGENT_CONF_DIR+'/postgres_remove',AgentConstants.AGENT_CONF_DIR+'/oracle_input',AgentConstants.AGENT_CONF_DIR+'/oracle_update',AgentConstants.AGENT_CONF_DIR+'/oracle_remove',AgentConstants.AGENT_CONF_DIR+'/'+AgentConstants.db_ssl_config]
class DirectoryEventHandler(pyinotify.ProcessEvent):
    def process_IN_ACCESS(self, event):
        global FILE_LIST_TO_MONITOR
        if (str(event.pathname) in FILE_LIST_TO_MONITOR):
            AgentLogger.log(AgentLogger.CHECKS,'File IN_ACCESS :: {}'.format(event.pathname))

    def process_IN_ATTRIB(self, event):
        global FILE_LIST_TO_MONITOR
        if (str(event.pathname) in FILE_LIST_TO_MONITOR):
            AgentLogger.log(AgentLogger.CHECKS,'File IN_ATTRIB :: {}'.format(event.pathname))

    def process_IN_CLOSE_NOWRITE(self, event):
        global FILE_LIST_TO_MONITOR
        if (str(event.pathname) in FILE_LIST_TO_MONITOR):
            AgentLogger.log(AgentLogger.CHECKS,'File IN_CLOSE_NOWRITE :: {}'.format(event.pathname))

    def process_IN_CLOSE_WRITE(self, event):
        # AgentLogger.log(AgentLogger.DATABASE,'File IN_CLOSE_WRITE :: {}'.format(event.pathname))
        if ('mysql_input' in str(event.pathname)):# and AgentConstants.MYSQL_INIT:
            AgentLogger.log(AgentLogger.DATABASE,'File IN_CLOSE_WRITE :: {}'.format(event.pathname))
            # AgentConstants.DB_CONSTANTS[AgentConstants.MYSQL_DB]['ADD_INSTANCE_START_TIME'] = time.time()
            mysql_monitoring.initialize()
        if ('mysql_remove' in str(event.pathname)):
            DatabaseUtil.remove_sql_instance(AgentConstants.MYSQL_DB,True)
        if ('postgres_input' in str(event.pathname)):
            AgentLogger.log(AgentLogger.DATABASE,'File IN_CLOSE_WRITE :: {}'.format(event.pathname))
            # AgentConstants.DB_CONSTANTS[AgentConstants.POSTGRES_DB]['ADD_INSTANCE_START_TIME'] = time.time()
            postgres_monitoring.initialize()
        if ('postgres_remove' in str(event.pathname)):
            DatabaseUtil.remove_sql_instance(AgentConstants.POSTGRES_DB,True)
        if ('oracle_input' in str(event.pathname)):
            AgentLogger.log(AgentLogger.DATABASE,'File IN_CLOSE_WRITE :: {}'.format(event.pathname))
            # AgentConstants.DB_CONSTANTS[AgentConstants.ORACLE_DB]['ADD_INSTANCE_START_TIME'] = time.time()
            oracledb_monitoring.initialize()
        if ('oracle_update' in str(event.pathname)):
            oracledb_monitoring.update_oracle_library_path()
        if ('oracle_remove' in str(event.pathname)):
            DatabaseUtil.remove_sql_instance(AgentConstants.ORACLE_DB,True)
        if (AgentConstants.db_ssl_config in str(event.pathname)):
            AgentLogger.log(AgentLogger.DATABASE,'File IN_CLOSE_WRITE :: {}'.format(event.pathname))
            DatabaseUtil.db_ssl_config()

    def process_IN_CREATE(self, event):
        global FILE_LIST_TO_MONITOR
        if (str(event.pathname) in FILE_LIST_TO_MONITOR):
            AgentLogger.log(AgentLogger.CHECKS,'File IN_CREATE :: {}'.format(event.pathname))

    def process_IN_DELETE(self, event):
        global FILE_LIST_TO_MONITOR
        if (str(event.pathname) in FILE_LIST_TO_MONITOR):
            AgentLogger.log(AgentLogger.CHECKS,'File IN_DELETE :: {}'.format(event.pathname))

    def process_IN_MODIFY(self, event):
        global FILE_LIST_TO_MONITOR
        if (str(event.pathname) in FILE_LIST_TO_MONITOR):
            AgentLogger.log(AgentLogger.CHECKS,'File IN_MODIFY :: {}'.format(event.pathname))

    def process_IN_OPEN(self, event):
        global FILE_LIST_TO_MONITOR
        if (str(event.pathname) in FILE_LIST_TO_MONITOR):
            AgentLogger.log(AgentLogger.CHECKS,'File IN_OPEN :: {}'.format(event.pathname))


class FileChangeNotify(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.watch_manager = None
        self.event_handler = None
        self.notifier = None

    def stop_watch_manager(self):
        if self.notifier:
            self.notifier.stop()

    def run(self):
        try:
            self.initialize()
        except Exception as e:
            AgentLogger.log(AgentLogger.CHECKS,' ************************** Exception while starting file change notifier thread **************************** ')
            traceback.print_exc()

    def initialize(self):
        try:
            self.watch_manager = pyinotify.WatchManager()
            self.watch_manager.add_watch(AgentConstants.AGENT_CONF_DIR, pyinotify.ALL_EVENTS)
            self.event_handler = DirectoryEventHandler()
            self.notifier = pyinotify.Notifier(self.watch_manager, self.event_handler)
            self.notifier.loop()
        except Exception as e:
            AgentLogger.log(AgentLogger.CHECKS,' ************************** Exception while initializing file change notifier **************************** ')
            traceback.print_exc()


def initialize():
    try:
        pynotify_obj = FileChangeNotify()
        pynotify_obj.setDaemon(True)
        pynotify_obj.start()
    except Exception as e:
        AgentLogger.log(AgentLogger.STDOUT,'***** Exception while initializing FileChangeNotifier ***** :: {}'.format(e))
        traceback.print_exc()
#if sys.argv[0]:
#    AgentLogger.log(AgentLogger.MAIN,'Param pass check print :: {} : {} .\n'.format(len(sys.argv), sys.argv))
#    if len(sys.argv) > 1:
#        if sys.argv[1]:
#            AgentLogger.log(AgentLogger.MAIN,'feature request accepted :: {}'.format('jil jung jug'))
