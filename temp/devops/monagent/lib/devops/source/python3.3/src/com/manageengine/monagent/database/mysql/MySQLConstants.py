import traceback



''' ==== CHILD DATABASE METRICS QUERY ==== '''
# mysql databases memory size in mb [database list from show database]
MYSQL_SCHEMAS_SIZE_MB                          = "SELECT IFNULL(SUM(data_length+index_length)/1024/1024,0) AS total_size_mb, IFNULL(SUM(index_length)/1024/1024,0) AS index_size_mb, IFNULL(SUM(data_length)/1024/1024,0) AS data_size_mb, count(1) AS table_count, IFNULL(SUM(table_rows),0) as row_count FROM INFORMATION_SCHEMA.TABLES WHERE table_schema='{}'"
# mysql database db name, and its column count
MYSQL_DATABASE_COLUMNS_COUNT                   = "SELECT count(1) AS column_count FROM INFORMATION_SCHEMA.COLUMNS WHERE table_schema='{}'"
# mysql top 10 tables based on row count size # not used
MYSQL_DATABASE_TOP_10_ROWS_TABLES              = "SELECT table_name, SUM(table_rows) AS row_count, IFNULL(SUM(data_length+index_length)/1024/1024,0) AS total_size_mb, IFNULL(SUM(index_length)/1024/1024,0) AS index_size_mb, IFNULL(SUM(data_length)/1024/1024,0) AS data_size_mb FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='{}' GROUP BY table_name ORDER BY row_count DESC LIMIT 10"
# mysql top 10 tables based on tables size
MYSQL_DATABASE_TOP_10_SIZE_TABLE               = "SELECT TABLE_NAME, IFNULL(SUM(data_length+index_length),0) AS size_byt, IFNULL(SUM(data_length),0) AS data_size_byt, IFNULL(SUM(index_length),0) AS index_size_byt, IFNULL(SUM(table_rows),0) AS row_count FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='{}' GROUP BY table_name ORDER BY size_byt DESC LIMIT 10"
# database child monitor tables done full scan
# in schema_tables_with_full_table_scans  -> latency unint is given with unit ms -> milli second, us -> micro second
# in x$schema_tables_with_full_table_scans  same data given with common latency ubit as pico second [verified]
MYSQL_DATABASE_TABLE_FULL_SCAN                 = "SELECT IFNULL(object_name,0), IFNULL(rows_full_scanned,0), IFNULL(latency,0) FROM sys.x$schema_tables_with_full_table_scans WHERE object_schema='{}' LIMIT 10"
# These views summarize I/O consumers to display time waiting for I/O, grouped by thread. By default, rows are sorted by descending total I/O latency. # https://dev.mysql.com/doc/refman/5.7/en/sys-io-by-thread-by-latency.html
MYSQL_RECENT_STATEMENTS_ERR_WRN                = "SELECT query,exec_count,errors,error_pct,warnings,warning_pct,first_seen,last_seen FROM sys.x$statements_with_errors_or_warnings WHERE db='{}' AND LAST_SEEN > DATE_SUB(NOW(), INTERVAL {} SECOND) ORDER BY errors DESC LIMIT 10"
# database wise statement execution analysif two type use [overall instance, and each databaes, with last particular given time in seconds] top sum time wait sorted descending
MYSQL_DATABASE_STATEMENT_ANALYSIS              = "SELECT DIGEST_TEXT, COUNT_STAR, ROUND(SUM_TIMER_WAIT/1000000000), ROUND(MIN_TIMER_WAIT/1000000000), ROUND(AVG_TIMER_WAIT/1000000000), ROUND(MAX_TIMER_WAIT/1000000000), ROUND(SUM_LOCK_TIME/1000000000), SUM_ERRORS, SUM_WARNINGS, SUM_ROWS_AFFECTED, SUM_ROWS_SENT, SUM_ROWS_EXAMINED, SUM_CREATED_TMP_DISK_TABLES, SUM_CREATED_TMP_TABLES, SUM_SELECT_FULL_JOIN, SUM_SELECT_FULL_RANGE_JOIN, SUM_SELECT_RANGE, SUM_SELECT_RANGE_CHECK, SUM_SELECT_SCAN, SUM_SORT_MERGE_PASSES, SUM_SORT_RANGE, SUM_SORT_ROWS, SUM_SORT_SCAN, SUM_NO_INDEX_USED, SUM_NO_GOOD_INDEX_USED, FIRST_SEEN, LAST_SEEN FROM performance_schema.events_statements_summary_by_digest WHERE schema_name='{}' AND LAST_SEEN > DATE_SUB(NOW(), INTERVAL {} SECOND) ORDER BY SUM_TIMER_WAIT desc LIMIT 10"
# database wise statement execution analysif two type use [overall instance, and each databaes, with last particular given time in seconds] top sum time wait sorted descending
MYSQL_DATABASE_STATEMENT_ANALYSIS_EXE_CNT      = "SELECT DIGEST_TEXT, COUNT_STAR, ROUND(SUM_TIMER_WAIT/1000000000), ROUND(MIN_TIMER_WAIT/1000000000), ROUND(AVG_TIMER_WAIT/1000000000), ROUND(MAX_TIMER_WAIT/1000000000), ROUND(SUM_LOCK_TIME/1000000000), SUM_ERRORS, SUM_WARNINGS, SUM_ROWS_AFFECTED, SUM_ROWS_SENT, SUM_ROWS_EXAMINED, SUM_CREATED_TMP_DISK_TABLES, SUM_CREATED_TMP_TABLES, SUM_SELECT_FULL_JOIN, SUM_SELECT_FULL_RANGE_JOIN, SUM_SELECT_RANGE, SUM_SELECT_RANGE_CHECK, SUM_SELECT_SCAN, SUM_SORT_MERGE_PASSES, SUM_SORT_RANGE, SUM_SORT_ROWS, SUM_SORT_SCAN, SUM_NO_INDEX_USED, SUM_NO_GOOD_INDEX_USED, FIRST_SEEN, LAST_SEEN FROM performance_schema.events_statements_summary_by_digest WHERE schema_name='{}' AND LAST_SEEN > DATE_SUB(NOW(), INTERVAL {} SECOND) ORDER BY COUNT_STAR desc LIMIT 10"
# database schema table wise statistics query [work bench] latency in seconds [ pico seconds value divided by 10^12 ]  xxx_latency default value is picosecond, in our query converted to micro second
MYSQL_DATABASE_SCHEMA_STATISTICS               = "SELECT IFNULL(SUM(total_latency/1000000000),0), IFNULL(SUM(rows_fetched),0), IFNULL(SUM(fetch_latency/1000000000),0), IFNULL(SUM(rows_inserted),0), IFNULL(SUM(insert_latency/1000000000),0), IFNULL(SUM(rows_updated),0), IFNULL(SUM(update_latency/1000000000),0), IFNULL(SUM(rows_deleted),0), IFNULL(SUM(delete_latency/1000000000),0), IFNULL(SUM(io_read_requests),0), IFNULL(SUM(io_read),0), IFNULL(SUM(io_read_latency/1000000000),0), IFNULL(SUM(io_write_requests),0), IFNULL(SUM(io_write),0), IFNULL(SUM(io_write_latency/1000000000),0), IFNULL(SUM(io_misc_requests),0), IFNULL(SUM(io_misc_latency/1000000000),0) FROM sys.x$schema_table_statistics WHERE table_schema='{}'"
# index scan count
MYSQL_DATABASE_INDEX_SCAN                      = "SELECT IFNULL(SUM(COUNT_STAR),0) FROM performance_schema.table_io_waits_summary_by_index_usage WHERE OBJECT_SCHEMA='{}' AND INDEX_NAME != 'NULL'"
# full scan count [sequential scan]
MYSQL_DATABASE_SEQUENTIAL_SCAN                 = "SELECT IFNULL(SUM(exec_count),0) FROM sys.x$statements_with_full_table_scans WHERE db='{}'"
# child database total warning, error count
MYSQL_DATABASE_WARN_ERROR_COUNT                = "SELECT IFNULL(SUM(SUM_ERRORS),0), IFNULL(SUM(SUM_WARNINGS),0) FROM performance_schema.events_statements_summary_by_digest WHERE schema_name LIKE '{}' AND LAST_SEEN > DATE_SUB(NOW(), INTERVAL {} SECOND)"
# mysql query wise avg latency data
MYSQL_QUERY_DATA_DATABSE_WISE                  = "SELECT query, db, exec_count, err_count, warn_count, ROUND(total_latency/1000000000), ROUND(max_latency/1000000000), ROUND(avg_latency/1000000000), first_seen, last_seen FROM sys.x$statements_with_runtimes_in_95th_percentile WHERE db='{}' AND last_seen > DATE_SUB(NOW(), INTERVAL {} SECOND) ORDER BY total_latency DESC LIMIT 10"
# mysql instance average query run time
MYSQL_AVG_QUERY_RUN_TIME                       = "SELECT IFNULL(SUM(COUNT_STAR),0) AS count, IFNULL(SUM(SUM_TIMER_WAIT)/1000000000,0) AS avg_waittime, IFNULL(SUM(SUM_LOCK_TIME)/1000000000,0) AS avg_locktime, IFNULL(SUM(SUM_ERRORS),0) AS avg_error, IFNULL(SUM(SUM_WARNINGS),0) AS avg_warning, IFNULL(SUM(SUM_ROWS_AFFECTED),0) AS avg_rows_affected, IFNULL(SUM(SUM_ROWS_SENT),0) AS avg_rows_sent, IFNULL(SUM(SUM_CREATED_TMP_DISK_TABLES),0) AS avg_tmp_disk_tb_crt, IFNULL(SUM(SUM_CREATED_TMP_TABLES),0) AS avg_tmp_tb_crt, IFNULL(SUM(SUM_ERRORS),0) as sum_error, IFNULL(SUM(SUM_WARNINGS),0) as sum_warning FROM performance_schema.events_statements_summary_by_digest"
MYSQL_AVG_QUERY_RUN_TIME_CP                    = "SELECT IFNULL(SUM(COUNT_STAR),0) AS count, IFNULL(SUM(SUM_TIMER_WAIT)/1000000000,0) AS avg_waittime, IFNULL(SUM(SUM_LOCK_TIME)/1000000000,0) AS avg_locktime, IFNULL(SUM(SUM_ERRORS),0) AS avg_error, IFNULL(SUM(SUM_WARNINGS),0) AS avg_warning, IFNULL(SUM(SUM_ROWS_AFFECTED),0) AS avg_rows_affected, IFNULL(SUM(SUM_ROWS_SENT),0) AS avg_rows_sent, IFNULL(SUM(SUM_CREATED_TMP_DISK_TABLES),0) AS avg_tmp_disk_tb_crt, IFNULL(SUM(SUM_CREATED_TMP_TABLES),0) AS avg_tmp_tb_crt, IFNULL(SUM(SUM_ERRORS),0) as sum_error, IFNULL(SUM(SUM_WARNINGS),0) as sum_warning FROM performance_schema.events_statements_summary_by_digest WHERE SCHEMA_NAME='{}'"





