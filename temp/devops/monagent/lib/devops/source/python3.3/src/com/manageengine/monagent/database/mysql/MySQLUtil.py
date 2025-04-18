import json
import time
import traceback , os, re

try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

import six.moves.urllib.request as urlconnection
from six.moves.urllib.parse import urlencode


from com.manageengine.monagent.database import DatabaseLogger, DBUtil, DBConstants
from com.manageengine.monagent.database.mysql import MySQLConstants


# mysql executor class, all data collection used this class to get mysql connection and execute query
class MySQLConnector(object):
    def init(self,input_dict):
        try:
            # input data for database connection from python
            self.instance                        = input_dict['instance']
            self.host                            = input_dict['host']
            self.user                            = input_dict['user']
            self.port                            = input_dict['port']
            self.mid                             = input_dict['mid']
            self.time_diff                       = input_dict['time_diff'] if 'time_diff' in input_dict else 0
            self.collection_type                 = input_dict['collection_type']
            self.password                        = input_dict['password'] if input_dict['password'] != 'None' else ''
            self.section_info                    = input_dict

            self.connection                      = None
            self.cursor                          = None
            self.version                         = None

            self.is_connected                    = False
            self.error                           = False
            self.error_msg                       = None

            self.total_execution_time            = 0

            self.final_data                      = {}

            if "Version" in input_dict:
                self.version                     = input_dict['Version']
            else:
                self.get_db_connection()
                self.version                     = self.connection.server_version
                self.close_db_connection()
            self.is_mariadb                      = True if "-mariadb" in self.version else False
            self.float_version                   = 0
            _version = re.search("\d+(\.\d+)*",self.version)
            if _version:
                self.float_version=float(_version.group().replace(",","").replace(".",",",1).replace(".","").replace(",","."))

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while initialising MySQL Util Class :: {}'.format(e))
            traceback.print_exc()


    # create connection with database and initialize mysql cursor
    def get_db_connection(self):
        try:
            connection_status, connection    = DBUtil.getConnection(self.section_info,DBConstants.MYSQL_DATABASE)
            if connection_status:
                self.connection    = connection
                self.cursor        = self.connection.cursor()
                self.is_connected  = True
            else:
                self.error         = True
                self.error_msg     = str(connection)
        except Exception as e:
            self.is_connected  = False
            self.error     = True
            self.error_msg = str(e)
            DatabaseLogger.Logger.log('Exception while getting database connection :: {} : Type-{} : Error-{}'.format(self.instance,self.collection_type,e))
            traceback.print_exc()
        finally:
            return self.is_connected, self.error_msg


    # close connection with database and kill mysql cursor created
    def close_db_connection(self):
        try:
            self.cursor.close()
            self.connection.close()
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while closing database connection :: {} : {}'.format(self.instance,e))
            traceback.print_exc()


    # mysql version is collected from show variables query, which is later used for version specific data collection
    def get_mysql_version(self):
        is_success = False
        try:
            is_success,output_list,self.error_msg = self.execute_mysql_query(MySQLConstants.MYSQL_VERSION_QUERY)
            if is_success and output_list:
                for each in output_list:
                    if "-" in each[1]:
                        self.version = each[1].split("-")[0]
                    else:
                        self.version = each[1]
                    if (each[1] or "").lower().find("mariadb") != -1:
                        self.version = self.version + "-mariadb"
                    break
        except Exception as e:
            self.error = True
            self.error_msg = str(e)
            DatabaseLogger.Logger.log('Exception while getting mysql version: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return is_success, self.version, self.error_msg


    # mysql query executed and list is output is returned as list [fetchall]
    def execute_mysql_query(self,query):
        is_executed = False
        output_list = None
        try:
            start_time                  = time.time()
            self.cursor.execute(query)
            end_time                    = time.time()
            output_list                 = self.cursor.fetchall()
            self.total_execution_time   = self.total_execution_time + float(end_time-start_time)
            is_executed                 = True
            DatabaseLogger.Logger.log('Query Executed :: Total - ({:.4f})sec :: Time - ({:.4f})sec :: Query - {}'.format(self.total_execution_time,(end_time-start_time),query),'QUERY')
        except Exception as e:
            self.error = True
            self.error_msg = str(e)
            DatabaseLogger.Logger.log('Exception while executing mysql query: {} : {} : {}'.format(self.instance,query,e))
            traceback.print_exc()
        return is_executed, output_list, self.error_msg


    # master/slave status query executed and output returned
    # separate method because used in 2 places, basic data collection and one day replication status data collection
    def collect_master_slave_status(self):
        is_m_success    = False
        is_s_success    = False
        master_status   = None
        slave_status    = None
        try:
            if not self.float_version or self.float_version < 8.4 or (self.is_mariadb and self.float_version < 10.52):
                is_m_success,master_status,self.error_msg  = self.execute_mysql_query(MySQLConstants.MYSQL_REPLICATION_MASTER_STATUS_QUERY)    # show master status
                is_s_success,slave_status,self.error_msg   = self.execute_mysql_query(MySQLConstants.MYSQL_REPLICATION_SLAVE_STATUS_QUERY)     # show slave status or show replica status
            else:
                is_m_success,master_status,self.error_msg  = self.execute_mysql_query(MySQLConstants.MYSQL_REPLICATION_BINARY_LOG_STATUS_QUERY)    # show master status
                is_s_success,slave_status,self.error_msg   = self.execute_mysql_query(MySQLConstants.MYSQL_REPLICATION_REPLICA_STATUS_QUERY)     # show slave status or show replica status
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while executing master/slave status query :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return is_m_success and is_s_success, master_status, slave_status, self.error_msg


    # decide whether the instance is master or slave with master/slave status
    def decide_instance_type(self,master_status,slave_status):
        replication_enabled  = False
        instance_type        = None
        try:
            # deciding whether mysql instance is master or slave or standalone
            if not master_status and not slave_status:
                replication_enabled                        = False                              # no master or slave status, so instance must be standalone
                instance_type                              = 'STANDALONE'
            elif (master_status and not slave_status):
                replication_enabled                        = True
                instance_type                              = "MASTER"
            elif master_status and slave_status:   # master master replication
                replication_enabled                        = True
                instance_type                              = "MASTER"
            elif not master_status and slave_status:
                replication_enabled                        = True
                instance_type                              = 'SLAVE'
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while deciding whether the instance is master/slave/standalone :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return replication_enabled,instance_type


    # method to get current time in milli seconds
    def getTimeInMillis(self,timeDiff):
        ''' With time_diff by default '''

        toReturn = None
        try:
            toReturn = round((time.time()*1000)+float(timeDiff))
            DatabaseLogger.Logger.debug('Time in millis returned : '+repr(toReturn)+' ----> '+repr(time.asctime(time.localtime(float(toReturn)/1000))))
        except Exception as e:
            DatabaseLogger.Logger.log(' ************************* Exception while calculating time based on time diff ************************* '+ repr(e))
            traceback.print_exc()
            toReturn = round(time.time()*1000)
        finally:
            if not toReturn is None:
                toReturn = int(toReturn)
        return toReturn

def check_mysql_connection(dict_param):
    conn_success = False
    err_msg = None
    try:
        try:
            connection_status, connection = DBUtil.getConnection(dict_param,DBConstants.MYSQL_DATABASE)
            if connection_status:
                cursor     = connection.cursor()
                conn_success = True
                cursor.close()
                connection.close()
            else:
                err_msg = str(connection)
        except Exception as e:
            conn_success = False
            err_msg = str(e)
            DatabaseLogger.Logger.log('========== agent could not connect to mysql instance :: {} ========== '+ repr(e))
    except Exception as e:
        conn_success = False
        err_msg = str(e)
        DatabaseLogger.Logger.log(' ************************* Exception while checking connection for MySQL Instance :: {} ************************* '+ repr(e))
        traceback.print_exc()
    finally:
        return conn_success, err_msg

def getTimeInMillis(timeDiff):
    ''' With time_diff by default '''

    toReturn = None
    try:
        toReturn = round((time.time()*1000)+float(timeDiff))
        DatabaseLogger.Logger.debug('Time in millis returned : '+repr(toReturn)+' ----> '+repr(time.asctime(time.localtime(float(toReturn)/1000))))
    except Exception as e:
        DatabaseLogger.Logger.log(' ************************* Exception while calculating time based on time diff outside  ************************* '+ repr(e))
        traceback.print_exc()
        toReturn = round(time.time()*1000)
    finally:
        if not toReturn is None:
            toReturn = int(toReturn)
    return toReturn