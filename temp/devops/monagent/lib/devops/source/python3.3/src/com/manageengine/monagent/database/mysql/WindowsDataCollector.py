import json
import time
import traceback , os
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

import six.moves.urllib.request as urlconnection
from six.moves.urllib.parse import urlencode


from com.manageengine.monagent.database import DatabaseLogger
from com.manageengine.monagent.database.mysql import MySQLConstants,MySQLUtil

class WindowsADCMetrics(object):
    def init(self, input_param):
        try:
            self.mysql_util_obj = MySQLUtil.MySQLConnector()
            self.mysql_util_obj.init(input_param)
            self.instance                    = input_param['instance']
            self.mid                         = input_param['mid']
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while initialising Windows ADC Data Collector Class :: {} : {}'.format(self.instance,e))
            traceback.print_exc()

    def collect_windows_adc_metrics(self):
        result_data = {}
        is_success = True
        err_msg = None
        try:
            is_success, err_msg = self.mysql_util_obj.get_db_connection()
            is_success, version, err_msg = self.mysql_util_obj.get_mysql_version()
            MySQLConstants.set_query_for_data_collection(version)

            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_WINDOWS_COMMON_VARIABLES_QUERY)
            if is_success:
                for variable in output_list:
                    if variable[0] == 'server_uuid':
                        result_data['uuid'] = str(variable[1])
                    if variable[0] == 'version':
                        result_data['Version'] = str(variable[1])

            is_success ,master_status, slave_status, err_msg = self.mysql_util_obj.collect_master_slave_status()
            if is_success:
                replication_enabled,instance_type = self.mysql_util_obj.decide_instance_type(master_status,slave_status)
                result_data['instance_type'] = instance_type

            self.mysql_util_obj.close_db_connection()
        except Exception as e:
            is_success = False
            err_msg = str(e)
            DatabaseLogger.Logger.log('Exception while collecting database list :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return is_success, result_data, err_msg