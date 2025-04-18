import json
import time
import traceback , os
try:
    import configparser
except Exception as e:
    import ConfigParser as configparser

import six.moves.urllib.request as urlconnection
from six.moves.urllib.parse import urlencode


from com.manageengine.monagent.database import DatabaseLogger,DBUtil
from com.manageengine.monagent.database.mysql import MySQLConstants,MySQLUtil

class ReplicationGroupMemberData(object):
    def init(self, input_param):
        try:
            self.mysql_util_obj = MySQLUtil.MySQLConnector()
            self.mysql_util_obj.init(input_param)
            self.instance                    = input_param['instance']
            self.mid                         = input_param['mid']
            self.replication_child_keys      = input_param['replication_child_keys']
            self.master_status = None
            self.slave_status = None
            self.instance_type = None
            self.conf_key = input_param['conf_key']
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while initialising Replication Group Member Data Collector Class :: {} : {}'.format(self.instance,e))
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
        replication_change_data = {}
        try:
            if 'instance_type' in self.conf_key:
                replication_change_data['previous_instance_type'] = self.conf_key['instance_type']
            else:
                replication_change_data['previous_instance_type'] = self.instance_type
            replication_change_data['current_instance_type'] = self.instance_type
            if self.instance_type == 'MASTER':
                replication_change_data['slave_data'] = self.collect_slave_hosts_data()
                replication_change_data['master_data'] = self.collect_master_hosts_data()
            elif self.instance_type == 'SLAVE':
                replication_change_data['master_data'] = self.collect_master_hosts_data()
        except Exception as e:
            DatabaseLogger.Logger.log('Exception while collecting replication onchange status data: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return replication_change_data

    def collect_replication_status(self):
        result_data = {}
        is_success = True
        err_msg = None
        try:
            is_success, err_msg = self.mysql_util_obj.get_db_connection()
            if is_success:
                is_success, version, err_msg = self.mysql_util_obj.get_mysql_version()
                MySQLConstants.set_query_for_data_collection(version)

                if is_success:
                    is_success,output_list,err_msg = self.mysql_util_obj.execute_mysql_query(MySQLConstants.MYSQL_COMMON_METRICS_COLLECTION_QUERY)
                    if is_success:
                        for variable in output_list:
                            if variable[0] in MySQLConstants.MYSQL_COMMON_METRICS_COLLECTION_GROUPING.keys():
                                result_data['uuid'] = str(variable[1])

                        is_success ,self.master_status, self.slave_status, err_msg = self.mysql_util_obj.collect_master_slave_status()
                        if is_success:
                            replication_enabled,self.instance_type = self.mysql_util_obj.decide_instance_type(self.master_status,self.slave_status)

                            # if mysql is or above 5.7, replication group members data can be collected [TABLE - performance_schema.replication_group_members/performance_schema.replication_group_member_stats]
                            # 5 extra metrics available from 8.0.0 [MEMBER_ROLE,MEMBER_VERSION,COUNT_TRANSACTIONS_REMOTE_APPLIED,COUNT_TRANSACTIONS_LOCAL_PROPOSED,COUNT_TRANSACTIONS_LOCAL_ROLLBACK]
                            if 'mariadb' not in version and version >= '5.7' and replication_enabled:
                                is_success, repl_member_list, err_msg = self.collect_replication_grp_member_stats()
                                if is_success:
                                    result_data['replication'] = DBUtil.MapID(repl_member_list,self.replication_child_keys,"mid","RMI")
                                else:
                                    result_data['replication'] = [{'status': '0', 'err_msg': err_msg}]
                        else:
                            result_data['status'] = '0'
                            result_data['err_msg'] = err_msg
                    else:
                        result_data['status'] = '0'
                        result_data['err_msg'] = err_msg
                else:
                    result_data['status'] = '0'
                    result_data['err_msg'] = err_msg

                result_data.update(self.collect_replication_onchange_data())

                self.mysql_util_obj.close_db_connection()
        except Exception as e:
            is_success = False
            err_msg = str(e)
            DatabaseLogger.Logger.log('Exception while collecting database list :: {} : {}'.format(self.instance,e))
            traceback.print_exc()
        finally:
            return is_success, result_data, err_msg