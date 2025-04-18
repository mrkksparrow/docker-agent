import traceback
from com.manageengine.monagent.database import DatabaseLogger,DBConstants
from com.manageengine.monagent.database.XMLExecutor import Executor

try:
    import pymysql
except Exception as e:
    traceback.print_exc()

try:
    import psycopg2
except:
    pass
try:
    import oracledb
except:
    pass


def _are_values_numeric(array):
    return all(v.isdigit() for v in array)

# one and only point to get connection of mysql database for NDBCluster
def getConnection(dict_info,connection_type,database=None,connection_attempts=1):
    try:
        if connection_type ==  DBConstants.MYSQL_DATABASE:
            ssl_dict = {}
            if 'ssl' in dict_info and dict_info['ssl'] == "true":
                if 'ssl-ca' in dict_info and dict_info['ssl-ca']!="":
                    ssl_dict['ca'] = dict_info['ssl-ca']
                if 'ssl-cert' in dict_info and dict_info['ssl-cert']!="" and 'ssl-key' in dict_info and dict_info['ssl-key']!="":
                    ssl_dict['cert'] = dict_info['ssl-cert']
                    ssl_dict['key'] = dict_info['ssl-key']
            if ssl_dict:
                connection = pymysql.connect(host=dict_info['host'], user=dict_info['user'],password=dict_info['password'], port=int(dict_info['port']),ssl={'ssl':ssl_dict},connect_timeout=30, charset="utf8")
            else:
                connection = pymysql.connect(host=dict_info['host'], user=dict_info['user'],password=dict_info['password'], port=int(dict_info['port']),connect_timeout=30, charset="utf8")
            return True, connection
        elif connection_type == DBConstants.POSTGRES_DATABASE:
            db_info = "host='{}' port={} dbname='{}' user='{}' password='{}' sslmode='{}'".format(dict_info['host'], dict_info['port'], database or dict_info['default_database'], dict_info['user'], dict_info['password'], dict_info.get('ssl-mode') or "prefer")
            if 'ssl' in dict_info and dict_info['ssl'] == "true":
                if 'ssl-ca' in dict_info and dict_info['ssl-ca']!="":
                    db_info+= " sslrootcert='"+dict_info['ssl-ca']+"'"
                if 'ssl-cert' in dict_info and dict_info['ssl-cert']!="" and 'ssl-key' in dict_info and dict_info['ssl-key']!="":
                    db_info+= " sslcert='"+dict_info['ssl-cert']+"' sslkey='"+dict_info['ssl-key']+"'"
            connection = psycopg2.connect(db_info)
            return True,connection
        elif connection_type == DBConstants.ORACLE_DATABASE:
            if database:
                dsn = oracledb.makedsn(dict_info.get("host"), int(dict_info.get("port")), service_name=database)
                connection=oracledb.connect(dsn=dsn,user=dict_info.get("user"),password=dict_info.get("password"))
                return True,connection
            else:
                DatabaseLogger.Logger.log("connection_type - {} :: service_name not available to make connection".format(connection_type))
                return False, {"ERROR":{"err_msg":"service_name not available to make connection"}}
        else:
            DatabaseLogger.Logger.log("Received database as None while trying to make connection :: connection_type - {}".format(connection_type))
            return False, {"ERROR":"Unknown connection_type"}

    except Exception as e:
        DatabaseLogger.Logger.log("Connection issue -> Exception :: connection_attempt - {} :: getConnection -> {} ".format(connection_attempts,e))
        # if connection_attempts<3:
        #    return getConnection(dict_params,connection_type,database,connection_attempts+1)
        traceback.print_exc()
        err={}
        try:
            err={"err_code":e.args[0],"err_msg":e.args[1],"connection_attempts":connection_attempts,"availability":"0"}
        except:
            err={"err_msg":str(e),"connection_attempts":connection_attempts,"availability":"0"}
        return False, {"ERROR":err,"REASON" : err.get("err_msg")}