# mysql version command
MYSQL_VERSION_QUERY                            = "SHOW GLOBAL VARIABLES WHERE VARIABLE_NAME IN ('version')"
# show master status command, shows binlog file data, used to verify instance is master
MYSQL_REPLICATION_MASTER_STATUS_QUERY          = "SHOW MASTER STATUS"
MYSQL_REPLICATION_BINARY_LOG_STATUS_QUERY      = "SHOW BINARY LOG STATUS"
# show slave status command, shows slave's data, used to verify instance is slave
MYSQL_REPLICATION_SLAVE_STATUS_QUERY           = None   # [show slave status or show replica status]
MYSQL_REPLICATION_REPLICA_STATUS_QUERY         = "SHOW REPLICA STATUS"
# shows slave instance data of the current master instance
MYSQL_SHOW_SLAVE_HOSTS                         = None   # [show slave hosts or show replicas]
# mysql top queries metrics
MYSQL_REPLICATION_GRP_MEMBERS_DATA_QUERY       = None    # [2 extra attribute in 8.0.22]
# collection of metric used around database data collection
MYSQL_COMMON_METRICS_COLLECTION_QUERY          = "SHOW GLOBAL VARIABLES WHERE VARIABLE_NAME IN ('server_uuid')"
# common variables used for both basic and insight monitor
MYSQL_BASIC_INSIGHT_COMMON_VARIABLES_QUERY     = "SHOW GLOBAL VARIABLES WHERE VARIABLE_NAME IN ('slow_query_log', 'slow_query_log_file','long_query_time','log_bin','server_uuid')"
MYSQL_INSIGHT_COMMON_VARIABLES_QUERY           = "SHOW GLOBAL VARIABLES WHERE VARIABLE_NAME IN ('long_query_time')"
MYSQL_WINDOWS_COMMON_VARIABLES_QUERY           = "SHOW GLOBAL VARIABLES WHERE VARIABLE_NAME IN ('server_uuid', 'version')"
# database count query
MYSQL_TOTAL_DATABASE_COUNT                     = "SELECT COUNT(*) FROM information_schema.SCHEMATA"
# mysql global variables metrics [myisam, performance, connections]
MYSQL_SHOW_GLOBAL_VARIABLES                    = "SHOW GLOBAL VARIABLES"
# mysql global status metrics [performance, net, myisam]
MYSQL_SHOW_GLOBAL_STATUS                       = "SHOW GLOBAL STATUS"
# mysql innodb data collection query [if no data present in in this query -> possibly mysql instance must be AWS Aurora instance
MYSQL_DATABASE_SCHEMA_STATISTICS_OVERALL       = "SELECT IFNULL(SUM(total_latency/1000000000),0), IFNULL(SUM(rows_fetched),0), IFNULL(SUM(fetch_latency/1000000000),0), IFNULL(SUM(rows_inserted),0), IFNULL(SUM(insert_latency/1000000000),0), IFNULL(SUM(rows_updated),0), IFNULL(SUM(update_latency/1000000000),0), IFNULL(SUM(rows_deleted),0), IFNULL(SUM(delete_latency/1000000000),0), IFNULL(SUM(io_read_requests),0), IFNULL(SUM(io_read),0), IFNULL(SUM(io_read_latency/1000000000),0), IFNULL(SUM(io_write_requests),0), IFNULL(SUM(io_write),0), IFNULL(SUM(io_write_latency/1000000000),0), IFNULL(SUM(io_misc_requests),0), IFNULL(SUM(io_misc_latency/1000000000),0) FROM sys.x$schema_table_statistics"
MYSQL_INNODB_DATA                              = "SHOW /*!50000 ENGINE*/ INNODB STATUS"
# mysql innodb support status enabled/disabled
MYSQL_ENGINE_STATUS                            = "SELECT ENGINE, SUPPORT, TRANSACTIONS, SAVEPOINTS FROM information_schema.ENGINES WHERE engine IN ('InnoDB','MyISAM','PERFORMANCE_SCHEMA')"
# mysql binlog file list with size
MYSQL_SHOW_BINARY_LOGS                         = "MYSQL_SHOW_BINARY_LOGS"
# mysql relay log files data
MYSQL_SHOW_RELAYLOG_EVENTS                     = "SHOW RELAYLOG EVENTS"
# mysql database db name, and its row count
MYSQL_DATABASE_ROWS_COUNT                      = "SELECT table_Schema, SUM(table_rows) AS row_count FROM INFORMATION_SCHEMA.TABLES WHERE table_schema LIKE '{}' GROUP BY table_schema ORDER BY row_count"
MYSQL_DATABASE_ROWS_SPECIFIC_TABLE             = "SELECT SUM(table_rows) AS row_count FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA LIKE '{}' AND table_name LIKE '{}'"
# mysql top 10 tables based on COLUMN count size
MYSQL_DATABASE_TOP_10_COLUMN_TABLES            = "SELECT table_name, count(*) AS column_count FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA LIKE '{}' GROUP BY table_name ORDER BY column_count DESC LIMIT 10"
MYSQL_DATABASE_COLUMN_SPEICIFIC_TABLE          = "SELECT count(*) AS column_count FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA LIKE '{}' AND table_name LIKE '{}'"
MYSQL_DATABASE_SIZE_SPECIFIC_TABLE             = "SELECT IFNULL(SUM(data_length+index_length),0) AS size_byt, IFNULL(SUM(data_length),0) AS data_size_byt, IFNULL(SUM(index_length),0) AS index_size_byt FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA LIKE '{}' AND TABLE_NAME LIKE '{}'"
# uptime query
MYSQL_DATABASE_STATUS_COMMON_QUERY             = "SHOW GLOBAL STATUS LIKE '{}'"
MYSQL_DATABASE_TABLE_FULL_SCAN_SPECIFIC        = "SELECT IFNULL(rows_full_scanned,0), IFNULL(ROUND(latency/1000000000),0) FROM sys.x$schema_tables_with_full_table_scans WHERE object_schema LIKE '{}' and object_name LIKE '{}'"
# mysql session metrics  [[ not available for 5.6 ]] find new query
MYSQL_SESSION_METRICS                          = "SELECT thd_id, pid, state, user, db, program_name, current_memory/1024 AS current_memory_kb, statement_latency/1000000000 AS cpu_time_ms, command, current_statement, lock_latency/1000000000 AS lock_latency_ms, last_statement AS last_query, last_statement_latency/1000000000 AS last_query_cpu_ms FROM sys.x$session"
# mysql slow queries metrics
MYSQL_SLOW_QUERY                               = "SELECT ID, USER, HOST, DB, COMMAND, TIME, STATE, INFO FROM INFORMATION_SCHEMA.PROCESSLIST where time>{} and command<>'Sleep' limit 10"
# mysql top queries metrics  [[ only available for 8.8 ]] find new query
MYSQL_TOP_CPU_QUERY                            = "SELECT db, exec_count, err_count, warn_count, total_latency/1000000000 AS total_latency, max_latency/1000000000 AS max_latency, avg_latency/1000000000 AS avg_latency, lock_latency/1000000000 AS lock_latency, first_seen, last_seen, query FROM sys.x$statement_analysis ORDER BY avg_latency DESC LIMIT 10"
# wait events from global instance sored by total latency   https://dev.mysql.com/doc/refman/5.7/en/sys-waits-global-by-latency.html
MYSQL_DATABASE_WAIT_EVENT_LATENCY              = "SELECT events, total, total_latency, avg_latency, max_latency FROM sys.x$waits_global_by_latency LIMIT 10"
# mysql instance connections established from different accounts #https://dev.mysql.com/doc/refman/5.6/en/performance-schema-accounts-table.html
MYSQL_PS_ACCOUNTS                              = "SELECT USER, HOST, CURRENT_CONNECTIONS, TOTAL_CONNECTIONS FROM performance_schema.accounts ORDER BY CURRENT_CONNECTIONS DESC LIMIT 10"
# mysql database lost query
MYSQL_LIST_DATABASE                            = "SHOW DATABASES"
# summarize memory use, grouped by user. By default, rows are sorted by descending amount of memory used. # https://dev.mysql.com/doc/refman/5.7/en/sys-memory-by-user-by-current-bytes.html
MYSQL_USERS_MEMORY                             = "SELECT user,current_count_used,current_allocated,current_avg_alloc,current_max_alloc,total_allocated FROM sys.x$memory_by_user_by_current_bytes LIMIT 10"
# summarize memory use, grouped by host. By default, rows are sorted by descending amount of memory used. # https://dev.mysql.com/doc/refman/5.7/en/sys-memory-by-host-by-current-bytes.html
MYSQL_HOSTS_MEMORY                             = "SELECT host,current_count_used,current_allocated,current_avg_alloc,current_max_alloc,total_allocated FROM sys.x$memory_by_host_by_current_bytes LIMIT 10" #
# These views summarize global I/O consumers to display amount of I/O, grouped by file. By default, rows are sorted by descending total I/O (bytes read and written). # https://dev.mysql.com/doc/refman/5.7/en/sys-io-global-by-file-by-bytes.html
MYSQL_FILE_IO_ACTIVITY                         = "SELECT file,count_read,total_read,avg_read,count_write,total_written,avg_write,total,write_pct FROM sys.x$io_global_by_file_by_bytes LIMIT 10"
# https://dev.mysql.com/doc/refman/5.7/en/sys-io-global-by-file-by-latency.html
MYSQL_FILE_IO_LATENCY                          = "SELECT file,total,total_latency,count_read,read_latency,count_write,write_latency,count_misc,misc_latency FROM sys.x$io_global_by_file_by_latency LIMIT 10"
# These views summarize global I/O consumers to display amount of I/O and time waiting for I/O, grouped by event. By default, rows are sorted by descending total I/O (bytes read and written). # https://dev.mysql.com/doc/refman/5.7/en/sys-io-global-by-wait-by-bytes.html
MYSQL_EVENT_IO_LATENCY                         = "SELECT event_name,total,total_latency,avg_latency,max_latency,read_latency,write_latency,misc_latency,count_read,total_read,avg_read,count_write,total_written,avg_written FROM sys.x$io_global_by_wait_by_latency LIMIT 10"

