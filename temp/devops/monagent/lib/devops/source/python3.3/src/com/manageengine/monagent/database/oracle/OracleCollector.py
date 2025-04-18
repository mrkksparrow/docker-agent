from com.manageengine.monagent.database import DatabaseLogger, DBUtil, DBConstants
from com.manageengine.monagent.database.oracle.ChildDatabaseDataCollector import ChildDatabaseDC,alter_session_container_db
from com.manageengine.monagent.database.mysql import MySQLUtil
import json,traceback
import concurrent.futures

def format_basic_perf(cached_data,data,instance_info):
    final_data = { 'PDBS' : {} }
    child_keys = instance_info.get("db_child_keys") or {}
    process_keys,asm_keys = child_keys.get("PROCESSES") or {}, child_keys.get("ASM_DISKGROUP") or {}
    ts_keys = child_keys.get(DBConstants.ORACLE_CHILD_TABLESPACE_TYPE) or {}
    CDB_ROOT = instance_info.get("CDB_ROOT") or 'CDB$ROOT'
    try:
        if 'CONTAINERS' in data:
            collect_conf = instance_info.get("collect_conf") or data["CONTAINERS"].get("isChanged")
            if "isChanged" in data["CONTAINERS"]:
                DatabaseLogger.Logger.log("[INFO] instance - {} :: config changed for CONTAINERS :: isChanged - {}".format(instance_info.get("instance_name"),data["CONTAINERS"].pop("isChanged")))
            if collect_conf:
                if CDB_ROOT in data['CONTAINERS']:
                    if "cnid" in data['CONTAINERS'][CDB_ROOT]:
                        data['CONTAINERS'][CDB_ROOT].pop("cnid")
                    final_data.update(data['CONTAINERS'].pop(CDB_ROOT) or {})
                final_data['PDBS'] = data.pop('CONTAINERS')
            else:
                if CDB_ROOT in data['CONTAINERS']:
                    data['CONTAINERS'].pop(CDB_ROOT)
                for pdb in data['CONTAINERS']:
                    final_data['PDBS'][pdb] = {}
                    # final_data['PDBS'][pdb] = {"opme":data['CONTAINERS'][pdb].get("opme")}
                    for metric in ['opme','optm','tosz','rcss','lund','pdct','mmcd','rstd', 'tbcnt']:
                        if metric in data['CONTAINERS'][pdb]:
                            final_data['PDBS'][pdb][metric] = data['CONTAINERS'][pdb][metric]
        else:
            DatabaseLogger.Logger.log("[INFO] instance - {} :: unable to fetch cdb and pdb details".format(instance_info.get("instance_name")))
        
        try:
            final_data['ASM_DISKGROUP'] = []
            if 'ASM_DISKGROUP' in data:
                asm_data = DBUtil.MapID(data.pop('ASM_DISKGROUP'),asm_keys,"asmid","name")
                for dg_name,dg_data in asm_data.items():
                    final_data['ASM_DISKGROUP'].append(dg_data)
            else:                
                DatabaseLogger.Logger.log("[INFO] instance - {} :: unable to fetch ASM_DISKGROUP details".format(instance_info.get("instance_name")))
        except Exception as e:
            DatabaseLogger.Logger.log("Exception while handling ASM_DISKGROUP data - {} :: instance - {}".format(e,instance_info.get("instance_name")))


        if 'TABLESPACE' in data:
            final_ts = []
            dc_tablespace = data.pop('TABLESPACE')
            for tablespace in dc_tablespace:
                if tablespace.get("tsnm"):
                    if tablespace["tsnm"] in ts_keys and "mid" in ts_keys[tablespace["tsnm"]] and ts_keys[tablespace["tsnm"]].get("status")=="0":
                        tablespace["cid"] = ts_keys[tablespace["tsnm"]]["mid"]
                        final_ts.append(tablespace)
                else: 
                    DatabaseLogger.Logger.log("instance - {} :: tsnm is not present in database :: {} :: {}".format(instance_info.get("instance_name"),CDB_ROOT,tablespace))
            final_data['TABLESPACE'] = final_ts
        else:
            DatabaseLogger.Logger.log("[INFO] instance - {} :: unable to fetch TABLESPACE details".format(instance_info.get("instance_name")))
        
        if 'PROCESSES' in data:
            final_data['PROCESSES'] = data.pop('PROCESSES')
            for process in final_data["PROCESSES"]:
                if process.get("pnam") and process["pnam"] in process_keys:
                    process["pmid"] = process_keys[process["pnam"]]
        
        try:
            if "SESSION" in data:
                data["SESSION"]["tuss"] = int(data["SESSION"].get("inss") or 0) + int(data["SESSION"].get("acss") or 0)
                data["SESSION"]["uscmrb"] = int(data["SESSION"].get("usrb") or 0) + int(data["SESSION"].get("uscm") or 0)
                data["SESSION"]["tert"] = int(data["SESSION"].get("rert") or 0) + int(data["SESSION"].get("sert") or 0)
        except Exception as e:
            DatabaseLogger.Logger.log("instance - {} :: issue in SESSION metrics calculation :: Error - {} ".format(instance_info.get("instance_name"),e))

        update_list = ["SGA_PGA", "SGA_DYNAMIC", "DATABASE_INSTANCE", "SESSION", "SINGLE_VALUES", "PARAMETERS", "PERFORMANCE_METRICS"]
        for updatable_dict in update_list:
            if updatable_dict not in data:
                continue
            if type(data[updatable_dict]) is dict:
                final_data.update(data.get(updatable_dict) or {})
            else:
                DatabaseLogger.Logger.log("instance - {} :: type mismatch for updatable_dict - {}".format(instance_info.get("instance_name"),updatable_dict))

        return final_data
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: format_basic_perf - {} :: instance - {}".format(e,instance_info.get("instance_name")))
        traceback.print_exc()