# Used by executor to execute multiple queries one by one based on multiple tags and returns output as dictionary.
def executeMultiTags(xmlExecutorObj, tags, dict_params, version, disabled_queries, connection_type,database=None,extended_connection=None,previousDC = {}):
    try:
        if extended_connection==None:
            connectionStatus,connection = getConnection(dict_params,connection_type,database)
        else:
            connectionStatus,connection = True,extended_connection
            
        if connectionStatus:
            data, raw_data = {}, {}
            for tag in tags:
                tag_raw_data,tmp = xmlExecutorObj.executeWithTag(dict_params.get("instance_name"),tag, connection,  version , disabled_queries, previousDC)
                if tmp is None:
                    DatabaseLogger.Logger.log("executeMultiTags :: connection_type - {} :: no data for tag - {}".format(connection_type,tag))
                    traceback.print_exc()
                    continue
                data.update(tmp or {})
                raw_data.update(tag_raw_data or {})
            if extended_connection==None:
                connection.close()
            return raw_data,data
        else:
            dict_copy = dict_params.copy()
            ignore_keys = ['password','xmlString','cached_data']
            for ignorable_key in ignore_keys:
                if ignorable_key in dict_copy:
                    dict_copy.pop(ignorable_key)
            DatabaseLogger.Logger.log(" Exception :: executeMultiTags :: connection_type - {} :: connection issue - {} :: tags - {} :: dict_params - {}".format(connection_type,connection.get("ERROR"), tags, dict_copy))
            traceback.print_exc()
            return None,connection   # Error Msg
    except Exception as e:
        DatabaseLogger.Logger.log(" Exception :: executeMultiTags :: connection_type - {} :: error - {} :: tags - {} :: version - {} :: disabled_queries - {}".format(connection_type, e, tags, version, disabled_queries))
        traceback.print_exc()

# Renames the child key, so that children are brought to L1 of dict
# Example {"memory":{"redoSize":100}} => {"memoryredoSize":100}
def ConvertL2NestingToL1(data):
    result = {}
    try:
        if data == None:
            return {}
        for node in data:
            if result.get(node) == None:
                result[node] = {}
            for __type in data[node]:
                for key in data[node][__type]:
                    result[node][__type + key] = data[node][__type][key]
        return result
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: ConvertL2NestingToL1 :: Error - {} ".format(e))
        traceback.print_exc()
        return {}

def getXMLExecutorObj(monitor_type,xml_string):
    try:
        if DBConstants.XML_EXECUTOR_OBJECTS.get(monitor_type) == None:
            DBConstants.XML_EXECUTOR_OBJECTS[monitor_type] = Executor(xml_string)
        return DBConstants.XML_EXECUTOR_OBJECTS.get(monitor_type)
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: getXMLExecutor :: Error - {} ".format(e))
        traceback.print_exc()
    
def clearXMLExecutorObj(monitor_type,clear_all=False):
    try:
        if monitor_type in DBConstants.XML_EXECUTOR_OBJECTS:
            DBConstants.XML_EXECUTOR_OBJECTS.pop(monitor_type)
        if clear_all:
            DBConstants.XML_EXECUTOR_OBJECTS={}
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: getXMLExecutor :: Error - {} ".format(e))
        traceback.print_exc()


def getOutputFromQuery(connection, query):
    try:
        with connection.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()
    except Exception as e:
        DatabaseLogger.Logger.log(" Exception :: getOutputFromQuery :: Query -> {} Exception -> {}".format(query, e))
        traceback.print_exc()

def MapID(data,Ids,key_name="mid",unique_key="dbn"):
    try:
        if type(data) is list:
            for obj in data:
                if obj.get(unique_key) not in ['',None] and obj[unique_key] in Ids:
                    obj[key_name] = Ids[obj[unique_key]]
        elif type(data) is dict:
            for key,val in data.items():
                if key in Ids:
                    val[key_name] = Ids[key]
    except Exception as e:
        DatabaseLogger.Logger.log(" Exception :: MapID :: Exception -> {}".format(e))
    return data