'''   # INSIGHT FUCTION CALLS
collect_session_data
collect_slow_query_data
collect_top_query_data
collect_pf_accounts_data
collect_waits_global_by_latency
collect_top_memory_by_users
collect_top_memory_by_hosts
collect_top_file_io_activity
collect_top_file_io_latency
collect_top_event_io_latency
collect_recent_stmt_err_wrn
'''

# =====================================================================================================================================================================
# =====================================================================================================================================================================
# The total bytes of memory allocated within the server
# BASIC
MYSQL_TOTAL_MEMORY_ALLOCATED                   = "SELECT IFNULL(total_allocated,0) from sys.x$memory_global_total" # https://dev.mysql.com/doc/refman/5.7/en/sys-memory-global-total.html

# insight
MYSQL_USERS_MEMORY_GROUPING = {
    'user'                              : ['USU', 0],   # Name
    'current_count_used'                : ['USCCU', 1], # Count
    'current_allocated'                 : ['USCA', 2],  # Bytes
    'current_avg_alloc'                 : ['USCAA', 3], # Bytes
    'current_max_alloc'                 : ['USCMA', 4], # Bytes
    'total_allocated'                   : ['USTA', 5],  # Bytes
}

# INSIGHT
MYSQL_HOSTS_MEMORY_GROUPING = {
    'host'                              : ['HTH', 0],   # Name
    'current_count_used'                : ['HTCCU', 1], # Count
    'current_allocated'                 : ['HTCA', 2],  # Bytes
    'current_avg_alloc'                 : ['HTCAA', 3], # Bytes
    'current_max_alloc'                 : ['HTCMA', 4], # Bytes
    'total_allocated'                   : ['HTTA', 5],  # Bytes
}

# INSIGHT
MYSQL_FILE_IO_ACTIVITY_GROUPING = {
    'file'                              : ['IOFE', 0],   # file
    'count_read'                        : ['IOCR', 1],   # Count
    'total_read'                        : ['IOTR', 2],   # Bytes
    'avg_read'                          : ['IOAR', 3],   # Bytes
    'count_write'                       : ['IOCW', 4],   # count
    'total_written'                     : ['IOTW', 5],   # Bytes
    'avg_write'                         : ['IOQW', 6],   # Count
    'total'                             : ['IOT', 7],    # Bytes
    'write_pct'                         : ['IOWP', 8],  # percent
}

# INSIGHT
MYSQL_FILE_IO_LATENCY_GROUPING = {
    'file'                              : ['IOLFE', 0],   # file
    'total'                             : ['IOLT', 1],   # Count
    'total_latency'                     : ['IOLTL', 2],   # seconds
    'count_read'                        : ['IOLCR', 3],   # count
    'read_latency'                      : ['IOLRL', 4],   # seconds
    'count_write'                       : ['IOLCW', 5],   # count
    'write_latency'                     : ['IOLWL', 6],    # seconds
    'count_misc'                        : ['IOLCM', 7],  # count
    'misc_latency'                      : ['IOLML', 8],  # seconds
}

# INSIGHT
MYSQL_EVENT_IO_LATENCY_GROUPING = {
    'event_name'                        : ['IOEEN', 0],   # The I/O event name, with the wait/io/file/ prefix stripped.
    'total'                             : ['IOET', 1],   # Count
    'total_latency'                     : ['IOETL', 2],   # seconds
    'avg_latency'                       : ['IOEAL', 3],   # seconds
    'max_latency'                       : ['IOEMAL', 4],   # seconds
    'read_latency'                      : ['IOERL', 5],    # count
    'write_latency'                     : ['IOEWL', 6],  # bytes
    'misc_latency'                      : ['IOEMSL', 7],  # bytes
    'count_read'                        : ['IOECR', 8],    # count
    'total_read'                        : ['IOETR', 9],  # bytes
    'avg_read'                          : ['IOEAR', 10],  # bytes
    'count_write'                       : ['IOECW', 11],   # count
    'total_written'                     : ['IOETW', 12],    # bytes
    'avg_written'                       : ['IOEAW', 13],  # bytes
}

# INSIGHT
MYSQL_RECENT_STATEMENTS_ERR_WRN_GROUPING = {
    'query'                             : ['SEWQ', 0],   # The I/O event name, with the wait/io/file/ prefix stripped.
    'db'                                : ['SEWDB', 1],   # Count
    'exec_count'                        : ['SEWEC', 2],   # seconds
    'errors'                            : ['SEWER', 3],   # seconds
    'error_pct'                         : ['SEWERP', 4],   # seconds
    'warnings'                          : ['SEWWN', 5],   # seconds
    'warning_pct'                       : ['SEWWNP', 6],    # count
    'first_seen'                        : ['SEWFS', 7],  # bytes
    'last_seen'                         : ['SEWLS', 8],  # bytes
}

