import json
import time
import sys
import re

import traceback , os
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

import six.moves.urllib.request as urlconnection
from six.moves.urllib.parse import urlencode

#from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent.database                                         import DatabaseLogger, DBConstants
from com.manageengine.monagent.database.oracle                                  import OracleCollector
from com.manageengine.monagent.database.postgres                                import PostgresCollector
from com.manageengine.monagent.database.mysql.DataCollector                     import MySQLCollector
from com.manageengine.monagent.database.mysql.cluster.ndbcluster.DataCollector  import NDBCollector



# First method called from [Linux/Windows] 
# if windows agent contains log_obj to write log
# if linux agent imports AgentLogger from main agent
def initialize(dict_param,log_obj=None):
    result_dict = {}
    try:
        # initialize logger as common for both linux and windows agent
        if dict_param['os'] == DBConstants.LINUX_AGENT:
            DatabaseLogger.initialize(DBConstants.LINUX_AGENT,None)
        elif dict_param['os'] == DBConstants.WINDOWS_AGENT:
            DatabaseLogger.initialize(DBConstants.WINDOWS_AGENT,log_obj)
            log_obj.info("dict param check :: {}")

        # check for which database application the call occoured [mysql]
        # call DataCollection class for respective application
        DatabaseLogger.Logger.debug('Database Executor received Input Dict :: {}'.format(dict_param))
        if 'application' in dict_param:
            if dict_param['application'] == DBConstants.MYSQL_DATABASE:
                mysql_obj       =   MySQLCollector()
                mysql_obj.init(dict_param)
                result_dict     =   mysql_obj.collect_mysql_data(dict_param)
            elif dict_param['application'] == DBConstants.MYSQL_NDB_CLUSTER:
                ndb_obj         =   NDBCollector()
                result_dict     =   ndb_obj.collect_ndb_data(dict_param)
            elif dict_param['application'] == DBConstants.POSTGRES_DATABASE:
                result_dict     =   PostgresCollector.collect_postgres_data(dict_param)
            elif dict_param['application'] == DBConstants.ORACLE_DATABASE:
                result_dict     =   OracleCollector.collect_data(dict_param)
                
    except Exception as e:
        DatabaseLogger.Logger.log('Exception while initializing Database agent Executor class :: {}'.format(e))
        traceback.print_exc()
    
    finally:
        # sent to the main agent
        return result_dict
