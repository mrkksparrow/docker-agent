import json
import time
import sys
import re
import traceback , os
from collections import defaultdict
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

import six.moves.urllib.request as urlconnection
from six.moves.urllib.parse import urlencode
long = int

from com.manageengine.monagent.database import DatabaseLogger,DBUtil
from com.manageengine.monagent.database.mysql import MySQLConstants

def innodb_data_parser(cursor):
    results = {}
    try:
        cursor.execute(MySQLConstants.MYSQL_INNODB_DATA)
        innodb_status = cursor.fetchone()
        innodb_status_text = innodb_status[2]

        results = defaultdict(int)

        txn_seen = False
        prev_line = ''
        for line in innodb_status_text.splitlines():
            line = line.strip()
            row = re.split(" +", line)
            row = [item.strip(',') for item in row]
            row = [item.strip(';') for item in row]
            row = [item.strip('[') for item in row]
            row = [item.strip(']') for item in row]

            if line.find('Mutex spin waits') == 0: # semaphores
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_mutex_spin_waits'][0]] = long(row[3])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_mutex_spin_rounds'][0]] = long(row[5])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_mutex_os_waits'][0]] = long(row[8])
            elif line.find('RW-shared spins') == 0 and line.find(';') > 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_s_lock_spin_waits'][0]] = long(row[2])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_x_lock_spin_waits'][0]] = long(row[8])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_s_lock_os_waits'][0]] = long(row[5])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_x_lock_os_waits'][0]] = long(row[11])
            elif line.find('RW-shared spins') == 0 and line.find('; RW-excl spins') == -1:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_s_lock_spin_waits'][0]] = long(row[2])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_s_lock_spin_rounds'][0]] = long(row[4])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_s_lock_os_waits'][0]] = long(row[7])
            elif line.find('RW-excl spins') == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_x_lock_spin_waits'][0]] = long(row[2])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_x_lock_spin_rounds'][0]] = long(row[4])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_x_lock_os_waits'][0]] = long(row[7])
            elif line.find('seconds the semaphore:') > 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_semaphore_waits'][0]] += 1
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_semaphore_wait_time'][0]] += long(float(row[9])) * 1000

            elif line.find('Trx id counter') == 0: # transactions
                txn_seen = True
            elif line.find('History list length') == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_history_list_length'][0]] = long(row[3])
            elif txn_seen and line.find('---TRANSACTION') == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_current_transactions'][0]] += 1
                if line.find('ACTIVE') > 0:
                    results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_active_transactions'][0]] += 1
            elif line.find('read views open inside InnoDB') > 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_read_views'][0]] = long(row[0])
            elif line.find('mysql tables in use') == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_tables_in_use'][0]] += long(row[4])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_locked_tables'][0]] += long(row[6])
            elif txn_seen and line.find('lock struct(s)') > 0:
                if line.find('LOCK WAIT') == 0:
                    results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_lock_structs'][0]] += long(row[2])
                    results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_locked_transactions'][0]] += 1
                elif line.find('ROLLING BACK') == 0:
                    results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_lock_structs'][0]] += long(row[2])
                else:
                    results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_lock_structs'][0]] += long(row[0])

            elif line.find(' OS file reads, ') > 0:  # file i/o
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_os_file_reads'][0]] = long(row[0])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_os_file_writes'][0]] = long(row[4])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_os_file_fsyncs'][0]] = long(row[8])
            elif line.find('Pending normal aio reads:') == 0:
                try:
                    if len(row) == 8:
                        results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_normal_aio_reads'][0]] = long(row[4])
                        results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_normal_aio_writes'][0]] = long(row[7])
                    elif len(row) == 14:
                        results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_normal_aio_reads'][0]] = long(row[4])
                        results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_normal_aio_writes'][0]] = long(row[10])
                    elif len(row) == 16:
                        if DBUtil._are_values_numeric(row[4:8]) and DBUtil._are_values_numeric(row[11:15]):
                            results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_normal_aio_reads'][0]] = (
                                    long(row[4]) + long(row[5]) + long(row[6]) + long(row[7])
                            )
                            results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_normal_aio_writes'][0]] = (
                                    long(row[11]) + long(row[12]) + long(row[13]) + long(row[14])
                            )

                        elif DBUtil._are_values_numeric(row[4:9]) and DBUtil._are_values_numeric(row[12:15]):
                            results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_normal_aio_reads'][0]] = long(row[4])
                            results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_normal_aio_writes'][0]] = long(row[12])
                        else:
                            DatabaseLogger.Logger.log('mysql performance not registered :: {}'.format(e))
                    elif len(row) == 18:
                        results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_normal_aio_reads'][0]] = long(row[4])
                        results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_normal_aio_writes'][0]] = long(row[12])
                    elif len(row) == 22:
                        results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_normal_aio_reads'][0]] = long(row[4])
                        results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_normal_aio_writes'][0]] = long(row[16])
                except ValueError as e:
                    DatabaseLogger.Logger.log('mysql oerformance not registered :: {}'.format(e))
            elif line.find('ibuf aio reads') == 0:
                if len(row) == 10:
                    results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_ibuf_aio_reads'][0]] = long(row[3])
                    results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_aio_log_ios'][0]] = long(row[6])
                    results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_aio_sync_ios'][0]] = long(row[9])
                elif len(row) == 7:
                    results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_ibuf_aio_reads'][0]] = 0
                    results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_aio_log_ios'][0]] = 0
                    results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_aio_sync_ios'][0]] = 0
            elif line.find('Pending flushes (fsync)') == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_log_flushes'][0]] = long(row[4])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_buffer_pool_flushes'][0]] = long(row[7])

            elif line.find('Ibuf for space 0: size ') == 0: # INSERT BUFFER AND ADAPTIVE HASH INDEX
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_size'][0]] = long(row[5])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_free_list'][0]] = long(row[9])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_segment_size'][0]] = long(row[12])
            elif line.find('Ibuf: size ') == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_size'][0]] = long(row[2])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_free_list'][0]] = long(row[6])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_segment_size'][0]] = long(row[9])

                if line.find('merges') > -1:
                    results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_merges'][0]] = long(row[10])
            elif line.find(', delete mark ') > 0 and prev_line.find('merged operations:') == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_merged_inserts'][0]] = long(row[1])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_merged_delete_marks'][0]] = long(row[4])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_merged_deletes'][0]] = long(row[6])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_merged'][0]] = (
                        results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_merged_inserts'][0]]
                        + results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_merged_delete_marks'][0]]
                        + results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_merged_deletes'][0]]
                )
            elif line.find(' merged recs, ') > 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_merged_inserts'][0]] = long(row[0])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_merged'][0]] = long(row[2])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_ibuf_merges'][0]] = long(row[5])
            elif line.find('Hash table size ') == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_hash_index_cells_total'][0]] = long(row[3])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_hash_index_cells_used'][0]] = long(row[6]) if line.find('used cells') > 0 else 0

            elif line.find(" pending log writes, ") > 0: # log
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_log_writes'][0]] = long(row[0])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_pending_checkpoint_writes'][0]] = long(row[4])
            elif line.find("Log sequence number") == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_lsn_current'][0]] = long(row[3])
            elif line.find("Log flushed up to") == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_lsn_flushed'][0]] = long(row[4])
            elif line.find("Last checkpoint at") == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_lsn_last_checkpoint'][0]] = long(row[3])

            elif line.find("Total memory allocated") == 0 and line.find("in additional pool allocated") > 0: # buffer pool and memoru
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_mem_total'][0]] = long(row[3])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_mem_additional_pool'][0]] = long(row[8])
            elif line.find('Adaptive hash index ') == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_mem_adaptive_hash'][0]] = long(row[3])
            elif line.find('Page hash           ') == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_mem_page_hash'][0]] = long(row[2])
            elif line.find('Dictionary cache    ') == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_mem_dictionary'][0]] = long(row[2])
            elif line.find('File system         ') == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_mem_file_system'][0]] = long(row[2])
            elif line.find('Lock system         ') == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_mem_lock_system'][0]] = long(row[2])
            elif line.find('Recovery system     ') == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_mem_recovery_system'][0]] = long(row[2])
            elif line.find('Threads             ') == 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_mem_thread_hash'][0]] = long(row[1])
            elif line.find("Pages read ahead") == 0:
                pass
            elif line.find(" queries inside InnoDB, ") > 0:
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_queries_inside'][0]] = long(row[0])
                results[MySQLConstants.MYSQL_INNODB_ENGINE_GROUPING['Innodb_queries_queued'][0]] = long(row[4])

            prev_line = line

    except Exception as e:
        DatabaseLogger.Logger.log('Exception while collecting innodb metrics :: {}'.format(e))
        traceback.print_exc()
    finally:
        return dict(results)

def check_innodb_engine(cursor):
    result_dict = {}
    is_innodb_enabled = False
    try:
        cursor.execute(MySQLConstants.MYSQL_ENGINE_STATUS)
        for engine in cursor:
            DatabaseLogger.Logger.log('ENGINE - {} :: SUPPORT - {} :: TRANSACTIONS - {} :: SAVEPOINTS - {}'.format(engine[0],engine[1],engine[2],engine[3]))
            if engine[0].lower() == 'innodb':
                if engine[1].lower() != 'no' or engine[1].lower() != 'disabled':
                    is_innodb_enabled = True
        if is_innodb_enabled:
            result_dict = innodb_data_parser(cursor)
            #DatabaseLogger.Logger.log('------ {} ------'.format(result_dict))
        else:
            DatabaseLogger.Logger.log('------ InnoDB Engine Support Disabled, hence skipping data collection ------')
    except Exception as e:
        pass
    finally:
        return result_dict