#
# BASIC [MYSQL_DATABASE_STATEMENT_ANALYSIS] better option
MYSQL_DB_WISE_STATEMENT_ANALYSIS                = "SELECT query,db,full_scan,exec_count,err_count,warn_count,total_latency,max_latency,avg_latency,lock_latency,rows_sent,rows_sent_avg,rows_examined,rows_examined_avg,rows_Affected,rows_affected_avg,tmp_tables,tmp_disk_tables,rows_sorted,sort_merge_passes FROM sys.x$statement_analysis WHERE db = '{}'"
# https://dev.mysql.com/doc/refman/5.7/en/sys-statement-analysis.html
MYSQL_DB_WISE_STATEMENT_ANALYSIS_GROUPING = {
    'query'                          : ['DBSQ', 0],   # STRING
    'db'                             : ['DBSDB', 1],   # text
    'full_scan'                      : ['DBSFS', 2],   # count
    'exec_count'                     : ['DBSEXC', 3],   # count
    'err_count'                      : ['DBSERC', 4],   # count
    'warn_count'                     : ['DBSWC', 5],   # count
    'total_latency'                  : ['DBSTL', 6],    # second
    'max_latency'                    : ['DBSMAL', 7],  # second
    'avg_latency'                    : ['DBSAL', 8],  # second
    'lock_latency'                   : ['DBSLL', 9],   # second
    'rows_sent'                      : ['DBSRS', 10],    # count
    'rows_sent_avg'                  : ['DBSRSA', 11],  # count
    'rows_examined'                  : ['DBSWE', 12],  # count
    'rows_examined_avg'              : ['DBSWEA', 13],   # count
    'rows_affected'                  : ['DBSRA', 14],   # count
    'rows_affected_avg'              : ['DBSRAA', 15],   # count
    'tmp_tables'                     : ['DBSTT', 16],   # count
    'tmp_disk_tables'                : ['DBSTDT', 17],   # count
    'rows_sorted'                    : ['DBSRSR', 18],   # count
    'sort_merge_passes'              : ['DBSSMP', 19],    # count
    #'digest'                    : ['DBS', 17],   # seconds
    #'first_seen'                    : ['DBS', 18],   # seconds
    #'last_seen'                     : ['DBS', 19],    # count

}
# =====================================================================================================================================================================
# =====================================================================================================================================================================

# common metrics data collection grouping
MYSQL_COMMON_METRICS_COLLECTION_GROUPING = {
    'server_uuid'                       : ['SU']
}

# metrics collected from MYSQL_SHOW_STATUS
MYSQL_GLOBAL_STATUS_GROUPING = {
    'Aborted_clients'                   : ['ACL', ['diff']],
    'Aborted_connects'                  : ['ACN', ['diff']],    # example wrong credentials :: mysql -u roo -p
    'Binlog_cache_disk_use'             : ['BCDU', ['diff']],
    'Binlog_cache_use'                  : ['BCU', ['diff']],
    'Binlog_stmt_cache_disk_use'        : ['BSCDU', ['diff']],
    'Binlog_stmt_cache_use'             : ['BSCU', ['diff']],
    'Bytes_received'                    : ['BR', ['rate_s']],
    'Bytes_sent'                        : ['BS', ['rate_s']],
    'Com_alter_table'                   : ['CAT', ['diff']],
    'Com_begin'                         : ['CBN', ['diff']],
    'Com_binlog'                        : ['CB', ['diff']],
    'Com_change_master'                 : ['CCM', ['diff']],
    'Com_commit'                        : ['CCOM', ['diff']],
    'Com_create_db'                     : ['CCD', ['diff']],
    'Com_delete'                        : ['CD', ['diff']],
    'Com_delete_multi'                  : ['CDM', ['diff']],
    'Com_drop_db'                       : ['CDD', ['diff']],
    'Com_drop_table'                    : ['CDT', ['diff']],
    'Com_group_replication_start'       : ['CGRST', ['diff']],
    'Com_group_replication_stop'        : ['CGRSP', ['diff']],
    'Com_insert'                        : ['CI', ['diff']],
    'Com_insert_select'                 : ['CIS', ['diff']],
    'Com_load'                          : ['CL', ['diff']],
    'Com_replace'                       : ['CRP', ['diff']],
    'Com_replace_select'                : ['CRS', ['diff']],
    'Com_revoke'                        : ['CRV', ['diff']],
    'Com_revoke_all'                    : ['CRVA', ['diff']],
    'Com_rollback'                      : ['CRB', ['diff']],
    'Com_rollback_to_savepoint'         : ['CRBTS', ['diff']],
    'Com_savepoint'                     : ['CSP', ['diff']],
    'Com_select'                        : ['CS', ['diff']],
    'Com_show_binlog_events'            : ['CSBE', ['diff']],
    'Com_show_binlogs'                  : ['CSB', ['diff']],
    'Com_shutdown'                      : ['CSD', ['diff']],
    'Com_slave_start'                   : ['CSST', ['diff']],
    'Com_slave_stop'                    : ['CSSP', ['diff']],
    'Com_stmt_execute'                  : ['CSE', ['diff']],
    'Com_update'                        : ['CU', ['diff']],
    'Com_update_multi'                  : ['CUM', ['diff']],
    'Connection_errors_accept'          : ['CEA', ['diff']],
    'Connection_errors_internal'        : ['CEI', ['diff']],
    'Connection_errors_max_connections' : ['CEMC', ['diff']],
    'Connection_errors_peer_address'    : ['CEPA', ['diff']],
    'Connection_errors_select'          : ['CES', ['diff']],
    'Connection_errors_tcpwrap'         : ['CETCP', ['diff']],
    'Connections'                       : ['CN', ['diff']],
    'Created_tmp_disk_tables'           : ['CTDT', ['rate_s']],# per sec
    'Created_tmp_files'                 : ['CTF', ['rate_s']],# per sec
    'Created_tmp_tables'                : ['CTT', ['rate_s']],# per sec
    'Handler_commit'                    : ['HC', ['rate_s']],# per sec
    'Handler_delete'                    : ['HDT', ['rate_s']],# per sec
    'Handler_discover'                  : ['HDS', ['rate_s']],# per sec
    'Handler_external_lock'             : ['HEL', ['rate_s']],# per sec
    'Handler_prepare'                   : ['HPR', ['rate_s']],# per sec
    'Handler_read_first'                : ['HRF', ['rate_s']],# per sec
    'Handler_read_key'                  : ['HRK', ['rate_s']],# per sec
    'Handler_read_last'                 : ['HRL', ['rate_s']],# per sec
    'Handler_read_next'                 : ['HRN', ['rate_s']],# per sec
    'Handler_read_prev'                 : ['HRP', ['rate_s']],# per sec
    'Handler_read_rnd'                  : ['HRR', ['rate_s']],# per sec
    'Handler_read_rnd_next'             : ['HRRN', ['rate_s']],# per sec
    'Handler_rollback'                  : ['HR', ['rate_s']],# per sec
    'Handler_savepoint'                 : ['HSP', ['rate_s']],# per sec
    'Handler_savepoint_rollback'        : ['HSPR', ['rate_s']],# per sec
    'Handler_update'                    : ['HU', ['rate_s']],# per sec
    'Handler_write'                     : ['HW', ['rate_s']],# per sec
    'Innodb_buffer_pool_bytes_data'     : ['IBPBDT', ['perf']],
    'Innodb_buffer_pool_bytes_dirty'    : ['IBPBDY', ['perf']],
    'Innodb_buffer_pool_pages_data'     : ['IBPPDT', ['perf']],
    'Innodb_buffer_pool_pages_dirty'    : ['IBPPDY', ['perf']],
    'Innodb_buffer_pool_pages_flushed'  : ['IBPPFL', ['rate_s']],
    'Innodb_buffer_pool_pages_free'     : ['IBPPF', ['perf']],
    'Innodb_buffer_pool_pages_misc'     : ['IBPPM', ['perf']],
    'Innodb_buffer_pool_pages_total'    : ['IBPPT', ['perf']],
    'Innodb_buffer_pool_read_requests'  : ['IBPRR', ['rate_s']],
    'Innodb_buffer_pool_reads'          : ['IBPR', ['rate_s']],
    'Innodb_buffer_pool_wait_free'      : ['IBPWF', ['rate_s']],
    'Innodb_buffer_pool_write_requests' : ['IBPWR', ['rate_s']],
    'Innodb_data_fsyncs'                : ['IDF', ['rate_s']],
    'Innodb_data_read'                  : ['IDR', ['rate_s']],
    'Innodb_data_reads'                 : ['IDRS', ['rate_s']],
    'Innodb_data_writes'                : ['IDWS', ['rate_s']],
    'Innodb_data_written'               : ['IDWN', ['rate_s']],
    'Innodb_log_write_requests'         : ['ILWR', ['rate_m']],# per min
    'Innodb_log_writes'                 : ['ILW', ['rate_m']],# per min
    'Innodb_os_log_fsyncs'              : ['IOLF', ['rate_m']],# per min
    'Innodb_page_size'                  : ['IPS', ['perf']],
    'Innodb_pages_created'              : ['IPC', ['rate_s']],
    'Innodb_pages_read'                 : ['IPR', ['rate_s']],
    'Innodb_pages_written'              : ['IPW', ['rate_s']],
    'Innodb_row_lock_current_waits'     : ['IRLCW', ['perf']], # already changing attribute
    'Innodb_row_lock_time'              : ['IRLT', ['diff']], # millisecond unit attribute
    'Innodb_row_lock_waits'             : ['IRLW', ['rate_s']],
    'Innodb_rows_deleted'               : ['IRD', ['rate_s']],
    'Innodb_rows_inserted'              : ['IRI', ['rate_s']],
    'Innodb_rows_read'                  : ['IRR', ['rate_s']],
    'Innodb_rows_updated'               : ['IRU', ['rate_s']],
    'Key_blocks_not_flushed'            : ['KBNF', ['perf']],# per min
    'Key_blocks_unused'                 : ['KBUU', ['perf']],# per min
    'Key_blocks_used'                   : ['KBU', ['perf']],# per min
    'Key_buffer_bytes_unflushed'        : ['KBBUF', ['derv']], # derived data
    'Key_buffer_bytes_used'             : ['KBBUS', ['derv']], # derived data
    'Key_read_requests'                 : ['KRR', ['rate_s']],
    'Key_reads'                         : ['KR', ['rate_s']],
    'Key_write_requests'                : ['KWR', ['rate_s']],
    'Key_writes'                        : ['KW', ['rate_s']],
    'Max_used_connections'              : ['MUC', ['perf']],
    'Max_used_connections_time'         : ['MUCT', ['date']],   # not available for [5.6] -> The time at which Max_used_connections reached its current value.
    'Open_files'                        : ['OF', ['perf']], # already changing attribute
    'Open_streams'                      : ['OS', ['perf']], # already changing attribute
    'Open_table_definitions'            : ['OTD', ['perf']], # already changing attribute
    'Open_tables'                       : ['OT', ['perf']], # already changing attribute
    'Opened_files'                      : ['ODF', ['rate_s']],
    'Opened_table_definitions'          : ['ODTD', ['rate_s']],
    'Opened_tables'                     : ['ODT', ['rate_s']],
    'Prepared_stmt_count'               : ['PSC', ['perf']], # already changing attribute
    'Qcache_free_blocks'                : ['QFB', ['perf']], # already changing attribute       # deprecated from 5.7
    'Qcache_free_memory'                : ['QFM', ['perf']], # already changing attribute       # deprecated from 5.7
    'Qcache_hits'                       : ['QH', ['diff']],                # deprecated from 5.7
    'Qcache_inserts'                    : ['QI', ['diff']],             # deprecated from 5.7
    'Qcache_lowmem_prunes'              : ['QLP', ['diff']],      # deprecated from 5.7
    'Qcache_not_cached'                 : ['QNC', ['diff']],         # deprecated from 5.7
    'Qcache_queries_in_cache'           : ['QQIC', ['diff']],  # deprecated from 5.7
    'Queries'                           : ['QR', ['rate_m']],# per min
    'Questions'                         : ['QS', ['rate_m']],# per min
    'Select_full_join'                  : ['SFJ', ['diff']],
    'Select_scan'                       : ['SS', ['diff']],
    'Slave_heartbeat_period'            : ['SHP', ['perf']], # already changing attribute   # deprecated from 5.7
    'Slave_last_heartbeat'              : ['SLH', ['date']],       # deprecated from 5.7
    'Slave_open_temp_tables'            : ['SOTT', ['perf']], # already changing attribute   # deprecated from 5.7
    'Slave_received_heartbeats'         : ['SRH', ['diff']],   # deprecated from 5.7
    'Slave_retried_transactions'        : ['SRT', ['diff']],  # deprecated from 5.7
    'Slow_launch_threads'               : ['SLT', ['diff']],
    'Sort_merge_passes'                 : ['SMP', ['rate_m']],# per min
    'Sort_range'                        : ['SRG', ['rate_m']],# per min
    'Sort_rows'                         : ['SRW', ['rate_m']],# per min
    'Sort_scan'                         : ['SSC', ['rate_m']],# per min
    'Slow_queries'                      : ['SQ', ['diff']],# first kept as rate_m, but has no use for threshold use case
    'Ssl_accepts'                       : ['SSLA', ['diff']],
    'Ssl_client_connects'               : ['SSLCC', ['diff']],
    'Ssl_finished_accepts'              : ['SSLFA', ['diff']],
    'Ssl_finished_connects'             : ['SSLFC', ['diff']],
    'Table_locks_immediate'             : ['TLI', ['rate_m']],# per min
    'Table_locks_waited'                : ['TLW', ['rate_m']],# per min
    #'Table_locks_waited_rate'          : ['TLWR', ['perf']],
    'Table_open_cache_hits'             : ['TOCH', ['diff']],
    'Table_open_cache_misses'           : ['TOCM', ['diff']],
    'Table_open_cache_overflows'        : ['TOCO', ['diff']],
    'Threads_cached'                    : ['TCH', ['perf']], # already changing attribute
    'Threads_connected'                 : ['TCN', ['perf']], # already changing attribute
    'Threads_created'                   : ['TCR', ['diff']], #
    'Threads_running'                   : ['TR', ['perf']], # already changing attribute
    'Uptime'                            : ['UT', ['perf']],
    'Uptime_since_flush_status'         : ['UTSFS', ['perf']],
}