def collect_basic_perf(instance_info,xmlExecutorObj,connection):
    data,result=None,{}
    try:
        cached_data = instance_info.get("cached_data")
        tags        = ["instance","oracledb"]
        if instance_info['collect_conf']:
            tags.append("config")
        raw_data, data  =   DBUtil.executeMultiTags(xmlExecutorObj, tags, instance_info, instance_info.get("Version"), instance_info.get("disabled_queries") or {}, DBConstants.ORACLE_DATABASE,instance_info.get('service_name'),extended_connection=connection,previousDC=cached_data)

        result.update( format_basic_perf(cached_data,data,instance_info) or {} )
        
        if data.get("ERROR"):
            result.update(  data.pop("ERROR") or {}  )
        else:
            result["availability"]  =   "1"
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: oracledb :: collect_basic_data - {} :: instance - {}".format(e,instance_info.get("instance_name")))
        traceback.print_exc()
        result={"availability":"0"}
    return (raw_data,result)

def collect_basic_data(instance_info):
    try:
        connectionStatus,connection = DBUtil.getConnection(instance_info,DBConstants.ORACLE_DATABASE,instance_info.get('service_name'))
        if not connectionStatus:
            return {},{"availability":"0","DC ERROR":connection.get("ERROR"),"reason": connection.get("REASON") or DBConstants.CONNECTION_FAILED_ERR_MSG}
        alter_session_for_cdb(connection,instance_info)

        cache_data,result ={}, {}
        instance_info["cached_data"]= json.loads(instance_info.get("cached_data") or "{}")
        pdb_child_keys = (instance_info.get("db_child_keys") or {}).get("ORACLE_PDB") or {}
        db_per_thread, db_per_zip = int(instance_info.get("db_per_thread") or 5), int(instance_info.get("db_per_zip") or 50)

        thread_obj_dict                 = {}
        threads_final_data              = {}
        divided_child_dbs               = []
        temp_dict                       = {}
        thread_child_cache_data         = {}

        xmlExecutorObj      =   DBUtil.getXMLExecutorObj(DBConstants.ORACLE_DATABASE,instance_info.get('xmlString'))
        cache_data,result   =   collect_basic_perf(instance_info,xmlExecutorObj,connection)
        mx_workers          =   int(len(pdb_child_keys)/db_per_thread)+1

        for index,db_name in enumerate(pdb_child_keys):
            # if pdb_child_keys[db_name].get("status")=="0" and (result["PDBS"].get(db_name) or {}).get("opme") != "MOUNTED":
            if pdb_child_keys[db_name].get("status")=="0" and db_name in result["PDBS"]:
                if  result["PDBS"][db_name].get("opme") == "MOUNTED":
                    result["PDBS"][db_name]["availability"] = "0"
                    result["PDBS"][db_name]["reason"] = db_name + " is in mounted state. Hence cannot make connection"
                else:
                    temp_dict[db_name]=pdb_child_keys[db_name]
            else:
                continue
            if (index+1) % db_per_thread == 0:
                divided_child_dbs.append(temp_dict)
                temp_dict = {}
        if temp_dict:
            divided_child_dbs.append(temp_dict)

        with concurrent.futures.ThreadPoolExecutor(max_workers=mx_workers) as executor:

            for dbs in divided_child_dbs:
                # child_db_obj = ChildDatabaseDC(instance_info,xmlExecutorObj,dbs,connection)
                child_db_obj = ChildDatabaseDC(instance_info,xmlExecutorObj,dbs)
                thread_obj = executor.submit(child_db_obj.collect_database_data)
                thread_obj_dict[thread_obj] = "oracle_db_thread"
            
            done,notDone = concurrent.futures.wait(thread_obj_dict, return_when=concurrent.futures.ALL_COMPLETED)
            
            db_count_for_zip = 0
            for each_divided_db_list in done:
                child_cache_data,db_data = each_divided_db_list.result()
                if db_data:
                    db_count_for_zip = db_count_for_zip + len(db_data)    # len(db_data) = total database count in result dict
                    threads_final_data.update(db_data)
                thread_child_cache_data.update(child_cache_data)
        connection.close()
        cache_data['child_data'] = thread_child_cache_data
        remove_dbs = []
        ct = MySQLUtil.getTimeInMillis(instance_info.get('time_diff') or 0)
        result["ct"]=ct
        for db in result["PDBS"]:
            if type(result["PDBS"][db]) is dict:
                result['PDBS'][db].update(threads_final_data.get(db) or {})

            if db in pdb_child_keys and "mid" in pdb_child_keys[db] and pdb_child_keys[db].get("status")=="0":
                result['PDBS'][db]['cid'] = pdb_child_keys[db]["mid"]
                result['PDBS'][db]['ct'] = ct
            else:
                remove_dbs.append(db)
        for db in remove_dbs:
            result['PDBS'].pop(db)
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: oracledb :: collect_basic_data - {} :: instance - {}".format(e,instance_info.get("instance_name")))
        traceback.print_exc()
    return cache_data,result

