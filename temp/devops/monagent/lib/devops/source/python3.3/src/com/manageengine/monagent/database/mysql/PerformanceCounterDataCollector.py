import json
import time
import concurrent.futures
import traceback , os
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

import six.moves.urllib.request as urlconnection
from six.moves.urllib.parse import urlencode

from com.manageengine.monagent.database import DatabaseLogger
from com.manageengine.monagent.database.mysql import MySQLConstants,MySQLUtil


# class used to collected volatile data in the agent startup and stored in variables and sent to next poll to calculate non-volatile data by subtracting this one
class PerformanceCounterCollector(object):
    def init(self, input_param):
        try:
            self.input_param                 = input_param
            self.instance                    = input_param['instance']
            self.mid                         = input_param['mid']
            self.child_keys                  = input_param['child_keys']
            self.mysql_util_obj              = MySQLUtil.MySQLConnector()
            self.mysql_util_obj.init(input_param)
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while initialising performance status data collector :: {} : {}'.format(self.instance,e))
            traceback.print_exc()


    # mysql_connector_obj will be used from ChildDatabaseDataCollector.collect_database_schema_metrics()
    # for databases that are added in between data collection dummy dc task will not happen
    # so in child data colection, if only previous data is available dc happens, else called here to collect dummy dc, next polling will happen there and sent to server
    def collect_child_database_counter_data(self,database,mysql_connector_obj=None):
        final_db_data_dict       = {}
        sep_mysql_util_obj       = None
        if mysql_connector_obj:
            self.mysql_util_obj  = mysql_connector_obj

        try:
            #for database in self.child_keys:
            # mysql> SELECT SUM(total_latency/1000000000), SUM(rows_fetched), SUM(fetch_latency/1000000000), SUM(rows_inserted), SUM(insert_latency/1000000000), SUM(rows_updated), SUM(update_latency/1000000000), SUM(rows_deleted), SUM(delete_latency/1000000000), SUM(io_read_requests), SUM(io_read), SUM(io_read_latency/1000000000), SUM(io_write_requests), SUM(io_write), SUM(io_write_latency/1000000000), SUM(io_misc_requests), SUM(io_misc_latency/1000000000) FROM sys.x$schema_table_statistics WHERE table_schema like 'jbossdb'\G
            # *************************** 1. row ***************************
            # SUM(total_latency/1000000000): 2185.4818
            # SUM(rows_fetched): 94673
            # SUM(fetch_latency/1000000000): 2008.7388
            # SUM(rows_inserted): 32
            # SUM(insert_latency/1000000000): 6.3424
            # SUM(rows_updated): 1383
            # SUM(update_latency/1000000000): 169.4212
            # SUM(rows_deleted): 30
            # SUM(delete_latency/1000000000): 0.9793
            # SUM(io_read_requests): 5074804
            # SUM(io_read): 880240511
            # SUM(io_read_latency/1000000000): 8812.6589
            # SUM(io_write_requests): 2541
            # SUM(io_write): 41631744
            # SUM(io_write_latency/1000000000): 56.2201
            # SUM(io_misc_requests): 4362825
            # SUM(io_misc_latency/1000000000): 9762.8197
            # 1 row in set (0.85 sec)
            start_time = str(time.time())
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_DATABASE_SCHEMA_STATISTICS).format(database))
            if is_success:
                for each in output_list:
                    final_db_data_dict                        = {}
                    final_db_data_dict['TSTL']                = float(each[0]) if each[0] else 0 # millisecond # total_latency # The total wait time of timed I/O events for the table.
                    final_db_data_dict['TSRF']                = int(each[1]) if each[1] else 0 # count # rows_fetched # The total number of rows read from the table.
                    final_db_data_dict['TSFL']                = float(each[2]) if each[2] else 0 # millisecond # fetch_latency # The total wait time of timed read I/O events for the table.
                    final_db_data_dict['TSRI']                = int(each[3]) if each[3] else 0 # count # rows_inserted # The total number of rows inserted into the table.
                    final_db_data_dict['TSIL']                = float(each[4]) if each[4] else 0 # millisecond # insert_latency # The total wait time of timed insert I/O events for the table.
                    final_db_data_dict['TSRU']                = int(each[5]) if each[5] else 0 # count # rows_updated # The total number of rows updated in the table.
                    final_db_data_dict['TSUL']                = float(each[6]) if each[6] else 0 # millisecond # update_latency # The total wait time of timed update I/O events for the table.
                    final_db_data_dict['TSRD']                = int(each[7]) if each[7] else 0 # count # rows_deleted # The total number of rows deleted from the table.
                    final_db_data_dict['TSDL']                = float(each[8]) if each[8] else 0 # millisecond # delete_latency # The total wait time of timed delete I/O events for the table.
                    final_db_data_dict['TSIORR']              = int(each[9]) if each[9] else 0 # count # io_read_requests # The total number of read requests for the table.
                    final_db_data_dict['TSIOR']               = int(each[10]) if each[10] else 0 # bytes # io_read # The total number of bytes read from the table.
                    final_db_data_dict['TSIORL']              = float(each[11]) if each[11] else 0 # millisecond # io_read_latency # The total wait time of reads from the table.
                    final_db_data_dict['TSIOWR']              = int(each[12]) if each[12] else 0 # count # io_write_requests # The total number of write requests for the table.
                    final_db_data_dict['TSIOW']               = int(each[13]) if each[13] else 0 # bytes # io_write # The total number of bytes written to the table.
                    final_db_data_dict['TSIOWL']              = float(each[14]) if each[14] else 0 # millisecond # io_write_latency # The total wait time of writes to the table.
                    final_db_data_dict['TSIOMR']              = int(each[15]) if each[15] else 0 # count # io_misc_requests # The total number of miscellaneous I/O requests for the table.
                    final_db_data_dict['TSIOML']              = float(each[16]) if each[16] else 0 # millisecond # io_misc_latency # The total wait time of miscellaneous I/O requests for the table.
                    final_db_data_dict['last_mdss_dc_time']   = start_time


            # mysql> SELECT IFNULL(SUM(COUNT_STAR),0) AS count, IFNULL((SUM(SUM_TIMER_WAIT)/SUM(COUNT_STAR))/1000000000,0) AS avg_waittime, IFNULL((SUM(SUM_LOCK_TIME)/SUM(COUNT_STAR))/1000000000,0) AS avg_locktime, IFNULL(SUM(SUM_ERRORS)/SUM(COUNT_STAR),0) AS avg_error, IFNULL(SUM(SUM_WARNINGS)/SUM(COUNT_STAR),0) AS avg_warning, IFNULL(SUM(SUM_ROWS_AFFECTED)/SUM(COUNT_STAR),0) AS avg_rows_affected, IFNULL(SUM(SUM_ROWS_SENT)/SUM(COUNT_STAR),0) AS avg_rows_sent, IFNULL(SUM(SUM_CREATED_TMP_DISK_TABLES)/SUM(COUNT_STAR),0) AS avg_tmp_disk_tb_crt, IFNULL(SUM(SUM_CREATED_TMP_TABLES)/SUM(COUNT_STAR),0) AS avg_tmp_tb_crt, IFNULL(SUM(SUM_ERRORS),0) as
            # sum_error, IFNULL(SUM(SUM_WARNINGS),0) as sum_warning FROM performance_schema.events_statements_summary_by_digest WHERE SCHEMA_NAME='jbossdb' AND LAST_SEEN > DATE_SUB(NOW(), INTERVAL 300000000 SECOND);
            # +-------+--------------+--------------+-----------+-------------+-------------------+---------------+---------------------+----------------+-----------+-------------+
            # | count | avg_waittime | avg_locktime | avg_error | avg_warning | avg_rows_affected | avg_rows_sent | avg_tmp_disk_tb_crt | avg_tmp_tb_crt | sum_error | sum_warning |
            # +-------+--------------+--------------+-----------+-------------+-------------------+---------------+---------------------+----------------+-----------+-------------+
            # |     0 |   0.00000000 |   0.00000000 |    0.0000 |      0.0000 |            0.0000 |        0.0000 |              0.0000 |         0.0000 |         0 |           0 |
            # +-------+--------------+--------------+-----------+-------------+-------------------+---------------+---------------------+----------------+-----------+-------------+
            # 1 row in set (0.05 sec)
            # separate child database summary page data [inspired from datadog]
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_AVG_QUERY_RUN_TIME_CP).format(database)) # the total bytes of memory allocated within the server.
            if is_success:
                for each in output_list:
                    final_db_data_dict['ITCS']                     = str(each[0]) if each[0] else 0  # count  # instance count star   # ITCS
                    final_db_data_dict['ITART']                    = str(each[1]) if each[1] else 0 # millisecond  # instance average query run time  # ITART
                    final_db_data_dict['ITALT']                    = str(each[2]) if each[2] else 0  # millisecond # instance average lock time  # ITALT
                    final_db_data_dict['ITAER']                    = str(each[3]) if each[3] else 0  # count  # instance average error  # ITAER
                    final_db_data_dict['ITAWN']                    = str(each[4]) if each[4] else 0  # count  # instance average warnings # ITAWN
                    final_db_data_dict['ITARF']                    = str(each[5]) if each[5] else 0  # count  # instance average rows affected # ITARF
                    final_db_data_dict['ITARS']                    = str(each[6]) if each[6] else 0  # count  # instance average rows sent # ITARS
                    final_db_data_dict['ITATDTC']                  = str(each[7]) if each[7] else 0  # count  # instance average temp disk table created # ITATDTC
                    final_db_data_dict['ITATTC']                   = str(each[8]) if each[8] else 0  # count  # instance average temp table created # ITATTC
                    final_db_data_dict['TSERC']                    = str(each[9]) if each[9] else 0  # count  # instance total error count in 300 second # TSERC
                    final_db_data_dict['TSWNC']                    = str(each[10]) if each[10] else 0  # count  # instance total warn count in 300 second # TSWNC


            # mysql index scan count from start of mysql
            # mysql> select * from performance_schema.table_io_waits_summary_by_index_usage where OBJECT_SCHEMA like 'jbossdb' and index_name != 'NULL' limit 1\G
            # *************************** 1. row ***************************
            # OBJECT_TYPE: TABLE
            # OBJECT_SCHEMA: jbossdb
            # OBJECT_NAME: WM_DYNAMIC_TABLE_SETTINGS
            # INDEX_NAME: PRIMARY
            # COUNT_STAR: 0
            # SUM_TIMER_WAIT: 0
            # MIN_TIMER_WAIT: 0
            # AVG_TIMER_WAIT: 0
            # MAX_TIMER_WAIT: 0
            # COUNT_READ: 0
            # SUM_TIMER_READ: 0
            # MIN_TIMER_READ: 0
            # AVG_TIMER_READ: 0
            # MAX_TIMER_READ: 0
            # COUNT_WRITE: 0
            # SUM_TIMER_WRITE: 0
            # MIN_TIMER_WRITE: 0
            # AVG_TIMER_WRITE: 0
            # MAX_TIMER_WRITE: 0
            # COUNT_FETCH: 0
            # SUM_TIMER_FETCH: 0
            # MIN_TIMER_FETCH: 0
            # AVG_TIMER_FETCH: 0
            # MAX_TIMER_FETCH: 0
            # COUNT_INSERT: 0
            # SUM_TIMER_INSERT: 0
            # MIN_TIMER_INSERT: 0
            # AVG_TIMER_INSERT: 0
            # MAX_TIMER_INSERT: 0
            # COUNT_UPDATE: 0
            # SUM_TIMER_UPDATE: 0
            # MIN_TIMER_UPDATE: 0
            # AVG_TIMER_UPDATE: 0
            # MAX_TIMER_UPDATE: 0
            # COUNT_DELETE: 0
            # SUM_TIMER_DELETE: 0
            # MIN_TIMER_DELETE: 0
            # AVG_TIMER_DELETE: 0
            # MAX_TIMER_DELETE: 0
            # 1 row in set (0.00 sec)
            # mysql> SELECT SUM(COUNT_STAR) FROM performance_schema.table_io_waits_summary_by_index_usage WHERE OBJECT_SCHEMA LIKE 'jbossdb' AND INDEX_NAME != 'NULL';
            # +-----------------+
            # | SUM(COUNT_STAR) |
            # +-----------------+
            # |            2015 |
            # +-----------------+
            # 1 row in set (0.05 sec)
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_DATABASE_INDEX_SCAN).format(database))
            if is_success:
                for each in output_list:
                    final_db_data_dict['IDSC']          = str(each[0]) # count # index scan count

            # mysql sequential scan count from start of mysql
            # mysql> SELECT * FROM sys.x$statements_with_full_table_scans WHERE db LIKE 'jbossdb' limit 1\G
            # *************************** 1. row ***************************
            # query: SELECT `JOB_ID` , `Jobs_1` . `SCHEDULE_ID` , `TASK_ID` , `Jobs_1` . `SCHEMAID` , `TRANSACTION_TIME` , `SCHEDULED_TIME` , `RETRY_SCHEDULE_ID` , `AUDIT_FLAG` , `Jobs_1` . `USER_ID` , `SCHEDULE_NAME` FROM `Jobs_1` LEFT JOIN `Schedule_1` USING ( `SCHEDULE_ID` ) WHERE `SCHEDULED_TIME` <= ? AND `ADMIN_STATUS` = ? AND `IS_COMMISIONED` = ? ORDER BY `SCHEDULED_TIME` LIMIT ?, ...
            # db: jbossdb
            # exec_count: 60
            # total_latency: 41908339000
            # no_index_used_count: 60
            # no_good_index_used_count: 0
            # no_index_used_pct: 100
            # rows_sent: 0
            # rows_examined: 840
            # rows_sent_avg: 0
            # rows_examined_avg: 14
            # first_seen: 2022-08-19 10:28:34
            # last_seen: 2022-08-19 10:58:04
            # digest: a47377cef47ef025f880772f832b66ef
            # 1 row in set (0.01 sec)
            # mysql> SELECT SUM(exec_count) FROM sys.x$statements_with_full_table_scans WHERE db LIKE 'jbossdb';
            # +-----------------+
            # | SUM(exec_count) |
            # +-----------------+
            # |             247 |
            # +-----------------+
            # 1 row in set (0.01 sec)
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_DATABASE_SEQUENTIAL_SCAN).format(database))
            if is_success:
                for each in output_list:
                    final_db_data_dict['SQSC']         = str(each[0]) # count # full scan done in db

            if sep_mysql_util_obj:
                sep_mysql_util_obj.close_db_connection()

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting dummy child database data :: {} : {}'.format(self.instance,e))
            traceback.print_exc()

        finally:
            return final_db_data_dict


    # performance startup data for basic monitor
    # child db dummy data called from here
    def collect_global_status_and_child_db_data(self):
        result_data  = {}
        is_success   = True
        err_msg      = None
        try:
            is_success, err_msg = self.mysql_util_obj.get_db_connection()

            if is_success:
                is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_SHOW_GLOBAL_STATUS)
                if is_success:
                    for variable in output_list:
                        if variable[0] in MySQLConstants.MYSQL_GLOBAL_STATUS_GROUPING.keys():
                            result_data[MySQLConstants.MYSQL_GLOBAL_STATUS_GROUPING[variable[0]][0]] = str(variable[1])
                else:
                    DatabaseLogger.Logger.log('MySQL perf data not collected')
                result_data['last_per_dc_time'] = str(time.time())

                # mysql> SELECT SUM(total_latency/1000000000), SUM(rows_fetched), SUM(fetch_latency/1000000000), SUM(rows_inserted), SUM(insert_latency/1000000000), SUM(rows_updated), SUM(update_latency/1000000000), SUM(rows_deleted), SUM(delete_latency/1000000000), SUM(io_read_requests), SUM(io_read), SUM(io_read_latency/1000000000), SUM(io_write_requests), SUM(io_write), SUM(io_write_latency/1000000000), SUM(io_misc_requests), SUM(io_misc_latency/1000000000) FROM sys.x$schema_table_statistics WHERE table_schema like 'jbossdb'\G
                # *************************** 1. row ***************************
                # SUM(total_latency/1000000000): 2185.4818
                # SUM(rows_fetched): 94673
                # SUM(fetch_latency/1000000000): 2008.7388
                # SUM(rows_inserted): 32
                # SUM(insert_latency/1000000000): 6.3424
                # SUM(rows_updated): 1383
                # SUM(update_latency/1000000000): 169.4212
                # SUM(rows_deleted): 30
                # SUM(delete_latency/1000000000): 0.9793
                # SUM(io_read_requests): 5074804
                # SUM(io_read): 880240511
                # SUM(io_read_latency/1000000000): 8812.6589
                # SUM(io_write_requests): 2541
                # SUM(io_write): 41631744
                # SUM(io_write_latency/1000000000): 56.2201
                # SUM(io_misc_requests): 4362825
                # SUM(io_misc_latency/1000000000): 9762.8197
                # 1 row in set (0.85 sec)
                start_time = str(time.time())
                is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_DATABASE_SCHEMA_STATISTICS).format('%'))
                if is_success:
                    for each in output_list:
                        result_data['TSTL']                = float(each[0]) if each[0] else 0 # millisecond # total_latency # The total wait time of timed I/O events for the table.
                        result_data['TSRF']                = int(each[1]) if each[1] else 0 # count # rows_fetched # The total number of rows read from the table.
                        result_data['TSFL']                = float(each[2]) if each[2] else 0 # millisecond # fetch_latency # The total wait time of timed read I/O events for the table.
                        result_data['TSRI']                = int(each[3]) if each[3] else 0 # count # rows_inserted # The total number of rows inserted into the table.
                        result_data['TSIL']                = float(each[4]) if each[4] else 0 # millisecond # insert_latency # The total wait time of timed insert I/O events for the table.
                        result_data['TSRU']                = int(each[5]) if each[5] else 0 # count # rows_updated # The total number of rows updated in the table.
                        result_data['TSUL']                = float(each[6]) if each[6] else 0 # millisecond # update_latency # The total wait time of timed update I/O events for the table.
                        result_data['TSRD']                = int(each[7]) if each[7] else 0 # count # rows_deleted # The total number of rows deleted from the table.
                        result_data['TSDL']                = float(each[8]) if each[8] else 0 # millisecond # delete_latency # The total wait time of timed delete I/O events for the table.
                        result_data['TSIORR']              = int(each[9]) if each[9] else 0 # count # io_read_requests # The total number of read requests for the table.
                        result_data['TSIOR']               = int(each[10]) if each[10] else 0 # bytes # io_read # The total number of bytes read from the table.
                        result_data['TSIORL']              = float(each[11]) if each[11] else 0 # millisecond # io_read_latency # The total wait time of reads from the table.
                        result_data['TSIOWR']              = int(each[12]) if each[12] else 0 # count # io_write_requests # The total number of write requests for the table.
                        result_data['TSIOW']               = int(each[13]) if each[13] else 0 # bytes # io_write # The total number of bytes written to the table.
                        result_data['TSIOWL']              = float(each[14]) if each[14] else 0 # millisecond # io_write_latency # The total wait time of writes to the table.
                        result_data['TSIOMR']              = int(each[15]) if each[15] else 0 # count # io_misc_requests # The total number of miscellaneous I/O requests for the table.
                        result_data['TSIOML']              = float(each[16]) if each[16] else 0 # millisecond # io_misc_latency # The total wait time of miscellaneous I/O requests for the table.
                        result_data['last_mdss_dc_time']   = str(start_time)

                # mysql> SELECT IFNULL(SUM(COUNT_STAR),0) AS count, IFNULL((SUM(SUM_TIMER_WAIT)/SUM(COUNT_STAR))/1000000000,0) AS avg_waittime, IFNULL((SUM(SUM_LOCK_TIME)/SUM(COUNT_STAR))/1000000000,0) AS avg_locktime, IFNULL(SUM(SUM_ERRORS)/SUM(COUNT_STAR),0) AS avg_error, IFNULL(SUM(SUM_WARNINGS)/SUM(COUNT_STAR),0) AS avg_warning, IFNULL(SUM(SUM_ROWS_AFFECTED)/SUM(COUNT_STAR),0) AS avg_rows_affected, IFNULL(SUM(SUM_ROWS_SENT)/SUM(COUNT_STAR),0) AS avg_rows_sent, IFNULL(SUM(SUM_CREATED_TMP_DISK_TABLES)/SUM(COUNT_STAR),0) AS avg_tmp_disk_tb_crt, IFNULL(SUM(SUM_CREATED_TMP_TABLES)/SUM(COUNT_STAR),0) AS avg_tmp_tb_crt, IFNULL(SUM(SUM_ERRORS),0) as
                # sum_error, IFNULL(SUM(SUM_WARNINGS),0) as sum_warning FROM performance_schema.events_statements_summary_by_digest WHERE SCHEMA_NAME='jbossdb' AND LAST_SEEN > DATE_SUB(NOW(), INTERVAL 300000000 SECOND);
                # +-------+--------------+--------------+-----------+-------------+-------------------+---------------+---------------------+----------------+-----------+-------------+
                # | count | avg_waittime | avg_locktime | avg_error | avg_warning | avg_rows_affected | avg_rows_sent | avg_tmp_disk_tb_crt | avg_tmp_tb_crt | sum_error | sum_warning |
                # +-------+--------------+--------------+-----------+-------------+-------------------+---------------+---------------------+----------------+-----------+-------------+
                # |     0 |   0.00000000 |   0.00000000 |    0.0000 |      0.0000 |            0.0000 |        0.0000 |              0.0000 |         0.0000 |         0 |           0 |
                # +-------+--------------+--------------+-----------+-------------+-------------------+---------------+---------------------+----------------+-----------+-------------+
                # 1 row in set (0.05 sec)
                # separate child database summary page data [inspired from datadog]
                is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_AVG_QUERY_RUN_TIME).format('%')) # the total bytes of memory allocated within the server.
                if is_success:
                    for each in output_list:
                        result_data['ITCS']                     = str(each[0]) if each[0] else 0  # count  # instance count star   # ITCS
                        result_data['ITART']                    = str(each[1]) if each[1] else 0 # millisecond  # instance average query run time  # ITART
                        result_data['ITALT']                    = str(each[2]) if each[2] else 0  # millisecond # instance average lock time  # ITALT
                        result_data['ITAER']                    = str(each[3]) if each[3] else 0  # count  # instance average error  # ITAER
                        result_data['ITAWN']                    = str(each[4]) if each[4] else 0  # count  # instance average warnings # ITAWN
                        result_data['ITARF']                    = str(each[5]) if each[5] else 0  # count  # instance average rows affected # ITARF
                        result_data['ITARS']                    = str(each[6]) if each[6] else 0  # count  # instance average rows sent # ITARS
                        result_data['ITATDTC']                  = str(each[7]) if each[7] else 0  # count  # instance average temp disk table created # ITATDTC
                        result_data['ITATTC']                   = str(each[8]) if each[8] else 0  # count  # instance average temp table created # ITATTC
                        result_data['TSERC']                    = str(each[9]) if each[9] else 0  # count  # instance total error count in 300 second # TSERC
                        result_data['TSWNC']                    = str(each[10]) if each[10] else 0  # count  # instance total warn count in 300 second # TSWNC

                # dummy data for child database
                # each database in child key is iterated and called to collect_child_database_counter_data
                # with separate thread [new change] [INFORMATION_SCHEMA] issue
                child_db_dummy_data  = {}
                thread_obj_dict      = {}
                if self.child_keys:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.child_keys)+1) as executor:
                        for database in self.child_keys:
                            # all these mysql generated database are avoided for performance purpose # testing
                            #if database in ['information_schema', 'sys', 'mysql', 'performance_schema']:
                            #    continue
                            # created a new concurrency thread obj and stores in thread_obj_dict
                            thread_obj = executor.submit(self.collect_child_database_counter_data, database)
                            thread_obj_dict[thread_obj]   = "db_thread"
                            result_data['Databases']      = {}
                            # once each thread completes its all task, result obtained
                            for each_divided_db_list in concurrent.futures.as_completed(thread_obj_dict):
                                db_data = each_divided_db_list.result()
                                child_db_dummy_data[database] = db_data

                result_data['child_data']    = child_db_dummy_data
                result_data['last_dc_time']  = str(time.time())

                self.mysql_util_obj.close_db_connection()
            else:
                DatabaseLogger.Logger.log(' ************ cannot connect to the mysql instance for counter data collection *************')
        except Exception as e:
            is_success = False
            err_msg = str(e)
            DatabaseLogger.Logger.log('Exception while collecting global performance stats for startup :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return is_success, result_data, err_msg