MYSQL_SLAVE_HOSTS_GROUPING = {
    'Server_id'                         : ['SID', 0],
    'Host'                              : ['SH', 1],
    'Port'                              : ['SP', 2],
    'Master_id'                         : ['SMI', 3],
    'Slave_UUID'                        : ['SUUID', 4],
}

MYSQL_MASTER_HOSTS_GROUPING = {
    'Master_Server_Id'                  : ['MSID', 39],
    'Master_Host'                       : ['MMH', 1],
    'Master_Port'                       : ['MMP', 3],
    'Master_UUID'                       : ['MMUID', 40],
}

# version [5.7, 8.0] two metrics added
# self.query['MYSQL_REPLICATION_STATUS_GROUPING']['Channel_name'] = ['CHN', 55]
# self.query['MYSQL_REPLICATION_STATUS_GROUPING']['Master_TLS_Version'] = ['MTLSV', 56]
MYSQL_REPLICATION_STATUS_GROUPING = {
    'Slave_IO_State'                    : ['SIS', 0],
    'Master_Host'                       : ['MH', 1],
    'Master_User'                       : ['MU', 2],
    'Master_Port'                       : ['MP', 3],
    'Connect_Retry'                     : ['CR', 4],
    'Master_Log_File'                   : ['MLF', 5],
    'Read_Master_Log_Pos'               : ['RMLP', 6],
    'Relay_Log_File'                    : ['RLF', 7],
    'Relay_Log_Pos'                     : ['RLP', 8],
    'Relay_Master_Log_File'             : ['RMLF', 9],
    'Slave_IO_Running'                  : ['SIR', 10],
    'Slave_SQL_Running'                 : ['SSR', 11],
    'Last_Errno'                        : ['LERN', 18],
    'Last_Error'                        : ['LER', 19],
    'Relay_Log_Space'                   : ['RLS', 22],
    'Seconds_Behind_Master'             : ['SBM', 32],
    'Last_IO_Errno'                     : ['LIOEN', 34], #
    'Last_IO_Error'                     : ['LIOE', 35],
    'Last_SQL_Errno'                    : ['LSQLEN', 36],
    'Last_SQL_Error'                    : ['LSQLE', 37],
    'Master_Server_Id'                  : ['MSI', 39],
    'Master_UUID'                       : ['MUUID', 40],
    'Master_Info_File'                  : ['MIF', 41],
    'SQL_Delay'                         : ['SD', 42],
    'Slave_SQL_Running_State'           : ['SSRS', 44],
    'Master_Retry_Count'                : ['MRC', 45],
    'Last_IO_Error_Timestamp'           : ['LIOET', 47],
    'Last_SQL_Error_Timestamp'          : ['LSQLET', 48],
    'Auto_Position'                     : ['AP', 53],
}

MYSQL_PERFORMANCE_REPLICATION_STATUS_GROUPING = {
    'Master_Host'                       : ['MH', 1],
    'Master_Port'                       : ['MP', 3],
    'Seconds_Behind_Master'             : ['SBM', 32],
    'Master_Server_Id'                  : ['MSI', 39],
    'Master_UUID'                       : ['MUUID', 40]
}

