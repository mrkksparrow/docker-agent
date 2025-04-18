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
from com.manageengine.monagent.database.mysql import MySQLConstants,MySQLUtil,PerformanceCounterDataCollector



# class object to collect the database list for data collection
class DatabaseDiscovery(object):
    # init monitor related data for creating separate connection from input param [user/pass/host/port]
    def init(self, input_param):
        try:
            self.instance                     = input_param['instance']
            self.mid                          = input_param['mid']
            self.mysql_util_obj               = MySQLUtil.MySQLConnector()
            self.mysql_util_obj.init(input_param)
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while initialising Database List Discover Class :: {} : {}'.format(self.instance,e))
            traceback.print_exc()

    # collects the database list
    def collect_database_list(self):
        database_list = []
        is_success = True
        err_msg = None
        try:
            # get connection for the cursor created in init
            is_success, err_msg = self.mysql_util_obj.get_db_connection()

            # mysql> SHOW DATABASES;
            # +--------------------+
            # | Database           |
            # +--------------------+
            # | information_schema |
            # | db2001db           |
            # | db336odb           |
            # | db337odb           |
            # | sys                |
            # +--------------------+
            # 46 rows in set (0.01 sec)
            # collects the list of databases
            if is_success:
                is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_LIST_DATABASE)
                if is_success and output_list:
                    for database in output_list:
                        database_list.append(database[0])
                elif is_success and not output_list:
                    DatabaseLogger.Logger.log('No database found')

                # close connection after the db list retrival
                self.mysql_util_obj.close_db_connection()

        except Exception as e:
            is_success = False
            err_msg = str(e)
            DatabaseLogger.Logger.log('Exception while collecting database list :: {} : {}'.format(self.instance,e))
            traceback.print_exc()

        finally:
            return is_success, database_list, err_msg



# common class for taking metrics [ db size, db row count, db column count, top tables based on size]
# issue was with INFORMATION_SCHEMA database, [only place db size related metrics can be found]
# no index in INFORMATION_SCHEMA, hence data collection for larger databases [more than 10000 rows, more than 1 gb] might take more time for execution
# percona proof [https://www.percona.com/blog/2011/12/23/solving-information_schema-slowness/]
# mysql article [https://dev.mysql.com/blog-archive/mysql-8-0-improvements-to-information_schema/]
# not used as of now [version 1 Sep 09, 2022], should find a way, or search idera query
class CollectTotalDBSizeData(object):
    # yet to be coded
    def init(self, mysql_util_obj, db_child_config, previous_data, input_param=None):
        try:
            self.mysql_util_obj = MySQLUtil.MySQLConnector()
            self.mysql_util_obj.init(input_param)
            self.child_keys                = db_child_config
            self.previous_child_data       = previous_data # previous_data['child_data']
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while initialising CollectTotalDBSizeData :: {}'.format(e))
            traceback.print_exc()

    def collect_db_size_row_data(self,):
        try:
            is_success, err_msg = self.mysql_util_obj.get_db_connection()
            total_query_with_db_list = ""

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting collect_db_size_row_data :: {}'.format(e))
            traceback.print_exc()