def discover_database(instance_info):
    result={"availability" : "0","mid":instance_info.get("mid")}
    try:
        connectionStatus,connection = DBUtil.getConnection(instance_info,DBConstants.ORACLE_DATABASE,instance_info.get("service_name"))
        if connectionStatus:
            alter_session_for_cdb(connection,instance_info)

            data = DBUtil.getOutputFromQuery(connection,DBConstants.ORACLE_DATABASE_DISCOVERY_QUERY)
            tmp = []
            for row in data:
                tmp.append(row[0])
            result["list"] = tmp
            result['availability']  = "1"
            result['monitor_type']  = DBConstants.ORACLE_MONITOR_TYPE
            result['child_type']    = DBConstants.ORACLE_CHILD_TYPE
            result['instance_name'] = instance_info.get("instance_name")
            connection.close()
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: oracledb :: discover_database - {} :: instance - {}".format(e,instance_info.get("instance_name")))
        traceback.print_exc()
    return result

def discover_tablespaces(instance_info):
    output = {"list_data":[],"instance_name":instance_info.get("instance_name"),"monitor_type": DBConstants.ORACLE_CHILD_TABLESPACE_TYPE}
    cdb_root = { "mid":instance_info.get("mid"), "list":[], "availability" : "1", "monitor_type" : DBConstants.ORACLE_MONITOR_TYPE, "child_type" : DBConstants.ORACLE_CHILD_TABLESPACE_TYPE, "instance_name" : instance_info.get("instance_name") }
    CDB_ROOT_NAME = instance_info.get("CDB_ROOT") or "CDB$ROOT"
    try:
        db_child_keys = (instance_info.get("db_child_keys") or {}).get(DBConstants.ORACLE_CHILD_TYPE) or {}
        connectionStatus,connection = DBUtil.getConnection(instance_info,DBConstants.ORACLE_DATABASE,instance_info.get('service_name'))
        if connectionStatus:
            alter_session_for_cdb(connection,instance_info)
            query_output = DBUtil.getOutputFromQuery(connection,DBConstants.ORACLE_TABLESPACES_DISCOVERY_QUERY)
            tmp_output={}
            for row in query_output:
                if row[0] in db_child_keys:
                    mid = db_child_keys[row[0]].get("mid")
                    if mid==None:
                        DatabaseLogger.Logger.log(" instance - {} :: Received None for mid :: Pluggable database name - {} :: db_child_keys[{}] - {} ".format(instance_info.get("instance_name"),row[0],row[0],db_child_keys[row[0]]))
                        continue
                    if tmp_output.get(mid)==None:
                        tmp_output[mid]=[0,[]]
                    if tmp_output[mid][0]>=DBConstants.MAX_TABLESPACE_PER_DATABASE or db_child_keys[row[0]].get("status")!="0":
                        continue
                    tmp_output[mid][1].append(row[1])
                    tmp_output[mid][0]+=1
                if str(row[0]).upper() == str(CDB_ROOT_NAME).upper():
                    cdb_root["list"].append(row[1])
            if cdb_root["list"]:
                output["list_data"].append(cdb_root)
            for key,val in tmp_output.items():
                output["list_data"].append({ "mid":key, "list":val[1], "availability" : "1", "monitor_type" : DBConstants.ORACLE_CHILD_TYPE, "child_type" : DBConstants.ORACLE_CHILD_TABLESPACE_TYPE, "instance_name" : instance_info.get("instance_name") })
            connection.close()
        else:
            DatabaseLogger.Logger.log("Tablespace discovery failed for instance :: cannot open connection to database :: instance_name - {}".format(instance_info.get("instance_name")))
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: oracledb :: discover_tablespaces - {} :: instance - {}".format(e,instance_info.get("instance_name")))
        traceback.print_exc()
    return output