# innodb engine metrics grouping [show innodb engine status]
MYSQL_INNODB_ENGINE_GROUPING = {
    'Innodb_active_transactions': ['IAT', 'perf'],
    'Innodb_current_transactions': ['ICT', 'perf'],
    'Innodb_hash_index_cells_total': ['IHICT', 'perf'],
    'Innodb_hash_index_cells_used': ['IHICU', 'perf'],
    'Innodb_history_list_length': ['IHLL', 'perf'],
    'Innodb_ibuf_free_list': ['IIFL', 'perf'],
    'Innodb_ibuf_merged': ['IIM', 'perf'],
    'Innodb_ibuf_merged_delete_marks': ['IIMDM', 'perf'],
    'Innodb_ibuf_merged_deletes': ['IIMD', 'perf'],
    'Innodb_ibuf_merged_inserts': ['IIMI', 'perf'],
    'Innodb_ibuf_merges': ['IIMS', 'perf'],
    'Innodb_ibuf_segment_size': ['IISS', 'perf'],
    'Innodb_ibuf_size': ['IIS', 'perf'],
    'Innodb_lock_structs': ['ILS', 'perf'],
    'Innodb_locked_tables': ['ILTB', 'perf'],
    'Innodb_locked_transactions': ['ILTR', 'perf'],
    'Innodb_lsn_current': ['ILC', 'perf'],
    'Innodb_lsn_flushed': ['ILF', 'perf'],
    'Innodb_lsn_last_checkpoint': ['ILLC', 'perf'],
    'Innodb_mem_adaptive_hash': ['IMAH', 'perf'],
    'Innodb_mem_additional_pool': ['IMAP', 'perf'],
    'Innodb_mem_dictionary': ['IMD', 'perf'],
    'Innodb_mem_file_system': ['IMFS', 'perf'],
    'Innodb_mem_lock_system': ['IMLS', 'perf'],
    'Innodb_mem_page_hash': ['IMPH', 'perf'],
    'Innodb_mem_recovery_system': ['IMRS', 'perf'],
    'Innodb_mem_thread_hash': ['IMTB', 'perf'],
    'Innodb_mem_total': ['IMT', 'perf'],
    'Innodb_mutex_os_waits': ['IMOW', 'perf'],
    'Innodb_mutex_spin_rounds': ['IMSR', 'perf'],
    'Innodb_mutex_spin_waits': ['IMSW', 'perf'],
    'Innodb_os_file_fsyncs': ['IOFF', 'perf'],
    'Innodb_os_file_reads': ['IOFR', 'perf'],
    'Innodb_os_file_writes': ['IOFW', 'perf'],
    'Innodb_pending_aio_log_ios': ['IPALI', 'perf'],
    'Innodb_pending_aio_sync_ios': ['IPASI', 'perf'],
    'Innodb_pending_buffer_pool_flushes': ['IPBPF', 'perf'],
    'Innodb_pending_checkpoint_writes': ['IPCW', 'perf'],
    'Innodb_pending_ibuf_aio_reads': ['IPIAR', 'perf'],
    'Innodb_pending_log_flushes': ['IPLF', 'perf'],
    'Innodb_pending_log_writes': ['IPLW', 'perf'],
    'Innodb_pending_normal_aio_reads': ['IPNAR', 'perf'],
    'Innodb_pending_normal_aio_writes': ['IPNAW', 'perf'],
    'Innodb_queries_inside': ['IQI', 'perf'],
    'Innodb_queries_queued': ['IQQ', 'perf'],
    'Innodb_read_views': ['IRV', 'perf'],
    'Innodb_s_lock_os_waits': ['ISLOW', 'perf'],
    'Innodb_s_lock_spin_rounds': ['ISLSR', 'perf'],
    'Innodb_s_lock_spin_waits': ['ISLSW', 'perf'],
    'Innodb_semaphore_waits': ['ISW', 'perf'],
    'Innodb_semaphore_wait_time': ['ISW', 'perf'],
    'Innodb_tables_in_use': ['ITIU', 'perf'],
    'Innodb_x_lock_os_waits': ['IXLOW', 'perf'],
    'Innodb_x_lock_spin_rounds': ['IXLSR', 'perf'],
    'Innodb_x_lock_spin_waits': ['IXLSW', 'perf'],
}

MYSQL_GLOBAL_VARIABLES_GROUPING = {
    #'Key_cache_utilization': ['KCU', 'conf'],
    'auto_generate_certs'               : ['AGC', 'conf'],           # not available for [5.6]
    'auto_increment_increment'          : ['AII', 'conf'],
    'auto_increment_offset'             : ['AIO', 'conf'],
    'autocommit'                        : ['AC', 'conf'],
    'automatic_sp_privileges'           : ['ASP', 'conf'],
    'back_log'                          : ['BL', 'conf'],
    'basedir'                           : ['BD', 'conf'],
    'big_tables'                        : ['BT', 'conf'],
    'binlog_cache_size'                 : ['BCS', 'conf'],
    'binlog_encryption'                 : ['BE', 'conf'],
    'binlog_error_action'               : ['BEA', 'conf'],
    'binlog_expire_logs_seconds'        : ['BELS', 'conf'],
    'binlog_format'                     : ['BF', 'conf'],
    'binlog_gtid_simple_recovery'       : ['BGSR', 'conf'],
    'binlog_stmt_cache_size'            : ['BSCS', 'conf'],
    'bulk_insert_buffer_size'           : ['BIBS', 'conf'],
    'check_proxy_users'                 : ['CPU', 'conf'],
    'connect_timeout'                   : ['CT', 'conf'],
    'datadir'                           : ['DD', 'conf'],
    'datetime_format'                   : ['DF', 'conf'],
    'default_storage_engine'            : ['DSE', 'conf'],
    'default_tmp_storage_engine'        : ['DTSE', 'conf'],
    'delayed_insert_limit'              : ['DIL', 'conf'],
    'delayed_insert_timeout'            : ['DIT', 'conf'],
    'delayed_queue_size'                : ['DQS', 'conf'],
    'expire_logs_days'                  : ['ELD', 'conf'],
    'general_log'                       : ['GL', 'conf'],
    'general_log_file'                  : ['GLF', 'conf'],
    'hostname'                          : ['HN', 'conf'],
    'init_slave'                        : ['IS', 'conf'],
    'innodb_autoinc_lock_mode'          : ['IALM', 'conf'],
    'innodb_buffer_pool_filename'       : ['IBPF', 'conf'],
    'innodb_buffer_pool_instances'      : ['IBPI', 'conf'],
    'innodb_buffer_pool_size'           : ['IBPS', 'conf'],
    'innodb_change_buffering'           : ['ICB', 'conf'],
    'innodb_data_file_path'             : ['IDFP', 'conf'],
    'innodb_data_home_dir'              : ['IDHD', 'conf'],
    'innodb_deadlock_detect'            : ['IDD', 'conf'],
    'innodb_flush_log_at_timeout'       : ['IFLAT', 'conf'],
    'innodb_flush_log_at_trx_commit'    : ['IFLATC', 'conf'],
    'innodb_io_capacity'                : ['IIC', 'conf'],
    'innodb_lock_wait_timeout'          : ['ILWT', 'conf'],
    'innodb_log_buffer_size'            : ['ILBS', 'conf'],
    'innodb_log_file_size'              : ['ILFS', 'conf'],
    'innodb_log_group_home_dir'         : ['ILGHD', 'conf'],
    'innodb_open_files'                 : ['IOF', 'conf'],
    'innodb_replication_delay'          : ['IRPD', 'conf'],
    'innodb_rollback_on_timeout'        : ['IROT', 'conf'],
    'innodb_temp_data_file_path'        : ['ITDFP', 'conf'],
    'innodb_version'                    : ['IV', 'conf'],
    'interactive_timeout'               : ['IT', 'conf'],
    'join_buffer_size'                  : ['JBS', 'conf'],
    'key_buffer_size'                   : ['KBS', 'conf'],
    'key_cache_age_threshold'           : ['KCAT', 'conf'],
    'key_cache_block_size'              : ['KCBS', 'conf'],
    'key_cache_division_limit'          : ['KCDL', 'conf'],
    'large_files_support'               : ['LFS', 'conf'],
    'large_page_size'                   : ['LPS', 'conf'],
    'lock_wait_timeout'                 : ['LWT', 'conf'],
    'log_bin'                           : ['LB', 'conf'],
    'log_bin_basename'                  : ['LBB', 'conf'],
    'log_bin_index'                     : ['LBI', 'conf'],
    'log_error'                         : ['LE', 'conf'],
    'long_query_time'                   : ['LQT', 'conf'],
    'max_allowed_packet'                : ['MAP', 'conf'],
    'max_binlog_cache_size'             : ['MBCS', 'conf'],
    'max_binlog_size'                   : ['MBS', 'conf'],
    'max_binlog_stmt_cache_size'        : ['MBSCS', 'conf'],
    'max_connect_errors'                : ['MCE', 'conf'],
    'max_connections'                   : ['MC', 'conf'],
    'max_delayed_threads'               : ['MDT', 'conf'],
    'max_error_count'                   : ['MEC', 'conf'],
    'max_heap_table_size'               : ['MHTS', 'conf'],
    'max_insert_delayed_threads'        : ['MIDT', 'conf'],
    'max_join_size'                     : ['MJS', 'conf'],
    'max_prepared_stmt_count'           : ['MPSC', 'conf'],
    'max_sp_recursion_depth'            : ['MSRD', 'conf'],
    'max_tmp_tables'                    : ['MTT', 'conf'],
    'max_user_connections'              : ['MUSC', 'conf'],
    'max_write_lock_count'              : ['MWLC', 'conf'],
    'myisam_data_pointer_size'          : ['MDPS', 'conf'],
    'myisam_max_sort_file_size'         : ['MMSFS', 'conf'],
    'myisam_mmap_size'                  : ['MMS', 'conf'],
    'myisam_recover_options'            : ['MRO', 'conf'],
    'myisam_repair_threads'             : ['MRT', 'conf'],
    'myisam_sort_buffer_size'           : ['MSBS', 'conf'],
    'myisam_stats_method'               : ['MSM', 'conf'],
    'myisam_use_mmap'                   : ['MUM', 'conf'],
    'net_buffer_length'                 : ['NBL', 'conf'],
    'net_read_timeout'                  : ['NRT', 'conf'],
    'net_retry_count'                   : ['NRC', 'conf'],
    'net_write_timeout'                 : ['NWT', 'conf'],
    'open_files_limit'                  : ['OFL', 'conf'],
    'performance_schema'                : ['PS', 'conf'],
    'pid_file'                          : ['PDF', 'conf'],
    'plugin_dir'                        : ['PLD', 'conf'],
    'port'                              : ['PT', 'conf'],
    'preload_buffer_size'               : ['PBS', 'conf'],
    'profiling_history_size'            : ['PHS', 'conf'],
    'query_alloc_block_size'            : ['QABS', 'conf'],
    'query_cache_size'                  : ['QCS', 'conf'],
    'query_prealloc_size'               : ['QPS', 'conf'],
    'range_alloc_block_size'            : ['RABS', 'conf'],
    'read_buffer_size'                  : ['RBS', 'conf'],
    'read_rnd_buffer_size'              : ['RRBS', 'conf'],
    'server_uuid'                       : ['SU', 'conf'],
    'slow_launch_time'                  : ['SLTM', 'conf'],
    'slow_query_log'                    : ['SQL', 'conf'],
    'slow_query_log_file'               : ['SQLF', 'conf'],
    'socket'                            : ['SK', 'conf'],
    'sort_buffer_size'                  : ['SBFS', 'conf'],
    'sql_auto_is_null'                  : ['SAIN', 'conf'],
    'sql_big_selects'                   : ['SBSL', 'conf'],
    'sql_buffer_result'                 : ['SBR', 'conf'],
    'sql_log_off'                       : ['SLO', 'conf'],
    'sql_safe_updates'                  : ['SSU', 'conf'],
    'sql_select_limit'                  : ['SSL', 'conf'],
    'sql_warnings'                      : ['SW', 'conf'],
    'sync_binlog'                       : ['SB', 'conf'],
    'table_definition_cache'            : ['TDC', 'conf'],
    'table_open_cache'                  : ['TOC', 'conf'],
    'thread_cache_size'                 : ['TCS', 'conf'],
    'version'                           : ['VR', 'conf'],
    'version_comment'                   : ['VRC', 'conf'],
    'version_compile_machine'           : ['VCM', 'conf'],
    'version_compile_os'                : ['VCO', 'conf'],
    'wait_timeout'                      : ['WT', 'conf'],
}