# class for collecting child database data
#
class DatabaseSchemaChildData(object):
    # initialize mysql connection for this thread and get child keys [db names] and previous db data for calculating volatile data
    # db_size_top_tb -> database for which size and top tables based on size metrics will be takes [irrespective of INFORMATION_SCHEMA issue]
    def init(self, db_child_config, previous_data, input_param=None):
        try:
            #DatabaseLogger.Logger.log('testing check :: {} :: {} :: {}'.format(mysql_util_obj, db_child_config, previous_data))
            self.child_keys                    = db_child_config
            self.mid                           = input_param['mid']
            self.mysql_util_obj                = MySQLUtil.MySQLConnector()
            self.mysql_util_obj.init(input_param)
            self.time_diff                     = input_param['time_diff']
            self.collect_size_top_tb           = input_param['db_size_top_tb'] if 'db_size_top_tb' in input_param['db_size_top_tb'] else []
            self.previous_child_data           = previous_data
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while initialising Database Schema Child Data :: {}'.format(e))
            traceback.print_exc()


    # collect database related metrics
    def collect_database_schema_metrics(self):
        result_dict = {}
        child_db_data_dict = {}
        current_data_for_next_poll = {}
        is_success = True
        err_msg = None
        try:

            # open the cursor connection for mysql connection
            is_success, err_msg = self.mysql_util_obj.get_db_connection()

            for database in self.child_keys:
                # for each database in self.child_keys dc happens [divided in group in datacollector.py] [ per thread n no. of databases]
                if is_success:
                    # if database added in middle of dc
                    # in case of dc started right after database discover, where there is no time to get dummy data for child database
                    # if no previous data found for the particular db, only dummy dc will happen, real dc happens from next dc
                    if database not in self.previous_child_data:
                        DatabaseLogger.Logger.log('No previous data found :: {}'.format(database))
                        prf_stp_dc_obj                       = PerformanceCounterDataCollector.PerformanceCounterCollector()
                        current_data_for_next_poll[database] = prf_stp_dc_obj.collect_child_database_counter_data(database,self.mysql_util_obj)
                        result_dict[database] = {}
                        result_dict[database]['meta_data']           = {}
                        result_dict[database]['meta_data']['hname']  = self.mysql_util_obj.host
                        result_dict[database]['meta_data']['iname']  = self.mysql_util_obj.instance
                        result_dict[database]['cid']                 = self.child_keys[database] # cid
                        result_dict[database]['mid']                 = self.mid # parent mid
                        result_dict[database]['schema_name']         = database
                        result_dict[database]['availability']        = '1'
                        result_dict[database]['ct']                  = self.mysql_util_obj.getTimeInMillis(self.time_diff)
                        result_dict[database]['DC ERROR'] = {}
                        #DatabaseLogger.Logger.log('Dummy data collection successful :: {}'.format(current_data_for_next_poll[database]))
                    else:
                        result_dict[database] = {}                         # result dict to be returned
                        current_data_for_next_poll[database] = {}          # current data stored and sent separate, for next poll interval
                        result_dict[database]['meta_data']           = {}
                        result_dict[database]['meta_data']['hname']  = self.mysql_util_obj.host
                        result_dict[database]['meta_data']['iname']  = self.mysql_util_obj.instance
                        result_dict[database]['cid']                 = self.child_keys[database] # cid
                        result_dict[database]['mid']                 = self.mid # parent mid
                        result_dict[database]['schema_name']         = database
                        result_dict[database]['ct']                  = self.mysql_util_obj.getTimeInMillis(self.time_diff) # collection time not working, spoiling whole data in server side [inform atchaya]


                        # mysql> SELECT IFNULL(SUM(data_length+index_length)/1024/1024,0) AS total_size_mb, IFNULL(SUM(index_length)/1024/1024,0) AS index_size_mb, IFNULL(SUM(data_length)/1024/1024,0) AS data_size_mb, count(1) AS table_count, IFNULL(SUM(table_rows),0) as row_count FROM INFORMATION_SCHEMA.TABLES WHERE table_schema='jbossdb';
                        # +---------------+---------------+--------------+-------------+-----------+
                        # | total_size_mb | index_size_mb | data_size_mb | table_count | row_count |
                        # +---------------+---------------+--------------+-------------+-----------+
                        # |   38.26562500 |   13.60937500 |  24.65625000 |        1463 |      8982 |
                        # +---------------+---------------+--------------+-------------+-----------+
                        # 1 row in set (0.84 sec)
                        # collects db name, total_size_byt, index_size_mb, data_size_byt, table_count, row count of the db, from [information_schema.tables]
                        # INFORMATION_SCHEMA related metrics will not be taken by default, due to mysql issue [no index]
                        # if mysql.cfg instance contains option [collect_size_top_tb = ['db_name1','db_name2']] metrics will be taken
                        if database in self.collect_size_top_tb:
                            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_SCHEMAS_SIZE_MB).format(database))
                            if is_success:
                                for schema in output_list:
                                    single_schema = {}
                                    result_dict[database]['TSMB'] = str(schema[0]) # mb # total_size_mb
                                    result_dict[database]['ISMB'] = str(schema[1]) # mb # index_size_mb
                                    result_dict[database]['DSMB'] = str(schema[2]) # mb # data_size_mb
                                    result_dict[database]['TBC'] = str(schema[3]) # count# table_count
                                    result_dict[database]['RWC'] = str(schema[4]) # count# table_count


                            # mysql> SELECT count(1) AS column_count FROM INFORMATION_SCHEMA.COLUMNS WHERE table_schema='jbossdb';
                            # +--------------+
                            # | column_count |
                            # +--------------+
                            # |        11086 |
                            # +--------------+
                            # 1 row in set (0.05 sec)
                            # column count from [INFORMATION_SCHEMA.COLUMNS]
                            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_DATABASE_COLUMNS_COUNT).format(database))
                            if is_success:
                                for schema in output_list:#
                                    result_dict[database]['CLC'] = str(schema[0]) # count # column_count


                        if database in self.collect_size_top_tb:
                            top_tables_by_size = []
                            is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_DATABASE_TOP_10_SIZE_TABLE).format(database))
                            if is_success:
                                for table in output_list:
                                    single_table                = {}
                                    single_table['CATEGORY']    = 'top_tables_by_size'
                                    single_table['DBN']         = database
                                    single_table['TBN']         = table[0]
                                    single_table['TSBT']        = str(table[1])
                                    single_table['DTSBT']       = str(table[2])
                                    single_table['INSBT']       = str(table[3])
                                    single_table['RWC']         = str(table[4])
                                    # hard coding other data to "-" [to reduce query run time and execution count] [in client only showing limited data]
                                    single_table['RFS']         = str("-")
                                    single_table['RFSL']        = str("-")
                                    single_table['CLC']         = str("-")
                                    top_tables_by_size.append(single_table)
                                result_dict[database]['top_tables_by_size'] = top_tables_by_size


                        # mysql> SELECT object_name, rows_full_scanned, latency FROM sys.x$schema_tables_with_full_table_scans WHERE object_schema='db2281db' LIMIT 10;
                        # +----------------------------+-------------------+-------------+
                        # | object_name                | rows_full_scanned | latency     |
                        # +----------------------------+-------------------+-------------+
                        # | WM_NOTIFICATION_ATTRIBUTES |             28675 | 51220950904 |
                        # +----------------------------+-------------------+-------------+
                        # 1 row in set (0.35 sec)
                        top_tables_by_full_scan = []
                        is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_DATABASE_TABLE_FULL_SCAN).format(database))
                        if is_success:
                            if output_list:
                                for table in output_list:
                                    single_table                 = {}
                                    single_table['CATEGORY']     = 'top_tables_by_full_scan'
                                    single_table['DBN']          = database
                                    single_table['TBN']          = table[0]
                                    single_table['RFS']          = str(table[1])
                                    single_table['RFSL']         = str(int(int(str(table[2]))/int(1000000000)))
                                    # hard coding other data to "-" [ to reduce query run time and exceution]
                                    single_table['TSBT']         = str("-")
                                    single_table['DTSBT']        = str("-")
                                    single_table['INSBT']        = str("-")
                                    single_table['RWC']          = str("-")
                                    single_table['CLC']          = str("-")
                                    top_tables_by_full_scan.append(single_table)
                                result_dict[database]['top_tables_by_full_scan'] = top_tables_by_full_scan
                            else:
                                result_dict[database]['top_tables_by_full_scan'] = [{'status': '0', 'msg': 'No data found for top tables by full scan'}]
                        else:
                            result_dict[database]['top_tables_by_full_scan'] = [{'status': '0', 'msg': str(err_msg)}]



                        # used for applog, to push common data need all metrics real data and not "-" [removed for performance improvement, might need later]
                        '''
                                    if len(column_count_table_name_list)>1:
                                        column_count_table_name_list = column_count_table_name_list + ",'{}'".format(table[0])
                                    else:
                                        column_count_table_name_list = column_count_table_name_list + "'{}'".format(table[0])
                                    if len(total_size_table_name_list)>1:
                                        total_size_table_name_list = total_size_table_name_list + ",'{}'".format(table[0])
                                    else:
                                        total_size_table_name_list = total_size_table_name_list + "'{}'".format(table[0])
                                    if len(full_scan_table_name_list)>1:
                                        full_scan_table_name_list = full_scan_table_name_list + ",'{}'".format(table[0])
                                    else:
                                        full_scan_table_name_list = full_scan_table_name_list + "'{}'".format(table[0])
                                        
                                        
                            #CREATING LIST OF TABLES FOR EXECUTING ONCE
                            top_tables_by_rows             = []
                            top_tables_by_rows_dict        = {}
                            column_count_table_name_list   = "("
                            total_size_table_name_list     = "("
                            full_scan_table_name_list      = "("
                            
                            
                            total_size_table_name_list = total_size_table_name_list + ")"
                            column_count_table_name_list = column_count_table_name_list + ")"
                            full_scan_table_name_list = full_scan_table_name_list + ")"
                            
                            #total_table_query = "SELECT table_name, count(*) AS column_count FROM INFORMATION_SCHEMA.COLUMNS WHERE table_name IN {} AND TABLE_SCHEMA LIKE '{}' GROUP BY table_name;"
                            #clmn_bool,clmn_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(total_table_query).format(database,rows_count_table_name_list))
                            #if clmn_bool:
                            #    single_table['CLC'] = str(clmn_list[0][0]) # count # column_count
                            
                            DatabaseLogger.Logger.log('JOINING TABLE NAME CHECK ROW :: {}'.format(rows_count_table_name_list))
                            DatabaseLogger.Logger.log('JOINING TABLE NAME CHECK CLM :: {}'.format(column_count_table_name_list))
                            DatabaseLogger.Logger.log('JOINING TABLE NAME CHECK TSZ :: {}'.format(total_size_table_name_list))
                            DatabaseLogger.Logger.log('JOINING TABLE NAME CHECK FRS :: {}'.format(full_scan_table_name_list))
    
                            total_column_table_query = "SELECT table_name, count(*) AS column_count FROM INFORMATION_SCHEMA.COLUMNS WHERE table_name IN {} AND TABLE_SCHEMA='{}' GROUP BY table_name;"
                            clmn_bool,clmn_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(total_column_table_query).format(column_count_table_name_list,database))
                            if clmn_bool:
                                #DatabaseLogger.Logger.log('CLOK :: \n{}\n{}'.format(clmn_list))
                                for each_table in clmn_list:
                                    if each_table[0] in top_tables_by_size_dict:
                                        top_tables_by_size_dict[each_table[0]]['CLC'] = str(each_table[1])
                                    if each_table[0] in top_tables_by_rows_dict:
                                        top_tables_by_rows_dict[each_table[0]]['CLC'] = str(each_table[1])
                                    if each_table[0] in top_tables_by_full_scan_dict:
                                        top_tables_by_full_scan_dict[each_table[0]]['CLC'] = str(each_table[1])
    
                            if len(total_size_table_name_list) > 2:
                                total_size_table_query = "SELECT TABLE_NAME, IFNULL(SUM(data_length+index_length),0) AS size_byt, IFNULL(SUM(data_length),0) AS data_size_byt, IFNULL(SUM(index_length),0) AS index_size_byt FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='{}' AND TABLE_NAME IN {} GROUP BY TABLE_NAME"
                                size_bool,size_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(total_size_table_query).format(database,total_size_table_name_list))
                                if size_bool:
                                    for each_table in size_list:
                                        #if each_table[0] in top_tables_by_size_dict:
                                        #    top_tables_by_size_dict[each_table[0]]['TSBT'] = str(each_table[1])
                                        #    top_tables_by_size_dict[each_table[0]]['DTSBT'] = str(each_table[2])
                                        #    top_tables_by_size_dict[each_table[0]]['INSBT'] = str(each_table[3])
                                        if each_table[0] in top_tables_by_rows_dict:
                                            top_tables_by_rows_dict[each_table[0]]['TSBT'] = str(each_table[1])
                                            top_tables_by_rows_dict[each_table[0]]['DTSBT'] = str(each_table[2])
                                            top_tables_by_rows_dict[each_table[0]]['INSBT'] = str(each_table[3])
                                        if each_table[0] in top_tables_by_full_scan_dict:
                                            top_tables_by_full_scan_dict[each_table[0]]['TSBT'] = str(each_table[1])
                                            top_tables_by_full_scan_dict[each_table[0]]['DTSBT'] = str(each_table[2])
                                            top_tables_by_full_scan_dict[each_table[0]]['INSBT'] = str(each_table[3])
                                    #single_table['TSBT'] = str(size_list[0][0]) # byte # size_byt
                                    #single_table['DTSBT'] = str(size_list[0][1]) # byte # data_size_byt
                                    #single_table['INSBT'] = str(size_list[0][2]) # byte # index_size_byt
                                    pass
    
                            if len(rows_count_table_name_list) > 2:
                                total_row_count_query = "SELECT table_name, SUM(table_rows) AS row_count FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='{}' AND table_name in {} GROUP BY table_name"
                                row_bool,row_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(total_row_count_query).format(database,rows_count_table_name_list))
                                if row_bool:
                                    for each_table in row_list:
                                        if each_table[0] in top_tables_by_size_dict:
                                            top_tables_by_size_dict[each_table[0]]['RWC'] = str(each_table[1])
                                        #if each_table[0] in top_tables_by_rows_dict:
                                        #    top_tables_by_rows_dict[each_table[0]]['RWC'] = str(each_table[1])
                                        if each_table[0] in top_tables_by_full_scan_dict:
                                            top_tables_by_full_scan_dict[each_table[0]]['RWC'] = str(each_table[1])
                                    #single_table['RWC'] = str(row_list[0][0]) # count # row_count
                                    pass
    
                            if len(full_scan_table_name_list) > 2:
                                total_full_scan_count_query = "SELECT object_name, IFNULL(rows_full_scanned,0), IFNULL(ROUND(latency/1000000000),0) FROM sys.x$schema_tables_with_full_table_scans WHERE object_schema='{}' and object_name in {} GROUP BY object_name"
                                full_scn_bool,tbl_fll_scn_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(total_full_scan_count_query).format(database,full_scan_table_name_list))
                                if full_scn_bool:
                                    if tbl_fll_scn_list:
                                        for each_table in tbl_fll_scn_list:
                                            if each_table[0] in top_tables_by_size_dict:
                                                top_tables_by_size_dict[each_table[0]]['RFS'] = str(each_table[1])
                                                top_tables_by_size_dict[each_table[0]]['RFSL'] = str(each_table[2])
                                            if each_table[0] in top_tables_by_rows_dict:
                                                top_tables_by_rows_dict[each_table[0]]['RFS'] = str(each_table[1])
                                                top_tables_by_rows_dict[each_table[0]]['RFSL'] = str(each_table[2])
                                            #if each_table[0] in top_tables_by_full_scan_dict:
                                            #    top_tables_by_full_scan_dict[each_table[0]]['CLC'] = str(each_table[1])
                                    for each_table in top_tables_by_size_dict:
                                        if 'RFS' not in top_tables_by_size_dict[each_table]:
                                            top_tables_by_size_dict[each_table]['RFS'] = "0"
                                        if 'RFSL' not in top_tables_by_size_dict[each_table]:
                                            top_tables_by_size_dict[each_table]['RFSL'] = "0"
                                    for each_table in top_tables_by_rows_dict:
                                        if 'RFS' not in top_tables_by_rows_dict[each_table]:
                                            top_tables_by_rows_dict[each_table]['RFS'] = "0"
                                        if 'RFSL' not in top_tables_by_rows_dict[each_table]:
                                            top_tables_by_rows_dict[each_table]['RFSL'] = "0"
    
                            DatabaseLogger.Logger.log('RESULT DATA COMBAINED ROW :: {}'.format(top_tables_by_rows_dict))
                            DatabaseLogger.Logger.log('RESULT DATA COMBAINED TSZ :: {}'.format(top_tables_by_size_dict))
                            DatabaseLogger.Logger.log('RESULT DATA COMBAINED FRS :: {}'.format(top_tables_by_full_scan_dict))
    
                            
                            #for each_table in top_tables_by_rows_dict:
                            #    top_tables_by_rows.append(top_tables_by_rows_dict[each_table])
                            #for each_table in top_tables_by_size_dict:
                            #    top_tables_by_size.append(top_tables_by_size_dict[each_table])
                            for each_table in top_tables_by_full_scan_dict:
                                top_tables_by_full_scan.append(top_tables_by_full_scan_dict[each_table])
    
                            #result_dict[database]['top_tables_by_rows'] = top_tables_by_rows
                            #result_dict[database]['top_tables_by_size'] = top_tables_by_size
                            #result_dict[database]['top_tables_by_full_scan'] = top_tables_by_full_scan
                            '''


                        # mysql> SELECT query,exec_count,errors,error_pct,warnings,warning_pct,first_seen,last_seen FROM sys.statements_with_errors_or_warnings WHERE db LIKE 'jbossdb' AND LAST_SEEN > DATE_SUB(NOW(), INTERVAL 300 SECOND) ORDER BY errors DESC LIMIT 10;
                        # +---------------------------------------------+------------+--------+-----------+----------+-------------+---------------------+---------------------+
                        # | query                                       | exec_count | errors | error_pct | warnings | warning_pct | first_seen          | last_seen           |
                        # +---------------------------------------------+------------+--------+-----------+----------+-------------+---------------------+---------------------+
                        # | SELECT *                                    |          1 |      1 |  100.0000 |        0 |      0.0000 | 2022-08-18 17:03:53 | 2022-08-18 17:03:53 |
                        # | SELECT `db` FROM `WM_APPLICATION_NOTIFIER`  |          1 |      1 |  100.0000 |        0 |      0.0000 | 2022-08-18 17:05:40 | 2022-08-18 17:05:40 |
                        # +---------------------------------------------+------------+--------+-----------+----------+-------------+---------------------+---------------------+
                        # 2 rows in set (0.02 sec)
                        top_statements_error_warning = []
                        is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_RECENT_STATEMENTS_ERR_WRN).format(database,'300'))
                        # see mysqlconstants -> MYSQL_RECENT_STATEMENTS_ERR_WRN_GROUPING
                        if is_success:
                            for instance in output_list:
                                single_instance = {}
                                single_instance['CATEGORY']      = 'top_statements_error_warning'
                                single_instance['DBN']           = database # text # database name
                                single_instance['SEWQ']          = (str(instance[0])[0:3000] if len(str(instance[0])) >= 3000 else str(instance[0])) # text # query
                                single_instance['SEWEC']         = str(instance[1]) # count # exec_count
                                single_instance['SEWER']         = str(instance[2]) # count # errors
                                single_instance['SEWERP']        = str(instance[3]) # percentage # error_pct
                                single_instance['SEWWN']         = str(instance[4]) # count # warnings
                                single_instance['SEWWNP']        = str(instance[5]) # percentage # warning_pct
                                single_instance['SEWFS']         = str(instance[6]) # text # first seen
                                single_instance['SEWLS']         = str(instance[7]) # text # last seen
                                top_statements_error_warning.append(single_instance)
                            result_dict[database]['top_statements_error_warning'] = top_statements_error_warning


                        # insight data, top query based on sum time wait for that query
                        # The total wait time of the summarized timed events. This value is calculated only for timed events because nontimed events have a wait time of NULL. The same is true for the other xxx_TIMER_WAIT values.
                        # mysql> SELECT DIGEST_TEXT, COUNT_STAR, ROUND(SUM_TIMER_WAIT/1000000000), ROUND(MIN_TIMER_WAIT/1000000000), ROUND(AVG_TIMER_WAIT/1000000000), ROUND(MAX_TIMER_WAIT/1000000000), ROUND(SUM_LOCK_TIME/1000000000), SUM_ERRORS, SUM_WARNINGS, SUM_ROWS_AFFECTED, SUM_ROWS_SENT, SUM_ROWS_EXAMINED, SUM_CREATED_TMP_DISK_TABLES, SUM_CREATED_TMP_TABLES, SUM_SELECT_FULL_JOIN, SUM_SELECT_FULL_RANGE_JOIN, SUM_SELECT_RANGE, SUM_SELECT_RANGE_CHECK, SUM_SELECT_SCAN, SUM_SORT_MERGE_PASSES, SUM_SORT_RANGE, SUM_SORT_ROWS, SUM_SORT_SCAN, SUM_NO_INDEX_USED, SUM_NO_GOOD_INDEX_USED, FIRST_SEEN, LAST_SEEN FROM performance_schema.events_statements_summary_by_digest WHERE schema_name like 'jbossdb' AND LAST_SEEN > DATE_SUB(NOW(), INTERVAL 300 SECOND) ORDER BY SUM_TIMER_WAIT desc LIMIT 10\G
                        # *************************** 1. row ***************************
                        # DIGEST_TEXT: SET `autocommit` = ?
                        # COUNT_STAR: 90149
                        # ROUND(SUM_TIMER_WAIT/1000000000): 53504
                        # ROUND(MIN_TIMER_WAIT/1000000000): 0
                        # ROUND(AVG_TIMER_WAIT/1000000000): 1
                        # ROUND(MAX_TIMER_WAIT/1000000000): 11385
                        # ROUND(SUM_LOCK_TIME/1000000000): 0
                        # SUM_ERRORS: 0
                        # SUM_WARNINGS: 0
                        # SUM_ROWS_AFFECTED: 0
                        # SUM_ROWS_SENT: 0
                        # SUM_ROWS_EXAMINED: 0
                        # SUM_CREATED_TMP_DISK_TABLES: 0
                        # SUM_CREATED_TMP_TABLES: 0
                        # SUM_SELECT_FULL_JOIN: 0
                        # SUM_SELECT_FULL_RANGE_JOIN: 0
                        # SUM_SELECT_RANGE: 0
                        # SUM_SELECT_RANGE_CHECK: 0
                        # SUM_SELECT_SCAN: 0
                        # SUM_SORT_MERGE_PASSES: 0
                        # SUM_SORT_RANGE: 0
                        # SUM_SORT_ROWS: 0
                        # SUM_SORT_SCAN: 0
                        # SUM_NO_INDEX_USED: 0
                        # SUM_NO_GOOD_INDEX_USED: 0
                        # FIRST_SEEN: 2022-08-18 11:03:43
                        # LAST_SEEN: 2022-08-18 17:19:46
                        top_query_by_total_wait = []
                        is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_DATABASE_STATEMENT_ANALYSIS).format(database,'300'))
                        if is_success:
                            for table in output_list:
                                single_query = {}
                                single_query['DBN']                = str(database) # text # database name
                                single_query['QST']                = (str(table[0])[0:3000] if len(str(table[0])) >= 3000 else str(table[0])) # text # query statement
                                single_query['QEXC']               = str(table[1]) # count # execution count
                                single_query['QSTW']               = str(table[2]) # millisecond # SUM_TIMER_WAIT
                                single_query['QNITW']              = str(table[3]) # millisecond # MIN_TIMER_WAIT
                                single_query['QATW']               = str(table[4]) # millisecond # AVG_TIMER_WAIT
                                single_query['QMXTW']              = str(table[5]) # millisecond # MAX_TIMER_WAIT
                                single_query['QSLT']               = str(table[6]) # millisecond # SUM_LOCK_TIME
                                single_query['QSER']               = str(table[7]) # count # SUM_ERRORS
                                single_query['QSWR']               = str(table[8]) # count # SUM_WARNINGS
                                single_query['QSRA']               = str(table[9]) # count # SUM_ROWS_AFFECTED
                                single_query['QSRS']               = str(table[10]) # count # SUM_ROWS_SENT
                                single_query['QSRE']               = str(table[11]) # count # SUM_ROWS_EXAMINED
                                single_query['QSCTDT']             = str(table[12]) # count # SUM_CREATED_TMP_DISK_TABLES
                                single_query['QSCTT']              = str(table[13]) # count # SUM_CREATED_TMP_TABLES
                                single_query['QSFJ']               = str(table[14]) # count # SUM_SELECT_FULL_JOIN
                                single_query['QSSFRJ']             = str(table[15]) # count # SUM_SELECT_FULL_RANGE_JOIN
                                single_query['QSSER']              = str(table[16]) # count # SUM_SELECT_RANGE
                                single_query['QSSRC']              = str(table[17]) # count # SUM_SELECT_RANGE_CHECK
                                single_query['QSSS']               = str(table[18]) # count # SUM_SELECT_SCAN
                                single_query['QSSMP']              = str(table[19]) # count # SUM_SORT_MERGE_PASSES
                                single_query['QSSRRA']             = str(table[20]) # count # SUM_SORT_RANGE
                                single_query['QSSRRW']             = str(table[21]) # count # SUM_SORT_ROWS
                                single_query['QSSRSC']             = str(table[22]) # count # SUM_SORT_SCAN
                                single_query['QSNIU']              = str(table[23]) # count # SUM_NO_INDEX_USED
                                single_query['QSNGIU']             = str(table[24]) # count # SUM_NO_GOOD_INDEX_USED
                                single_query['QFS']                = str(table[25]) # text # FIRST_SEEN
                                single_query['QLS']                = str(table[26]) # text # LAST_SEEN
                                single_query['CATEGORY']           = str('top_query_by_total_wait')
                                top_query_by_total_wait.append(single_query)
                            result_dict[database]['top_query_by_total_wait'] = top_query_by_total_wait


                        # top queries based on execution count
                        # mysql> SELECT DIGEST_TEXT, COUNT_STAR, ROUND(SUM_TIMER_WAIT/1000000000), ROUND(MIN_TIMER_WAIT/1000000000), ROUND(AVG_TIMER_WAIT/1000000000), ROUND(MAX_TIMER_WAIT/1000000000), ROUND(SUM_LOCK_TIME/1000000000), SUM_ERRORS, SUM_WARNINGS, SUM_ROWS_AFFECTED, SUM_ROWS_SENT, SUM_ROWS_EXAMINED, SUM_CREATED_TMP_DISK_TABLES, SUM_CREATED_TMP_TABLES, SUM_SELECT_FULL_JOIN, SUM_SELECT_FULL_RANGE_JOIN, SUM_SELECT_RANGE, SUM_SELECT_RANGE_CHECK, SUM_SELECT_SCAN, SUM_SORT_MERGE_PASSES, SUM_SORT_RANGE, SUM_SORT_ROWS, SUM_SORT_SCAN, SUM_NO_INDEX_USED, SUM_NO_GOOD_INDEX_USED, FIRST_SEEN, LAST_SEEN FROM performance_schema.events_statements_summary_by_digest WHERE schema_name like 'jbossdb' AND LAST_SEEN > DATE_SUB(NOW(), INTERVAL 300 SECOND) ORDER BY COUNT_STAR desc LIMIT 10\G
                        # *************************** 1. row ***************************
                        # DIGEST_TEXT: SET `autocommit` = ?
                        # COUNT_STAR: 97362
                        # ROUND(SUM_TIMER_WAIT/1000000000): 54599
                        # ROUND(MIN_TIMER_WAIT/1000000000): 0
                        # ROUND(AVG_TIMER_WAIT/1000000000): 1
                        # ROUND(MAX_TIMER_WAIT/1000000000): 11385
                        # ROUND(SUM_LOCK_TIME/1000000000): 0
                        # SUM_ERRORS: 0
                        # SUM_WARNINGS: 0
                        # SUM_ROWS_AFFECTED: 0
                        # SUM_ROWS_SENT: 0
                        # SUM_ROWS_EXAMINED: 0
                        # SUM_CREATED_TMP_DISK_TABLES: 0
                        # SUM_CREATED_TMP_TABLES: 0
                        # SUM_SELECT_FULL_JOIN: 0
                        # SUM_SELECT_FULL_RANGE_JOIN: 0
                        # SUM_SELECT_RANGE: 0
                        # SUM_SELECT_RANGE_CHECK: 0
                        # SUM_SELECT_SCAN: 0
                        # SUM_SORT_MERGE_PASSES: 0
                        # SUM_SORT_RANGE: 0
                        # SUM_SORT_ROWS: 0
                        # SUM_SORT_SCAN: 0
                        # SUM_NO_INDEX_USED: 0
                        # SUM_NO_GOOD_INDEX_USED: 0
                        # FIRST_SEEN: 2022-08-18 11:03:43
                        # LAST_SEEN: 2022-08-18 17:59:26
                        top_query_by_total_exe = []
                        is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_DATABASE_STATEMENT_ANALYSIS_EXE_CNT).format(database,'300'))
                        if is_success:
                            for table in output_list:
                                single_query                       = {}
                                single_query['DBN']                = str(database) # text # database name
                                single_query['QST']                = (str(table[0])[0:3000] if len(str(table[0])) >= 3000 else str(table[0])) # text # query statement
                                single_query['QEXC']               = str(table[1]) # count # execution count
                                single_query['QSTW']               = str(table[2]) # millisecond # SUM_TIMER_WAIT
                                single_query['QNITW']              = str(table[3]) # millisecond # MIN_TIMER_WAIT
                                single_query['QATW']               = str(table[4]) # millisecond # AVG_TIMER_WAIT
                                single_query['QMXTW']              = str(table[5]) # millisecond # MAX_TIMER_WAIT
                                single_query['QSLT']               = str(table[6]) # millisecond # SUM_LOCK_TIME
                                single_query['QSER']               = str(table[7]) # count # SUM_ERRORS
                                single_query['QSWR']               = str(table[8]) # count # SUM_WARNINGS
                                single_query['QSRA']               = str(table[9]) # count # SUM_ROWS_AFFECTED
                                single_query['QSRS']               = str(table[10]) # count # SUM_ROWS_SENT
                                single_query['QSRE']               = str(table[11]) # count # SUM_ROWS_EXAMINED
                                single_query['QSCTDT']             = str(table[12]) # count # SUM_CREATED_TMP_DISK_TABLES
                                single_query['QSCTT']              = str(table[13]) # count # SUM_CREATED_TMP_TABLES
                                single_query['QSFJ']               = str(table[14]) # count # SUM_SELECT_FULL_JOIN
                                single_query['QSSFRJ']             = str(table[15]) # count # SUM_SELECT_FULL_RANGE_JOIN
                                single_query['QSSER']              = str(table[16]) # count # SUM_SELECT_RANGE
                                single_query['QSSRC']              = str(table[17]) # count # SUM_SELECT_RANGE_CHECK
                                single_query['QSSS']               = str(table[18]) # count # SUM_SELECT_SCAN
                                single_query['QSSMP']              = str(table[19]) # count # SUM_SORT_MERGE_PASSES
                                single_query['QSSRRA']             = str(table[20]) # count # SUM_SORT_RANGE
                                single_query['QSSRRW']             = str(table[21]) # count # SUM_SORT_ROWS
                                single_query['QSSRSC']             = str(table[22]) # count # SUM_SORT_SCAN
                                single_query['QSNIU']              = str(table[23]) # count # SUM_NO_INDEX_USED
                                single_query['QSNGIU']             = str(table[24]) # count # SUM_NO_GOOD_INDEX_USED
                                single_query['QFS']                = str(table[25]) # text # FIRST_SEEN
                                single_query['QLS']                = str(table[26]) # text # LAST_SEEN
                                single_query['CATEGORY']           = str('top_query_by_total_exe')
                                top_query_by_total_exe.append(single_query)
                            result_dict[database]['top_query_by_total_exe'] = top_query_by_total_exe

                        # basic data, child monitor data,
                        schema_performance_data = []
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
                                result_dict[database]['TSTL']                                = ((float(each[0]) if each[0] else 0) - float(self.previous_child_data[database]['TSTL']))  # millisecond # total_latency # The total wait time of timed I/O events for the table.
                                result_dict[database]['TSRF']                                = ((int(each[1]) if each[1] else 0) - int(self.previous_child_data[database]['TSRF'])) # count # rows_fetched # The total number of rows read from the table.
                                result_dict[database]['TSFL']                                = ((float(each[2]) if each[2] else 0) - float(self.previous_child_data[database]['TSFL'])) # millisecond # fetch_latency # The total wait time of timed read I/O events for the table.
                                result_dict[database]['TSRI']                                = ((int(each[3]) if each[3] else 0) - int(self.previous_child_data[database]['TSRI'])) # count # rows_inserted # The total number of rows inserted into the table.
                                result_dict[database]['TSIL']                                = ((float(each[4]) if each[4] else 0) - float(self.previous_child_data[database]['TSIL'])) # millisecond # insert_latency # The total wait time of timed insert I/O events for the table.
                                result_dict[database]['TSRU']                                = ((int(each[5]) if each[5] else 0) - int(self.previous_child_data[database]['TSRU'])) # count # rows_updated # The total number of rows updated in the table.
                                result_dict[database]['TSUL']                                = ((float(each[6]) if each[6] else 0) - float(self.previous_child_data[database]['TSUL'])) # millisecond # update_latency # The total wait time of timed update I/O events for the table.
                                result_dict[database]['TSRD']                                = ((int(each[7]) if each[7] else 0) - int(self.previous_child_data[database]['TSRD'])) # count # rows_deleted # The total number of rows deleted from the table.
                                result_dict[database]['TSDL']                                = ((float(each[8]) if each[8] else 0) - float(self.previous_child_data[database]['TSDL'])) # millisecond # delete_latency # The total wait time of timed delete I/O events for the table.
                                result_dict[database]['TSIORR']                              = ((int(each[9]) if each[9] else 0) - int(self.previous_child_data[database]['TSIORR'])) # count # io_read_requests # The total number of read requests for the table.
                                result_dict[database]['TSIOR']                               = ((int(each[10]) if each[10] else 0) - int(self.previous_child_data[database]['TSIOR'])) # bytes # io_read # The total number of bytes read from the table.
                                result_dict[database]['TSIORL']                              = ((float(each[11]) if each[11] else 0) - float(self.previous_child_data[database]['TSIORL'])) # millisecond # io_read_latency # The total wait time of reads from the table.
                                result_dict[database]['TSIOWR']                              = ((int(each[12]) if each[12] else 0) - int(self.previous_child_data[database]['TSIOWR'])) # count # io_write_requests # The total number of write requests for the table.
                                result_dict[database]['TSIOW']                               = ((int(each[13]) if each[13] else 0) - int(self.previous_child_data[database]['TSIOW'])) # bytes # io_write # The total number of bytes written to the table.
                                result_dict[database]['TSIOWL']                              = ((float(each[14]) if each[14] else 0) - float(self.previous_child_data[database]['TSIOWL'])) # millisecond # io_write_latency # The total wait time of writes to the table.
                                result_dict[database]['TSIOMR']                              = ((int(each[15]) if each[15] else 0) - int(self.previous_child_data[database]['TSIOMR'])) # count # io_misc_requests # The total number of miscellaneous I/O requests for the table.
                                result_dict[database]['TSIOML']                              = ((float(each[16]) if each[16] else 0) - float(self.previous_child_data[database]['TSIOML'])) # millisecond # io_misc_latency # The total wait time of miscellaneous I/O requests for the table.
                                current_data_for_next_poll[database]['TSTL']                 = float(each[0]) if each[0] else 0
                                current_data_for_next_poll[database]['TSRF']                 = float(each[1]) if each[1] else 0
                                current_data_for_next_poll[database]['TSFL']                 = float(each[2]) if each[2] else 0
                                current_data_for_next_poll[database]['TSRI']                 = float(each[3]) if each[3] else 0
                                current_data_for_next_poll[database]['TSIL']                 = float(each[4]) if each[4] else 0
                                current_data_for_next_poll[database]['TSRU']                 = float(each[5]) if each[5] else 0
                                current_data_for_next_poll[database]['TSUL']                 = float(each[6]) if each[6] else 0
                                current_data_for_next_poll[database]['TSRD']                 = float(each[7]) if each[7] else 0
                                current_data_for_next_poll[database]['TSDL']                 = float(each[8]) if each[8] else 0
                                current_data_for_next_poll[database]['TSIORR']               = float(each[9]) if each[9] else 0
                                current_data_for_next_poll[database]['TSIOR']                = float(each[10]) if each[10] else 0
                                current_data_for_next_poll[database]['TSIORL']               = float(each[11]) if each[11] else 0
                                current_data_for_next_poll[database]['TSIOWR']               = float(each[12]) if each[12] else 0
                                current_data_for_next_poll[database]['TSIOW']                = float(each[13]) if each[13] else 0
                                current_data_for_next_poll[database]['TSIOWL']               = float(each[14]) if each[14] else 0
                                current_data_for_next_poll[database]['TSIOMR']               = float(each[15]) if each[15] else 0
                                current_data_for_next_poll[database]['TSIOML']               = float(each[16]) if each[16] else 0
                                current_data_for_next_poll[database]['last_mdss_dc_time']    = start_time  # to get exact time diff change

                            result_dict[database]['TPUT']                                    = str(float( (int(result_dict[database]['TSIOR'])+int(result_dict[database]['TSIOW'])) / float(float(start_time) - float(self.previous_child_data[database]['last_mdss_dc_time'])) )) # bytes/sec
                            # throughput = ( (io_reads + io_writes) / (last query executed time - current time) ) # bytes/sec


                        # mysql index scan count from start of mysql
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
                                result_dict[database]['IDSC']                                = str(int(each[0]) - int(self.previous_child_data[database]['IDSC'])) # count # index scan count
                                current_data_for_next_poll[database]['IDSC']                 = str(int(each[0]))


                        # mysql sequential scan count from start of mysql
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
                                result_dict[database]['SQSC']                               = str(int(each[0]) - int(self.previous_child_data[database]['SQSC'])) # count # full scan done in db
                                current_data_for_next_poll[database]['SQSC']                = str(int(each[0]))


                        # mysql> SELECT query, db, exec_count, err_count, warn_count, ROUND(total_latency/1000000000), ROUND(max_latency/1000000000), ROUND(avg_latency/1000000000), first_seen, last_seen FROM sys.x$statements_with_runtimes_in_95th_percentile WHERE db LIKE 'jbossdb' AND last_seen > DATE_SUB(NOW(), INTERVAL 300000 SECOND) ORDER BY total_latency DESC LIMIT 10\G
                        # *************************** 1. row ***************************
                        # query: SELECT `Schedule_31` . `SCHEDULE_ID` , `Schedule_31` . `SCHEDULE_NAME` , `Schedule_31` . `IS_COMMON` , `Schedule_31` . `USER_ID` , `Schedule_31` . `SCHEMAID` , `Periodic_31` . `SCHEDULE_ID` , `Periodic_31` . `START_DATE` , `Periodic_31` . `END_DATE` , `Periodic_31` . `TIME_PERIOD` , `Periodic_31` . `SCHEDULE_MODE` , `Calendar_31` . `SCHEDULE_ID` , `Calendar_31` . `REPEAT_FREQUENCY` , `Calendar_31` . `TIME_OF_DAY` , `Calendar_31` . `DAY_OF_WEEK` , `Calendar_31` . `WEEK` , `Calendar_31` . `DATE_OF_MONTH` , `Calendar_31` . `MONTH_OF_YEAR` , `Calendar_31` . `YEAR_OF_DECADE` , `Calendar_31` . `TZ` , `Calendar_31` . `SKIP_FREQUENCY` , `Calendar_31` . `USE_DATE_IN_REVERSE` , `Calendar_31` . `FIRST_DAY_OF_WEEK` , `Calendar_31` . `RUN_ONCE` FROM `Schedule_31` LEFT JOIN `Periodic_31` ON `Schedule_31` . `SCHEDULE_ID` = `Periodic_31` . `SCHEDULE_ID` LEFT JOIN `Calendar_31` ON `Schedule_31` . `SCHEDULE_ID` = `Calendar_31` . `SCHEDULE_ID` WHERE ( `Schedule_31` . `SCHEDULE_ID` = ? )
                        # db: jbossdb
                        # exec_count: 1
                        # err_count: 0
                        # warn_count: 0
                        # ROUND(total_latency/1000000000): 41
                        # ROUND(max_latency/1000000000): 41
                        # ROUND(avg_latency/1000000000): 41
                        # first_seen: 2022-08-19 10:28:34
                        # last_seen: 2022-08-19 10:28:34
                        # 2 rows in set (0.12 sec)
                        # mysql query wise data, based on database
                        is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(str(MySQLConstants.MYSQL_QUERY_DATA_DATABSE_WISE).format(database,'300'))
                        if is_success:
                            top_query_by_avg_latency = []
                            for each in output_list:
                                single_query                    = {}
                                single_query['QQRY']            = (str(each[0])[0:3000] if len(str(each[0])) >= 3000 else str(each[0])) if each[0] else 0 # text # query statement   # QQRY
                                single_query['DBN']             = str(each[1]) if each[1] else 0 # test # query executed db # DBN
                                single_query['QEXC']            = str(each[2]) if each[2] else 0 # count # query execution count # QEXC
                                single_query['QERRC']           = str(each[3]) if each[3] else 0 # count # query error count # QERRC
                                single_query['QWRC']            = str(each[4]) if each[4] else 0 # count # query warn count # QWRC
                                single_query['QTL']             = str(each[5]) if each[5] else 0 # microsecond # query execution total latency # QTL
                                single_query['QML']             = str(each[6]) if each[6] else 0 # microsecond # query execution max latency # QML
                                single_query['QAVL']            = str(each[7]) if each[7] else 0 # microsecond # query execution average latency # QAVL
                                single_query['QFTS']            = str(each[8]) if each[8] else 0 # test # query execution first seen # QFTS
                                single_query['QLTS']            = str(each[9]) if each[9] else 0 # text # query execution last seen # QLTS
                                single_query['CATEGORY']        = 'top_query_by_avg_latency'
                                top_query_by_avg_latency.append(single_query)
                            result_dict[database]['top_query_by_avg_latency'] = top_query_by_avg_latency


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
                                result_dict[database]['ITCS']                          = (float(each[0]) if each[0] else 0) - float(self.previous_child_data[database]['ITCS']) # str(each[0]) if each[0] else 0  # count  # instance count star   # ITCS
                                result_dict[database]['ITART']                         = "0" if not int(result_dict[database]['ITCS']) else (((float(each[1]) if each[1] else 0) - float(self.previous_child_data[database]['ITART'])) / result_dict[database]['ITCS']) # str(each[1]) if each[1] else 0 # millisecond  # instance average query run time  # ITART
                                result_dict[database]['ITALT']                         = "0" if not int(result_dict[database]['ITCS']) else (((float(each[2]) if each[2] else 0) - float(self.previous_child_data[database]['ITALT'])) / result_dict[database]['ITCS']) # str(each[2]) if each[2] else 0  # millisecond # instance average lock time  # ITALT
                                result_dict[database]['ITAER']                         = "0" if not int(result_dict[database]['ITCS']) else (((float(each[3]) if each[3] else 0) - float(self.previous_child_data[database]['ITAER'])) / result_dict[database]['ITCS']) # str(each[3]) if each[3] else 0  # count  # instance average error  # ITAER
                                result_dict[database]['ITAWN']                         = "0" if not int(result_dict[database]['ITCS']) else (((float(each[4]) if each[4] else 0) - float(self.previous_child_data[database]['ITAWN'])) / result_dict[database]['ITCS']) # str(each[4]) if each[4] else 0  # count  # instance average warnings # ITAWN
                                result_dict[database]['ITARF']                         = "0" if not int(result_dict[database]['ITCS']) else (((float(each[5]) if each[5] else 0) - float(self.previous_child_data[database]['ITARF'])) / result_dict[database]['ITCS']) # str(each[5]) if each[5] else 0  # count  # instance average rows affected # ITARF
                                result_dict[database]['ITARS']                         = "0" if not int(result_dict[database]['ITCS']) else (((float(each[6]) if each[6] else 0) - float(self.previous_child_data[database]['ITARS'])) / result_dict[database]['ITCS']) # str(each[6]) if each[6] else 0  # count  # instance average rows sent # ITARS
                                result_dict[database]['ITATDTC']                       = "0" if not int(result_dict[database]['ITCS']) else (((float(each[7]) if each[7] else 0) - float(self.previous_child_data[database]['ITATDTC'])) / result_dict[database]['ITCS']) # str(each[7]) if each[7] else 0  # count  # instance average temp disk table created # ITATDTC
                                result_dict[database]['ITATTC']                        = "0" if not int(result_dict[database]['ITCS']) else (((float(each[8]) if each[8] else 0) - float(self.previous_child_data[database]['ITATTC'])) / result_dict[database]['ITCS']) # str(each[8]) if each[8] else 0  # count  # instance average temp table created # ITATTC
                                result_dict[database]['TSERC']                         = (float(each[9]) if each[9] else 0) - float(self.previous_child_data[database]['TSERC']) # str(each[9]) if each[9] else 0  # count  # instance total error count in 300 second # TSERC
                                result_dict[database]['TSWNC']                         = (float(each[10]) if each[10] else 0) - float(self.previous_child_data[database]['TSWNC']) # str(each[10]) if each[10] else 0  # count  # instance total warn count in 300 second # TSWNC
                                current_data_for_next_poll[database]['ITCS']           = float(each[0]) if each[0] else 0
                                current_data_for_next_poll[database]['ITART']          = float(each[1]) if each[0] else 0
                                current_data_for_next_poll[database]['ITALT']          = float(each[2]) if each[0] else 0
                                current_data_for_next_poll[database]['ITAER']          = float(each[3]) if each[0] else 0
                                current_data_for_next_poll[database]['ITAWN']          = float(each[4]) if each[0] else 0
                                current_data_for_next_poll[database]['ITARF']          = float(each[5]) if each[0] else 0
                                current_data_for_next_poll[database]['ITARS']          = float(each[6]) if each[0] else 0
                                current_data_for_next_poll[database]['ITATDTC']        = float(each[7]) if each[0] else 0
                                current_data_for_next_poll[database]['ITATTC']         = float(each[8]) if each[0] else 0
                                current_data_for_next_poll[database]['TSERC']          = float(each[9]) if each[0] else 0
                                current_data_for_next_poll[database]['TSWNC']          = float(each[10]) if each[0] else 0

                else:
                    result_dict[database] = {}          # current data stored and sent separate, for next poll interval
                    result_dict[database]['meta_data']           = {}
                    result_dict[database]['meta_data']['hname']  = self.mysql_util_obj.host
                    result_dict[database]['meta_data']['iname']  = self.mysql_util_obj.instance
                    result_dict[database]['cid']                 = self.child_keys[database] # cid
                    result_dict[database]['mid']                 = self.mid # parent mid
                    result_dict[database]['schema_name']         = database
                    result_dict[database]['availability']        = '0'
                    result_dict[database]['ct']                  = self.mysql_util_obj.getTimeInMillis(self.time_diff)
                    result_dict[database]['DC ERROR'] = {}
                    result_dict[database]['DC ERROR']['connection_error'] = {
                        'status':'0',
                        'error_msg': str(err_msg)
                    }

                # close the mysql connection created after data collection
            self.mysql_util_obj.close_db_connection()



        except Exception as e:
            is_success = False
            err_msg = str(e)
            DatabaseLogger.Logger.log('Exception while collecting individual database data :: db list - {} :: Error - {}'.format(self.child_keys,e))
            traceback.print_exc()
        finally:
            return is_success,result_dict,current_data_for_next_poll,err_msg