def alter_session_for_cdb(connection,instance_info):
    try:
        CDB_ROOT = instance_info.get("CDB_ROOT") or "CDB$ROOT"
        con_name = DBUtil.getOutputFromQuery(connection, "select SYS_CONTEXT('USERENV', 'CON_NAME') from dual")
        if con_name!=None and con_name[0][0] != CDB_ROOT:
            status, attempt = alter_session_container_db(connection,CDB_ROOT,instance_info.get("instance_name"))
            if not status:
                DatabaseLogger.Logger.log("unable to change session to CDB$ROOT :: instance_name - {}".format(instance_info.get("instance_name")))
        else:
            DatabaseLogger.Logger.log("session connected to container - {} :: instance_name - {}".format(con_name,instance_info.get("instance_name")))
    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: oracledb :: alter_session_for_cdb - {} :: instance - {}".format(e,instance_info.get("instance_name")))

def collect_data(instance_info):
    result = {}
    try:
        collection_type = instance_info.get("collection_type")
        if collection_type == "0":
            result  =   collect_basic_data(instance_info)
        elif collection_type == "1":
            result  =   discover_database(instance_info)
        elif collection_type == "2":
            result  =   discover_tablespaces(instance_info)

    except Exception as e:
        DatabaseLogger.Logger.log("Exception :: oracledb :: collect_data - {} :: instance - {}".format(e,instance_info.get("instance_name")))
        traceback.print_exc()
    return result