# version [8.0] more metrics added
# 'MEMBER_ROLE': ['RMR', 5],
# 'MEMBER_VERSION': ['RMV', 6],
# 'COUNT_TRANSACTIONS_REMOTE_APPLIED': ['RCTRA', 11],
# 'COUNT_TRANSACTIONS_LOCAL_PROPOSED': ['RCTLP', 12],
# 'COUNT_TRANSACTIONS_LOCAL_ROLLBACK': ['RCTLR', 13],

MYSQL_REPLICATION_GRP_DATA_GROUPING_SAMPLE = {
    'CHANNEL_NAME'                      : ['RCN', 0],
    'MEMBER_ID'                         : ['RMI', 1],
    'MEMBER_HOST'                       : ['RMH', 2],
    'MEMBER_PORT'                       : ['RMP', 3],
    'MEMBER_STATE'                      : ['RMS', 4],
    'COUNT_TRANSACTIONS_IN_QUEUE'       : ['RCTIQ', 7],
    'COUNT_TRANSACTIONS_CHECKED'        : ['RCTC', 8],
    'COUNT_CONFLICTS_DETECTED'          : ['RCCD', 9],
    'COUNT_TRANSACTIONS_ROWS_VALIDATING': ['RCTRV', 10],
}

MYSQL_BASIC_INSIGHT_COMMON_VARIABLES = {
    'slow_query_log'                    : None,
    'slow_query_log_file'               : None,
    'long_query_time'                   : None,
    'log_bin'                           : None,
    'server_uuid'                       : None,
}

MYSQL_INSIGHT_COMMON_VARIABLES = {
    'long_query_time'                   : None,
}

MYSQL_PS_ACCOUNTS_GROUPING = {
    'USER'                              : ['AU', 0],
    'HOST'                              : ['AH', 1],
    'CURRENT_CONNECTIONS'               : ['ACC', 2],
    'TOTAL_CONNECTIONS'                 : ['ATC', 0],
}

