
"""

Site24x7 MySql Plugin

"""


import traceback,re,json,os,subprocess,time,sys
from com.manageengine.monagent.logger import AgentLogger
from com.manageengine.monagent  import AgentConstants

try:
    import pymysql
    AgentConstants.PYMYSQL_MODULE='1'
except Exception as e:
    AgentLogger.log([AgentLogger.DATABASE, AgentLogger.STDERR], "can't import pymysql")
    traceback.print_exc()

class MySQL(object):
    def __init__(self,connection_obj):
        self.connection = connection_obj

    def get_global_variables(self,global_variables,data):
        try:
            data['max_connections'] = global_variables['max_connections']
            data['open_files_limit'] = global_variables['open_files_limit']
        except Exception as e:
            pass

    def get_global_metrics(self,global_metrics,data):
        try:
            data['uptime'] = global_metrics['Uptime']
            data['open_tables'] = global_metrics['Open_tables']
            data['slow_queries'] = global_metrics['Slow_queries']
            data['threads_connected'] = global_metrics['Threads_connected']
            data['threads_running'] = global_metrics['Threads_running']
            data['max_used_connections'] = global_metrics['Max_used_connections']
            data['buffer_pool_pages_total'] = global_metrics['Innodb_buffer_pool_pages_total']
            data['buffer_pool_pages_free'] = global_metrics['Innodb_buffer_pool_pages_free']
            data['buffer_pool_pages_dirty'] = global_metrics['Innodb_buffer_pool_pages_dirty']
            data['buffer pool pages data'] = global_metrics['Innodb_buffer_pool_pages_data']
            data['qcache_hits'] = global_metrics['Qcache_hits']
            data['qcache_free_memory'] = global_metrics['Qcache_free_memory']
            data['qcache_not_cached'] = global_metrics['Qcache_not_cached']
            data['qcache_in_cache'] = global_metrics['Qcache_queries_in_cache']
            writes = (global_metrics['Com_insert'] +global_metrics['Com_replace'] +global_metrics['Com_update'] +global_metrics['Com_delete'])
            data['writes'] = writes
            reads = global_metrics['Com_select'] + data['qcache_hits']
            data['reads'] = reads
            try:
                data['rw ratio'] = reads/writes
            except ZeroDivisionError:
                data['rw ratio'] = 0
            transactions = (global_metrics['Com_commit'] +global_metrics['Com_rollback'])
            data['transactions'] = transactions
            data['aborted_clients'] = global_metrics['Aborted_clients']
            data['aborted_connects'] = global_metrics['Aborted_connects']
            data['created_tmp_tables'] = global_metrics['Created_tmp_tables']
            data['created_tmp_tables_on_disk'] = global_metrics['Created_tmp_disk_tables']
            data['select_full_join'] = global_metrics['Select_full_join']
            result = global_metrics['Slave_running']
            if result == 'OFF':
                result = 0
            else:
                result = 1
            data['slave_running'] = result
            data['open_files'] = global_metrics['Open_files']
        except Exception as e:
            print(e)

    def execute_query(self,query):
        cursor = None
        try:
            cursor = self.connection.cursor()
            cursor.execute(query)
            metric = {}
            for entry in cursor:
                try:
                    metric[entry[0]] = float(entry[1])
                except ValueError as e:
                    metric[entry[0]] = entry[1]
            return metric
        except pymysql.OperationalError as message:
            pass
        finally:
            if cursor:cursor.close()

    def metric_collector(self):
        data = {}
        try:
            global_metrics = self.execute_query('SHOW GLOBAL STATUS')
            global_variables = self.execute_query('SHOW VARIABLES')
            self.get_global_metrics(global_metrics,data)
            self.get_global_variables(global_variables,data)
        except Exception as e:
            data['status']=0
            data['msg']=e
        finally:
            if self.connection:self.connection.close()
        return data

def get_sock_path():
        _output, _status, _proc = None, False, None
        try:
            _proc = subprocess.Popen("netstat -ln | awk '/mysql(.*)?\.sock/ { print $9 }'" ,shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(0.5)
            if not _proc.poll() is None:
                _status = True
                _output, error = _proc.communicate()
                _output = _output.strip("\n")
        except Exception as e:
            if type(_proc) is subprocess.Popen:
                _proc.kill()
                _proc.poll()
        finally:
            return _status, _output

def get_db_connection(configurations):
        import pymysql
        connection = None
        error = None
        try:
            if 'use_mysql_conf' in configurations and configurations['use_mysql_conf']!='False':
                connection = pymysql.connect(default_read_file='/etc/mysql/my.cnf')
            else:
                connection = pymysql.connect(host=configurations.get('hostname'), user=configurations.get('username'), passwd=configurations.get('password'), port=int(configurations.get('port')))
        except Exception as e:
            error = str(e)
        return connection , error


def main(dict_params):
    result = {}
    configurations = {'hostname': dict_params['hostname'], 'port': dict_params['port'], 'username': dict_params['username'], \
                      'password': dict_params['password'],'use_mysql_conf':dict_params['use_mysql_conf']}    
    connection_obj , error = get_db_connection(configurations)
    if not connection_obj:
        result['status']=0
        result['msg']=error
    else:
        mysql_plugins = MySQL(connection_obj)
        result = mysql_plugins.metric_collector()
    result['plugin_version'] = dict_params['plugin_version']
    result['hearbeat_required'] = dict_params['heartbeat']
    return result

if __name__ == "__main__" or __name__.endswith('util.AgentUtil') or __name__.endswith('test_exec'):
    result = {}
    plugin_version="1"
    heartbeat="true"
    USE_MYSQL_CONF_FILE=False
    configurations = {'hostname': 'sriram-', 'port': 3306, 'username': 'test', 'password': '' , 'version':plugin_version,'heartbeat':heartbeat,'use_mysql_cnf':USE_MYSQL_CONF_FILE}
    connection_obj,error = get_db_connection(configurations)
    if not connection_obj:
        result['status']=0
        result['msg']='Connection Error'
    else:
        mysql_plugins = MySQL(connection_obj)
        result = mysql_plugins.metric_collector()
    s247ScriptOutput = result