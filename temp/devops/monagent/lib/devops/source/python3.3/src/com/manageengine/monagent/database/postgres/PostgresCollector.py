from com.manageengine.monagent.database import DatabaseLogger,DBUtil,DBConstants
from com.manageengine.monagent.database.mysql import MySQLUtil
from com.manageengine.monagent.database.postgres.ChildDatabaseDataCollector import ChildDatabaseDC
import json,traceback,concurrent.futures,copy

def add_child_ID(dict_data,child_keys):
    try:
        if dict_data:
            for dbname,entry in dict_data.items():
                if entry:
                    entry['cid'] = child_keys.get(dbname) or '' # cid added to appropriate database.

                    # cache_hit_ratio and disk_hit_ratio is calculated here.
                    if 'bkh' in entry and "bkr" in entry:
                        entry["chr"]   =   round(entry.get('bkh') * 100 / (entry.get('bkh') + entry.get('bkr') or 1),2)
                        # entry["dhr"]   =   round(100-entry['chr'],2)

                    if entry.get('prf') and entry.get("prr"):
                        entry["rfbr"]  =   round(entry.get('prf') * 100 / entry.get('prr'),2)

                    for removable_metric in ['bkh','bkr','prf','prr','datid']:
                        if entry.get(removable_metric)!=None:
                            entry.pop(removable_metric)
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: add_child_ID - {} :: traceback - {}".format(e,traceback.print_exc()))
    return dict_data

# overall instance metrics is calculated by adding all database metrics.
def overall_instance_data(list_of_db_data):
    result={}
    try:
        if list_of_db_data==None:
            DatabaseLogger.Logger.log("In overall_instance_data received list_of_db_data as - None. (This occurs while agent restarts) ")
            return {}
        metrics_to_be_summed = {"bkh":"bkh","bkr":"bkr","rf":"rf","rr":"rr","prf":"prf","prr":"prr","cft":"oc","brt":"obrt","bwt":"obwt","ddl":"odl",
                                "tmpb":"otb","tmpu":"otf","rupd":"orut","rins":"ori","rdel":"ord","tc":"otc","tr":"otr",
                                "actt":"oat","idtt":"oit"}
        for metric in metrics_to_be_summed:
            tmp,present=0,False
            for dbname,db_data in list_of_db_data.items():
                if db_data and metric in db_data and db_data[metric]>=0:
                    tmp+=db_data[metric]
                    present=True
            if present:
                result[metrics_to_be_summed[metric]]=tmp

        tmp,present=0,False
        for dbname,db_data in list_of_db_data.items():
            if db_data and "nbe" in db_data and db_data["nbe"]>=0:
                tmp+=db_data["nbe"]
                present=True
        if present:
            result["onb"]=tmp

        if 'bkh' in result and "bkr" in result:
            result["ochr"]   =   round(result.get('bkh') * 100 / (result.get('bkh') + result.get('bkr') or 1),2)

        if result.get('prf') and result.get("prr"):
            result["orfr"]  =   round(result.get('prf') * 100 / result.get('prr'),2)
            # prf - 'pure_tup_fetched' and prr - 'pure_tup_returned'. These are not subtracted with previous DC.
            # These two metrics is used to calculate Rows Fecthed / Returned percentage(from the point of installation of postgres database).

        for removable_metric in ['bkh','bkr','prf','prr']:
            if result.get(removable_metric)!=None:
                result.pop(removable_metric)
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: overall_instance_data - {} :: traceback - {}".format(e,traceback.print_exc()))
    return result

def format_basic_perf(cached_data,data,instance_info):
    result={}
    try:
        instance_dbs={}
        poll_interval = int(instance_info.get('perf_poll_interval') or 300) 

        # Holds the shortname for metrics that are to be subtracted from previous DC
        metrics_to_compute = {
            "DBMAIN"    : ["rf","rr","cft","brt","bwt","ddl","tmpb","tmpu","rupd","rins","rdel","tc","tr","actt","idtt"],
            "STBG"      : ["cpr","cpt","bcp","bcl","bbd"],
            "WAL"       : ["wbt"],
            "ARCH"      : ["ac","fc"]
        }

        for tag in ["STBG","WAL","ARCH"]:
            result.update(  compute_metrics_using_subtraction(cached_data.get(tag),data.get(tag)  or {},metrics_to_compute[tag],poll_interval) or {} )

        cached_DBMAIN,  fetched_DBMAIN  =   cached_data.get("DBMAIN") or {},   data.get("DBMAIN") or {}

        for db in fetched_DBMAIN:
            instance_dbs[db] = compute_metrics_using_subtraction(cached_DBMAIN.get(db),fetched_DBMAIN.get(db),metrics_to_compute["DBMAIN"],poll_interval)
        
        result.update(overall_instance_data(instance_dbs))

        result["databases"]     =   add_child_ID( instance_dbs, instance_info.get('db_child_keys') or {}) # some keys are removed inside add_child_ID. so overall_instance_data should be executed before add_child_ID

        for tag_name in ['CONNCNT','STLC','IMPPERF','AVAC','REPD','WALF']:
            result.update(   data.get(tag_name)    or {}   )
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: format_basic_perf - {} :: traceback - {}".format(e,traceback.print_exc()))
    return result

# Helper function used for subtracting cached data by newly fetched data.
# The data subtracted based on stats_reset time. If stats table got reset, then the newly fetched data should not be subtracted by cached data.
# For every database entry there is different stats_reset time. 
def compute_metrics_using_subtraction(oldData,newData,metrics_to_compute,poll_interval):
    try:
        result  = None
        if oldData and newData:
            result = copy.deepcopy(newData)
            if 'stats_reset' in newData and newData.get("stats_reset")>poll_interval:
                for metric in metrics_to_compute:
                    if metric in newData and metric in oldData and newData[metric]>=oldData[metric]:
                        result[metric] = newData[metric] - oldData[metric]
            if 'stats_reset' in result:
                result.pop('stats_reset')
        return result
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: computeMetricsUsingSubtraction - {} :: traceback - {}".format(e,traceback.print_exc()))