def set_query_for_data_collection(version):
    try:
        global MYSQL_REPLICATION_SLAVE_STATUS_QUERY
        global MYSQL_SHOW_SLAVE_HOSTS
        global MYSQL_REPLICATION_GRP_MEMBERS_DATA_QUERY
        global MYSQL_SHOW_BINARY_LOGS#
        global MYSQL_SHOW_RELAYLOG_EVENTS
        global MYSQL_SLAVE_HOSTS_GROUPING
        global MYSQL_MASTER_HOSTS_GROUPING
        global MYSQL_REPLICATION_STATUS_GROUPING
        global MYSQL_REPLICATION_GRP_DATA_GROUPING
        global MYSQL_REPLICATION_GRP_DATA_GROUPING_SAMPLE
        global MYSQL_COMMON_METRICS_COLLECTION_QUERY

        if 'mariadb' in version:
            MYSQL_COMMON_METRICS_COLLECTION_QUERY          = "SHOW GLOBAL VARIABLES WHERE VARIABLE_NAME IN ('server_id')"

            MYSQL_SLAVE_HOSTS_GROUPING = {
                'Server_id'                         : ['SID', 0],
                'Host'                              : ['SH', 1],
                'Port'                              : ['SP', 2],
                'Master_id'                         : ['SMI', 3],
                # 'Slave_UUID'                        : ['SUUID', 4],
            }
            MYSQL_MASTER_HOSTS_GROUPING = {
                'Master_Server_Id'                  : ['MSID', 40],
                'Master_Host'                       : ['MMH', 1],
                'Master_Port'                       : ['MMP', 3],
                # 'Master_UUID'                       : ['MMUID', 40],
            }
            MYSQL_REPLICATION_GRP_MEMBERS_DATA_QUERY        = None
            MYSQL_REPLICATION_GRP_DATA_GROUPING             = None

            for rm in ['Master_UUID','Master_Info_File','Master_Retry_Count','Last_IO_Error_Timestamp','Last_SQL_Error_Timestamp','Auto_Position']:
                if MYSQL_REPLICATION_STATUS_GROUPING.get(rm):
                    MYSQL_REPLICATION_STATUS_GROUPING.pop(rm)
            MYSQL_REPLICATION_STATUS_GROUPING.update({
                'Slave_IO_State'                    : ['SIS', 0],
                'Master_Host'                       : ['MH', 1],
                'Master_User'                       : ['MU', 2],
                'Master_Port'                       : ['MP', 3],
                'Connect_Retry'                     : ['CR', 4],
                'Master_Log_File'                   : ['MLF', 5],
                'Read_Master_Log_Pos'               : ['RMLP', 6],
                'Relay_Log_File'                    : ['RLF', 7],
                'Relay_Log_Pos'                     : ['RLP', 8],
                'Relay_Master_Log_File'             : ['RMLF', 9],
                'Slave_IO_Running'                  : ['SIR', 10],
                'Slave_SQL_Running'                 : ['SSR', 11],
                'Last_Errno'                        : ['LERN', 19],
                'Last_Error'                        : ['LER', 20],
                'Relay_Log_Space'                   : ['RLS', 23],
                'Seconds_Behind_Master'             : ['SBM', 33],
                'Last_IO_Errno'                     : ['LIOEN', 35], #
                'Last_IO_Error'                     : ['LIOE', 36],
                'Last_SQL_Errno'                    : ['LSQLEN', 37],
                'Last_SQL_Error'                    : ['LSQLE', 38],
                'Master_Server_Id'                  : ['MSI', 40],
                'SQL_Delay'                         : ['SD', 48],
                'Slave_SQL_Running_State'           : ['SSRS', 50]
            })
            MYSQL_REPLICATION_SLAVE_STATUS_QUERY            = 'SHOW SLAVE STATUS'

        elif version >= '5.6' and version < '5.7':
            MYSQL_REPLICATION_SLAVE_STATUS_QUERY            = 'SHOW SLAVE STATUS'

            MYSQL_REPLICATION_STATUS_GROUPING               = MYSQL_REPLICATION_STATUS_GROUPING

            # not available for 5.6 version
            MYSQL_REPLICATION_GRP_MEMBERS_DATA_QUERY        = None
            MYSQL_REPLICATION_GRP_DATA_GROUPING             = None

            MYSQL_SHOW_SLAVE_HOSTS                          = 'SHOW SLAVE HOSTS'
            MYSQL_SLAVE_HOSTS_GROUPING                      = MYSQL_SLAVE_HOSTS_GROUPING
            MYSQL_MASTER_HOSTS_GROUPING                     = MYSQL_MASTER_HOSTS_GROUPING

            MYSQL_SHOW_BINARY_LOGS                          = 'SHOW BINARY LOGS'
            MYSQL_SHOW_RELAYLOG_EVENTS                      = 'SHOW RELAYLOG EVENTS'


        elif version >= '5.7' and version < '5.8':

            MYSQL_REPLICATION_SLAVE_STATUS_QUERY            = 'SHOW SLAVE STATUS'

            MYSQL_REPLICATION_STATUS_GROUPING               = MYSQL_REPLICATION_STATUS_GROUPING
            MYSQL_REPLICATION_STATUS_GROUPING['Channel_name']                       = ['CHN', 55]
            MYSQL_REPLICATION_STATUS_GROUPING['Master_TLS_Version']                 = ['MTLSV', 56]

            MYSQL_REPLICATION_GRP_MEMBERS_DATA_QUERY        = "SELECT t1.CHANNEL_NAME,t1.MEMBER_ID,t1.MEMBER_HOST,t1.MEMBER_PORT,t1.MEMBER_STATE,t2.COUNT_TRANSACTIONS_IN_QUEUE,t2.COUNT_TRANSACTIONS_CHECKED,t2.COUNT_CONFLICTS_DETECTED,t2.COUNT_TRANSACTIONS_ROWS_VALIDATING FROM performance_schema.replication_group_members t1, performance_schema.replication_group_member_stats t2 where t1.MEMBER_ID = t2.MEMBER_ID"

            MYSQL_REPLICATION_GRP_DATA_GROUPING             = MYSQL_REPLICATION_GRP_DATA_GROUPING_SAMPLE

            MYSQL_SHOW_SLAVE_HOSTS                          = 'SHOW SLAVE HOSTS'
            MYSQL_SLAVE_HOSTS_GROUPING                      = MYSQL_SLAVE_HOSTS_GROUPING
            MYSQL_MASTER_HOSTS_GROUPING                     = MYSQL_MASTER_HOSTS_GROUPING

            MYSQL_SHOW_BINARY_LOGS                          = 'SHOW BINARY LOGS'
            MYSQL_SHOW_RELAYLOG_EVENTS                      = 'SHOW RELAYLOG EVENTS'


        elif version >= '8.0' and version < '8.0.22':

            MYSQL_REPLICATION_SLAVE_STATUS_QUERY            = 'SHOW SLAVE STATUS'

            MYSQL_REPLICATION_STATUS_GROUPING               = MYSQL_REPLICATION_STATUS_GROUPING
            MYSQL_REPLICATION_STATUS_GROUPING['Channel_name']                        = ['CHN', 55]
            MYSQL_REPLICATION_STATUS_GROUPING['Master_TLS_Version']                  = ['MTLSV', 56]

            MYSQL_REPLICATION_GRP_MEMBERS_DATA_QUERY        = "SELECT t1.CHANNEL_NAME,t1.MEMBER_ID,t1.MEMBER_HOST,t1.MEMBER_PORT,t1.MEMBER_STATE,t1.MEMBER_ROLE,t1.MEMBER_VERSION,t2.COUNT_TRANSACTIONS_IN_QUEUE,t2.COUNT_TRANSACTIONS_CHECKED,t2.COUNT_CONFLICTS_DETECTED,t2.COUNT_TRANSACTIONS_ROWS_VALIDATING,t2.COUNT_TRANSACTIONS_REMOTE_APPLIED,t2.COUNT_TRANSACTIONS_LOCAL_PROPOSED,t2.COUNT_TRANSACTIONS_LOCAL_ROLLBACK FROM performance_schema.replication_group_members t1, performance_schema.replication_group_member_stats t2 where t1.MEMBER_ID = t2.MEMBER_ID"

            MYSQL_REPLICATION_GRP_DATA_GROUPING             = MYSQL_REPLICATION_GRP_DATA_GROUPING_SAMPLE
            MYSQL_REPLICATION_GRP_DATA_GROUPING['MEMBER_ROLE']                       = ['RMR', 5]
            MYSQL_REPLICATION_GRP_DATA_GROUPING['MEMBER_VERSION']                    = ['RMV', 6]
            MYSQL_REPLICATION_GRP_DATA_GROUPING['COUNT_TRANSACTIONS_REMOTE_APPLIED'] = ['RCTRA', 11]
            MYSQL_REPLICATION_GRP_DATA_GROUPING['COUNT_TRANSACTIONS_LOCAL_PROPOSED'] = ['RCTLP', 12]
            MYSQL_REPLICATION_GRP_DATA_GROUPING['COUNT_TRANSACTIONS_LOCAL_ROLLBACK'] = ['RCTLR', 13]

            MYSQL_SHOW_SLAVE_HOSTS                          = 'SHOW SLAVE HOSTS'
            MYSQL_SLAVE_HOSTS_GROUPING                      = MYSQL_SLAVE_HOSTS_GROUPING
            MYSQL_MASTER_HOSTS_GROUPING                     = MYSQL_MASTER_HOSTS_GROUPING

            MYSQL_SHOW_BINARY_LOGS                          = 'SHOW BINARY LOGS'
            MYSQL_SHOW_RELAYLOG_EVENTS                      = 'SHOW RELAYLOG EVENTS'


        elif version >= '8.0.22':

            MYSQL_REPLICATION_SLAVE_STATUS_QUERY            = 'SHOW REPLICA STATUS'

            MYSQL_REPLICATION_STATUS_GROUPING               = MYSQL_REPLICATION_STATUS_GROUPING
            MYSQL_REPLICATION_STATUS_GROUPING['Channel_name']                        = ['CHN', 55]
            MYSQL_REPLICATION_STATUS_GROUPING['Master_TLS_Version']                  = ['MTLSV', 56]

            MYSQL_REPLICATION_GRP_MEMBERS_DATA_QUERY        = "SELECT t1.CHANNEL_NAME,t1.MEMBER_ID,t1.MEMBER_HOST,t1.MEMBER_PORT,t1.MEMBER_STATE,t1.MEMBER_ROLE,t1.MEMBER_VERSION,t2.COUNT_TRANSACTIONS_IN_QUEUE,t2.COUNT_TRANSACTIONS_CHECKED,t2.COUNT_CONFLICTS_DETECTED,t2.COUNT_TRANSACTIONS_ROWS_VALIDATING,t2.COUNT_TRANSACTIONS_REMOTE_APPLIED,t2.COUNT_TRANSACTIONS_LOCAL_PROPOSED,t2.COUNT_TRANSACTIONS_LOCAL_ROLLBACK FROM performance_schema.replication_group_members t1, performance_schema.replication_group_member_stats t2 where t1.MEMBER_ID = t2.MEMBER_ID"

            MYSQL_REPLICATION_GRP_DATA_GROUPING             = MYSQL_REPLICATION_GRP_DATA_GROUPING_SAMPLE
            MYSQL_REPLICATION_GRP_DATA_GROUPING['MEMBER_ROLE']                       = ['RMR', 5]
            MYSQL_REPLICATION_GRP_DATA_GROUPING['MEMBER_VERSION']                    = ['RMV', 6]
            MYSQL_REPLICATION_GRP_DATA_GROUPING['COUNT_TRANSACTIONS_REMOTE_APPLIED'] = ['RCTRA', 11]
            MYSQL_REPLICATION_GRP_DATA_GROUPING['COUNT_TRANSACTIONS_LOCAL_PROPOSED'] = ['RCTLP', 12]
            MYSQL_REPLICATION_GRP_DATA_GROUPING['COUNT_TRANSACTIONS_LOCAL_ROLLBACK'] = ['RCTLR', 13]

            MYSQL_SHOW_SLAVE_HOSTS                          = 'SHOW REPLICAS'
            MYSQL_SLAVE_HOSTS_GROUPING                      = MYSQL_SLAVE_HOSTS_GROUPING
            MYSQL_MASTER_HOSTS_GROUPING                     = MYSQL_MASTER_HOSTS_GROUPING

            MYSQL_SHOW_BINARY_LOGS                          = 'SHOW BINARY LOGS'
            MYSQL_SHOW_RELAYLOG_EVENTS                      = 'SHOW RELAYLOG EVENTS'


    except Exception as e:
        traceback.print_exc()
