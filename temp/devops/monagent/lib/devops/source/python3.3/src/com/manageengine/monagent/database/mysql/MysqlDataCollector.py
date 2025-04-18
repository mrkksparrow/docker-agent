import json
import time
import traceback , os
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

import six.moves.urllib.request as urlconnection
from six.moves.urllib.parse import urlencode

from com.manageengine.monagent.database import DatabaseLogger, DBUtil
from com.manageengine.monagent.database.mysql import InnodbDataParser,MySQLConstants,MySQLUtil,ChildDatabaseDataCollector,PerformanceCounterDataCollector



# advance mysql monitor, data collection [performance and configuration data]
class MysqlMetricsCollector(object):
    # initialize input param for making mysql connection [user/pass/host/port]
    # previous data for volatile data
    # config data for sending only while onchange
    def init(self, input_param):
        try:
            self.master_status               = None
            self.slave_status                = None
            self.instance_type               = None
            self.onChange                    = False
            self.input_param                 = input_param

            self.conf_key                    = input_param['conf_key']
            self.time_diff                   = input_param['time_diff']
            self.previous_data               = input_param['previous_data']
            self.instance                    = input_param['instance']
            self.mid                         = input_param['mid']
            self.replication_child_keys      = input_param['replication_child_keys']
            self.mysql_util_obj              = MySQLUtil.MySQLConnector()
            self.mysql_util_obj.init(input_param)
            self.last_per_dc_time            = input_param['previous_data']['last_per_dc_time'] if 'last_per_dc_time' in input_param['previous_data'] else None

            self.result_conf_data            = {}
            self.result_perf_data            = {}
            self.result_current_data_cpy     = {}

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while initialising MySQL Metrics Collector Class :: {} : {}'.format(self.instance,e))
            traceback.print_exc()


    # masters host related metrics [show slave status/show replica status]
    def collect_data_from_slave_status(self):
        try:
            if self.slave_status:
                for slave_instance in self.slave_status:
                    for each in MySQLConstants.MYSQL_REPLICATION_STATUS_GROUPING:
                        self.result_conf_data[MySQLConstants.MYSQL_REPLICATION_STATUS_GROUPING[each][0]] = str(slave_instance[MySQLConstants.MYSQL_REPLICATION_STATUS_GROUPING[each][1]])
                    break
            else:
                DatabaseLogger.Logger.log('slave status contains no data')

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while parsing slave status query output :: {}'.format(e))
            traceback.print_exc()
    
    def collect_performance_data_from_slave_status(self):
        result_data = {}
        try:
            if self.slave_status:
                for slave_instance in self.slave_status:
                    for each in MySQLConstants.MYSQL_PERFORMANCE_REPLICATION_STATUS_GROUPING:
                        result_data[MySQLConstants.MYSQL_PERFORMANCE_REPLICATION_STATUS_GROUPING[each][0]] = str(slave_instance[MySQLConstants.MYSQL_PERFORMANCE_REPLICATION_STATUS_GROUPING[each][1]])
                    break
            else:
                DatabaseLogger.Logger.log('slave status contains no data.')
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while parsing slave status query output :: collect_performance_data_from_slave_status :: {}'.format(e))
            traceback.print_exc()
        finally:
            return result_data

    # slave hosts for the master instance is collected in list [show slave hosts/show replicas]
    def collect_slave_hosts_data(self):
        slave_member_list = []
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_SHOW_SLAVE_HOSTS)
            if is_success:
                for single_member in output_list:
                    slave_member = {}
                    for each in (MySQLConstants.MYSQL_SLAVE_HOSTS_GROUPING):
                        slave_member[MySQLConstants.MYSQL_SLAVE_HOSTS_GROUPING[each][0]] = str(single_member[MySQLConstants.MYSQL_SLAVE_HOSTS_GROUPING[each][1]])
                    slave_member_list.append(slave_member)
            else:
                DatabaseLogger.Logger.log('show slave hosts data not available')
                # have to think for error case, how to send err_msg to server

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting mysql slave hosts stats :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return slave_member_list


    # master host for the slave instance is collected in list [show slave status]
    def collect_master_hosts_data(self):
        master_member_list = []
        try:
            if self.slave_status:
                for single_member in self.slave_status:
                    master_member = {}
                    for each in (MySQLConstants.MYSQL_MASTER_HOSTS_GROUPING):
                        master_member[MySQLConstants.MYSQL_MASTER_HOSTS_GROUPING[each][0]] = str(single_member[MySQLConstants.MYSQL_MASTER_HOSTS_GROUPING[each][1]])
                    master_member_list.append(master_member)
            else:
                DatabaseLogger.Logger.log('show slave status data not available')
                # have to think for error case, how to send err_msg to server
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting mysql master hosts stats :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return master_member_list


    # need to add comments
    def collect_replication_onchange_data(self):
        replication_change_data                                   = {}
        try:
            replication_change_data['mid']                        = self.mid
            replication_change_data['instance']                   = self.instance
            replication_change_data['previous_instance_type']     = self.conf_key['instance_type'] if 'instance_type' in self.conf_key else self.instance_type
            replication_change_data['current_instance_type']      = self.instance_type
            if self.instance_type == 'MASTER':
                replication_change_data['slave_data']             = self.collect_slave_hosts_data()
            elif self.instance_type == 'SLAVE':
                replication_change_data['master_data']            = self.collect_master_hosts_data()
            if self.result_conf_data and 'SU' in self.result_conf_data:
                replication_change_data['uuid']                   = self.result_conf_data['SU']

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting replication onchange status data: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return replication_change_data


    # currently collected conf metrics is checked with past conf metrics, is onchange true, new conf metrics added to dc
    # check whether master slave status is changer, if yes, new metrics is added to be sent for cluster config servlet
    def verify_onchange_metrics(self):
        onchange = False
        try:
            # conf metrics onchange check
            if 'conf' not in self.conf_key or not self.conf_key['conf']:
                onchange = True
            else:
                for each in self.result_conf_data:
                    if each not in self.conf_key['conf']:
                        onchange = True
                        break
                    elif self.result_conf_data[each] != self.conf_key['conf'][each]:
                        onchange = True
                        break
                # master slave status change check
            if 'instance_type' not in self.conf_key or self.conf_key['instance_type'] != self.instance_type:
                self.result_perf_data['replication_onchange'] = self.collect_replication_onchange_data()
                onchange = True

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while verifying conf metrics onchange :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return onchange


    # mysql global variable metrics collected [show global variables] check for onchange, and added/removed in dc metrics
    def collect_variable_performance_metrics(self):
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_SHOW_GLOBAL_VARIABLES)
            if is_success:
                for variable in output_list:
                    if variable[0] in MySQLConstants.MYSQL_GLOBAL_VARIABLES_GROUPING.keys():
                        self.result_conf_data[MySQLConstants.MYSQL_GLOBAL_VARIABLES_GROUPING[variable[0]][0]] = str(variable[1])

            # check for conf key data presence and currently collected conf metrics any value changed
            if 'conf' in self.conf_key and self.conf_key['conf'] and self.result_conf_data:
                self.onChange = self.verify_onchange_metrics()
            elif not self.result_conf_data:
                DatabaseLogger.Logger.log('MySQL conf data not collected')
            elif not self.conf_key:
                self.result_perf_data['replication_onchange'] = self.collect_replication_onchange_data()
                self.onChange = True

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting global variables metrics :: {} : {}'.format(self.instance,e))
            traceback.print_exc()


    # mysql performance metrics is collected, if
    def collect_status_performance_metrics(self):
        try:
            self.result_perf_data['ct'] = self.mysql_util_obj.getTimeInMillis(self.time_diff)
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_TOTAL_DATABASE_COUNT)
            if is_success:
                for count in output_list:
                    self.result_perf_data['DBC'] = str(count[0])

            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_SHOW_GLOBAL_STATUS)
            current_time = time.time()
            if is_success:
                # time diff taken to get exact accurate data between polling
                time_diff = int(float(current_time) - float(self.last_per_dc_time))
                for variable in output_list:
                    if variable[0] in MySQLConstants.MYSQL_GLOBAL_STATUS_GROUPING.keys():
                        for metric_type in MySQLConstants.MYSQL_GLOBAL_STATUS_GROUPING[variable[0]][1]:
                            if metric_type == 'rate_s':
                                self.result_perf_data[MySQLConstants.MYSQL_GLOBAL_STATUS_GROUPING[variable[0]][0]]  = (int(str(variable[1])) - int(self.previous_data[MySQLConstants.MYSQL_GLOBAL_STATUS_GROUPING[variable[0]][0]])) / int(time_diff)
                            elif metric_type == 'rate_m':
                                self.result_perf_data[MySQLConstants.MYSQL_GLOBAL_STATUS_GROUPING[variable[0]][0]]  = (int(str(variable[1])) - int(self.previous_data[MySQLConstants.MYSQL_GLOBAL_STATUS_GROUPING[variable[0]][0]])) / (int(time_diff)/60)
                            elif metric_type == 'diff':
                                self.result_perf_data[MySQLConstants.MYSQL_GLOBAL_STATUS_GROUPING[variable[0]][0]]  = (int(str(variable[1])) - int(self.previous_data[MySQLConstants.MYSQL_GLOBAL_STATUS_GROUPING[variable[0]][0]]))
                            else:
                                self.result_perf_data[MySQLConstants.MYSQL_GLOBAL_STATUS_GROUPING[variable[0]][0]]  = str(variable[1])
                        # current data stored as it is for next polling to calculate non-volatile data
                        self.result_current_data_cpy[MySQLConstants.MYSQL_GLOBAL_STATUS_GROUPING[variable[0]][0]]   = str(variable[1])

                self.result_current_data_cpy['last_per_dc_time']      = str(current_time)
                self.result_perf_data['CNUS']                         = str((int(self.result_perf_data['TR']) / int(self.result_conf_data['MC'])) * 100)
                # Connection Usage = Threads_running / Max_connections
                self.result_perf_data['CNNUS']                        = str(100 - float(self.result_perf_data['CNUS']))
                self.result_perf_data['OFUS']                         = str((int(self.result_perf_data['OF']) / int(self.result_conf_data['OFL'])) * 100)
                # Open Files Usage = Open_files / Open_Files_limit
                self.result_perf_data['OFNUS']                        = str(100 - float(self.result_perf_data['OFUS']))
                #self.result_perf_data['writes']                      = str(int(self.result_perf_data['CI'])+int(self.result_perf_data['CRP'])+int(self.result_perf_data['CU'])+int(self.result_perf_data['CUM'])+int(self.result_perf_data['CD'])+int(self.result_perf_data['CDM']))
                #self.result_perf_data['reads']                       = str(int(self.result_perf_data['CS']) + int(self.result_perf_data['QH']))
                #self.result_perf_data['transactions']                = str(int(self.result_perf_data['CS']) + int(self.result_perf_data['CCOM']))
                self.result_perf_data['KBBUF']                        = int(self.result_perf_data['KBNF']) * int(self.result_conf_data['KCBS'])
                # Key_buffer_bytes_unflushed                          = Key_blocks_not_flushed * key_cache_block_size # dd
                self.result_perf_data['KBBUS']                        = int(self.result_perf_data['KBU']) * int(self.result_conf_data['KCBS'])
                # Key_buffer_bytes_used                               = Key_blocks_used * key_cache_block_size # dd
                self.result_perf_data['IBPPUS']                       = (int(self.result_perf_data['IBPPT']) - int(self.result_perf_data['IBPPF']))
                # innodb_buffer_pool_pages_used                       = Innodb_buffer_pool_pages_total - Innodb_buffer_pool_pages_free # dd
                self.result_perf_data['IBPBF']                        = (int(self.result_perf_data['IBPPF']) * int(self.result_perf_data['IPS']))
                # Innodb_buffer_pool_bytes_free                       = Innodb_buffer_pool_pages_free * innodb_page_size # dd
                self.result_perf_data['IBPBT']                        = (int(self.result_perf_data['IBPPT']) * int(self.result_perf_data['IPS']))
                # Innodb_buffer_pool_bytes_total                      = Innodb_buffer_pool_pages_total * innodb_page_size # dd
                self.result_perf_data['IBPBU']                        = (int(self.result_perf_data['IBPPT']) - int(self.result_perf_data['IBPPF'])) * int(self.result_perf_data['IPS'])
                # Innodb_buffer_pool_bytes_used                       = innodb_buffer_pool_pages_used * innodb_page_size # dd
                self.result_perf_data['IBPPUP']                       = ((int(self.result_perf_data['IBPPT']) - int(self.result_perf_data['IBPPF'])) / int(self.result_perf_data['IBPPT'])) * 100
                self.result_perf_data['IBPPNUP']                      = 100 - self.result_perf_data['IBPPUP']
                # Innodb_buffer_pool_pages_utilization                = innodb_buffer_pool_pages_used / Innodb_buffer_pool_pages_total # dd
                self.result_perf_data['TCHR']                         = float((int(self.result_perf_data['TOCH']) / int(int(self.result_perf_data['TOCH'] + self.result_perf_data['TOCM']))) * 100)
                self.result_perf_data['TCHRNU']                       = 100 - self.result_perf_data['TCHR']
                # table_open_cache_efficiency                         = Table_open_cache_hits  / (Table_open_cache_hits  + Table_open_cache_misses ) # https://github.com/major/MySQLTuner-perl/issues/548
                #self.result_perf_data['TCHRNU']                      = 100 - float(self.result_perf_data['TCHR'])
            else:
                DatabaseLogger.Logger.log('MySQL perf data not collected')

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting global performance stats :: {} : {}'.format(self.instance,e))
            traceback.print_exc()


    # mysql performance metrics for summary page
    def collect_summary_page_metrics(self):
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_TOTAL_MEMORY_ALLOCATED) # the total bytes of memory allocated within the server.
            if is_success:
                for each in output_list:
                    self.result_perf_data['MEM'] = int(each[0]) if each[0] else 0  # bytes

            # Writes = Com_insert + Com_update + Com_delete
            self.result_perf_data['ITW']   = self.result_perf_data['CI'] + self.result_perf_data['CU'] + self.result_perf_data['CD']
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_AVG_QUERY_RUN_TIME_CP).format('%')) # the total bytes of memory allocated within the server.
            if is_success:
                for each in output_list:
                    self.result_perf_data['ITCS']             = (float(each[0]) if each[0] else 0) - float(self.previous_data['ITCS']) # int(each[0]) if each[0] else 0   # instance average count star
                    self.result_perf_data['ITART']            = "0" if not int(self.result_perf_data['ITCS']) else (((float(each[1]) if each[1] else 0) - float(self.previous_data['ITART'])) / self.result_perf_data['ITCS']) # int(each[1]) if each[1] else 0  # instance average query run time #micro sec
                    self.result_perf_data['ITALT']            = "0" if not int(self.result_perf_data['ITCS']) else (((float(each[2]) if each[2] else 0) - float(self.previous_data['ITALT'])) / self.result_perf_data['ITCS']) # int(each[2]) if each[2] else 0  # instance average lock time #micro sec
                    self.result_perf_data['ITAER']            = "0" if not int(self.result_perf_data['ITCS']) else (((float(each[3]) if each[3] else 0) - float(self.previous_data['ITAER'])) / self.result_perf_data['ITCS']) # int(each[3]) if each[3] else 0  # instance average error
                    self.result_perf_data['ITAWN']            = "0" if not int(self.result_perf_data['ITCS']) else (((float(each[4]) if each[4] else 0) - float(self.previous_data['ITAWN'])) / self.result_perf_data['ITCS']) # int(each[4]) if each[4] else 0  # instance average warnings
                    self.result_perf_data['ITARF']            = "0" if not int(self.result_perf_data['ITCS']) else (((float(each[5]) if each[5] else 0) - float(self.previous_data['ITARF'])) / self.result_perf_data['ITCS']) # int(each[5]) if each[5] else 0  # instance average rows affected
                    self.result_perf_data['ITARS']            = "0" if not int(self.result_perf_data['ITCS']) else (((float(each[6]) if each[6] else 0) - float(self.previous_data['ITARS'])) / self.result_perf_data['ITCS']) # int(each[6]) if each[6] else 0  # instance average rows sent
                    self.result_perf_data['ITATDTC']          = "0" if not int(self.result_perf_data['ITCS']) else (((float(each[7]) if each[7] else 0) - float(self.previous_data['ITATDTC'])) / self.result_perf_data['ITCS']) # int(each[7]) if each[7] else 0  # instance average temp disk table created
                    self.result_perf_data['ITATTC']           = "0" if not int(self.result_perf_data['ITCS']) else (((float(each[8]) if each[8] else 0) - float(self.previous_data['ITATTC'])) / self.result_perf_data['ITCS']) # int(each[8]) if each[8] else 0  # instance average temp table created
                    self.result_perf_data['TSERC']            = (float(each[9]) if each[9] else 0) - float(self.previous_data['TSERC'])
                    self.result_perf_data['TSWNC']            = (float(each[10]) if each[10] else 0) - float(self.previous_data['TSWNC'])
                    self.result_current_data_cpy['ITCS']      = float(each[0]) if each[0] else 0
                    self.result_current_data_cpy['ITART']     = float(each[1]) if each[1] else 0
                    self.result_current_data_cpy['ITALT']     = float(each[2]) if each[2] else 0
                    self.result_current_data_cpy['ITAER']     = float(each[3]) if each[3] else 0
                    self.result_current_data_cpy['ITAWN']     = float(each[4]) if each[4] else 0
                    self.result_current_data_cpy['ITARF']     = float(each[5]) if each[5] else 0
                    self.result_current_data_cpy['ITARS']     = float(each[6]) if each[6] else 0
                    self.result_current_data_cpy['ITATDTC']   = float(each[7]) if each[7] else 0
                    self.result_current_data_cpy['ITATTC']    = float(each[8]) if each[8] else 0
                    self.result_current_data_cpy['TSERC']     = float(each[9]) if each[9] else 0
                    self.result_current_data_cpy['TSWNC']     = float(each[10]) if each[10] else 0

            start_time = str(time.time())
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_DATABASE_SCHEMA_STATISTICS_OVERALL).format('%'))
            if is_success:
                for each in output_list:
                    self.result_perf_data['TSTL']                       = ((float(each[0]) if each[0] else 0) - float(self.previous_data['TSTL']))  # millisecond # total_latency # The total wait time of timed I/O events for the table.
                    self.result_perf_data['TSRF']                       = ((int(each[1]) if each[1] else 0) - int(self.previous_data['TSRF'])) # count # rows_fetched # The total number of rows read from the table.
                    self.result_perf_data['TSFL']                       = ((float(each[2]) if each[2] else 0) - float(self.previous_data['TSFL'])) # millisecond # fetch_latency # The total wait time of timed read I/O events for the table.
                    self.result_perf_data['TSRI']                       = ((int(each[3]) if each[3] else 0) - int(self.previous_data['TSRI'])) # count # rows_inserted # The total number of rows inserted into the table.
                    self.result_perf_data['TSIL']                       = ((float(each[4]) if each[4] else 0) - float(self.previous_data['TSIL'])) # millisecond # insert_latency # The total wait time of timed insert I/O events for the table.
                    self.result_perf_data['TSRU']                       = ((int(each[5]) if each[5] else 0) - int(self.previous_data['TSRU'])) # count # rows_updated # The total number of rows updated in the table.
                    self.result_perf_data['TSUL']                       = ((float(each[6]) if each[6] else 0) - float(self.previous_data['TSUL'])) # millisecond # update_latency # The total wait time of timed update I/O events for the table.
                    self.result_perf_data['TSRD']                       = ((int(each[7]) if each[7] else 0) - int(self.previous_data['TSRD'])) # count # rows_deleted # The total number of rows deleted from the table.
                    self.result_perf_data['TSDL']                       = ((float(each[8]) if each[8] else 0) - float(self.previous_data['TSDL'])) # millisecond # delete_latency # The total wait time of timed delete I/O events for the table.
                    self.result_perf_data['TSIORR']                     = ((int(each[9]) if each[9] else 0) - int(self.previous_data['TSIORR'])) # count # io_read_requests # The total number of read requests for the table.
                    self.result_perf_data['TSIOR']                      = ((int(each[10]) if each[10] else 0) - int(self.previous_data['TSIOR'])) # bytes # io_read # The total number of bytes read from the table.
                    self.result_perf_data['TSIORL']                     = ((float(each[11]) if each[11] else 0) - float(self.previous_data['TSIORL'])) # millisecond # io_read_latency # The total wait time of reads from the table.
                    self.result_perf_data['TSIOWR']                     = ((int(each[12]) if each[12] else 0) - int(self.previous_data['TSIOWR'])) # count # io_write_requests # The total number of write requests for the table.
                    self.result_perf_data['TSIOW']                      = ((int(each[13]) if each[13] else 0) - int(self.previous_data['TSIOW'])) # bytes # io_write # The total number of bytes written to the table.
                    self.result_perf_data['TSIOWL']                     = ((float(each[14]) if each[14] else 0) - float(self.previous_data['TSIOWL'])) # millisecond # io_write_latency # The total wait time of writes to the table.
                    self.result_perf_data['TSIOMR']                     = ((int(each[15]) if each[15] else 0) - int(self.previous_data['TSIOMR'])) # count # io_misc_requests # The total number of miscellaneous I/O requests for the table.
                    self.result_perf_data['TSIOML']                     = ((float(each[16]) if each[16] else 0) - float(self.previous_data['TSIOML'])) # millisecond # io_misc_latency # The total wait time of miscellaneous I/O requests for the table.
                    self.result_current_data_cpy['TSTL']                = float(each[0]) if each[0] else 0
                    self.result_current_data_cpy['TSRF']                = int(each[1]) if each[1] else 0
                    self.result_current_data_cpy['TSFL']                = float(each[2]) if each[2] else 0
                    self.result_current_data_cpy['TSRI']                = int(each[3]) if each[3] else 0
                    self.result_current_data_cpy['TSIL']                = float(each[4]) if each[4] else 0
                    self.result_current_data_cpy['TSRU']                = int(each[5]) if each[5] else 0
                    self.result_current_data_cpy['TSUL']                = float(each[6]) if each[6] else 0
                    self.result_current_data_cpy['TSRD']                = int(each[7]) if each[7] else 0
                    self.result_current_data_cpy['TSDL']                = float(each[8]) if each[8] else 0
                    self.result_current_data_cpy['TSIORR']              = int(each[9]) if each[9] else 0
                    self.result_current_data_cpy['TSIOR']               = int(each[10]) if each[10] else 0
                    self.result_current_data_cpy['TSIORL']              = float(each[11]) if each[11] else 0
                    self.result_current_data_cpy['TSIOWR']              = int(each[12]) if each[12] else 0
                    self.result_current_data_cpy['TSIOW']               = int(each[13]) if each[13] else 0
                    self.result_current_data_cpy['TSIOWL']              = float(each[14]) if each[14] else 0
                    self.result_current_data_cpy['TSIOMR']              = int(each[15]) if each[15] else 0
                    self.result_current_data_cpy['TSIOML']              = float(each[16]) if each[16] else 0
                    self.result_current_data_cpy['last_mdss_dc_time']   = start_time

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting metrics for summary page :: {} : {}'.format(self.instance,e))
            traceback.print_exc()

    # innodb engine metrics collected    [
    # requires querying user to have PROCESS privileges
    # this parser is highly inspired from Percona monitoring plugins work and datadog
    # most metrics are available in status/vaiable query, balance is collected here
    def collect_innodb_data(self):
        try:
            self.result_perf_data.update(InnodbDataParser.check_innodb_engine(self.mysql_util_obj.cursor))
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting innnodb metrics :: {} : {}'.format(self.instance,e))


    # collect biblog or relay log file size, file count
    def collect_binlog_relay_log_data(self):
        try:
            # check whether binlog enabled and collecting metrics
            if self.result_conf_data['LB'] == 'ON':
                is_success,binlog_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_SHOW_BINARY_LOGS)
                if is_success and binlog_list:
                    binlog_size = 0
                    for each in binlog_list:
                        binlog_size = binlog_size + each[1]
                    self.result_perf_data['BLFC']  = str(len(binlog_list))
                    self.result_perf_data['BLS']   = str(binlog_size)
                else:
                    DatabaseLogger.Logger.log('show binary logs data not available')
            else:
                DatabaseLogger.Logger.log('binlog is not enabled in mysql instance :: {}'.format(self.instance))

            # colledt relay logs files size and count, if present
            is_success,relaylog_list,err_msg   = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_SHOW_RELAYLOG_EVENTS)
            if is_success and relaylog_list:
                self.result_perf_data['RLFC']  = str(len(relaylog_list))
                if 'RLS' in self.result_conf_data:
                    self.result_perf_data['RLS']  = str(self.result_conf_data['RLS'])
                else:
                    DatabaseLogger.Logger.log('No relay log space data found from slave status data')
            else:
                DatabaseLogger.Logger.log('show relaylogs events data not available')
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting mysql slave hosts stats :: {} : {}'.format(self.instance,e))
            traceback.print_exc()


    # replication group members data can be collected [TABLE - performance_schema.replication_group_members/performance_schema.replication_group_member_stats]
    def collect_replication_grp_member_stats(self):
        repl_member_list = []
        is_success = True
        err_msg = None
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_REPLICATION_GRP_MEMBERS_DATA_QUERY)
            if is_success:
                for single_member in output_list:
                    replication_member = {}
                    for each in MySQLConstants.MYSQL_REPLICATION_GRP_DATA_GROUPING:
                        replication_member[MySQLConstants.MYSQL_REPLICATION_GRP_DATA_GROUPING[each][0]] = str(single_member[MySQLConstants.MYSQL_REPLICATION_GRP_DATA_GROUPING[each][1]])
                    repl_member_list.append(replication_member)
            else:
                DatabaseLogger.Logger.log('group replication data contains no data')
        except Exception as e:
            is_success = False
            err_msg = str(e)
            DatabaseLogger.Logger.log('Exception while collecting mysql group replication member stats :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return is_success, repl_member_list, err_msg

    def collect_performance_data(self):
        result_data = {}
        result_data['DC ERROR'] = {}
        is_success = False
        is_con_success = False
        err_msg = None
        try:

            is_con_success, err_msg = self.mysql_util_obj.get_db_connection()
            if is_con_success:
                if self.last_per_dc_time:
                    DatabaseLogger.Logger.log('====== Total Execution Time before DC Start :: {} ======'.format(self.mysql_util_obj.total_execution_time),'QUERY')
                    is_success, version, err_msg = self.mysql_util_obj.get_mysql_version()
                    MySQLConstants.set_query_for_data_collection(version)

                    is_success ,self.master_status, self.slave_status, err_msg = self.mysql_util_obj.collect_master_slave_status()
                    if is_success:
                        replication_enabled,self.instance_type = self.mysql_util_obj.decide_instance_type(self.master_status,self.slave_status)

                        if self.instance_type == 'SLAVE':
                            self.collect_data_from_slave_status()
                        if self.slave_status:
                            result_data.update(self.collect_performance_data_from_slave_status())
                    try:
                        if version >= '5.7' and replication_enabled:
                            is_success, repl_member_list, err_msg = self.collect_replication_grp_member_stats()

                            if is_success:
                                result_data['replication'] = DBUtil.MapID(repl_member_list,self.replication_child_keys,"mid","RMI")
                            else:
                                result_data['replication'] = [{'status': '0', 'err_msg': err_msg}]
                    except Exception as e:
                        DatabaseLogger.Logger.log(' Exception while collecting replication group status :: {}'.format(e))

                    #if version >= '5.7' and replication_enabled:
                    #    self.collect_replication_grp_member_stats()
                    #DatabaseLogger.Logger.log(' %%%%%%%%%%%%%%%%%%%%%% :: {} \n%%%%%%%%%%%%%%%%%%%%%% :: {}'.format(self.result_perf_data, self.result_conf_data))

                    self.collect_variable_performance_metrics()
                    #DatabaseLogger.Logger.log(' %%%%%%%%%%%%%%%%%%%%%% :: {} \n%%%%%%%%%%%%%%%%%%%%%% :: {}'.format(self.result_perf_data, self.result_conf_data))

                    self.collect_status_performance_metrics()
                    #DatabaseLogger.Logger.log(' \n%%%%%%%%%%%%%%%%%%%%%% :: {} \n%%%%%%%%%%%%%%%%%%%%%% :: {}'.format(self.result_perf_data, self.result_conf_data))

                    self.collect_summary_page_metrics()

                    self.collect_innodb_data()

                    self.collect_binlog_relay_log_data()

                    DatabaseLogger.Logger.log('====== Total Execution Time after DC Start :: {} ======'.format(self.mysql_util_obj.total_execution_time),'QUERY')
                    

                    result_data.update(self.result_perf_data)
                    result_data['current_data']                    = self.result_current_data_cpy

                    if not self.onChange:
                        DatabaseLogger.Logger.log(' ====== Conf metrics not changed, Hence skipping for upload ======')
                        result_data['conf']                        = {}
                    else:
                        DatabaseLogger.Logger.log(' ====== Conf metrics changed, Hence adding for upload ======')
                        result_data['conf']                        = self.result_conf_data
                else:
                    prf_stp_dc_obj = PerformanceCounterDataCollector.PerformanceCounterCollector()
                    self.input_param['child_keys'] = {}
                    prf_stp_dc_obj.init(self.input_param)
                    is_success,current_data,self.error_msg = prf_stp_dc_obj.collect_global_status_and_child_db_data()
                    result_data['current_data'] = current_data if current_data else {}
                self.mysql_util_obj.close_db_connection()

            else:
                DatabaseLogger.Logger.log(' ************ cannot connect to the mysql instance *************')
                result_data['DC ERROR']['connection_error'] = {
                    'status':'0',
                    'error_msg': str(err_msg)
                }

            result_data['ct']                              = self.mysql_util_obj.getTimeInMillis(self.time_diff)
            result_data['instance_type']                   = self.instance_type


        except Exception as e:
            is_con_success = False
            err_msg = str(e)
            result_data['ct']                              = self.mysql_util_obj.getTimeInMillis(self.time_diff)
            result_data['instance_type']                   = self.instance_type
            result_data['DC ERROR']['connection_error'] = {
                'status':'0',
                'error_msg': str(err_msg)
            }
            DatabaseLogger.Logger.log('Exception while collecting database basic monitor data :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return is_con_success, result_data, err_msg
