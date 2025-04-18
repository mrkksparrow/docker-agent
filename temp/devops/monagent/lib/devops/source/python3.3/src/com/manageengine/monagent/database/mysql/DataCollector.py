import json
import time
import threading
import concurrent.futures
import traceback , os
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

import six.moves.urllib.request as urlconnection
from six.moves.urllib.parse import urlencode

from com.manageengine.monagent.database import DatabaseLogger,DBConstants
from com.manageengine.monagent.database.mysql import InnodbDataParser,MySQLConstants,ChildDatabaseDataCollector,InsightDataCollector,WindowsDataCollector,PerformanceCounterDataCollector,ReplicationGroupDataCollector,MysqlDataCollector,MySQLUtil



# main class for the mysql database, from where all subtype data collection is called
class MySQLCollector(object):
    def init(self,input_dict):
        try:
            self.instance                        = input_dict['instance']
            self.mid                             = input_dict['mid']
            self.collection_type                 = input_dict['collection_type']
            self.error_msg                       = None
            self.final_data                      = {}

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while initializing mysql collector :: {}'.format(e))
            traceback.print_exc()


    # adding default key/values for collected data, for upload
    def separate_database_data(self,availability,err_msg):
        final_list = []
        try:
            if 'Databases' in self.final_data:
                db_data_len = len(self.final_data['Databases'])
                if db_data_len > 0:
                    start,end = 1,30
                    while end <= db_data_len:
                        single_dict = {}
                        db_dict = {}
                        db_list_to_pop = []
                        iter_var = 1
                        for each in self.final_data['Databases']:
                            if iter_var >= 30:
                                break
                            iter_var += 1
                            db_list_to_pop.append(each)
                            db_dict[each] = self.final_data['Databases'][each]
                        for each in db_list_to_pop:
                            self.final_data['Databases'].pop(each)

                        single_dict['mid'] = self.mid
                        single_dict['instance'] = self.instance
                        single_dict['availability'] = availability
                        single_dict['Databases'] = db_dict
                        if availability == '0':
                            single_dict['err_msg'] = err_msg
                        final_list.append(single_dict)
                        start += 30
                        end += 30
                    if start <= db_data_len:
                        db_list_to_pop = []
                        single_dict = {}
                        db_dict = {}
                        for each in self.final_data['Databases']:
                            db_list_to_pop.append(each)
                            db_dict[each] = self.final_data['Databases'][each]
                        for each in db_list_to_pop:
                            self.final_list['Databases'].pop(each)
                        single_dict['mid'] = self.mid
                        single_dict['instance'] = self.instance
                        single_dict['availability'] = availability
                        single_dict['Databases'] = db_dict
                        if availability == '0':
                            single_dict['err_msg'] = err_msg
                        final_list.append(single_dict)

            if 'Databases' in self.final_data:
                self.final_data.pop('Databases')
            self.final_data['mid'] = self.mid
            self.final_data['instance'] = self.instance
            self.final_data['availability'] = availability
            if availability == '0':
                self.final_data['err_msg'] = err_msg

            final_list.append(self.final_data)

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while separating database data :: {}'.format(e))
            traceback.print_exc()
        finally:
            return final_list


    # default metrics to identify instance data in server
    def get_default_dc_param(self,availability,err_msg):
        try:
            if self.final_data['collection_type'] in ["6", "0", "5", "2", "3"]:
                return
            self.final_data['mid'] = self.mid
            self.final_data['instance'] = self.instance
            self.final_data['availability'] = availability
            if availability == '0':
                self.final_data['err_msg'] = err_msg

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while writing default metrics in result dict :: {}'.format(e))
            traceback.print_exc()


    # method to call separate collection class for respective collections
    def collect_mysql_data(self,dict_param):
        availability = '0'
        try:
            if dict_param:
                availability = '1'

                # basic monitor data collection [MysqlDataCollector]
                if self.collection_type == "0":
                    conn_sucess = False
                    err_msg = None
                    conn_sucess,err_msg = MySQLUtil.check_mysql_connection(dict_param)
                    if conn_sucess:
                        adv_prf_dc_obj = MysqlDataCollector.MysqlMetricsCollector()
                        adv_prf_dc_obj.init(dict_param)
                        is_success,self.final_data,self.error_msg = adv_prf_dc_obj.collect_performance_data()
                        if not is_success:
                            availability = '0'
                            self.final_data['err_msg'] = self.error_msg
                        self.final_data['collection_type'] = "0"
                        self.final_data['mid'] = self.mid
                        self.final_data['instance'] = self.instance
                        self.final_data['availability'] = availability
                        self.final_data['ct'] = MySQLUtil.getTimeInMillis(dict_param['time_diff'])
                    else:
                        self.final_data['collection_type'] = "0"
                        self.final_data['availability'] = '0'
                        self.final_data['reason'] = err_msg
                        self.final_data['instance'] = self.instance
                        self.final_data['mid'] = self.mid
                        self.final_data['ct'] = MySQLUtil.getTimeInMillis(dict_param['time_diff'])


                        # child database monitor data collection [ChildDatabaseDataCollector]
                elif self.collection_type == "6":
                    conn_sucess = False
                    err_msg = None
                    child_keys                      = dict_param['child_keys']
                    previous_data                   = dict_param['previous_data']
                    scheduler                       = dict_param['scheduler']
                    db_per_thread                   = scheduler['db_per_thread']    # 5
                    db_per_zip                      = scheduler['db_per_zip']       # 50

                    divided_db_list                 = []         # list where the divided child_key dicts are appended
                    divided_db_dict                 = {}         # temp dict used to separate the child_key dict
                    thread_obj_dict                 = {}         # thread obj [ collect data for group of databases ] stored in dict and iterated as_completed thread
                    single_thread_result_data       = {}         # each thread result data is stored in dict and added to list [ final_data_list ]
                    current_data_for_next_poll      = {}         # used to store the current data and used in next poll to calculate non volatile data
                    final_data_list                 = []         # final list of result dict sent to main agent

                    # divide the child_keys [contains all database list from configuration serverlet] into separate dict for assigning separate thread
                    conn_sucess,err_msg = MySQLUtil.check_mysql_connection(dict_param)
                    if conn_sucess:
                        db_len_for_one_thread           = 0
                        for each in child_keys:
                            # to avoid mysql generated database [performance issue]
                            #if each in ['information_schema', 'sys', 'mysql', 'performance_schema']:
                            #    continue
                            db_len_for_one_thread = db_len_for_one_thread + 1
                            divided_db_dict[each] = child_keys[each]
                            if db_len_for_one_thread == int(db_per_thread):     # 5 database per thread
                                db_len_for_one_thread = 0
                                divided_db_copy = divided_db_dict.copy()
                                divided_db_list.append(divided_db_copy)
                                divided_db_dict = {}
                        if db_len_for_one_thread > 0:
                            divided_db_list.append(divided_db_dict)

                        # create one thread per divided list of dict of databases
                        with concurrent.futures.ThreadPoolExecutor(max_workers=len(child_keys)+1) as executor:
                            # thread created for list of dict of databases
                            for each_dict in divided_db_list:
                                chld_dbmtr_dc_obj = ChildDatabaseDataCollector.DatabaseSchemaChildData()
                                chld_dbmtr_dc_obj.init(each_dict,previous_data,dict_param)
                                thread_obj = executor.submit(chld_dbmtr_dc_obj.collect_database_schema_metrics)
                                thread_obj_dict[thread_obj] = "db_thread"

                            # each thread produce a result dict stored in ['Databases'] and ['mid'] is added for server side to identify different zips of same monitor instance
                            #single_thread_result_data['Databases'] = {}
                            #single_thread_result_data['mid'] = self.mid
                            db_count_for_zip = 0
                            for each_divided_db_list in concurrent.futures.as_completed(thread_obj_dict):
                                is_success, db_data, current_data_for_np, err_msg = each_divided_db_list.result()
                                if db_data:
                                    db_count_for_zip = db_count_for_zip + len(db_data)    # len(db_data) = total database count in result dict
                                    single_thread_result_data.update(db_data)
                                #single_thread_result_data['ct'] = str(time.time())
                                if current_data_for_np:
                                    current_data_for_next_poll.update(current_data_for_np)
                                #if db_count_for_zip >= int(db_per_zip):
                                #    db_count_for_zip = 0
                                #    final_data_list.append(single_thread_result_data.copy())
                                #    single_thread_result_data['Databases'] = {}
                            #if db_count_for_zip > 0:
                            #    final_data_list.append(single_thread_result_data)

                        # ['Data'] is looped in main agent and stored each dict in one file, zipped and pushed accordingly
                        self.final_data['Data'] = single_thread_result_data
                        self.final_data['current_data'] = current_data_for_next_poll
                        self.final_data['instance'] = self.instance
                        self.final_data['mid'] = self.mid
                        self.final_data['collection_type'] = "6"
                    else:
                        current_time = MySQLUtil.getTimeInMillis(dict_param['time_diff'])
                        self.final_data['Data'] = {}
                        self.final_data['collection_type'] = "6"
                        self.final_data['mid'] = self.mid
                        self.final_data['instance'] = self.instance
                        self.final_data['availability'] = '0'
                        self.final_data['reason'] = str(err_msg)
                        for db_name,db_cid in child_keys.items():
                            single_db_data = {}
                            single_db_data['meta_data'] = {}
                            single_db_data['meta_data']['hname'] = dict_param['host']
                            single_db_data['meta_data']['iname'] = self.instance
                            single_db_data['cid'] = db_cid
                            single_db_data['mid'] = self.mid
                            single_db_data['schema_name'] = db_name
                            single_db_data['availability'] = '0'
                            single_db_data['ct'] = current_time
                            single_db_data['DC ERROR'] = {}
                            single_db_data['DC ERROR']['connection_error'] = {
                                'status':'0',
                                'error_msg': str(err_msg)
                            }
                            self.final_data['Data'][db_name] = {}
                            self.final_data['Data'][db_name] = single_db_data


                # one day once replication on change check task [master/slave/standalone]
                elif self.collection_type == "2":
                    conn_sucess = False
                    err_msg = None
                    conn_sucess,err_msg = MySQLUtil.check_mysql_connection(dict_param)
                    if conn_sucess:
                        rpl_grp_dc_obj = ReplicationGroupDataCollector.ReplicationGroupMemberData()
                        rpl_grp_dc_obj.init(dict_param)
                        is_success,self.final_data,self.error_msg = rpl_grp_dc_obj.collect_replication_status()
                        self.final_data['availability'] = '1'
                        if not is_success:
                            self.final_data['availability'] = '0'
                    else:
                        self.final_data['availability'] = '0'
                        self.final_data['reason'] = err_msg
                    self.final_data['mid'] = self.mid
                    self.final_data['instance'] = self.instance
                    self.final_data['collection_type'] = "2"

                # Performance Startup Data Collection [data for first poll previous data]
                elif self.collection_type == "5":
                    conn_sucess = False
                    err_msg = None
                    conn_sucess,err_msg = MySQLUtil.check_mysql_connection(dict_param)
                    if conn_sucess:
                        prf_stp_dc_obj = PerformanceCounterDataCollector.PerformanceCounterCollector()
                        prf_stp_dc_obj.init(dict_param)
                        is_success,self.final_data,self.error_msg = prf_stp_dc_obj.collect_global_status_and_child_db_data()
                        self.final_data['availability'] = '1'
                        if not is_success:
                            self.final_data['availability'] = '0'
                    else:
                        self.final_data['availability'] = '0'
                        self.final_data['reason'] = err_msg
                    self.final_data['collection_type'] = "5"
                    self.final_data['mid'] = self.mid
                    self.final_data['instance'] = self.instance

                # insight data collection over all mysql [as of now disabled]
                elif self.collection_type == "1":
                    inst_dt_clt_obj = InsightDataCollector.MySQLInsightDataCollector()
                    inst_dt_clt_obj.init(dict_param)
                    is_success,self.final_data,self.error_msg = inst_dt_clt_obj.collect_insight_data()
                    if not is_success:
                        availability = '0'
                    self.final_data['collection_type'] = "1"

                # Windows agent related changes # will add coment later, not used as of now
                elif self.collection_type == "4":
                    win_adc_dc_obj = WindowsDataCollector.WindowsADCMetrics()
                    win_adc_dc_obj.init(dict_param)
                    is_success,self.final_data['data'],self.error_msg = win_adc_dc_obj.collect_windows_adc_metrics()
                    if not is_success:
                        availability = '0'
                    self.final_data['collection_type'] = "4"

                # Database list Discovery to register as child monitor
                elif self.collection_type == "3":
                    conn_sucess = False
                    err_msg = None
                    conn_sucess,err_msg = MySQLUtil.check_mysql_connection(dict_param)
                    if conn_sucess:
                        chl_db_dc_obj = ChildDatabaseDataCollector.DatabaseDiscovery()
                        chl_db_dc_obj.init(dict_param)
                        is_success,self.final_data['list'],self.error_msg = chl_db_dc_obj.collect_database_list()
                        self.final_data['availability'] = '1'
                        if not is_success:
                            self.final_data['availability'] = '0'
                    else:
                        self.final_data['availability'] = '0'
                        self.final_data['reason'] = err_msg
                    self.final_data['collection_type'] = "3"
                    self.final_data['mid'] = self.mid
                    self.final_data['instance'] = self.instance
                    self.final_data['monitor_type'] = DBConstants.MYSQL_MONITOR_TYPE
                    self.final_data['child_type'] = DBConstants.MYSQL_CHILD_TYPE

            self.get_default_dc_param(availability,self.error_msg)

        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting mysql data :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            DatabaseLogger.Logger.debug('FINAL DATA TO BE SENT :: {} :: {} : {}'.format(self.instance, self.final_data['collection_type'], self.final_data))
            return self.final_data