def format_basic_config(data):
    result = {}
    try:
        result=data.get('CONFIG') or {}
        result.update(data.get('PRCON') or {})
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: format_basic_config - {} :: traceback - {}".format(e,traceback.print_exc()))
    return result

def collect_basic_perf(args):
    data,result=None,{}
    try:
        instance_info=args[0]
        cached_data = instance_info.get("cached_data")
        tags = ["pg_server"]
        if instance_info['collect_conf']:
            tags.append("pg_server_config")
        xmlExecutorObj  =   DBUtil.getXMLExecutorObj(DBConstants.POSTGRES_DATABASE,instance_info.get('xmlString'))
        raw_data, data  =   DBUtil.executeMultiTags(xmlExecutorObj, tags, instance_info, instance_info.get("Version"), instance_info.get("disabled_queries") or {}, DBConstants.POSTGRES_DATABASE)

        result.update( format_basic_perf(cached_data,data,instance_info) or {} )
        if instance_info['collect_conf']:
            result.update( format_basic_config(data) or {} )
        
        if data.get("REASON"):
            if data.get("ERROR"):
                result["DC ERROR"] = data.pop("ERROR")
            result["reason"] = data.get("REASON") or DBConstants.CONNECTION_FAILED_ERR_MSG
        else:
            result["availability"]  =   "1"
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: collect_basic_perf - {} :: traceback - {}".format(e,traceback.print_exc()))
        result={"availability":"0"}
    return (data,result)

def discover_database(instance_info):
    result={"availability" : "0","mid":instance_info.get("mid")}
    try:
        connectionStatus,connection = DBUtil.getConnection(instance_info,DBConstants.POSTGRES_DATABASE)
        if connectionStatus:
            data = DBUtil.getOutputFromQuery(connection,DBConstants.POSTGRES_DATABASE_DISCOVERY_QUERY)
            tmp = []
            for row in data:
                tmp.append(row[0])
            result["list"] = tmp
            result['availability']  = "1"
            result['monitor_type']  = DBConstants.POSTGRES_MONITOR_TYPE
            result['child_type']    = DBConstants.POSTGRES_CHILD_TYPE
            result['instance_name'] = instance_info.get("instance_name") 
        else:
            DatabaseLogger.Logger.log(" Connection failed for discover_database - {} :: Database Type - {}".format(result,DBConstants.POSTGRES_DATABASE))
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: discover_database - {} :: traceback - {}".format(e,traceback.print_exc()))
    return result

def collect_basic_data(instance_info):
    try:
        cache_data,result ={}, {}
        instance_info["cached_data"]= json.loads(instance_info.get("cached_data") or "{}")
        db_child_keys = instance_info.get("db_child_keys") or {}
        db_per_thread, db_per_zip = int(instance_info.get("db_per_thread") or 5), int(instance_info.get("db_per_zip") or 50)

        thread_obj_dict                 = {}
        threads_final_data              = {}
        divided_child_dbs               = []
        temp_dict                       = {}
        thread_child_cache_data         = {}

        for index,db_name in enumerate(db_child_keys):
            temp_dict[db_name]=db_child_keys[db_name]
            if (index+1) % db_per_thread == 0:
                divided_child_dbs.append(temp_dict)
                temp_dict = {}
        if temp_dict:
            divided_child_dbs.append(temp_dict)

        cache_data,result = collect_basic_perf([instance_info])
        mx_workers= int(len(db_child_keys)/db_per_thread)+1
        xmlExecutorObj  =   DBUtil.getXMLExecutorObj(DBConstants.POSTGRES_DATABASE,instance_info.get('xmlString'))

        with concurrent.futures.ThreadPoolExecutor(max_workers=mx_workers) as executor:
            # perf_thread_obj = executor.submit(collect_basic_perf,instance_info)

            for dbs in divided_child_dbs:
                child_db_obj = ChildDatabaseDC(instance_info,xmlExecutorObj,dbs)
                thread_obj = executor.submit(child_db_obj.collect_database_data)
                thread_obj_dict[thread_obj] = "postgres_db_thread"
            
            done,notDone = concurrent.futures.wait(thread_obj_dict, return_when=concurrent.futures.ALL_COMPLETED)
            # cache_data,result = perf_thread_obj.result()
            db_count_for_zip = 0
            for each_divided_db_list in done:
                child_cache_data,db_data = each_divided_db_list.result()
                if db_data:
                    db_count_for_zip = db_count_for_zip + len(db_data)    # len(db_data) = total database count in result dict
                    threads_final_data.update(db_data)
                thread_child_cache_data.update(child_cache_data)
            
        cache_data['child_data'] = thread_child_cache_data

        ct = MySQLUtil.getTimeInMillis(instance_info.get('time_diff') or 0)
        result["ct"] = ct
        for db in result["databases"]:
            if result["databases"][db]:
                result['databases'][db].update(threads_final_data.get(db) or {})
                result['databases'][db]["ct"] = ct
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: collect_basic_data - {} :: traceback - {}".format(e,traceback.print_exc()))
    return cache_data,result

def collect_postgres_data(instance_info):
    result = {}
    try:
        collection_type = instance_info.get("collection_type")
        if collection_type == "0":
            result  =   collect_basic_data(instance_info)
        elif collection_type == "1":
            result  =   discover_database(instance_info)
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: collect_postgres_data - {} :: traceback - {}".format(e,traceback.print_exc()))
    return result