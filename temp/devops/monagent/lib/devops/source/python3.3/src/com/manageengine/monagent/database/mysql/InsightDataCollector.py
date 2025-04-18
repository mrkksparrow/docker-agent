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


class MySQLInsightDataCollector(object):
    def init(self, input_param):
        try:
            self.mysql_util_obj = MySQLUtil.MySQLConnector()
            self.mysql_util_obj.init(input_param)

            self.instance                    = input_param['instance']
            self.mid                         = input_param['mid']

            self.session                     = input_param['session']
            self.top_query                   = input_param['top_query']
            self.slow_query                  = input_param['slow_query']
            self.memory                      = input_param['memory']
            self.file_io                     = input_param['file_io']
            self.event_analysis              = input_param['event_analysis']
            self.error_analysis              = input_param['error_analysis']
            self.statement_analysis          = input_param['statement_analysis']
            self.user_analysis               = input_param['user_analysis']
            self.host_analysis               = input_param['host_analysis']

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while initialising Database List Discover Class :: {}'.format(e))
            traceback.print_exc()


    def collect_insight_common_variables(self):
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_INSIGHT_COMMON_VARIABLES_QUERY)
            if is_success:
                for variable in output_list:
                    if variable[0] in MySQLConstants.MYSQL_INSIGHT_COMMON_VARIABLES.keys():
                        MySQLConstants.MYSQL_INSIGHT_COMMON_VARIABLES[variable[0]] = str(variable[1])
            else:
                DatabaseLogger.Logger.log('common variable query have no output')
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting insight common variables :: {} : {}'.format(self.instance,e))
            traceback.print_exc()


    # session related metrics of current respective mysql instance node   [SYS.X$SESSION]
    # IMPORTANT [[[ query not available for 5.6,5.7 ]]] need to change
    def collect_session_data(self):
        result_list = []
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_SESSION_METRICS)
            if is_success:
                for session in output_list:
                    single_session = {}
                    single_session['Category'] = 'SESSION'
                    single_session['thread_id'] = str(session[0]) # TI
                    single_session['pid'] = str(session[1]) # PID
                    single_session['state'] = str(session[2]) # SST
                    single_session['user'] = str(session[3]) # SUSR
                    single_session['db'] = str(session[4]) # SDBN
                    single_session['program_name'] = str(session[5]) # PN
                    single_session['current_memory_kb'] = str(session[6]) # MUKB
                    single_session['cpu_time_ms'] = str(session[7]) # CTM
                    single_session['command'] = str(session[8]) # SCMD
                    single_session['current_statement'] = str(session[9]) # QRS
                    single_session['lock_latency_ms'] = str(session[10]) # LLM
                    single_session['last_query'] = str(session[11]) # LQST
                    single_session['last_query_cpu_ms'] = str(session[12]) # LQCM
                    result_list.append(single_session)
                #self.result_insight_dict['session'] = result_list
            else:
                result_list.append({'status': '0', 'err_msg': err_msg})
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting session related metrics :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return result_list


    # slow query data collected, point to point data     IMPORTANT [[ nned to change query or method ]]  [INFORMATION_SCHEMA.PROCESSLIST]
    # collecting queries's data which are currently running with more than long_query_time defined in global variables
    def collect_slow_query_data(self):
        result_list = []
        try:
            if MySQLConstants.MYSQL_INSIGHT_COMMON_VARIABLES['long_query_time']:
                sq_data_query = MySQLConstants.MYSQL_SLOW_QUERY.format(str(MySQLConstants.MYSQL_INSIGHT_COMMON_VARIABLES['long_query_time']))
                is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(sq_data_query)
                if is_success:
                    #DatabaseLogger.Logger.log('sucess :: {} '.format(output_list))
                    for slow_query in output_list:
                        single_slow_query = {}
                        single_slow_query['Category'] = 'SLOW_QUERY'
                        single_slow_query['id'] = str(slow_query[0]) # SQID
                        single_slow_query['user'] = str(slow_query[1]) # SQUSR
                        single_slow_query['host'] = str(slow_query[2]) # SQHN
                        single_slow_query['db'] = str(slow_query[3]) # SQDBN
                        single_slow_query['command'] = str(slow_query[4]) # SQCMD
                        single_slow_query['time'] = str(slow_query[5]) # TM
                        single_slow_query['state'] = str(slow_query[6]) # SQST
                        single_slow_query['info'] = str(slow_query[7]) # INF
                        result_list.append(single_slow_query)

                    #self.result_insight_dict['slow_query']=result_list
                else:
                    result_list.append({'status': '0', 'err_msg': err_msg})
            else:
                DatabaseLogger.Logger.log('long query time for calculating slow query not found hence skipping ')
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting slow query data :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return result_list

    # collects top 10 query based on cpu consumption  [SYS.S$STATEMENT_ANALYSIS]
    # IMPORTANT [[[ query not available for 5.6]]] need to change
    def collect_top_query_data(self):
        result_list = []
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_DATABASE_STATEMENT_ANALYSIS).format('%','300'))
            if is_success:
                for query in output_list:
                    single_query = {}
                    single_query['Category'] = 'TOP_CPU_QUERY'
                    single_query['table_name'] = query[0]
                    single_query['DIGEST_TEXT'] = str(query[1])
                    single_query['COUNT_STAR'] = str(query[2])
                    single_query['SUM_TIMER_WAIT'] = str(query[3])
                    single_query['MIN_TIMER_WAIT'] = str(query[4])
                    single_query['AVG_TIMER_WAIT'] = str(query[5])
                    single_query['MAX_TIMER_WAIT'] = str(query[6])
                    single_query['SUM_LOCK_TIME'] = str(query[7])
                    single_query['SUM_ERRORS'] = str(query[8])
                    single_query['SUM_WARNINGS'] = str(query[9])
                    single_query['SUM_ROWS_AFFECTED'] = str(query[10])
                    single_query['SUM_ROWS_SENT'] = str(query[11])
                    single_query['SUM_ROWS_EXAMINED'] = str(query[12])
                    single_query['SUM_CREATED_TMP_DISK_TABLES'] = str(query[13])
                    single_query['SUM_CREATED_TMP_TABLES'] = str(query[14])
                    single_query['SUM_SELECT_FULL_JOIN'] = str(query[15])
                    single_query['SUM_SELECT_FULL_RANGE_JOIN'] = str(query[16])
                    single_query['SUM_SELECT_RANGE'] = str(query[17])
                    single_query['SUM_SELECT_RANGE_CHECK'] = str(query[18])
                    single_query['SUM_SELECT_SCAN'] = str(query[19])
                    single_query['SUM_SORT_MERGE_PASSES'] = str(query[20])
                    single_query['SUM_SORT_RANGE'] = str(query[21])
                    single_query['SUM_SORT_ROWS'] = str(query[22])
                    single_query['SUM_SORT_SCAN'] = str(query[23])
                    single_query['SUM_NO_INDEX_USED'] = str(query[24])
                    single_query['FIRST_SEEN'] = str(query[25])
                    single_query['LAST_SEEN'] = str(query[26])
                    result_list.append(single_query)

                #self.result_insight_dict['top_cpu_query'] = result_list
            else:
                result_list.append({'status': '0', 'err_msg': err_msg})
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting top cpu query data :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return result_list

    # collects top 10 query based on execution count  [SYS.S$STATEMENT_ANALYSIS]
    # IMPORTANT [[[ query not available for 5.6]]] need to change
    def collect_top_exe_count_data(self):
        result_list = []
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_DATABASE_STATEMENT_ANALYSIS_EXE_CNT).format('%','300'))
            if is_success:
                for query in output_list:
                    single_query = {}
                    single_query['Category'] = 'TOP_EXC_QUERY'
                    single_query['table_name'] = query[0]
                    single_query['DIGEST_TEXT'] = str(query[1])
                    single_query['COUNT_STAR'] = str(query[2])
                    single_query['SUM_TIMER_WAIT'] = str(query[3])
                    single_query['MIN_TIMER_WAIT'] = str(query[4])
                    single_query['AVG_TIMER_WAIT'] = str(query[5])
                    single_query['MAX_TIMER_WAIT'] = str(query[6])
                    single_query['SUM_LOCK_TIME'] = str(query[7])
                    single_query['SUM_ERRORS'] = str(query[8])
                    single_query['SUM_WARNINGS'] = str(query[9])
                    single_query['SUM_ROWS_AFFECTED'] = str(query[10])
                    single_query['SUM_ROWS_SENT'] = str(query[11])
                    single_query['SUM_ROWS_EXAMINED'] = str(query[12])
                    single_query['SUM_CREATED_TMP_DISK_TABLES'] = str(query[13])
                    single_query['SUM_CREATED_TMP_TABLES'] = str(query[14])
                    single_query['SUM_SELECT_FULL_JOIN'] = str(query[15])
                    single_query['SUM_SELECT_FULL_RANGE_JOIN'] = str(query[16])
                    single_query['SUM_SELECT_RANGE'] = str(query[17])
                    single_query['SUM_SELECT_RANGE_CHECK'] = str(query[18])
                    single_query['SUM_SELECT_SCAN'] = str(query[19])
                    single_query['SUM_SORT_MERGE_PASSES'] = str(query[20])
                    single_query['SUM_SORT_RANGE'] = str(query[21])
                    single_query['SUM_SORT_ROWS'] = str(query[22])
                    single_query['SUM_SORT_SCAN'] = str(query[23])
                    single_query['SUM_NO_INDEX_USED'] = str(query[24])
                    single_query['FIRST_SEEN'] = str(query[25])
                    single_query['LAST_SEEN'] = str(query[26])
                    result_list.append(single_query)

                #self.result_insight_dict['top_cpu_query'] = result_list
            else:
                result_list.append({'status': '0', 'err_msg': err_msg})
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting top cpu query data :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return result_list

    # collects accounts data that has connected to the MySQL server  [PERFORMANCE_SCHEMA.ACCOUNTS]
    def collect_pf_accounts_data(self):
        result_list = []
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_PS_ACCOUNTS)
            if is_success:
                for instance in output_list:
                    single_instance = {}
                    single_instance['Category'] = 'ACCOUNTS'
                    single_instance['AU'] = str(instance[0])
                    single_instance['AH'] = str(instance[1])
                    single_instance['ACC'] = str(instance[2])
                    single_instance['ATC'] = str(instance[3])
                    result_list.append(single_instance)
                #self.result_insight_dict['accounts'] = result_list
            else:
                result_list.append({'status': '0', 'err_msg': err_msg})
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting accounts connected data :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return result_list

    # collects global wait events sorted by total latency of the even  [sys.x$waits_global_by_latency]
    def collect_waits_global_by_latency(self):
        result_list = []
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_DATABASE_WAIT_EVENT_LATENCY)
            if is_success:
                for instance in output_list:
                    single_instance = {}
                    single_instance['Category'] = 'GLOBAL_WAITS'
                    single_instance['events'] = str(instance[0])
                    single_instance['total_count'] = str(instance[1])   # The total number of occurrences of the event.
                    single_instance['total_latency'] = str(instance[2])
                    single_instance['avg_latency'] = str(instance[3])
                    single_instance['max_latency'] = str(instance[4])
                    result_list.append(single_instance)
                #self.result_insight_dict['global_events_waits_by_latency'] = result_list
            else:
                result_list.append({'status': '0', 'err_msg': err_msg})
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting global waits by total latency :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return result_list

    # collects global wait events sorted by total latency of the even  [sys.x$waits_global_by_latency]
    def collect_top_memory_by_users(self):
        result_list = []
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_USERS_MEMORY)
            # see mysqlconstants -> MYSQL_USERS_MEMORY_GROUPING
            if is_success:
                for instance in output_list:
                    single_instance = {}
                    single_instance['Category'] = 'USER_MEMORY'
                    single_instance['user'] = instance[0] # USU
                    single_instance['current_count_used'] = str(instance[1]) # USCCU
                    single_instance['current_allocated'] = str(instance[2]) # USCA
                    single_instance['current_avg_alloc'] = str(instance[3]) # USCAA
                    single_instance['current_max_alloc'] = str(instance[4]) # USCMA
                    single_instance['total_allocated'] = str(instance[5]) # USTA
                    result_list.append(single_instance)
                #self.result_insight_dict['top_users_by_memory'] = result_list
            else:
                result_list.append({'status': '0', 'err_msg': err_msg})
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting top users by memory :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return result_list

    # collects global wait events sorted by total latency of the even  [sys.x$waits_global_by_latency]
    def collect_top_memory_by_hosts(self):
        result_list = []
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_HOSTS_MEMORY)
            # see mysqlconstants -> MYSQL_HOSTS_MEMORY_GROUPING
            if is_success:
                for instance in output_list:
                    single_instance = {}
                    single_instance['Category'] = 'HOST_MEMORY'
                    single_instance['host'] = instance[0] # HTH
                    single_instance['current_count_used'] = str(instance[1]) # HTCCU
                    single_instance['current_allocated'] = str(instance[2]) # HTCA
                    single_instance['current_avg_alloc'] = str(instance[3]) # HTCAA
                    single_instance['current_max_alloc'] = str(instance[4]) # HTCMA
                    single_instance['total_allocated'] = str(instance[5]) # HTTA
                    result_list.append(single_instance)
                #self.result_insight_dict['top_hosts_by_memory'] = result_list
            else:
                result_list.append({'status': '0', 'err_msg': err_msg})
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting top hosts by memory :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return result_list

    # collects global wait events sorted by total latency of the even  [sys.x$waits_global_by_latency]
    def collect_top_file_io_activity(self):
        result_list = []
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_FILE_IO_ACTIVITY)
            # see mysqlconstants -> MYSQL_FILE_IO_ACTIVITY_GROUPING
            if is_success:
                for instance in output_list:
                    single_instance = {}
                    single_instance['Category'] = 'FILE_IO_ACTIVITY'
                    single_instance['file'] = str(instance[0]) # IOFE
                    single_instance['count_read'] = str(instance[1]) # IOCR
                    single_instance['total_read'] = str(instance[2]) # IOTR
                    single_instance['avg_read'] = str(instance[3]) # IOAR
                    single_instance['count_write'] = str(instance[4]) # IOCW
                    single_instance['total_written'] = str(instance[5]) # IOTW
                    single_instance['avg_write'] = str(instance[6]) # IOQW
                    single_instance['total'] = str(instance[7]) # IOT
                    single_instance['write_pct'] = str(instance[8]) # IOWP
                    result_list.append(single_instance)
                #self.result_insight_dict['top_file_io_activity'] = result_list
            else:
                result_list.append({'status': '0', 'err_msg': err_msg})
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting top file io activity:: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return result_list

    # collects global wait events sorted by total latency of the even  [sys.x$waits_global_by_latency]
    def collect_top_file_io_latency(self):
        result_list = []
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_FILE_IO_LATENCY)
            # see mysqlconstants -> MYSQL_FILE_IO_LATENCY_GROUPING
            if is_success:
                for instance in output_list:
                    single_instance = {}
                    single_instance['Category'] = 'FILE_IO_LATENCY'
                    single_instance['file'] = str(instance[0]) # IOLFE
                    single_instance['total'] = str(instance[1]) # IOLT
                    single_instance['total_latency'] = str(instance[2]) # IOLTL
                    single_instance['count_read'] = str(instance[3]) # IOLCR
                    single_instance['read_latency'] = str(instance[4]) # IOLRL
                    single_instance['count_write'] = str(instance[5]) # IOLCW
                    single_instance['write_latency'] = str(instance[6]) # IOLWL
                    single_instance['count_misc'] = str(instance[7]) # IOLCM
                    single_instance['misc_latency'] = str(instance[8]) # IOLML
                    result_list.append(single_instance)
                #self.result_insight_dict['top_file_io_latency'] = result_list
            else:
                result_list.append({'status': '0', 'err_msg': err_msg})
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting top file io by latency :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return result_list


    # collects global wait events sorted by total latency of the even  [sys.x$waits_global_by_latency]
    def collect_top_event_io_latency(self):
        result_list = []
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_EVENT_IO_LATENCY)
            # see mysqlconstants -> MYSQL_EVENT_IO_LATENCY_GROUPING
            if is_success:
                for instance in output_list:
                    single_instance = {}
                    single_instance['Category'] = 'EVENT_IO_LATENCY'
                    single_instance['event_name'] = str(instance[0]) # IOEEN
                    single_instance['total'] = str(instance[1]) # IOET
                    single_instance['total_latency'] = str(instance[2]) # IOETL
                    single_instance['avg_latency'] = str(instance[3]) # IOEAL
                    single_instance['max_latency'] = str(instance[4]) # IOEMAL
                    single_instance['read_latency'] = str(instance[5]) # IOERL
                    single_instance['write_latency'] = str(instance[6]) # IOEWL
                    single_instance['misc_latency'] = str(instance[7]) # IOEMSL
                    single_instance['count_read'] = str(instance[8]) # IOECR
                    single_instance['total_read'] = str(instance[9]) # IOETR
                    single_instance['avg_read'] = str(instance[10]) # IOEAR
                    single_instance['count_write'] = str(instance[11]) # IOECW
                    single_instance['total_written'] = str(instance[12]) # IOETW
                    single_instance['avg_written'] = str(instance[13]) # IOEAW
                    result_list.append(single_instance)
                #self.result_insight_dict['top_events_io_latency'] = result_list
            else:
                result_list.append({'status': '0', 'err_msg': err_msg})
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting top event io by latency :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return result_list

    # collects global wait events sorted by total latency of the even  [sys.x$waits_global_by_latency]
    def collect_recent_stmt_err_wrn(self):
        result_list = []
        try:
            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_RECENT_STATEMENTS_ERR_WRN).format('%','100000000'))
            # see mysqlconstants -> MYSQL_RECENT_STATEMENTS_ERR_WRN_GROUPING
            if is_success:
                for instance in output_list:
                    single_instance = {}
                    single_instance['Category'] = 'STATEMENT_ERROR_WARNING'
                    single_instance['query'] = str(instance[0]) # SEWQ
                    single_instance['db'] = str(instance[1]) # SEWDB
                    single_instance['exec_count'] = str(instance[2]) # SEWEC
                    single_instance['errors'] = str(instance[3]) # SEWER
                    single_instance['error_pct'] = str(instance[4]) # SEWERP
                    single_instance['warnings'] = str(instance[5]) # SEWWN
                    single_instance['warning_pct'] = str(instance[6]) # SEWWNP
                    single_instance['first_seen'] = str(instance[7]) # SEWFS
                    single_instance['last_seen'] = str(instance[8]) # SEWLS
                    result_list.append(single_instance)
                #self.result_insight_dict['top_recent_statement_err_warn'] = result_list
            else:
                result_list.append({'status': '0', 'err_msg': err_msg})
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting statement error and warnings :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return result_list


    def collect_insight_data(self):
        result_data = {}
        is_success = True
        err_msg = None
        try:

            is_success, err_msg = self.mysql_util_obj.get_db_connection()
            if is_success:
                DatabaseLogger.Logger.log('====== Total Execution Time before DC Start :: {} ======'.format(self.mysql_util_obj.total_execution_time),'QUERY')
                is_success, version, err_msg = self.mysql_util_obj.get_mysql_version()
                MySQLConstants.set_query_for_data_collection(version)

                self.collect_insight_common_variables()

                # session opened related metrics
                # IMPORTANT  [[ only for 5.7, 8.0 ]]
                if self.session == 'true':
                    result_data['SESSION'] = self.collect_session_data()

                # queries that are executing exceding long_query_time is collected
                # IMPORTANT [[ need to change collecting method ]]
                if self.slow_query == 'true':
                    result_data['SLOW_QUERY'] = self.collect_slow_query_data()

                # collecting top 10 query based on high cpu consumption
                if self.top_query == 'true':
                    result_data['TOP_EXC_QUERY'] = self.collect_top_exe_count_data()

                # collecting user and host connections established from different accounts
                result_data['ACCOUNTS'] = self.collect_pf_accounts_data()

                # global events by wait sorted by total latency
                if self.statement_analysis == 'true':
                    result_data['GLOBAL_WAITS'] = self.collect_waits_global_by_latency()

                # global events by wait sorted by total latency
                if self.user_analysis == 'true':
                    result_data['USER_MEMORY'] = self.collect_top_memory_by_users()

                # global events by wait sorted by total latency
                if self.host_analysis == 'true':
                    result_data['HOST_MEMORY'] = self.collect_top_memory_by_hosts()

                # global events by wait sorted by total latency
                if self.file_io == 'true':
                    result_data['FILE_IO_ACTIVITY'] = self.collect_top_file_io_activity()

                # global events by wait sorted by total latency
                if self.file_io == 'true':
                    result_data['FILE_IO_LATENCY'] = self.collect_top_file_io_latency()

                # global events by wait sorted by total latency
                if self.event_analysis == 'true':
                    result_data['EVENT_IO_LATENCY'] = self.collect_top_event_io_latency()

                # global events by wait sorted by total latency
                if self.error_analysis == 'true':
                    result_data['STATEMENT_ERROR_WARNING'] = self.collect_recent_stmt_err_wrn()

                DatabaseLogger.Logger.log('====== Total Execution Time ag=fter DC Start :: {} ======'.format(self.mysql_util_obj.total_execution_time),'QUERY')
                self.mysql_util_obj.close_db_connection()


        except Exception as e:
            is_success = False
            err_msg = str(e)
            DatabaseLogger.Logger.log('Exception while collecting database insight data :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return is_success, result_data, err_msg